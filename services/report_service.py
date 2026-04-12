"""Reporting helpers — aggregated queries for dashboard and exports."""

from __future__ import annotations

from typing import Any, Dict, List

from db import Database


class ReportService:
    """Advanced reports not covered by basic :class:`~db.Database` stats."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def daily_revenue(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return revenue and order count per day for the last *days* days.

        Results are ordered newest-first.
        """
        rows = self.db.conn.execute(
            "SELECT substr(created_at,1,10) AS day,"
            "       COUNT(*) AS orders,"
            "       COALESCE(SUM(total),0) AS revenue"
            " FROM orders"
            " GROUP BY day"
            " ORDER BY day DESC"
            " LIMIT ?",
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]

    def revenue_by_payment(self) -> List[Dict[str, Any]]:
        """Return revenue and order count grouped by payment method."""
        rows = self.db.conn.execute(
            "SELECT payment_method,"
            "       COUNT(*) AS orders,"
            "       COALESCE(SUM(total),0) AS revenue"
            " FROM orders"
            " GROUP BY payment_method",
        ).fetchall()
        return [dict(r) for r in rows]

    def sales_by_category(self) -> List[Dict[str, Any]]:
        """Return quantity sold and revenue grouped by product category."""
        rows = self.db.conn.execute(
            "SELECT p.category,"
            "       SUM(oi.quantity) AS qty,"
            "       SUM(oi.subtotal) AS revenue"
            " FROM order_items oi"
            " LEFT JOIN products p ON oi.product_id = p.id"
            " GROUP BY p.category"
            " ORDER BY revenue DESC",
        ).fetchall()
        return [dict(r) for r in rows]
