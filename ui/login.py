"""Login window for RezaFood POS with brute-force rate limiting."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, ClassVar, Dict

from config import (
    APP_NAME,
    APP_VERSION,
    FONT,
    LOGIN_LOCKOUT_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    THEME,
)
from db import Database
from logger import logger
from utils import check_password


class LoginWindow(tk.Toplevel):
    """Modal login dialog shown at application start."""

    # Class-level stores for rate limiting — shared across instances so that
    # re-showing the login dialog after logout preserves the counters.
    _failed_attempts: ClassVar[Dict[str, int]] = {}
    _lockout_until: ClassVar[Dict[str, float]] = {}

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
        now = time.monotonic()
        lockout_end = self._lockout_until.get(username, 0)
        if now < lockout_end:
            remaining = int(lockout_end - now)
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
            attempts = self._failed_attempts.get(username, 0) + 1
            self._failed_attempts[username] = attempts

            if attempts >= MAX_LOGIN_ATTEMPTS:
                self._lockout_until[username] = now + LOGIN_LOCKOUT_SECONDS
                self._failed_attempts[username] = 0
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

        # --- Success ---
        self._failed_attempts.pop(username, None)
        self._lockout_until.pop(username, None)
        logger.info("User '%s' logged in successfully.", username)

        user = {
            "id": user_row["id"],
            "username": user_row["username"],
            "role": user_row["role"],
        }
        self.destroy()
        self.on_success(user)

    def _on_close(self) -> None:
        """Closing the login window exits the application."""
        self.master.destroy()
