"""Receipt generation for RezaFood POS orders."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal

from config import APP_NAME, APP_VERSION, RECEIPTS_DIR
from utils import fmt_currency, now_str

# Supported receipt widths (characters)
_WIDTHS: Dict[str, int] = {
    "thermal": 42,   # 80 mm thermal printer
    "wide": 58,      # wider 80-column format
    "a4": 72,        # A4 paper (monospace)
}

ReceiptFormat = Literal["thermal", "wide", "a4"]


class ReceiptBuilder:
    """Builds and saves plain-text receipts for a completed order.

    Args:
        format: One of ``"thermal"`` (default, 42 chars), ``"wide"`` (58 chars),
                or ``"a4"`` (72 chars).
    """

    def __init__(
        self,
        order_id: int,
        cashier: str,
        payment_method: str,
        items: List[Dict[str, Any]],
        total: float,
        paid: float = 0.0,
        discount_amount: float = 0.0,
        format: ReceiptFormat = "thermal",
    ) -> None:
        self.order_id = order_id
        self.cashier = cashier
        self.payment_method = payment_method
        self.items = items
        self.total = total
        self.paid = paid
        self.discount_amount = discount_amount
        self.change = max(0.0, paid - total)
        self.timestamp = now_str()
        self.width = _WIDTHS.get(format, _WIDTHS["thermal"])

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self) -> str:
        """Return the receipt as a multi-line string."""
        W = self.width
        sep = "-" * W
        eq = "=" * W

        # Name column width scales with total width; always leave room for
        # Qty (4), Price (9), Sub (9) + 3 spaces = 25 chars minimum for W=42
        name_col = max(16, W - 25)
        header_row = (
            f"{'Item':<{name_col}} {'Qty':>4} {'Price':>9} {'Sub':>9}"
        )

        lines: List[str] = [
            eq,
            f"{APP_NAME} v{APP_VERSION}".center(W),
            eq,
            f"Order # : {self.order_id}",
            f"Date    : {self.timestamp}",
            f"Cashier : {self.cashier}",
            sep,
            header_row,
            sep,
        ]

        for item in self.items:
            name = str(item.get("product_name", ""))[:name_col]
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0))
            sub = float(item.get("subtotal", 0))
            lines.append(
                f"{name:<{name_col}} {qty:>4} {fmt_currency(price):>9}"
                f" {fmt_currency(sub):>9}"
            )

        lines += [
            sep,
            f"{'SUBTOTAL':>{W - 10}} {fmt_currency(self.total + self.discount_amount):>9}",
        ]

        if self.discount_amount > 0:
            lines.append(
                f"{'DISCOUNT':>{W - 10}} -{fmt_currency(self.discount_amount):>8}"
            )

        lines += [
            f"{'TOTAL':>{W - 10}} {fmt_currency(self.total):>9}",
        ]

        if self.paid > 0:
            lines += [
                f"{'PAID':>{W - 10}} {fmt_currency(self.paid):>9}",
                f"{'CHANGE':>{W - 10}} {fmt_currency(self.change):>9}",
            ]

        lines += [
            sep,
            f"Payment : {self.payment_method}",
            sep,
            "Thank you for your visit!".center(W),
            eq,
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(self) -> str:
        """Write the receipt to *receipts/receipt_XXXXXX.txt*.

        Returns the absolute file path.
        """
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        filename = f"receipt_{self.order_id:06d}.txt"
        filepath = os.path.join(RECEIPTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.build())
        return os.path.abspath(filepath)
