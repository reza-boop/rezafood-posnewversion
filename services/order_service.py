"""Business logic for order creation and discount application."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from db import Database


class OrderService:
    """Orchestrates order placement with discount resolution."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def resolve_discount(self, code: str, subtotal: float) -> Tuple[float, float]:
        """Return ``(discount_amount, final_total)`` for the given coupon.

        If *code* is empty or not found the order proceeds at full price.
        """
        if not code or not code.strip():
            return 0.0, subtotal

        discount = self.db.get_discount_by_code(code)
        if not discount:
            return 0.0, subtotal

        if discount["type"] == "percent":
            amount = subtotal * discount["value"] / 100.0
        else:
            amount = float(discount["value"])

        amount = min(round(amount, 2), subtotal)
        return amount, round(subtotal - amount, 2)

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_order(
        self,
        cashier_id: int,
        cashier_name: str,
        payment_method: str,
        items: List[Dict[str, Any]],
        discount_amount: float = 0.0,
    ) -> int:
        """Validate business rules and persist the order.

        Returns the new order ID.
        Raises :exc:`ValueError` for invalid input.
        """
        if not items:
            raise ValueError("Cannot create an empty order.")

        subtotal = sum(float(i["subtotal"]) for i in items)
        total = max(0.0, round(subtotal - discount_amount, 2))

        return self.db.create_order(
            cashier_id,
            cashier_name,
            total,
            payment_method,
            items,
            discount_amount,
        )
