"""Main POS application window with all tabs.

Tabs (visible depending on role):
  POS       — cart, product selection, checkout  (cashier + admin)
  Orders    — history, detail view, reprint       (cashier + admin)
  Dashboard — statistics, low-stock alert         (cashier + admin)
  Products  — CRUD                                (admin only)
  Users     — CRUD                                (admin only)
  Audit Log — activity log, export                (admin only)
  Settings  — backup DB, open folders             (admin only)
"""

from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Dict, List, Optional

from config import (
    APP_NAME,
    APP_VERSION,
    AUDIT_LOG_LIMIT,
    BACKUPS_DIR,
    EXPORTS_DIR,
    FONT,
    LOW_STOCK_THRESHOLD,
    PAYMENT_METHODS,
    RECEIPTS_DIR,
    THEME,
)
from db import Database
from receipts import ReceiptBuilder
from ui.dialogs import ProductDialog, UserDialog
from utils import (
    backup_db,
    date_str,
    export_to_csv,
    fmt_currency,
    open_folder,
    print_file,
    time_stamp,
)


# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

def _styled_tree(
    parent: tk.Widget,
    columns: List[str],
    col_widths: Optional[List[int]] = None,
    height: int = 14,
) -> ttk.Treeview:
    """Return a dark-themed Treeview with a vertical scrollbar."""
    style = ttk.Style()
    uid = f"Custom{id(parent)}.Treeview"
    style.configure(
        uid,
        background=THEME["tree_bg"],
        foreground=THEME["tree_fg"],
        fieldbackground=THEME["tree_bg"],
        rowheight=24,
        font=FONT["default"],
    )
    style.configure(
        f"{uid}.Heading",
        background=THEME["tree_heading_bg"],
        foreground=THEME["tree_heading_fg"],
        font=FONT["bold"],
    )
    style.map(uid, background=[("selected", THEME["select_bg"])])

    frame = tk.Frame(parent, bg=THEME["bg"])
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        height=height,
        style=uid,
    )
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    if col_widths:
        for col, w in zip(columns, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")
    else:
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="center")

    tree.tag_configure("odd",  background=THEME["tree_row_odd"])
    tree.tag_configure("even", background=THEME["tree_row_even"])

    return tree


def _btn(
    parent: tk.Widget,
    text: str,
    command,
    danger: bool = False,
    width: int = 14,
) -> tk.Button:
    bg = THEME["danger"] if danger else THEME["button_bg"]
    return tk.Button(
        parent,
        text=text,
        font=FONT["bold"],
        bg=bg,
        fg=THEME["bg"],
        activebackground=THEME["surface2"],
        activeforeground=THEME["fg"],
        relief="flat",
        padx=10,
        pady=6,
        cursor="hand2",
        width=width,
        command=command,
    )


def _section_label(parent: tk.Widget, text: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=FONT["heading"],
        bg=THEME["bg"],
        fg=THEME["accent"],
    )


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------

