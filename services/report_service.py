"""Reporting helpers — aggregated queries for dashboard and exports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import Database


class ReportService:
    """Advanced reports not covered by basic :class:`~db.Database` stats."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def daily_revenue(
        self,
        days: int = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return revenue and order count per day.

        When *date_from* / *date_to* (``'YYYY-MM-DD'``) are supplied the
        *days* parameter is ignored and the exact date range is used instead.
        Results are ordered newest-first.
        """
        if date_from or date_to:
            clauses: List[str] = []
            params: List[Any] = []
            if date_from:
                clauses.append("substr(created_at,1,10) >= ?")
                params.append(date_from)
            if date_to:
                clauses.append("substr(created_at,1,10) <= ?")
                params.append(date_to)
            where = "WHERE " + " AND ".join(clauses) if clauses else ""
            rows = self.db.conn.execute(
                f"SELECT substr(created_at,1,10) AS day,"
                f"       COUNT(*) AS orders,"
                f"       COALESCE(SUM(total),0) AS revenue"
                f" FROM orders {where}"
                f" GROUP BY day ORDER BY day DESC",
                params,
            ).fetchall()
        else:
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

    def top_cashiers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the top cashiers ranked by total revenue generated."""
        rows = self.db.conn.execute(
            "SELECT cashier_name,"
            "       COUNT(*) AS orders,"
            "       COALESCE(SUM(total),0) AS revenue"
            " FROM orders"
            " GROUP BY cashier_name"
            " ORDER BY revenue DESC"
            " LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def hourly_distribution(self) -> List[Dict[str, Any]]:
        """Return order count per hour of the day (0–23) for all time."""
        rows = self.db.conn.execute(
            "SELECT CAST(substr(created_at,12,2) AS INTEGER) AS hour,"
            "       COUNT(*) AS orders"
            " FROM orders"
            " GROUP BY hour"
            " ORDER BY hour",
        ).fetchall()
        return [dict(r) for r in rows]
