"""Login window for RezaFood POS."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from config import APP_NAME, APP_VERSION, FONT, THEME
from db import Database
from utils import check_password


class LoginWindow(tk.Toplevel):
    """Modal login dialog shown at application start."""

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

        # Centre over the (hidden) root window
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

        # Header
        tk.Label(
            card,
            text=APP_NAME,
            font=FONT["large"],
            bg=surf,
            fg=THEME["accent"],
        ).pack()
        tk.Label(
            card,
            text=f"Point of Sale  v{APP_VERSION}",
            font=FONT["default"],
            bg=surf,
            fg=THEME["fg"],
        ).pack(pady=(0, 24))

        # Username
        tk.Label(
            card, text="Username", font=FONT["bold"], bg=surf, fg=THEME["fg"]
        ).pack(anchor="w")
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

        # Password
        tk.Label(
            card, text="Password", font=FONT["bold"], bg=surf, fg=THEME["fg"]
        ).pack(anchor="w")
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

        # Login button
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

        # Bind Enter key
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

        user_row = self.db.get_user_by_username(username)
        if not user_row or not check_password(password, user_row["password_hash"]):
            messagebox.showerror(
                "Login Failed",
                "Invalid username or password.",
                parent=self,
            )
            self._password_entry.delete(0, "end")
            return

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
