"""Settings tab — database backup, folder shortcuts, exports (admin only)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from config import BACKUPS_DIR, EXPORTS_DIR, RECEIPTS_DIR, THEME
from ui.tabs import BaseTab
from ui.widgets import btn, section_label
from utils import backup_db, export_to_csv, open_folder, time_stamp

if TYPE_CHECKING:
    from ui.main import PosApp


class SettingsTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " ⚙ Settings ")

    def _build(self) -> None:
        card = tk.Frame(self, bg=THEME["surface"], padx=30, pady=30)
        card.pack(padx=40, pady=40, anchor="nw")

        section_label(card, "Database").pack(anchor="w", pady=(0, 8))
        btn(card, "Backup Database", self._backup, width=22).pack(anchor="w", pady=4)

        section_label(card, "Folders").pack(anchor="w", pady=(16, 8))
        for label, folder in [
            ("Open Receipts Folder", RECEIPTS_DIR),
            ("Open Backups Folder",  BACKUPS_DIR),
            ("Open Exports Folder",  EXPORTS_DIR),
        ]:
            btn(card, label, lambda f=folder: open_folder(f), width=24).pack(
                anchor="w", pady=4
            )

        section_label(card, "Data Export").pack(anchor="w", pady=(16, 8))
        btn(card, "Export Orders CSV",   self._export_orders,   width=22).pack(anchor="w", pady=4)
        btn(card, "Export Products CSV", self._export_products, width=22).pack(anchor="w", pady=4)

    def refresh(self) -> None:
        pass  # static tab — nothing to refresh

    def _backup(self) -> None:
        try:
            path = backup_db()
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "backup_db", path
            )
            messagebox.showinfo(
                "Backup", f"Database backed up to:\n{os.path.abspath(path)}",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.root)

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
