"""Orders tab — order history with filtering and detail view."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from config import FONT, PAYMENT_METHODS, THEME
from receipts import ReceiptBuilder
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree
from utils import fmt_currency, print_file

if TYPE_CHECKING:
    from ui.main import PosApp


class OrdersTab(BaseTab):
    """Order history with date/cashier/payment filters and inline detail."""

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📋 Orders ")

    def _build(self) -> None:
        top = tk.Frame(self, bg=THEME["bg"])
        top.pack(fill="both", expand=True, padx=8, pady=8)

        # ---- Filter bar ----
        filter_bar = tk.Frame(top, bg=THEME["surface"], padx=8, pady=6)
        filter_bar.pack(fill="x", pady=(0, 6))

        def _lbl(text: str) -> None:
            tk.Label(
                filter_bar, text=text, font=FONT["bold"],
                bg=THEME["surface"], fg=THEME["fg"],
            ).pack(side="left", padx=(8, 2))

        def _entry(var: tk.StringVar, width: int = 12) -> None:
            tk.Entry(
                filter_bar,
                textvariable=var,
                font=FONT["default"],
                bg=THEME["entry_bg"],
                fg=THEME["entry_fg"],
                insertbackground=THEME["fg"],
                relief="flat",
                bd=4,
                width=width,
            ).pack(side="left", padx=(0, 4))

        self._filter_from = tk.StringVar()
        self._filter_to = tk.StringVar()
        self._filter_cashier = tk.StringVar()
        self._filter_payment = tk.StringVar(value="")

        _lbl("From:")
        _entry(self._filter_from)
        _lbl("To:")
        _entry(self._filter_to)
        _lbl("Cashier:")
        _entry(self._filter_cashier, 10)
        _lbl("Payment:")
        pay_choices = [""] + list(PAYMENT_METHODS)
        pay_menu = tk.OptionMenu(filter_bar, self._filter_payment, *pay_choices)
        pay_menu.configure(
            font=FONT["default"], bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            relief="flat", highlightthickness=0, width=10,
        )
        pay_menu["menu"].configure(
            bg=THEME["entry_bg"], fg=THEME["entry_fg"], font=FONT["default"],
        )
        pay_menu.pack(side="left", padx=4)

        tk.Button(
            filter_bar,
            text="Filter",
            font=FONT["bold"],
            bg=THEME["accent"],
            fg=THEME["bg"],
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._apply_filter,
        ).pack(side="left", padx=4)
        tk.Button(
            filter_bar,
            text="Clear",
            font=FONT["bold"],
            bg=THEME["surface2"],
            fg=THEME["fg"],
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._clear_filter,
        ).pack(side="left", padx=4)

        # ---- Order list ----
        left = tk.Frame(top, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True)

        section_label(left, "Order History").pack(anchor="w", pady=(0, 4))
        self._orders_tree = styled_tree(
            left,
            ["ID", "Date", "Cashier", "Total", "Payment"],
            [50, 160, 120, 100, 110],
            height=18,
        )
        self._orders_tree.bind("<ButtonRelease-1>", lambda _e: self._show_detail())

        btn_row = tk.Frame(left, bg=THEME["bg"])
        btn_row.pack(fill="x", pady=(6, 0))
        btn(btn_row, "Refresh", self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Reprint", self._reprint).pack(side="left", padx=4)

        # ---- Detail panel ----
        right = tk.Frame(top, bg=THEME["surface"], width=340)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        section_label(right, "  Order Detail").pack(anchor="w", padx=8, pady=(8, 4))

        self._detail_tree = styled_tree(
            right,
            ["Product", "Qty", "Price", "Sub"],
            [130, 50, 75, 75],
            height=14,
        )

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

    def refresh(self) -> None:
        self._orders_tree.delete(*self._orders_tree.get_children())
        orders = self.db.get_all_orders()
        for i, o in enumerate(orders):
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

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self) -> None:
        self._orders_tree.delete(*self._orders_tree.get_children())
        orders = self.db.get_orders_filtered(
            date_from=self._filter_from.get().strip(),
            date_to=self._filter_to.get().strip(),
            cashier=self._filter_cashier.get().strip(),
            payment=self._filter_payment.get().strip(),
        )
        for i, o in enumerate(orders):
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

    def _clear_filter(self) -> None:
        self._filter_from.set("")
        self._filter_to.set("")
        self._filter_cashier.set("")
        self._filter_payment.set("")
        self.refresh()

    # ------------------------------------------------------------------
    # Detail / reprint
    # ------------------------------------------------------------------

    def _show_detail(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return

        self._detail_tree.delete(*self._detail_tree.get_children())
        for i, it in enumerate(self.db.get_order_items(order_id)):
            tag = "even" if i % 2 == 0 else "odd"
            self._detail_tree.insert(
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

        discount = order["discount_amount"] if "discount_amount" in order.keys() else 0.0
        discount_line = (
            f"Discount: -{fmt_currency(discount)}\n" if discount else ""
        )
        self._order_info_var.set(
            f"Order #{order['id']}\n"
            f"Date : {order['created_at']}\n"
            f"By   : {order['cashier_name']}\n"
            f"Pay  : {order['payment_method']}\n"
            f"{discount_line}"
            f"Total: {fmt_currency(order['total'])}"
        )

    def _reprint(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            messagebox.showinfo("Select Order", "Select an order first.", parent=self.root)
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return
        items = [dict(row) for row in self.db.get_order_items(order_id)]
        discount = order["discount_amount"] if "discount_amount" in order.keys() else 0.0
        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=order["cashier_name"],
            payment_method=order["payment_method"],
            items=items,
            total=order["total"],
            discount_amount=discount,
        )
        path = builder.save()
        ok = print_file(path)
        msg = f"Receipt saved:\n{path}" + ("\n\nPrint job sent." if ok else "")
        messagebox.showinfo("Reprint", msg, parent=self.root)