class PosApp:
    """Root application controller; builds the main window and all tabs."""

    def __init__(self, root: tk.Tk, db: Database, user: dict) -> None:
        self.root = root
        self.db = db
        self.user = user  # {"id": int, "username": str, "role": str}
        self.is_admin = user["role"] == "admin"

        # POS cart state
        self._cart: List[Dict[str, Any]] = []
        self._cart_total: float = 0.0
        self._products_cache: List[sqlite3.Row] = []

        self._configure_root()
        self._build_ui()

        # Refresh dynamic content on startup
        self._refresh_pos_products()
        self._refresh_dashboard()
        self._refresh_orders_list()
        if self.is_admin:
            self._refresh_products_list()
            self._refresh_users_list()
            self._refresh_audit_log()

    # ------------------------------------------------------------------
    # Root window configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title(
            f"{APP_NAME} v{APP_VERSION}  —  {self.user['username']}  [{self.user['role']}]"
        )
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1200x720")
        self.root.minsize(900, 600)
        # Centre on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 1200, 720
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ------------------------------------------------------------------
    # Top-level UI skeleton
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ---- Header bar ----
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

        # ---- Notebook (tabs) ----
        style = ttk.Style()
        style.configure(
            "Dark.TNotebook",
            background=THEME["bg"],
            borderwidth=0,
        )
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

        self._build_pos_tab()
        self._build_orders_tab()
        self._build_dashboard_tab()

        if self.is_admin:
            self._build_products_tab()
            self._build_users_tab()
            self._build_audit_tab()
            self._build_settings_tab()

    # ==================================================================
    # POS TAB
    # ==================================================================

    def _build_pos_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 🛒 POS ")

        # Left: product grid + search
        left = tk.Frame(tab, bg=THEME["bg"], width=480)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        # Search bar
        search_row = tk.Frame(left, bg=THEME["bg"])
        search_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            search_row, text="Search:", font=FONT["bold"],
            bg=THEME["bg"], fg=THEME["fg"]
        ).pack(side="left")
        self._pos_search_var = tk.StringVar()
        self._pos_search_var.trace_add("write", lambda *_: self._filter_pos_products())
        tk.Entry(
            search_row,
            textvariable=self._pos_search_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Product list (treeview)
        _section_label(left, "Products").pack(anchor="w")
        cols = ["ID", "Name", "Category", "Price", "Stock"]
        widths = [40, 180, 100, 80, 60]
        self._pos_prod_tree = _styled_tree(left, cols, widths, height=16)
        self._pos_prod_tree.bind("<Double-1>", lambda _e: self._add_to_cart_from_tree())

        tk.Button(
            left,
            text="+ Add to Cart",
            font=FONT["bold"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._add_to_cart_from_tree,
        ).pack(pady=(6, 0))

        # Right: cart
        right = tk.Frame(tab, bg=THEME["surface"], width=380)
        right.pack(side="right", fill="y", padx=(4, 8), pady=8)
        right.pack_propagate(False)

        _section_label(right, "  Cart").pack(anchor="w", padx=8, pady=(8, 4))

        cols_c = ["#", "Product", "Qty", "Price", "Sub"]
        widths_c = [28, 130, 40, 70, 80]
        self._cart_tree = _styled_tree(right, cols_c, widths_c, height=14)

        # Cart total
        total_frame = tk.Frame(right, bg=THEME["surface"])
        total_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(
            total_frame, text="Total:", font=FONT["heading"],
            bg=THEME["surface"], fg=THEME["fg"]
        ).pack(side="left")
        self._cart_total_var = tk.StringVar(value="0.00")
        tk.Label(
            total_frame,
            textvariable=self._cart_total_var,
            font=FONT["heading"],
            bg=THEME["surface"],
            fg=THEME["accent"],
        ).pack(side="right")

        # Payment method
        pay_frame = tk.Frame(right, bg=THEME["surface"])
        pay_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(
            pay_frame, text="Payment:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"]
        ).pack(side="left")
        self._payment_var = tk.StringVar(value=PAYMENT_METHODS[0])
        pay_menu = tk.OptionMenu(pay_frame, self._payment_var, *PAYMENT_METHODS)
        pay_menu.configure(
            font=FONT["default"], bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            relief="flat", highlightthickness=0
        )
        pay_menu["menu"].configure(
            bg=THEME["entry_bg"], fg=THEME["entry_fg"], font=FONT["default"]
        )
        pay_menu.pack(side="right")

        # Cash paid (for change calculation)
        cash_frame = tk.Frame(right, bg=THEME["surface"])
        cash_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            cash_frame, text="Cash paid:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"]
        ).pack(side="left")
        self._cash_paid_var = tk.StringVar(value="0")
        tk.Entry(
            cash_frame,
            textvariable=self._cash_paid_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=4,
            width=12,
        ).pack(side="right")

        # Action buttons
        btn_frame = tk.Frame(right, bg=THEME["surface"])
        btn_frame.pack(fill="x", padx=8, pady=6)
        _btn(btn_frame, "Remove Item", self._remove_cart_item, danger=True, width=13).pack(
            side="left", padx=3
        )
        _btn(btn_frame, "Clear Cart", self._clear_cart, danger=True, width=11).pack(
            side="left", padx=3
        )
        tk.Button(
            right,
            text="  Checkout  ",
            font=FONT["title"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            activebackground=THEME["accent"],
            relief="flat",
            pady=12,
            cursor="hand2",
            command=self._checkout,
        ).pack(fill="x", padx=8, pady=(4, 10))

    # ---- POS helpers ----

    def _refresh_pos_products(self) -> None:
        self._products_cache = list(self.db.get_all_products())
        self._filter_pos_products()

    def _filter_pos_products(self) -> None:
        query = self._pos_search_var.get().strip().lower()
        self._pos_prod_tree.delete(*self._pos_prod_tree.get_children())
        for i, p in enumerate(self._products_cache):
            if query and query not in p["name"].lower() and query not in p["category"].lower():
                continue
            tag = "even" if i % 2 == 0 else "odd"
            self._pos_prod_tree.insert(
                "",
                "end",
                values=(
                    p["id"],
                    p["name"],
                    p["category"],
                    fmt_currency(p["price"]),
                    p["stock"],
                ),
                tags=(tag,),
            )

    def _add_to_cart_from_tree(self) -> None:
        sel = self._pos_prod_tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Please select a product first.", parent=self.root)
            return
        values = self._pos_prod_tree.item(sel[0], "values")
        product_id = int(values[0])
        product = self.db.get_product_by_id(product_id)
        if not product:
            return
        if product["stock"] <= 0:
            messagebox.showwarning(
                "Out of Stock",
                f"'{product['name']}' is out of stock.",
                parent=self.root,
            )
            return

        # Ask for quantity
        qty = simpledialog.askinteger(
            "Quantity",
            f"How many '{product['name']}'?",
            minvalue=1,
            maxvalue=product["stock"],
            parent=self.root,
        )
        if not qty:
            return

        # Check already in cart
        for item in self._cart:
            if item["product_id"] == product_id:
                new_qty = item["quantity"] + qty
                if new_qty > product["stock"]:
                    messagebox.showwarning(
                        "Insufficient Stock",
                        f"Only {product['stock']} units available.",
                        parent=self.root,
                    )
                    return
                item["quantity"] = new_qty
                item["subtotal"] = item["unit_price"] * new_qty
                self._render_cart()
                return

        self._cart.append(
            {
                "product_id": product_id,
                "product_name": product["name"],
                "quantity": qty,
                "unit_price": product["price"],
                "subtotal": product["price"] * qty,
            }
        )
        self._render_cart()

    def _render_cart(self) -> None:
        self._cart_tree.delete(*self._cart_tree.get_children())
        total = 0.0
        for i, item in enumerate(self._cart, 1):
            tag = "even" if i % 2 == 0 else "odd"
            self._cart_tree.insert(
                "",
                "end",
                values=(
                    i,
                    item["product_name"],
                    item["quantity"],
                    fmt_currency(item["unit_price"]),
                    fmt_currency(item["subtotal"]),
                ),
                tags=(tag,),
            )
            total += item["subtotal"]
        self._cart_total = total
        self._cart_total_var.set(fmt_currency(total))

    def _remove_cart_item(self) -> None:
        sel = self._cart_tree.selection()
        if not sel:
            return
        idx = self._cart_tree.index(sel[0])
        if 0 <= idx < len(self._cart):
            del self._cart[idx]
            self._render_cart()

    def _clear_cart(self) -> None:
        if self._cart and not messagebox.askyesno(
            "Clear Cart", "Remove all items from cart?", parent=self.root
        ):
            return
        self._cart.clear()
        self._render_cart()

    def _checkout(self) -> None:
        if not self._cart:
            messagebox.showinfo("Empty Cart", "Add items to the cart first.", parent=self.root)
            return

        payment = self._payment_var.get()
        paid_str = self._cash_paid_var.get().strip()
        paid = 0.0
        if payment == "Cash":
            try:
                paid = float(paid_str)
            except ValueError:
                messagebox.showwarning(
                    "Invalid Amount", "Please enter a valid cash amount.", parent=self.root
                )
                return
            if paid < self._cart_total:
                messagebox.showwarning(
                    "Insufficient Cash",
                    f"Cash paid ({fmt_currency(paid)}) is less than total ({fmt_currency(self._cart_total)}).",
                    parent=self.root,
                )
                return

        if not messagebox.askyesno(
            "Confirm Checkout",
            f"Total: {fmt_currency(self._cart_total)}\nPayment: {payment}\nProceed?",
            parent=self.root,
        ):
            return

        order_id = self.db.create_order(
            cashier_id=self.user["id"],
            cashier_name=self.user["username"],
            total=self._cart_total,
            payment_method=payment,
            items=self._cart,
        )

        # Build and save receipt
        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=self.user["username"],
            payment_method=payment,
            items=self._cart,
            total=self._cart_total,
            paid=paid,
        )
        receipt_path = builder.save()

        # Attempt to print
        print_file(receipt_path)

        # Audit log
        self.db.add_audit_log(
            self.user["id"],
            self.user["username"],
            "checkout",
            f"Order #{order_id} total={fmt_currency(self._cart_total)} payment={payment}",
        )

        messagebox.showinfo(
            "Order Complete",
            f"Order #{order_id} saved!\nReceipt: {receipt_path}",
            parent=self.root,
        )

        self._cart.clear()
        self._render_cart()
        self._cash_paid_var.set("0")
        self._refresh_pos_products()
        self._refresh_orders_list()
        self._refresh_dashboard()

    # ==================================================================
    # ORDERS TAB
    # ==================================================================

    def _build_orders_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 📋 Orders ")

        top = tk.Frame(tab, bg=THEME["bg"])
        top.pack(fill="both", expand=True, padx=8, pady=8)

        # Orders list (left)
        left = tk.Frame(top, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True)

        _section_label(left, "Order History").pack(anchor="w", pady=(0, 4))

        cols = ["ID", "Date", "Cashier", "Total", "Payment"]
        widths = [50, 160, 120, 100, 110]
        self._orders_tree = _styled_tree(left, cols, widths, height=18)
        self._orders_tree.bind("<ButtonRelease-1>", lambda _e: self._show_order_detail())

        btn_row = tk.Frame(left, bg=THEME["bg"])
        btn_row.pack(fill="x", pady=(6, 0))
        _btn(btn_row, "Refresh", self._refresh_orders_list).pack(side="left", padx=4)
        _btn(btn_row, "Reprint", self._reprint_order).pack(side="left", padx=4)

        # Order detail (right)
        right = tk.Frame(top, bg=THEME["surface"], width=340)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        _section_label(right, "  Order Detail").pack(anchor="w", padx=8, pady=(8, 4))

        cols_d = ["Product", "Qty", "Price", "Sub"]
        widths_d = [130, 50, 75, 75]
        self._order_detail_tree = _styled_tree(right, cols_d, widths_d, height=14)

        self._order_info_var = tk.StringVar(value="Select an order to view details.")
        tk.Label(
            right,
            textvariable=self._order_info_var,
            font=FONT["default"],
            bg=THEME["surface"],
            fg=THEME["fg"],
            justify="left",
            wraplength=320,
        ).pack(padx=8, pady=4)

    def _refresh_orders_list(self) -> None:
        self._orders_tree.delete(*self._orders_tree.get_children())
        for i, o in enumerate(self.db.get_all_orders()):
            tag = "even" if i % 2 == 0 else "odd"
            self._orders_tree.insert(
                "",
                "end",
                iid=str(o["id"]),
                values=(
                    o["id"],
                    o["created_at"],
                    o["cashier_name"],
                    fmt_currency(o["total"]),
                    o["payment_method"],
                ),
                tags=(tag,),
            )

    def _show_order_detail(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return

        self._order_detail_tree.delete(*self._order_detail_tree.get_children())
        for i, it in enumerate(self.db.get_order_items(order_id)):
            tag = "even" if i % 2 == 0 else "odd"
            self._order_detail_tree.insert(
                "",
                "end",
                values=(
                    it["product_name"],
                    it["quantity"],
                    fmt_currency(it["unit_price"]),
                    fmt_currency(it["subtotal"]),
                ),
                tags=(tag,),
            )

        self._order_info_var.set(
            f"Order #{order['id']}\n"
            f"Date : {order['created_at']}\n"
            f"By   : {order['cashier_name']}\n"
            f"Pay  : {order['payment_method']}\n"
            f"Total: {fmt_currency(order['total'])}"
        )

    def _reprint_order(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            messagebox.showinfo("Select Order", "Select an order first.", parent=self.root)
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return
        items = [dict(row) for row in self.db.get_order_items(order_id)]
        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=order["cashier_name"],
            payment_method=order["payment_method"],
            items=items,
            total=order["total"],
        )
        path = builder.save()
        ok = print_file(path)
        msg = f"Receipt saved:\n{path}" + ("\n\nPrint job sent." if ok else "")
        messagebox.showinfo("Reprint", msg, parent=self.root)

    # ==================================================================
    # DASHBOARD TAB
    # ==================================================================

    def _build_dashboard_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 📊 Dashboard ")
        self._dash_tab = tab

        # Top stats row
        stats_row = tk.Frame(tab, bg=THEME["bg"])
        stats_row.pack(fill="x", padx=12, pady=12)

        self._stat_vars: Dict[str, tk.StringVar] = {}
        stats_defs = [
            ("Today Orders", "today_orders", THEME["accent"]),
            ("Today Revenue", "today_revenue", THEME["accent2"]),
            ("Total Revenue", "all_revenue", THEME["warning"]),
            ("Total Products", "total_products", THEME["fg"]),
            ("Total Users", "total_users", THEME["fg"]),
        ]
        for label, key, color in stats_defs:
            card = tk.Frame(stats_row, bg=THEME["surface"], padx=16, pady=12)
            card.pack(side="left", expand=True, fill="both", padx=6)
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            tk.Label(card, text=label, font=FONT["bold"], bg=THEME["surface"], fg=THEME["fg"]).pack()
            tk.Label(card, textvariable=var, font=FONT["large"], bg=THEME["surface"], fg=color).pack()

        # Middle: top products + low stock
        mid = tk.Frame(tab, bg=THEME["bg"])
        mid.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Top products
        left = tk.Frame(mid, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        _section_label(left, "Top-Selling Products").pack(anchor="w", pady=(0, 4))
        cols = ["Product", "Qty Sold", "Revenue"]
        widths = [200, 100, 120]
        self._dash_top_tree = _styled_tree(left, cols, widths, height=10)

        # Low stock
        right = tk.Frame(mid, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        _section_label(right, f"Low Stock (≤ {LOW_STOCK_THRESHOLD})").pack(anchor="w", pady=(0, 4))
        cols_ls = ["ID", "Name", "Category", "Stock"]
        widths_ls = [50, 180, 120, 70]
        self._dash_low_tree = _styled_tree(right, cols_ls, widths_ls, height=10)

        # Refresh button
        _btn(tab, "Refresh Dashboard", self._refresh_dashboard, width=20).pack(pady=6)

    def _refresh_dashboard(self) -> None:
        today = date_str()
        stats = self.db.get_today_stats(today)
        self._stat_vars["today_orders"].set(str(stats["orders"]))
        self._stat_vars["today_revenue"].set(fmt_currency(stats["revenue"]))
        self._stat_vars["all_revenue"].set(fmt_currency(self.db.get_all_time_revenue()))
        self._stat_vars["total_products"].set(str(self.db.get_total_products()))
        self._stat_vars["total_users"].set(str(self.db.get_total_users()))

        # Top products
        self._dash_top_tree.delete(*self._dash_top_tree.get_children())
        for i, p in enumerate(self.db.get_top_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._dash_top_tree.insert(
                "",
                "end",
                values=(p["product_name"], p["total_qty"], fmt_currency(p["total_revenue"])),
                tags=(tag,),
            )

        # Low stock
        self._dash_low_tree.delete(*self._dash_low_tree.get_children())
        for i, p in enumerate(self.db.get_low_stock_products(LOW_STOCK_THRESHOLD)):
            tag = "even" if i % 2 == 0 else "odd"
            self._dash_low_tree.insert(
                "",
                "end",
                values=(p["id"], p["name"], p["category"], p["stock"]),
                tags=(tag,),
            )

    # ==================================================================
    # PRODUCTS TAB  (admin only)
    # ==================================================================

    def _build_products_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 🥗 Products ")

        _section_label(tab, "Product Management").pack(anchor="w", padx=8, pady=(8, 4))

        cols = ["ID", "Name", "Category", "Price", "Stock", "Updated"]
        widths = [50, 200, 110, 90, 70, 160]
        self._prod_tree = _styled_tree(tab, cols, widths, height=18)

        btn_row = tk.Frame(tab, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        _btn(btn_row, "Add Product", self._add_product).pack(side="left", padx=4)
        _btn(btn_row, "Edit Product", self._edit_product).pack(side="left", padx=4)
        _btn(btn_row, "Delete Product", self._delete_product, danger=True).pack(side="left", padx=4)
        _btn(btn_row, "Refresh", self._refresh_products_list).pack(side="left", padx=4)
        _btn(btn_row, "Export CSV", self._export_products_csv).pack(side="left", padx=4)

    def _refresh_products_list(self) -> None:
        self._prod_tree.delete(*self._prod_tree.get_children())
        for i, p in enumerate(self.db.get_all_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._prod_tree.insert(
                "",
                "end",
                iid=str(p["id"]),
                values=(
                    p["id"],
                    p["name"],
                    p["category"],
                    fmt_currency(p["price"]),
                    p["stock"],
                    p["updated_at"],
                ),
                tags=(tag,),
            )

    def _add_product(self) -> None:
        dlg = ProductDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.db.add_product(r["name"], r["category"], r["price"], r["stock"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_product", f"name={r['name']}"
                )
                self._refresh_products_list()
                self._refresh_pos_products()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit_product(self) -> None:
        sel = self._prod_tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Select a product to edit.", parent=self.root)
            return
        product_id = int(sel[0])
        row = self.db.get_product_by_id(product_id)
        if not row:
            return
        product = dict(row)
        dlg = ProductDialog(self.root, product=product)
        if dlg.result:
            r = dlg.result
            try:
                self.db.update_product(product_id, r["name"], r["category"], r["price"], r["stock"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_product", f"id={product_id} name={r['name']}"
                )
                self._refresh_products_list()
                self._refresh_pos_products()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete_product(self) -> None:
        sel = self._prod_tree.selection()
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
        self.db.delete_product(product_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_product", f"id={product_id} name={row['name']}"
        )
        self._refresh_products_list()
        self._refresh_pos_products()

    def _export_products_csv(self) -> None:
        products = self.db.get_all_products()
        headers = ["ID", "Name", "Category", "Price", "Stock", "Created", "Updated"]
        rows = [
            (p["id"], p["name"], p["category"], p["price"], p["stock"], p["created_at"], p["updated_at"])
            for p in products
        ]
        path = os.path.join(EXPORTS_DIR, f"products_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_products_csv", path
        )
        messagebox.showinfo("Export", f"Products exported to:\n{os.path.abspath(path)}", parent=self.root)

    # ==================================================================
    # USERS TAB  (admin only)
    # ==================================================================

    def _build_users_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 👤 Users ")

        _section_label(tab, "User Management").pack(anchor="w", padx=8, pady=(8, 4))

        cols = ["ID", "Username", "Role", "Created"]
        widths = [50, 200, 100, 180]
        self._users_tree = _styled_tree(tab, cols, widths, height=18)

        btn_row = tk.Frame(tab, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        _btn(btn_row, "Add User", self._add_user).pack(side="left", padx=4)
        _btn(btn_row, "Edit User", self._edit_user).pack(side="left", padx=4)
        _btn(btn_row, "Delete User", self._delete_user, danger=True).pack(side="left", padx=4)
        _btn(btn_row, "Refresh", self._refresh_users_list).pack(side="left", padx=4)

    def _refresh_users_list(self) -> None:
        self._users_tree.delete(*self._users_tree.get_children())
        for i, u in enumerate(self.db.get_all_users()):
            tag = "even" if i % 2 == 0 else "odd"
            self._users_tree.insert(
                "",
                "end",
                iid=str(u["id"]),
                values=(u["id"], u["username"], u["role"], u["created_at"]),
                tags=(tag,),
            )

    def _add_user(self) -> None:
        dlg = UserDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.db.add_user(r["username"], r["password"], r["role"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_user", f"username={r['username']} role={r['role']}"
                )
                self._refresh_users_list()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit_user(self) -> None:
        sel = self._users_tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to edit.", parent=self.root)
            return
        user_id = int(sel[0])
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        dlg = UserDialog(self.root, user=dict(row))
        if dlg.result:
            r = dlg.result
            try:
                self.db.update_user(user_id, r["username"], r["password"] or None, r["role"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_user", f"id={user_id} username={r['username']}"
                )
                self._refresh_users_list()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete_user(self) -> None:
        sel = self._users_tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to delete.", parent=self.root)
            return
        user_id = int(sel[0])
        if user_id == self.user["id"]:
            messagebox.showwarning("Cannot Delete", "You cannot delete your own account.", parent=self.root)
            return
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        if not messagebox.askyesno(
            "Confirm Delete", f"Delete user '{row['username']}'?", parent=self.root
        ):
            return
        self.db.delete_user(user_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_user", f"id={user_id} username={row['username']}"
        )
        self._refresh_users_list()

    # ==================================================================
    # AUDIT LOG TAB  (admin only)
    # ==================================================================

    def _build_audit_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" 📝 Audit Log ")

        _section_label(tab, f"Audit Log (last {AUDIT_LOG_LIMIT})").pack(
            anchor="w", padx=8, pady=(8, 4)
        )

        cols = ["ID", "Date", "User", "Action", "Details"]
        widths = [50, 160, 110, 130, 350]
        self._audit_tree = _styled_tree(tab, cols, widths, height=20)

        btn_row = tk.Frame(tab, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        _btn(btn_row, "Refresh", self._refresh_audit_log).pack(side="left", padx=4)
        _btn(btn_row, "Export CSV", self._export_audit_csv).pack(side="left", padx=4)

    def _refresh_audit_log(self) -> None:
        self._audit_tree.delete(*self._audit_tree.get_children())
        for i, log in enumerate(self.db.get_audit_logs(AUDIT_LOG_LIMIT)):
            tag = "even" if i % 2 == 0 else "odd"
            self._audit_tree.insert(
                "",
                "end",
                values=(
                    log["id"],
                    log["created_at"],
                    log["username"],
                    log["action"],
                    log["details"] or "",
                ),
                tags=(tag,),
            )

    def _export_audit_csv(self) -> None:
        logs = self.db.get_audit_logs(AUDIT_LOG_LIMIT)
        headers = ["ID", "Date", "User ID", "Username", "Action", "Details"]
        rows = [
            (lg["id"], lg["created_at"], lg["user_id"], lg["username"], lg["action"], lg["details"])
            for lg in logs
        ]
        path = os.path.join(EXPORTS_DIR, f"audit_log_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        messagebox.showinfo("Export", f"Audit log exported to:\n{os.path.abspath(path)}", parent=self.root)

    # ==================================================================
    # SETTINGS TAB  (admin only)
    # ==================================================================

    def _build_settings_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(tab, text=" ⚙ Settings ")

        card = tk.Frame(tab, bg=THEME["surface"], padx=30, pady=30)
        card.pack(padx=40, pady=40, anchor="nw")

        _section_label(card, "Database").pack(anchor="w", pady=(0, 8))
        _btn(card, "Backup Database", self._backup_db, width=22).pack(anchor="w", pady=4)

        _section_label(card, "Folders").pack(anchor="w", pady=(16, 8))
        for label, folder in [
            ("Open Receipts Folder", RECEIPTS_DIR),
            ("Open Backups Folder", BACKUPS_DIR),
            ("Open Exports Folder", EXPORTS_DIR),
        ]:
            _btn(
                card,
                label,
                lambda f=folder: open_folder(f),
                width=24,
            ).pack(anchor="w", pady=4)

        _section_label(card, "Data Export").pack(anchor="w", pady=(16, 8))
        _btn(card, "Export Orders CSV", self._export_orders_csv, width=22).pack(anchor="w", pady=4)
        _btn(card, "Export Products CSV", self._export_products_csv, width=22).pack(anchor="w", pady=4)

    def _backup_db(self) -> None:
        try:
            path = backup_db()
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "backup_db", path
            )
            messagebox.showinfo("Backup", f"Database backed up to:\n{os.path.abspath(path)}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.root)

    def _export_orders_csv(self) -> None:
        orders = self.db.get_all_orders()
        headers = ["ID", "Date", "Cashier ID", "Cashier", "Total", "Payment"]
        rows = [
            (o["id"], o["created_at"], o["cashier_id"], o["cashier_name"], o["total"], o["payment_method"])
            for o in orders
        ]
        path = os.path.join(EXPORTS_DIR, f"orders_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_orders_csv", path
        )
        messagebox.showinfo("Export", f"Orders exported to:\n{os.path.abspath(path)}", parent=self.root)

    # ==================================================================
    # Logout
    # ==================================================================

    def _logout(self) -> None:
        if messagebox.askyesno("Logout", "Log out and return to login screen?", parent=self.root):
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "logout", ""
            )
            self.root.destroy()
