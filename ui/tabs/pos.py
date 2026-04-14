"""POS tab — product selection, cart management, and checkout."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import TYPE_CHECKING, Any, Dict, List

from config import FONT, PAYMENT_METHODS, THEME
from receipts import ReceiptBuilder
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree
from utils import fmt_currency, print_file

if TYPE_CHECKING:
    from tkinter import ttk
    from ui.main import PosApp


class PosTab(BaseTab):
    """Cart + product grid + checkout."""

    def __init__(self, notebook, app: "PosApp") -> None:
        self._cart: List[Dict[str, Any]] = []
        self._cart_total: float = 0.0
        self._products_cache: List[sqlite3.Row] = []
        super().__init__(notebook, app, " 🛒 POS ")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        from config import CATEGORIES

        # Left: product grid + search + category filters + barcode
        left = tk.Frame(self, bg=THEME["bg"], width=480)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        # --- Barcode input row (F3 shortcut focuses it) ---
        barcode_row = tk.Frame(left, bg=THEME["bg"])
        barcode_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            barcode_row, text="🔍 Barcode:", font=FONT["bold"],
            bg=THEME["bg"], fg=THEME["fg"],
        ).pack(side="left")
        self._barcode_var = tk.StringVar()
        self._barcode_entry = tk.Entry(
            barcode_row,
            textvariable=self._barcode_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
            width=18,
        )
        self._barcode_entry.pack(side="left", padx=(6, 0))
        self._barcode_entry.bind("<Return>", lambda _e: self._add_by_barcode())
        tk.Button(
            barcode_row,
            text="Add",
            font=FONT["bold"],
            bg=THEME["accent"],
            fg=THEME["bg"],
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._add_by_barcode,
        ).pack(side="left", padx=(4, 0))

        # --- Search row ---
        search_row = tk.Frame(left, bg=THEME["bg"])
        search_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            search_row, text="Search:", font=FONT["bold"],
            bg=THEME["bg"], fg=THEME["fg"],
        ).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_products())
        self._search_entry = tk.Entry(
            search_row,
            textvariable=self._search_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # --- Category filter buttons (F4-F9 shortcuts) ---
        cat_row = tk.Frame(left, bg=THEME["bg"])
        cat_row.pack(fill="x", pady=(0, 4))
        self._active_category: str = ""
        all_btn = tk.Button(
            cat_row, text="All", font=FONT["bold"],
            bg=THEME["accent"], fg=THEME["bg"],
            relief="flat", padx=8, pady=2, cursor="hand2",
            command=lambda: self._set_category(""),
        )
        all_btn.pack(side="left", padx=(0, 2))
        self._cat_buttons: dict = {"": all_btn}
        for cat in CATEGORIES:
            c = cat  # capture
            b = tk.Button(
                cat_row, text=cat, font=FONT["bold"],
                bg=THEME["surface2"], fg=THEME["fg"],
                relief="flat", padx=8, pady=2, cursor="hand2",
                command=lambda _c=c: self._set_category(_c),
            )
            b.pack(side="left", padx=2)
            self._cat_buttons[cat] = b

        section_label(left, "Products").pack(anchor="w")
        self._prod_tree = styled_tree(
            left,
            ["ID", "Name", "Category", "Price", "Stock"],
            [40, 180, 100, 80, 60],
            height=14,
        )
        self._prod_tree.bind("<Double-1>", lambda _e: self._add_to_cart())
        self._prod_tree.bind("<Return>", lambda _e: self._add_to_cart())

        tk.Button(
            left,
            text="+ Add to Cart  (Enter)",
            font=FONT["bold"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            relief="flat",
            padx=10,
            pady=8,
            cursor="hand2",
            command=self._add_to_cart,
        ).pack(fill="x", pady=(6, 0))

        # Right: cart
        right = tk.Frame(self, bg=THEME["surface"], width=380)
        right.pack(side="right", fill="y", padx=(4, 8), pady=8)
        right.pack_propagate(False)

        section_label(right, "  Cart").pack(anchor="w", padx=8, pady=(8, 4))

        self._cart_tree = styled_tree(
            right,
            ["#", "Product", "Qty", "Price", "Sub"],
            [28, 130, 40, 70, 80],
            height=10,
        )

        # Discount row
        disc_frame = tk.Frame(right, bg=THEME["surface"])
        disc_frame.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(
            disc_frame, text="Coupon:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._coupon_var = tk.StringVar()
        tk.Entry(
            disc_frame,
            textvariable=self._coupon_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=4,
            width=10,
        ).pack(side="left", padx=(4, 2))
        tk.Button(
            disc_frame,
            text="Apply",
            font=FONT["bold"],
            bg=THEME["accent"],
            fg=THEME["bg"],
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._apply_coupon,
        ).pack(side="left")
        self._discount_label = tk.Label(
            disc_frame, text="", font=FONT["default"],
            bg=THEME["surface"], fg=THEME["accent2"],
        )
        self._discount_label.pack(side="right")

        # Totals
        total_frame = tk.Frame(right, bg=THEME["surface"])
        total_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            total_frame, text="Total:", font=FONT["heading"],
            bg=THEME["surface"], fg=THEME["fg"],
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
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._payment_var = tk.StringVar(value=PAYMENT_METHODS[0])
        pay_menu = tk.OptionMenu(pay_frame, self._payment_var, *PAYMENT_METHODS)
        pay_menu.configure(
            font=FONT["default"], bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            relief="flat", highlightthickness=0,
        )
        pay_menu["menu"].configure(
            bg=THEME["entry_bg"], fg=THEME["entry_fg"], font=FONT["default"],
        )
        pay_menu.pack(side="right")

        # Cash paid
        cash_frame = tk.Frame(right, bg=THEME["surface"])
        cash_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            cash_frame, text="Cash paid:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
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
        btn(btn_frame, "Remove Item", self._remove_item, danger=True, width=13).pack(
            side="left", padx=3
        )
        btn(btn_frame, "Clear Cart", self._clear_cart, danger=True, width=11).pack(
            side="left", padx=3
        )

        tk.Button(
            right,
            text="  ✔  Checkout  (F2)  ",
            font=FONT["title"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            activebackground=THEME["accent"],
            relief="flat",
            pady=16,
            cursor="hand2",
            command=self._checkout,
        ).pack(fill="x", padx=8, pady=(4, 10))

    # ------------------------------------------------------------------
    # Public API (called by PosApp)
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._products_cache = list(self.db.get_all_products())
        self._filter_products()

    def focus_search(self) -> None:
        """Switch notebook to this tab and focus the search field."""
        self.app.notebook.select(self)
        self._search_entry.focus_set()

    def focus_barcode(self) -> None:
        """Switch notebook to this tab and focus the barcode entry."""
        self.app.notebook.select(self)
        self._barcode_entry.focus_set()

    def trigger_checkout(self) -> None:
        self._checkout()

    def clear_cart_cmd(self) -> None:
        self._clear_cart()

    # ------------------------------------------------------------------
    # Category filter
    # ------------------------------------------------------------------

    def _set_category(self, category: str) -> None:
        self._active_category = category
        for cat, btn_widget in self._cat_buttons.items():
            if cat == category:
                btn_widget.configure(bg=THEME["accent"], fg=THEME["bg"])
            else:
                btn_widget.configure(bg=THEME["surface2"], fg=THEME["fg"])
        self._filter_products()

    # ------------------------------------------------------------------
    # Barcode lookup
    # ------------------------------------------------------------------

    def _add_by_barcode(self) -> None:
        """Look up a product by exact name match from the barcode field and add to cart."""
        query = self._barcode_var.get().strip()
        if not query:
            return
        matches = [
            p for p in self._products_cache
            if p["name"].lower() == query.lower()
        ]
        if not matches:
            # Fall back to partial match
            matches = [
                p for p in self._products_cache
                if query.lower() in p["name"].lower()
            ]
        if not matches:
            messagebox.showwarning(
                "Not Found",
                f"No product found matching '{query}'.",
                parent=self.root,
            )
            self._barcode_var.set("")
            return
        if len(matches) > 1:
            messagebox.showinfo(
                "Multiple Matches",
                f"'{query}' matches {len(matches)} products.\n"
                "Use the search box to narrow down, then double-click.",
                parent=self.root,
            )
            self._search_var.set(query)
            self._barcode_var.set("")
            return
        product = matches[0]
        if product["stock"] <= 0:
            messagebox.showwarning(
                "Out of Stock",
                f"'{product['name']}' is out of stock.",
                parent=self.root,
            )
            self._barcode_var.set("")
            return
        # Add 1 unit directly (typical barcode-scanner workflow)
        for item in self._cart:
            if item["product_id"] == product["id"]:
                new_qty = item["quantity"] + 1
                if new_qty > product["stock"]:
                    messagebox.showwarning(
                        "Insufficient Stock",
                        f"Only {product['stock']} units available.",
                        parent=self.root,
                    )
                    self._barcode_var.set("")
                    return
                item["quantity"] = new_qty
                item["subtotal"] = item["unit_price"] * new_qty
                self._render_cart()
                self._barcode_var.set("")
                return
        self._cart.append(
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": 1,
                "unit_price": product["price"],
                "subtotal": product["price"],
            }
        )
        self._render_cart()
        self._barcode_var.set("")

    # ------------------------------------------------------------------
    # Product list
    # ------------------------------------------------------------------

    def _filter_products(self) -> None:
        query = self._search_var.get().strip().lower()
        cat_filter = getattr(self, "_active_category", "")
        self._prod_tree.delete(*self._prod_tree.get_children())
        for i, p in enumerate(self._products_cache):
            if cat_filter and p["category"] != cat_filter:
                continue
            if query and query not in p["name"].lower() and query not in p["category"].lower():
                continue
            tag = "even" if i % 2 == 0 else "odd"
            self._prod_tree.insert(
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

    # ------------------------------------------------------------------
    # Cart management
    # ------------------------------------------------------------------

    def _add_to_cart(self) -> None:
        sel = self._prod_tree.selection()
        if not sel:
            messagebox.showinfo(
                "Select Product", "Please select a product first.", parent=self.root
            )
            return
        values = self._prod_tree.item(sel[0], "values")
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

        qty = simpledialog.askinteger(
            "Quantity",
            f"How many '{product['name']}'?",
            minvalue=1,
            maxvalue=product["stock"],
            parent=self.root,
        )
        if qty is None:
            return

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
        # Re-apply any active discount to update the displayed total
        self._recalc_total()

    def _remove_item(self) -> None:
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
        self._coupon_var.set("")
        self._discount_amount = 0.0
        self._discount_label.configure(text="")
        self._render_cart()

    # ------------------------------------------------------------------
    # Discount / coupon
    # ------------------------------------------------------------------

    def _apply_coupon(self) -> None:
        code = self._coupon_var.get().strip()
        subtotal = sum(i["subtotal"] for i in self._cart)
        discount_amount, final = self.app.order_service.resolve_discount(
            code, subtotal
        )
        if code and discount_amount == 0.0:
            messagebox.showwarning(
                "Invalid Coupon",
                f"Coupon code '{code}' is not valid or has expired.",
                parent=self.root,
            )
            return
        self._discount_amount = discount_amount
        if discount_amount > 0:
            self._discount_label.configure(
                text=f"-{fmt_currency(discount_amount)}"
            )
        else:
            self._discount_label.configure(text="")
        self._recalc_total()

    def _recalc_total(self) -> None:
        discount = getattr(self, "_discount_amount", 0.0)
        subtotal = sum(i["subtotal"] for i in self._cart)
        final = max(0.0, subtotal - discount)
        self._cart_total = final
        self._cart_total_var.set(fmt_currency(final))

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def _checkout(self) -> None:
        if not self._assert_session_active():
            return
        if not self._cart:
            messagebox.showinfo(
                "Empty Cart", "Add items to the cart first.", parent=self.root
            )
            return

        payment = self._payment_var.get()
        paid_str = self._cash_paid_var.get().strip()
        paid = 0.0
        if payment == "Cash":
            try:
                paid = float(paid_str)
            except ValueError:
                messagebox.showwarning(
                    "Invalid Amount",
                    "Please enter a valid cash amount.",
                    parent=self.root,
                )
                return
            if paid < self._cart_total:
                messagebox.showwarning(
                    "Insufficient Cash",
                    f"Cash paid ({fmt_currency(paid)}) is less than"
                    f" total ({fmt_currency(self._cart_total)}).",
                    parent=self.root,
                )
                return

        discount_amount = getattr(self, "_discount_amount", 0.0)

        if not messagebox.askyesno(
            "Confirm Checkout",
            f"Total: {fmt_currency(self._cart_total)}\nPayment: {payment}\nProceed?",
            parent=self.root,
        ):
            return

        order_id = self.app.order_service.place_order(
            cashier_id=self.user["id"],
            cashier_name=self.user["username"],
            payment_method=payment,
            items=self._cart,
            discount_amount=discount_amount,
        )

        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=self.user["username"],
            payment_method=payment,
            items=self._cart,
            total=self._cart_total,
            paid=paid,
            discount_amount=discount_amount,
        )
        receipt_text = builder.build()
        receipt_path = builder.save()

        # Show preview and offer to print
        if self._show_receipt_preview(receipt_text):
            printed = print_file(receipt_path)
            print_note = (
                "" if printed else "\n(Print job could not be sent — receipt saved.)"
            )
        else:
            print_note = "\n(Printing skipped.)"

        self.db.add_audit_log(
            self.user["id"],
            self.user["username"],
            "checkout",
            f"Order #{order_id} total={fmt_currency(self._cart_total)} payment={payment}",
        )

        messagebox.showinfo(
            "Order Complete",
            f"Order #{order_id} saved!\nReceipt: {receipt_path}{print_note}",
            parent=self.root,
        )

        self._cart.clear()
        self._discount_amount = 0.0
        self._discount_label.configure(text="")
        self._coupon_var.set("")
        self._cash_paid_var.set("0")
        self._render_cart()
        self.app.product_service.invalidate_cache()
        self.refresh()

        # Refresh related tabs
        self.app.refresh_tab("orders")
        self.app.refresh_tab("dashboard")

    # ------------------------------------------------------------------
    # Receipt preview
    # ------------------------------------------------------------------

    def _show_receipt_preview(self, receipt_text: str) -> bool:
        """Show a receipt preview popup. Returns True if user wants to print."""
        result: Dict[str, bool] = {"print": False}

        dlg = tk.Toplevel(self.root)
        dlg.title("Receipt Preview")
        dlg.configure(bg=THEME["bg"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        txt = tk.Text(
            dlg,
            font=FONT["mono"],
            bg=THEME["surface"],
            fg=THEME["fg"],
            relief="flat",
            bd=8,
            width=46,
            height=28,
        )
        txt.pack(padx=12, pady=(12, 6))
        txt.insert("1.0", receipt_text)
        txt.configure(state="disabled")

        btn_row = tk.Frame(dlg, bg=THEME["bg"])
        btn_row.pack(pady=(0, 12))

        def _print_and_close() -> None:
            result["print"] = True
            dlg.destroy()

        tk.Button(
            btn_row,
            text="Print",
            font=FONT["bold"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=_print_and_close,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_row,
            text="Close",
            font=FONT["bold"],
            bg=THEME["surface2"],
            fg=THEME["fg"],
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=dlg.destroy,
        ).pack(side="left", padx=6)

        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        dlg.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        dlg.wait_window()
        return result["print"]
