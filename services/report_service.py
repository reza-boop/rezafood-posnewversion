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
        return self.db.report.daily_revenue(days, date_from, date_to)

    def revenue_by_payment(self) -> List[Dict[str, Any]]:
        """Return revenue and order count grouped by payment method."""
        return self.db.report.revenue_by_payment()

    def sales_by_category(self) -> List[Dict[str, Any]]:
        """Return quantity sold and revenue grouped by product category."""
        return self.db.report.sales_by_category()

    def top_cashiers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the top cashiers ranked by total revenue generated."""
        return self.db.report.top_cashiers(limit)

    def hourly_distribution(self) -> List[Dict[str, Any]]:
        """Return order count per hour of the day (0–23) for all time."""
        return self.db.report.hourly_distribution()
