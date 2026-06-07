"""Business logic for order creation and discount application."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from config import ORDER_TYPES, PAYMENT_METHODS
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
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_items(self, items: List[Dict[str, Any]]) -> None:
        """Raise :exc:`ValueError` if any item has invalid quantity or price."""
        for item in items:
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0))
            if qty <= 0:
                name = item.get("product_name", "?")
                raise ValueError(
                    f"Item '{name}' has invalid quantity {qty}. Must be ≥ 1."
                )
            if price < 0:
                name = item.get("product_name", "?")
                raise ValueError(
                    f"Item '{name}' has negative unit price {price}."
                )

    def _validate_stock(self, items: List[Dict[str, Any]]) -> None:
        """Raise :exc:`ValueError` if any product has insufficient stock."""
        for item in items:
            pid = item.get("product_id")
            if pid is None:
                continue
            product = self.db.get_product_by_id(int(pid))
            if product is None:
                raise ValueError(
                    f"Product ID {pid} not found."
                )
            qty = int(item.get("quantity", 0))
            if product["stock"] < qty:
                raise ValueError(
                    f"Insufficient stock for '{product['name']}': "
                    f"requested {qty}, available {product['stock']}."
                )

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
        order_type: str = "Take Away",
    ) -> int:
        """Validate business rules and persist the order.

        Returns the new order ID.
        Raises :exc:`ValueError` for invalid input.
        """
        if not items:
            raise ValueError("Cannot create an empty order.")

        if payment_method not in PAYMENT_METHODS:
            raise ValueError(
                f"Invalid payment method '{payment_method}'. "
                f"Must be one of: {', '.join(PAYMENT_METHODS)}."
            )

        if order_type not in ORDER_TYPES:
            raise ValueError(
                f"Invalid order type '{order_type}'. "
                f"Must be one of: {', '.join(ORDER_TYPES)}."
            )

        self._validate_items(items)
        self._validate_stock(items)

        subtotal = sum(float(i["subtotal"]) for i in items)
        total = max(0.0, round(subtotal - discount_amount, 2))

        return self.db.create_order(
            cashier_id,
            cashier_name,
            total,
            payment_method,
            items,
            discount_amount,
            order_type,
        )
