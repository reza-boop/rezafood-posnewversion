"""Receipt generation for RezaFood POS orders."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from config import APP_NAME, APP_VERSION, RECEIPTS_DIR
from utils import fmt_currency, now_str

_LINE_WIDTH = 42


class ReceiptBuilder:
    """Builds and saves plain-text receipts for a completed order."""

    def __init__(
        self,
        order_id: int,
        cashier: str,
        payment_method: str,
        items: List[Dict[str, Any]],
        total: float,
        paid: float = 0.0,
    ) -> None:
        self.order_id = order_id
        self.cashier = cashier
        self.payment_method = payment_method
        self.items = items
        self.total = total
        self.paid = paid
        self.change = max(0.0, paid - total)
        self.timestamp = now_str()

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self) -> str:
        """Return the receipt as a multi-line string."""
        W = _LINE_WIDTH
        sep = "-" * W
        eq = "=" * W

        lines: List[str] = [
            eq,
            f"{APP_NAME} v{APP_VERSION}".center(W),
            eq,
            f"Order # : {self.order_id}",
            f"Date    : {self.timestamp}",
            f"Cashier : {self.cashier}",
            sep,
            f"{'Item':<20} {'Qty':>4} {'Price':>8} {'Sub':>8}",
            sep,
        ]

        for item in self.items:
            name = str(item.get("product_name", ""))[:19]
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0))
            sub = float(item.get("subtotal", 0))
            lines.append(
                f"{name:<20} {qty:>4} {fmt_currency(price):>8} {fmt_currency(sub):>8}"
            )

        lines += [
            sep,
            f"{'TOTAL':>{W - 9}} {fmt_currency(self.total):>8}",
        ]

        if self.paid > 0:
            lines += [
                f"{'PAID':>{W - 9}} {fmt_currency(self.paid):>8}",
                f"{'CHANGE':>{W - 9}} {fmt_currency(self.change):>8}",
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
