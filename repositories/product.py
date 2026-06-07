"""Product CRUD operations."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from utils import now_str
from db import DuplicateError, ValidationError
from repositories.base import BaseRepository


class ProductRepository(BaseRepository):
    """Manages all persistence operations for the *products* table."""

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products ORDER BY category, name"
        ).fetchall()

    def get_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()

    def add(self, name: str, category: str, price: float, stock: int, vat_rate: float = 7.0) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO products"
                " (name, category, price, vat_rate, stock, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (name, category, price, vat_rate, stock, ts, ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Product '{name}' already exists.") from exc

    def update(
        self,
        product_id: int,
        name: str,
        category: str,
        price: float,
        stock: int,
        vat_rate: float = 7.0,
    ) -> None:
        ts = now_str()
        self.conn.execute(
            "UPDATE products"
            " SET name=?, category=?, price=?, vat_rate=?, stock=?, updated_at=?"
            " WHERE id=?",
            (name, category, price, vat_rate, stock, ts, product_id),
        )
        self.conn.commit()

    def delete(self, product_id: int) -> None:
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM order_items WHERE product_id=?",
            (product_id,),
        ).fetchone()
        if row and row["cnt"] > 0:
            cnt = row["cnt"]
            noun = "order item" if cnt == 1 else "order items"
            raise ValidationError(
                f"Cannot delete product: it is referenced by {cnt} {noun}. "
                "Delete would corrupt order history."
            )
        self.conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def get_low_stock(self, threshold: int = 5) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE stock <= ? ORDER BY stock",
            (threshold,),
        ).fetchall()

    def get_top(self, limit: int = 5) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT product_name,"
            "       SUM(quantity) AS total_qty,"
            "       SUM(subtotal) AS total_revenue"
            " FROM order_items"
            " GROUP BY product_name"
            " ORDER BY total_qty DESC"
            " LIMIT ?",
            (limit,),
        ).fetchall()

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM products").fetchone()
        return row["cnt"]
