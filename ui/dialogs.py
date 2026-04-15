"""CRUD dialogs for RezaFood POS — products, users, and discounts."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from config import CATEGORIES, FONT, MIN_PASSWORD_LENGTH, ROLES, THEME


# ---------------------------------------------------------------------------
# Password validation helper
# ---------------------------------------------------------------------------

def validate_password_strength(password: str) -> str:
    """Return an error string, or ``''`` if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return ""


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class _BaseDialog(tk.Toplevel):
    """Shared base for modal CRUD dialogs."""

    def __init__(self, parent: tk.Widget, title: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=THEME["bg"])
        self.result: Optional[dict] = None
        self.grab_set()
        self.transient(parent)
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
        except Exception:
            px, py = 200, 200
        self.geometry(f"+{px + 60}+{py + 60}")

    # Styling helpers
    def _label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent, text=text, font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        )

    def _entry(self, parent: tk.Widget, textvariable: tk.Variable) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=textvariable,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
            width=28,
        )

    def _option_menu(
        self, parent: tk.Widget, variable: tk.StringVar, choices: list
    ) -> tk.OptionMenu:
        menu = tk.OptionMenu(parent, variable, *choices)
        menu.configure(
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            activebackground=THEME["surface2"],
            activeforeground=THEME["fg"],
            relief="flat",
            highlightthickness=0,
        )
        menu["menu"].configure(
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            font=FONT["default"],
            activebackground=THEME["select_bg"],
        )
        return menu

    def _button(
        self, parent: tk.Widget, text: str, command, danger: bool = False
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
            padx=18,
            pady=7,
            cursor="hand2",
            command=command,
        )


# ---------------------------------------------------------------------------
# Product dialog
# ---------------------------------------------------------------------------

class ProductDialog(_BaseDialog):
    """Add or edit a product."""

    def __init__(
        self, parent: tk.Widget, product: Optional[dict] = None
    ) -> None:
        title = "Edit Product" if product else "Add Product"
        super().__init__(parent, title)
        self._product = product
        self._build()
        if product:
            self._populate(product)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._name_var  = tk.StringVar()
        self._cat_var   = tk.StringVar(value=CATEGORIES[0])
        self._price_var = tk.StringVar()
        self._stock_var = tk.StringVar()

        rows = [
            ("Name:",     self._name_var,  "entry"),
            ("Category:", self._cat_var,   "combo"),
            ("Price:",    self._price_var, "entry"),
            ("Stock:",    self._stock_var, "entry"),
        ]

        for i, (lbl, var, kind) in enumerate(rows):
            self._label(card, lbl).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            if kind == "entry":
                self._entry(card, var).grid(row=i, column=1, sticky="ew", pady=5)
            else:
                self._option_menu(card, var, CATEGORIES).grid(
                    row=i, column=1, sticky="ew", pady=5
                )

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, product: dict) -> None:
        self._name_var.set(str(product.get("name", "")))
        self._cat_var.set(str(product.get("category", CATEGORIES[0])))
        self._price_var.set(str(product.get("price", "")))
        self._stock_var.set(str(product.get("stock", "")))

    def _save(self) -> None:
        name      = self._name_var.get().strip()
        cat       = self._cat_var.get().strip()
        price_str = self._price_var.get().strip()
        stock_str = self._stock_var.get().strip()

        if not name:
            messagebox.showwarning("Validation", "Product name is required.", parent=self)
            return

        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Validation", "Price must be a non-negative number.", parent=self
            )
            return

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Validation", "Stock must be a non-negative integer.", parent=self
            )
            return

        self.result = {"name": name, "category": cat, "price": price, "stock": stock}
        self.destroy()


# ---------------------------------------------------------------------------
# User dialog
# ---------------------------------------------------------------------------

