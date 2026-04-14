"""Products tab — CRUD for menu items (admin only)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from config import EXPORTS_DIR, FONT, THEME
from ui.dialogs import ProductDialog
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree
from utils import export_to_csv, fmt_currency, time_stamp

if TYPE_CHECKING:
    from ui.main import PosApp


class ProductsTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 🥗 Products ")

    def _build(self) -> None:
        section_label(self, "Product Management").pack(anchor="w", padx=8, pady=(8, 4))

        self._tree = styled_tree(
            self,
            ["ID", "Name", "Category", "Price", "Stock", "Updated"],
            [50, 200, 110, 90, 70, 160],
            height=18,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Add Product",    self._add).pack(side="left", padx=4)
        btn(btn_row, "Edit Product",   self._edit).pack(side="left", padx=4)
        btn(btn_row, "Delete Product", self._delete, danger=True).pack(side="left", padx=4)
        btn(btn_row, "Refresh",        self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Export CSV",     self._export_csv).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, p in enumerate(self.db.get_all_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                iid=str(p["id"]),
                values=(
                    p["id"], p["name"], p["category"],
                    fmt_currency(p["price"]), p["stock"], p["updated_at"],
                ),
                tags=(tag,),
            )

    def _add(self) -> None:
        if not self._assert_session_active():
            return
        dlg = ProductDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.app.product_service.add_product(
                    r["name"], r["category"], r["price"], r["stock"]
                )
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_product", f"name={r['name']}",
                )
                self.refresh()
                self.app.refresh_tab("pos")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit(self) -> None:
        if not self._assert_session_active():
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Select a product to edit.", parent=self.root)
            return
        product_id = int(sel[0])
        row = self.db.get_product_by_id(product_id)
        if not row:
            return
        dlg = ProductDialog(self.root, product=dict(row))
        if dlg.result:
            r = dlg.result
            try:
                self.app.product_service.update_product(
                    product_id, r["name"], r["category"], r["price"], r["stock"]
                )
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_product", f"id={product_id} name={r['name']}",
                )
                self.refresh()
                self.app.refresh_tab("pos")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete(self) -> None:
        if not self._assert_session_active():
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Select a product to delete.", parent=self.root)
            return
        product_id = int(sel[0])
        row = self.db.get_product_by_id(product_id)
        if not row:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete product '{row['name']}'? This cannot be undone.",
            parent=self.root,
        ):
            return
        self.app.product_service.delete_product(product_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_product", f"id={product_id} name={row['name']}",
        )
        self.refresh()
        self.app.refresh_tab("pos")

    def _export_csv(self) -> None:
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
