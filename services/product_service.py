"""Business-logic helpers for product management."""

from __future__ import annotations

from config import CATEGORIES, LOW_STOCK_THRESHOLD
from db import Database


class ProductService:
    """Validation and stock queries for the product domain."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def validate(
        self, name: str, category: str, price: float, stock: int
    ) -> str:
        """Return a human-readable error message, or ``''`` if valid."""
        if not name.strip():
            return "Product name is required."
        if category not in CATEGORIES:
            return f"Category must be one of: {', '.join(CATEGORIES)}."
        if price < 0:
            return "Price cannot be negative."
        if stock < 0:
            return "Stock cannot be negative."
        return ""

    def low_stock_count(self) -> int:
        """Return the number of products at or below the low-stock threshold."""
        return len(self.db.get_low_stock_products(LOW_STOCK_THRESHOLD))
