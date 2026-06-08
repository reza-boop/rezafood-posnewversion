"""Login window for RezaFood POS with brute-force rate limiting."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable, ClassVar

from config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_ADMIN_PASSWORD,
    FONT,
    LOGIN_LOCKOUT_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    THEME,
)
from db import Database
from logger import logger
from utils import RateLimiter, check_password


class LoginWindow(tk.Toplevel):
    """Modal login dialog shown at application start."""

    # Class-level limiter — shared across instances so that re-showing the
    # login dialog after logout preserves the counters.
    _rate_limiter: ClassVar[RateLimiter] = RateLimiter(
        max_attempts=MAX_LOGIN_ATTEMPTS,
        lockout_seconds=LOGIN_LOCKOUT_SECONDS,
    )

    def __init__(
        self,
        parent: tk.Tk,
        db: Database,
        on_success: Callable[[dict], None],
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.on_success = on_success

        self.title(f"{APP_NAME} — Login")
        self.resizable(False, False)
        self.configure(bg=THEME["bg"])

        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()
        self.transient(parent)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        self._username_entry.focus_set()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        surf = THEME["surface"]

        outer = tk.Frame(self, bg=THEME["bg"], padx=40, pady=40)
        outer.pack()

        card = tk.Frame(outer, bg=surf, padx=35, pady=35)
        card.pack()

        tk.Label(
            card, text=APP_NAME, font=FONT["large"],
            bg=surf, fg=THEME["accent"],
        ).pack()
        tk.Label(
            card, text=f"Point of Sale  v{APP_VERSION}", font=FONT["default"],
            bg=surf, fg=THEME["fg"],
        ).pack(pady=(0, 24))

        tk.Label(card, text="Username", font=FONT["bold"], bg=surf, fg=THEME["fg"]).pack(anchor="w")
        self._username_entry = tk.Entry(
            card,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=6,
            width=26,
        )
        self._username_entry.pack(fill="x", pady=(2, 12))

        tk.Label(card, text="Password", font=FONT["bold"], bg=surf, fg=THEME["fg"]).pack(anchor="w")
        self._password_entry = tk.Entry(
            card,
            show="*",
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=6,
            width=26,
        )
        self._password_entry.pack(fill="x", pady=(2, 22))

        tk.Button(
            card,
            text="  Login  ",
            font=FONT["bold"],
            bg=THEME["button_bg"],
            fg=THEME["button_fg"],
            activebackground=THEME["accent2"],
            activeforeground=THEME["bg"],
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2",
            command=self._attempt_login,
        ).pack(fill="x")

        self.bind("<Return>", lambda _e: self._attempt_login())

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _attempt_login(self) -> None:
        username = self._username_entry.get().strip()
        password = self._password_entry.get()

        if not username or not password:
            messagebox.showwarning(
                "Input Required",
                "Please enter both username and password.",
                parent=self,
            )
            return

        # --- Rate limiting ---
        if self._rate_limiter.is_locked(username):
            remaining = int(self._rate_limiter.remaining_lockout(username))
            messagebox.showerror(
                "Account Locked",
                f"Too many failed attempts.\nTry again in {remaining} second(s).",
                parent=self,
            )
            self._password_entry.delete(0, "end")
            return

        # --- Credential check ---
        user_row = self.db.get_user_by_username(username)
        if not user_row or not check_password(password, user_row["password_hash"]):
            attempts = self._rate_limiter.record_failure(username)

            if self._rate_limiter.is_locked(username):
                minutes = LOGIN_LOCKOUT_SECONDS // 60
                messagebox.showerror(
                    "Account Locked",
                    f"Too many failed attempts.\n"
                    f"This username is locked for {minutes} minute(s).",
                    parent=self,
                )
                logger.warning(
                    "Account '%s' locked after %d failed login attempts.",
                    username, MAX_LOGIN_ATTEMPTS,
                )
            else:
                remaining_attempts = MAX_LOGIN_ATTEMPTS - attempts
                messagebox.showerror(
                    "Login Failed",
                    f"Invalid username or password.\n"
                    f"{remaining_attempts} attempt(s) remaining before lockout.",
                    parent=self,
                )
                logger.warning(
                    "Failed login attempt for '%s' (%d/%d).",
                    username, attempts, MAX_LOGIN_ATTEMPTS,
                )

            self._password_entry.delete(0, "end")
            return

        if self._must_change_default_admin_password(user_row):
            if not self._force_change_default_admin_password(user_row):
                self._password_entry.delete(0, "end")
                return

        # --- Success ---
        self._rate_limiter.reset(username)
        logger.info("User '%s' logged in successfully.", username)

        user = {
            "id": user_row["id"],
            "username": user_row["username"],
            "role": user_row["role"],
        }
        self.destroy()
        self.on_success(user)

    def _must_change_default_admin_password(self, user_row) -> bool:
        return bool(user_row["must_change_password"])

    def _force_change_default_admin_password(self, user_row) -> bool:
        messagebox.showwarning(
            "Password Change Required",
            "Default admin password detected.\nYou must set a new password to continue.",
            parent=self,
        )
        while True:
            new_password = simpledialog.askstring(
                "New Password",
                f"Enter a new admin password (min {MIN_PASSWORD_LENGTH} chars):",
                show="*",
                parent=self,
            )
            if new_password is None:
                messagebox.showerror(
                    "Password Required",
                    "You must change the default admin password to log in.",
                    parent=self,
                )
                return False

            if len(new_password) < MIN_PASSWORD_LENGTH:
                messagebox.showwarning(
                    "Weak Password",
                    f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
                    parent=self,
                )
                continue

            if new_password == DEFAULT_ADMIN_PASSWORD:
                messagebox.showwarning(
                    "Invalid Password",
                    "New password cannot be the default password.",
                    parent=self,
                )
                continue

            confirm_password = simpledialog.askstring(
                "Confirm Password",
                "Re-enter the new password:",
                show="*",
                parent=self,
            )
            if confirm_password is None:
                messagebox.showerror(
                    "Password Required",
                    "Password confirmation is required.",
                    parent=self,
                )
                return False

            if confirm_password != new_password:
                messagebox.showwarning(
                    "Mismatch",
                    "Passwords do not match. Please try again.",
                    parent=self,
                )
                continue

            self.db.update_user(
                user_row["id"],
                user_row["username"],
                new_password,
                user_row["role"],
            )
            self.db.add_audit_log(
                user_row["id"],
                user_row["username"],
                "force_password_change",
                "default_admin_password_replaced",
            )
            logger.info("User '%s' replaced default admin password.", user_row["username"])
            return True

    def _on_close(self) -> None:
        """Closing the login window exits the application."""
        self.master.destroy()
