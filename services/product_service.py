"""Business-logic helpers for product management."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from config import CATEGORIES, LOW_STOCK_THRESHOLD
from db import Database

# Products cache entry: (timestamp, data)
_CacheEntry = Tuple[float, List[Any]]
_CACHE_TTL_SECONDS = 30  # invalidate cached product list after 30 s


class ProductService:
    """Validation and stock queries for the product domain."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: Optional[_CacheEntry] = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_valid(self) -> bool:
        if self._cache is None:
            return False
        age = time.monotonic() - self._cache[0]
        return age < _CACHE_TTL_SECONDS

    def invalidate_cache(self) -> None:
        """Force the next :meth:`get_all_products` call to hit the database."""
        self._cache = None

    def get_all_products(self) -> List[Any]:
        """Return all products, using an in-process TTL cache.

        The cache is automatically invalidated after
        :data:`_CACHE_TTL_SECONDS` seconds or when :meth:`invalidate_cache`
        is called explicitly (e.g. after add / update / delete).
        """
        if not self._cache_valid():
            self._cache = (time.monotonic(), self.db.get_all_products())
        return self._cache[1]  # type: ignore[index]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self, name: str, category: str, price: float, stock: int
    ) -> str:
        """Return a human-readable error message, or ``''`` if valid."""
        if not name.strip():
            return "Product name is required."
        if len(name.strip()) > 100:
            return "Product name must be 100 characters or fewer."
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

    def search(self, query: str) -> List[Any]:
        """Return products whose name or category contains *query* (case-insensitive)."""
        q = query.strip().lower()
        if not q:
            return self.get_all_products()
        return [
            p for p in self.get_all_products()
            if q in p["name"].lower() or q in p["category"].lower()
        ]
