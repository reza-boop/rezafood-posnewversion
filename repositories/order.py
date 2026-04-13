"""Order and order-item persistence operations."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from utils import now_str
from repositories.base import BaseRepository


class OrderRepository(BaseRepository):
    """Manages all persistence operations for *orders* and *order_items*."""

    def create(
        self,
        cashier_id: int,
        cashier_name: str,
        total: float,
        payment_method: str,
        items: List[Dict[str, Any]],
        discount_amount: float = 0.0,
    ) -> int:
        """Persist a new order with its items and decrement stock atomically.

        The entire operation is wrapped in a single SQLite transaction so that
        a crash mid-way cannot leave the database in a partially-updated state.

        Returns the new order ID.
        """
        ts = now_str()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO orders"
                " (cashier_id, cashier_name, total, discount_amount, payment_method, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (cashier_id, cashier_name, total, discount_amount, payment_method, ts),
            )
            order_id = cur.lastrowid
            for item in items:
                self.conn.execute(
                    "INSERT INTO order_items"
                    " (order_id, product_id, product_name, quantity, unit_price, subtotal)"
                    " VALUES (?,?,?,?,?,?)",
                    (
                        order_id,
                        item["product_id"],
                        item["product_name"],
                        item["quantity"],
                        item["unit_price"],
                        item["subtotal"],
                    ),
                )
                self.conn.execute(
                    "UPDATE products SET stock = stock - ?, updated_at=? WHERE id=?",
                    (item["quantity"], ts, item["product_id"]),
                )
        return order_id  # type: ignore[return-value]

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM orders ORDER BY id DESC"
        ).fetchall()

    def get_filtered(
        self,
        date_from: str = "",
        date_to: str = "",
        cashier: str = "",
        payment: str = "",
    ) -> List[sqlite3.Row]:
        """Return orders matching the given filters (all optional)."""
        clauses: List[str] = []
        params: List[Any] = []
        if date_from:
            clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("created_at <= ?")
            params.append(date_to + " 23:59:59")
        if cashier:
            clauses.append("cashier_name LIKE ?")
            params.append(f"%{cashier}%")
        if payment:
            clauses.append("payment_method = ?")
            params.append(payment)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return self.conn.execute(
            f"SELECT * FROM orders {where} ORDER BY id DESC", params
        ).fetchall()

    def get_by_id(self, order_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()

    def get_items(self, order_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (order_id,)
        ).fetchall()

    def get_today_stats(self, date: str) -> Dict[str, Any]:
        """Return order count and total revenue for *date* ('YYYY-MM-DD')."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(total), 0) AS revenue"
            " FROM orders WHERE created_at LIKE ?",
            (f"{date}%",),
        ).fetchone()
        return {"orders": row["cnt"], "revenue": row["revenue"]}

    def get_all_time_revenue(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS revenue FROM orders"
        ).fetchone()
        return row["revenue"]
