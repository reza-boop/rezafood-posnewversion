"""Tab base class for RezaFood POS."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

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
