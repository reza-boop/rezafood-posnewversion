"""Main POS application window.

Orchestrates the top-level window, tab notebook, session timeout, and
global keyboard shortcuts.  All tab-specific logic lives in ``ui/tabs/``.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Optional

from config import (
    APP_NAME,
    APP_VERSION,
    FONT,
    SESSION_TIMEOUT_MINUTES,
    THEME,
)
from db import Database
from logger import logger
import config_store
from services.backup_service import BackupService
from services.order_service import OrderService
from services.product_service import ProductService
from services.report_service import ReportService
from services.sync_service import SyncService
from ui.tabs import BaseTab
from ui.tabs.audit import AuditTab
from ui.tabs.dashboard import DashboardTab
from ui.tabs.orders import OrdersTab
from ui.tabs.pos import PosTab
from ui.tabs.products import ProductsTab
from ui.tabs.settings import SettingsTab
from ui.tabs.users import UsersTab


class PosApp:
    """Root application controller — builds the window and all tabs."""

    _SESSION_CHECK_INTERVAL_MS = 30_000  # check every 30 s

    def __init__(self, root: tk.Tk, db: Database, user: dict) -> None:
        self.root = root
        self.db = db
        self.user = user
        self.is_admin = user["role"] == "admin"

        # Services
        self.order_service = OrderService(db)
        self.product_service = ProductService(db)
        self.report_service = ReportService(db)
        self.backup_service = BackupService()
        self.sync_service = SyncService(on_change=self._on_sync_change)

        # Tab registry
        self._tabs: Dict[str, BaseTab] = {}

        self._configure_root()
        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._setup_session_timeout()
        self._initial_refresh()
        self._restore_background_services()

        logger.info("User '%s' opened main window.", user["username"])

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title(
            f"{APP_NAME} v{APP_VERSION}  —  {self.user['username']}  [{self.user['role']}]"
        )
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1200x720")
        self.root.minsize(900, 600)
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 1200, 720
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ------------------------------------------------------------------
    # UI skeleton
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header bar
        header = tk.Frame(self.root, bg=THEME["surface"], height=48)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"  {APP_NAME}",
            font=FONT["heading"],
            bg=THEME["surface"],
            fg=THEME["accent"],
        ).pack(side="left", padx=10)

        tk.Label(
            header,
            text=f"Logged in: {self.user['username']}  ({self.user['role']})",
            font=FONT["default"],
            bg=THEME["surface"],
            fg=THEME["fg"],
        ).pack(side="right", padx=20)

        tk.Button(
            header,
            text="Logout",
            font=FONT["bold"],
            bg=THEME["danger"],
            fg=THEME["bg"],
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._logout,
        ).pack(side="right", padx=10)

        # Notebook
        style = ttk.Style()
        style.configure("Dark.TNotebook", background=THEME["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=THEME["surface"],
            foreground=THEME["fg"],
            font=FONT["bold"],
            padding=(12, 6),
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", THEME["accent"])],
            foreground=[("selected", THEME["bg"])],
        )

        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

        # Build tabs
        self._tabs["pos"] = PosTab(self.notebook, self)
        self._tabs["orders"] = OrdersTab(self.notebook, self)
        self._tabs["dashboard"] = DashboardTab(self.notebook, self)

        if self.is_admin:
            self._tabs["products"] = ProductsTab(self.notebook, self)
            self._tabs["users"] = UsersTab(self.notebook, self)
            self._tabs["audit"] = AuditTab(self.notebook, self)
            self._tabs["settings"] = SettingsTab(self.notebook, self)

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------

    def get_tab(self, name: str) -> Optional[BaseTab]:
        return self._tabs.get(name)

    def refresh_tab(self, name: str) -> None:
        tab = self._tabs.get(name)
        if tab:
            tab.refresh()

    def _initial_refresh(self) -> None:
        for tab in self._tabs.values():
            tab.refresh()

    def _restore_background_services(self) -> None:
        """Re-start auto-backup and sync if they were enabled in a previous session."""
        settings = config_store.load()
        if settings.get("auto_backup_enabled") and self.is_admin:
            interval = int(settings.get("auto_backup_interval_minutes", 60))
            remote = settings.get("remote_backup_path", "")
            self.backup_service.start_auto_backup(interval, remote)
            logger.info("Auto-backup restored: every %d min → '%s'", interval, remote)

        if settings.get("sync_enabled"):
            path = settings.get("sync_shared_db_path", "")
            poll = int(settings.get("sync_poll_interval_seconds", 30))
            try:
                self.sync_service.start(path, poll_seconds=poll)
                logger.info("Sync restored: monitoring '%s' every %ds", path, poll)
            except Exception as exc:
                logger.warning("Could not restore sync: %s", exc)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_keyboard_shortcuts(self) -> None:
        """Bind global hotkeys.

        F1  — switch to POS tab and focus product search
        F2  — trigger checkout (only when on POS tab)
        F3  — switch to POS tab and focus barcode entry
        F5  — refresh the currently visible tab
        Esc — clear the cart (only when on POS tab)
        """
        self.root.bind("<F1>", self._kb_focus_search)
        self.root.bind("<F2>", self._kb_checkout)
        self.root.bind("<F3>", self._kb_focus_barcode)
        self.root.bind("<F5>", self._kb_refresh)
        self.root.bind("<Escape>", self._kb_clear_cart)

    def _kb_focus_search(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos:
            pos.focus_search()  # type: ignore[attr-defined]

    def _kb_focus_barcode(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos:
            pos.focus_barcode()  # type: ignore[attr-defined]

    def _kb_checkout(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos and self._current_tab_name() == "pos":
            pos.trigger_checkout()  # type: ignore[attr-defined]

    def _kb_refresh(self, _event=None) -> None:
        name = self._current_tab_name()
        if name:
            self.refresh_tab(name)

    def _kb_clear_cart(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos and self._current_tab_name() == "pos":
            pos.clear_cart_cmd()  # type: ignore[attr-defined]

    def _current_tab_name(self) -> Optional[str]:
        """Return the key of the currently selected tab, or None."""
        try:
            selected = self.notebook.select()
            for name, tab in self._tabs.items():
                if str(tab) == selected:
                    return name
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Session timeout
    # ------------------------------------------------------------------

    def _setup_session_timeout(self) -> None:
        self._last_activity = time.monotonic()
        self.root.bind_all("<KeyPress>", self._on_activity, add=True)
        self.root.bind_all("<ButtonPress>", self._on_activity, add=True)
        self._session_after_id: Optional[str] = None
        self._schedule_session_check()

    def _on_activity(self, _event=None) -> None:
        self._last_activity = time.monotonic()

    def _schedule_session_check(self) -> None:
        self._session_after_id = self.root.after(
            self._SESSION_CHECK_INTERVAL_MS, self._check_session
        )

    def _check_session(self) -> None:
        elapsed_minutes = (time.monotonic() - self._last_activity) / 60
        if elapsed_minutes >= SESSION_TIMEOUT_MINUTES:
            logger.info(
                "Session timeout for user '%s' after %.1f min idle.",
                self.user["username"],
                elapsed_minutes,
            )
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "session_timeout", ""
            )
            messagebox.showinfo(
                "Session Expired",
                f"Your session expired after {SESSION_TIMEOUT_MINUTES} minutes of inactivity.\n"
                "Please log in again.",
                parent=self.root,
            )
            self.root.destroy()
            return
        self._schedule_session_check()

    # ------------------------------------------------------------------
    # Sync change callback
    # ------------------------------------------------------------------

    def _on_sync_change(self) -> None:
        """Called from the SyncService polling thread when a remote change is detected."""
        # Schedule UI refresh on the main thread (Tkinter is not thread-safe)
        self.root.after(0, self._refresh_all_tabs)

    def _refresh_all_tabs(self) -> None:
        """Refresh every registered tab (called from main thread)."""
        self.product_service.invalidate_cache()
        for tab in self._tabs.values():
            try:
                tab.refresh()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def _logout(self) -> None:
        if messagebox.askyesno(
            "Logout", "Log out and return to login screen?", parent=self.root
        ):
            if self._session_after_id:
                self.root.after_cancel(self._session_after_id)
            self.backup_service.stop_auto_backup()
            self.sync_service.stop()
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "logout", ""
            )
            logger.info("User '%s' logged out.", self.user["username"])
            self.root.destroy()
