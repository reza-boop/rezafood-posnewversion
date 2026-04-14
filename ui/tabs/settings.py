"""Settings tab — database backup, cloud backup, multi-terminal sync, folder shortcuts, exports (admin only)."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import config_store
from config import BACKUPS_DIR, EXPORTS_DIR, FONT, RECEIPTS_DIR, THEME
from ui.tabs import BaseTab
from ui.widgets import btn, section_label
from utils import export_to_csv, open_folder, time_stamp

if TYPE_CHECKING:
    from ui.main import PosApp


class SettingsTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " ⚙ Settings ")

    def _build(self) -> None:
        # Scrollable frame so all sections fit on smaller screens
        canvas = tk.Canvas(self, bg=THEME["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=THEME["bg"])
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        pad = {"padx": 40, "pady": (8, 0)}

        # ----------------------------------------------------------------
        # Local backup
        # ----------------------------------------------------------------
        card = tk.Frame(inner, bg=THEME["surface"], padx=24, pady=16)
        card.pack(fill="x", **pad)
        section_label(card, "💾 Local Backup").pack(anchor="w", pady=(0, 6))
        btn(card, "Backup Now (ZIP)", self._backup_local, width=24).pack(anchor="w", pady=2)

        # ----------------------------------------------------------------
        # Cloud / remote backup
        # ----------------------------------------------------------------
        cloud_card = tk.Frame(inner, bg=THEME["surface"], padx=24, pady=16)
        cloud_card.pack(fill="x", **pad)
        section_label(cloud_card, "☁  Cloud / Remote Backup").pack(anchor="w", pady=(0, 6))

        # Remote path
        rp_row = tk.Frame(cloud_card, bg=THEME["surface"])
        rp_row.pack(fill="x", pady=2)
        tk.Label(
            rp_row, text="Remote path:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"], width=16, anchor="w",
        ).pack(side="left")
        self._remote_path_var = tk.StringVar(
            value=config_store.get("remote_backup_path")
        )
        tk.Entry(
            rp_row,
            textvariable=self._remote_path_var,
            font=FONT["default"],
            bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat", bd=4, width=36,
        ).pack(side="left", padx=(4, 0))

        # Auto-backup toggle + interval
        auto_row = tk.Frame(cloud_card, bg=THEME["surface"])
        auto_row.pack(fill="x", pady=4)
        self._auto_backup_var = tk.BooleanVar(
            value=config_store.get("auto_backup_enabled")
        )
        tk.Checkbutton(
            auto_row,
            text="Auto-backup every",
            variable=self._auto_backup_var,
            font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
            selectcolor=THEME["surface2"],
            activebackground=THEME["surface"],
            activeforeground=THEME["fg"],
            command=self._toggle_auto_backup,
        ).pack(side="left")
        self._interval_var = tk.StringVar(
            value=str(config_store.get("auto_backup_interval_minutes"))
        )
        tk.Entry(
            auto_row,
            textvariable=self._interval_var,
            font=FONT["default"],
            bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat", bd=4, width=5,
        ).pack(side="left", padx=(4, 2))
        tk.Label(
            auto_row, text="minutes",
            font=FONT["default"], bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")

        cloud_btn_row = tk.Frame(cloud_card, bg=THEME["surface"])
        cloud_btn_row.pack(fill="x", pady=(6, 2))
        btn(cloud_btn_row, "Backup to Remote Now", self._backup_remote, width=24).pack(
            side="left", padx=(0, 8)
        )
        btn(cloud_btn_row, "Save Settings", self._save_cloud_settings, width=16).pack(
            side="left"
        )

        self._last_backup_label = tk.Label(
            cloud_card, text="Last backup: —",
            font=FONT["default"], bg=THEME["surface"], fg=THEME["accent"],
        )
        self._last_backup_label.pack(anchor="w", pady=(4, 0))

        self._auto_status_label = tk.Label(
            cloud_card, text="Auto-backup: off",
            font=FONT["default"], bg=THEME["surface"], fg=THEME["fg"],
        )
        self._auto_status_label.pack(anchor="w")

        # ----------------------------------------------------------------
        # Multi-terminal sync
        # ----------------------------------------------------------------
        sync_card = tk.Frame(inner, bg=THEME["surface"], padx=24, pady=16)
        sync_card.pack(fill="x", **pad)
        section_label(sync_card, "🔄 Multi-Terminal Sync").pack(anchor="w", pady=(0, 6))

        tk.Label(
            sync_card,
            text="Point all terminals at the same SQLite file on a shared network drive.",
            font=FONT["default"], bg=THEME["surface"], fg=THEME["fg"],
            wraplength=500, justify="left",
        ).pack(anchor="w", pady=(0, 6))

        sp_row = tk.Frame(sync_card, bg=THEME["surface"])
        sp_row.pack(fill="x", pady=2)
        tk.Label(
            sp_row, text="Shared DB path:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"], width=16, anchor="w",
        ).pack(side="left")
        self._sync_path_var = tk.StringVar(
            value=config_store.get("sync_shared_db_path")
        )
        tk.Entry(
            sp_row,
            textvariable=self._sync_path_var,
            font=FONT["default"],
            bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat", bd=4, width=36,
        ).pack(side="left", padx=(4, 0))

        poll_row = tk.Frame(sync_card, bg=THEME["surface"])
        poll_row.pack(fill="x", pady=4)
        tk.Label(
            poll_row, text="Poll interval:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"], width=16, anchor="w",
        ).pack(side="left")
        self._poll_var = tk.StringVar(
            value=str(config_store.get("sync_poll_interval_seconds"))
        )
        tk.Entry(
            poll_row,
            textvariable=self._poll_var,
            font=FONT["default"],
            bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat", bd=4, width=6,
        ).pack(side="left", padx=(4, 2))
        tk.Label(
            poll_row, text="seconds",
            font=FONT["default"], bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")

        sync_btn_row = tk.Frame(sync_card, bg=THEME["surface"])
        sync_btn_row.pack(fill="x", pady=(6, 2))
        self._sync_connect_btn = btn(
            sync_btn_row, "Connect", self._sync_connect, width=14
        )
        self._sync_connect_btn.pack(side="left", padx=(0, 6))
        btn(sync_btn_row, "Disconnect", self._sync_disconnect, danger=True, width=14).pack(
            side="left"
        )

        self._sync_status_label = tk.Label(
            sync_card, text="Sync: not connected",
            font=FONT["bold"], bg=THEME["surface"], fg=THEME["fg"],
        )
        self._sync_status_label.pack(anchor="w", pady=(4, 0))

        # ----------------------------------------------------------------
        # Folders
        # ----------------------------------------------------------------
        folder_card = tk.Frame(inner, bg=THEME["surface"], padx=24, pady=16)
        folder_card.pack(fill="x", **pad)
        section_label(folder_card, "📁 Folders").pack(anchor="w", pady=(0, 6))
        for label, folder in [
            ("Open Receipts Folder", RECEIPTS_DIR),
            ("Open Backups Folder",  BACKUPS_DIR),
            ("Open Exports Folder",  EXPORTS_DIR),
        ]:
            btn(folder_card, label, lambda f=folder: open_folder(f), width=24).pack(
                anchor="w", pady=2
            )

        # ----------------------------------------------------------------
        # Data export
        # ----------------------------------------------------------------
        export_card = tk.Frame(inner, bg=THEME["surface"], padx=24, pady=16)
        export_card.pack(fill="x", padx=40, pady=(8, 24))
        section_label(export_card, "📊 Data Export").pack(anchor="w", pady=(0, 6))
        btn(export_card, "Export Orders CSV",   self._export_orders,   width=22).pack(anchor="w", pady=2)
        btn(export_card, "Export Products CSV", self._export_products, width=22).pack(anchor="w", pady=2)

        # Re-apply auto-backup state from saved settings
        self._refresh_auto_status()
        self._refresh_sync_status()

    def refresh(self) -> None:
        self._refresh_auto_status()
        self._refresh_sync_status()

    # ------------------------------------------------------------------
    # Local backup
    # ------------------------------------------------------------------

    def _backup_local(self) -> None:
        if not self._assert_session_active():
            return
        try:
            path = self.app.backup_service.create_zip_backup()
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "backup_db", path
            )
            self._update_last_backup_label()
            messagebox.showinfo(
                "Backup", f"Database backed up to:\n{os.path.abspath(path)}",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Cloud / remote backup
    # ------------------------------------------------------------------

    def _save_cloud_settings(self) -> None:
        remote = self._remote_path_var.get().strip()
        try:
            interval = int(self._interval_var.get())
            if interval < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Invalid Interval",
                "Auto-backup interval must be a positive integer (minutes).",
                parent=self.root,
            )
            return
        config_store.set("remote_backup_path", remote)
        config_store.set("auto_backup_interval_minutes", interval)
        messagebox.showinfo("Saved", "Cloud backup settings saved.", parent=self.root)

    def _backup_remote(self) -> None:
        if not self._assert_session_active():
            return
        remote = self._remote_path_var.get().strip()
        if not remote:
            messagebox.showwarning(
                "No Remote Path",
                "Enter a remote backup path first.",
                parent=self.root,
            )
            return

        def _do_backup():
            try:
                path = self.app.backup_service.upload_to_remote_path(remote)
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "cloud_backup", path,
                )
                self.root.after(
                    0,
                    lambda: (
                        self._update_last_backup_label(),
                        messagebox.showinfo(
                            "Cloud Backup",
                            f"Uploaded to:\n{path}",
                            parent=self.root,
                        ),
                    ),
                )
            except Exception as exc:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Cloud Backup Failed", str(exc), parent=self.root
                    ),
                )

        threading.Thread(target=_do_backup, daemon=True).start()

    def _toggle_auto_backup(self) -> None:
        enabled = self._auto_backup_var.get()
        try:
            interval = int(self._interval_var.get())
            if interval < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Invalid Interval",
                "Auto-backup interval must be a positive integer (minutes).",
                parent=self.root,
            )
            self._auto_backup_var.set(False)
            return

        remote = self._remote_path_var.get().strip()
        config_store.set("auto_backup_enabled", enabled)
        config_store.set("auto_backup_interval_minutes", interval)
        config_store.set("remote_backup_path", remote)

        if enabled:
            self.app.backup_service.start_auto_backup(interval, remote)
        else:
            self.app.backup_service.stop_auto_backup()

        self._refresh_auto_status()

    def _refresh_auto_status(self) -> None:
        if not hasattr(self, "_auto_status_label"):
            return
        running = self.app.backup_service.auto_backup_running
        self._auto_status_label.configure(
            text=f"Auto-backup: {'⏱ running' if running else 'off'}",
            fg=THEME["accent2"] if running else THEME["fg"],
        )
        self._update_last_backup_label()

    def _update_last_backup_label(self) -> None:
        if not hasattr(self, "_last_backup_label"):
            return
        t = self.app.backup_service.last_backup_time
        self._last_backup_label.configure(
            text=f"Last backup: {t if t else '—'}"
        )

    # ------------------------------------------------------------------
    # Multi-terminal sync
    # ------------------------------------------------------------------

    def _sync_connect(self) -> None:
        if not self._assert_session_active():
            return
        path = self._sync_path_var.get().strip()
        try:
            poll = int(self._poll_var.get())
            if poll < 5:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Invalid Poll Interval",
                "Poll interval must be ≥ 5 seconds.",
                parent=self.root,
            )
            return

        if not path:
            messagebox.showwarning(
                "No Path", "Enter a shared database path first.", parent=self.root
            )
            return

        try:
            self.app.sync_service.start(path, poll_seconds=poll)
        except FileNotFoundError as exc:
            messagebox.showerror("Sync Error", str(exc), parent=self.root)
            return

        config_store.set("sync_shared_db_path", path)
        config_store.set("sync_poll_interval_seconds", poll)
        config_store.set("sync_enabled", True)
        self._refresh_sync_status()
        messagebox.showinfo(
            "Sync Connected",
            f"Monitoring for changes every {poll}s:\n{path}",
            parent=self.root,
        )

    def _sync_disconnect(self) -> None:
        self.app.sync_service.stop()
        config_store.set("sync_enabled", False)
        self._refresh_sync_status()

    def _refresh_sync_status(self) -> None:
        if not hasattr(self, "_sync_status_label"):
            return
        running = self.app.sync_service.is_running
        path = self.app.sync_service.shared_path or "—"
        self._sync_status_label.configure(
            text=f"Sync: {'🟢 connected — ' + path if running else '🔴 not connected'}",
            fg=THEME["accent2"] if running else THEME["fg"],
        )

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export_orders(self) -> None:
        orders = self.db.get_all_orders()
        headers = ["ID", "Date", "Cashier ID", "Cashier", "Total", "Discount", "Payment"]
        rows = [
            (o["id"], o["created_at"], o["cashier_id"], o["cashier_name"],
             o["total"], o.get("discount_amount", 0), o["payment_method"])
            for o in orders
        ]
        path = os.path.join(EXPORTS_DIR, f"orders_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_orders_csv", path
        )
        messagebox.showinfo(
            "Export", f"Orders exported to:\n{os.path.abspath(path)}", parent=self.root
        )

    def _export_products(self) -> None:
        products = self.db.get_all_products()
        headers = ["ID", "Name", "Category", "Price", "Stock", "Created", "Updated"]
        rows = [
            (p["id"], p["name"], p["category"], p["price"],
             p["stock"], p["created_at"], p["updated_at"])
            for p in products
        ]
        path = os.path.join(EXPORTS_DIR, f"products_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_products_csv", path
        )
        messagebox.showinfo(
            "Export", f"Products exported to:\n{os.path.abspath(path)}", parent=self.root
        )