class UserDialog(_BaseDialog):
    """Add or edit a user account."""

    def __init__(
        self, parent: tk.Widget, user: Optional[dict] = None
    ) -> None:
        title = "Edit User" if user else "Add User"
        super().__init__(parent, title)
        self._user = user
        self._build()
        if user:
            self._populate(user)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._username_var = tk.StringVar()
        self._password_var = tk.StringVar()
        self._role_var     = tk.StringVar(value=ROLES[1])

        pw_hint = " (blank = keep)" if self._user else ""

        self._label(card, "Username:").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 12))
        self._entry(card, self._username_var).grid(row=0, column=1, sticky="ew", pady=5)

        self._label(card, f"Password:{pw_hint}").grid(
            row=1, column=0, sticky="w", pady=5, padx=(0, 12)
        )
        tk.Entry(
            card,
            textvariable=self._password_var,
            show="*",
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
            width=28,
        ).grid(row=1, column=1, sticky="ew", pady=5)

        self._label(card, "Role:").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 12))
        self._option_menu(card, self._role_var, ROLES).grid(
            row=2, column=1, sticky="ew", pady=5
        )

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=3, column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, user: dict) -> None:
        self._username_var.set(str(user.get("username", "")))
        self._role_var.set(str(user.get("role", ROLES[1])))

    def _save(self) -> None:
        username = self._username_var.get().strip()
        password = self._password_var.get()
        role     = self._role_var.get().strip()

        if not username:
            messagebox.showwarning("Validation", "Username is required.", parent=self)
            return

        if not self._user and not password:
            messagebox.showwarning(
                "Validation", "Password is required for new users.", parent=self
            )
            return

        if password:
            err = validate_password_strength(password)
            if err:
                messagebox.showwarning("Validation", err, parent=self)
                return

        self.result = {"username": username, "password": password, "role": role}
        self.destroy()


# ---------------------------------------------------------------------------
# Discount dialog
# ---------------------------------------------------------------------------

_DISCOUNT_TYPES = ["percent", "fixed"]


class DiscountDialog(_BaseDialog):
    """Add or edit a discount/coupon code."""

    def __init__(
        self, parent: tk.Widget, discount: Optional[dict] = None
    ) -> None:
        title = "Edit Discount" if discount else "Add Discount"
        super().__init__(parent, title)
        self._discount = discount
        self._build()
        if discount:
            self._populate(discount)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._code_var   = tk.StringVar()
        self._type_var   = tk.StringVar(value=_DISCOUNT_TYPES[0])
        self._value_var  = tk.StringVar()
        self._active_var = tk.BooleanVar(value=True)

        rows = [
            ("Code:",  self._code_var,  "entry"),
            ("Type:",  self._type_var,  "combo"),
            ("Value:", self._value_var, "entry"),
        ]

        for i, (lbl, var, kind) in enumerate(rows):
            self._label(card, lbl).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            if kind == "entry":
                self._entry(card, var).grid(row=i, column=1, sticky="ew", pady=5)
            else:
                self._option_menu(card, var, _DISCOUNT_TYPES).grid(
                    row=i, column=1, sticky="ew", pady=5
                )

        tk.Checkbutton(
            card,
            text="Active",
            variable=self._active_var,
            font=FONT["bold"],
            bg=surf,
            fg=THEME["fg"],
            selectcolor=THEME["entry_bg"],
            activebackground=surf,
            activeforeground=THEME["fg"],
        ).grid(row=len(rows), column=1, sticky="w", pady=5)

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=len(rows) + 1, column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, discount: dict) -> None:
        self._code_var.set(str(discount.get("code", "")))
        self._type_var.set(str(discount.get("type", _DISCOUNT_TYPES[0])))
        self._value_var.set(str(discount.get("value", "")))
        self._active_var.set(bool(discount.get("active", True)))

    def _save(self) -> None:
        code  = self._code_var.get().strip().upper()
        dtype = self._type_var.get().strip()
        val_s = self._value_var.get().strip()
        active = self._active_var.get()

        if not code:
            messagebox.showwarning("Validation", "Coupon code is required.", parent=self)
            return

        if dtype == "percent":
            try:
                value = float(val_s)
                if not (0 < value <= 100):
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "Validation", "Percent discount must be between 0 and 100.", parent=self
                )
                return
        else:
            try:
                value = float(val_s)
                if value <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "Validation", "Fixed discount must be a positive number.", parent=self
                )
                return

        self.result = {
            "code": code,
            "type": dtype,
            "value": value,
            "active": active,
        }
        self.destroy()
