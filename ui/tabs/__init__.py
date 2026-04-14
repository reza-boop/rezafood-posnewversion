"""Tab base class for RezaFood POS."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from config import SESSION_TIMEOUT_MINUTES

if TYPE_CHECKING:
    from ui.main import PosApp


class BaseTab(tk.Frame):
    """Abstract base for every tab panel in the notebook."""

    def __init__(
        self, notebook: ttk.Notebook, app: "PosApp", tab_text: str
    ) -> None:
        from config import THEME

        super().__init__(notebook, bg=THEME["bg"])
        self.app = app
        self.db = app.db
        self.user = app.user
        self.root = app.root

        notebook.add(self, text=tab_text)
        self._build()

    def _build(self) -> None:
        """Build tab contents. Override in subclasses."""

    def refresh(self) -> None:
        """Refresh displayed data. Override in subclasses."""

    def _assert_session_active(self) -> bool:
        """Return True if the session is still valid, False (and show error) otherwise.

        Call this at the beginning of every sensitive operation (checkout,
        add/edit/delete).  If the session has expired the user sees a clear
        message and must log in again.
        """
        elapsed_minutes = (time.monotonic() - self.app._last_activity) / 60
        if elapsed_minutes >= SESSION_TIMEOUT_MINUTES:
            messagebox.showerror(
                "Session Expired",
                "Your session has expired due to inactivity.\n"
                "Please save your work and log in again.",
                parent=self.root,
            )
            return False
        return True
