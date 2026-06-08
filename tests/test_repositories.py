"""Unit tests for the individual repository classes."""

from __future__ import annotations

import sqlite3

import pytest

from db import Database, DuplicateError
from repositories.audit import AuditRepository
from repositories.discount import DiscountRepository
from repositories.order import OrderRepository
from repositories.product import ProductRepository
from repositories.report import ReportRepository
from repositories.user import UserRepository


# ---------------------------------------------------------------------------
# Shared fixture: in-memory Database (creates schema + repositories)
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    database = Database(db_name=":memory:")
    yield database
    database.close()


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------

class TestUserRepository:
    def test_get_by_username_returns_admin(self, db):
        row = db.users.get_by_username("admin")
        assert row is not None
        assert row["role"] == "admin"

    def test_add_and_get(self, db):
        db.users.add("alice", "pw123456", "cashier")
        row = db.users.get_by_username("alice")
        assert row is not None
        assert row["role"] == "cashier"

    def test_get_all_includes_added(self, db):
        db.users.add("bob", "pw123456", "admin")
        usernames = [u["username"] for u in db.users.get_all()]
        assert "bob" in usernames

    def test_update(self, db):
        db.users.add("charlie", "oldpass1", "cashier")
        uid = db.users.get_by_username("charlie")["id"]
        db.users.update(uid, "charlie2", "newpass1", "admin")
        updated = db.users.get_by_username("charlie2")
        assert updated is not None
        assert updated["role"] == "admin"

    def test_update_without_password(self, db):
        db.users.add("diana", "pw123456", "cashier")
        uid = db.users.get_by_username("diana")["id"]
        db.users.update(uid, "diana", None, "admin")
        assert db.users.get_by_username("diana")["role"] == "admin"

    def test_delete(self, db):
        db.users.add("eve", "pw123456", "cashier")
        uid = db.users.get_by_username("eve")["id"]
        db.users.delete(uid)
        assert db.users.get_by_username("eve") is None

    def test_duplicate_raises(self, db):
        db.users.add("frank", "pw123456", "cashier")
        with pytest.raises(DuplicateError):
            db.users.add("frank", "other123", "cashier")

    def test_count(self, db):
        before = db.users.count()
        db.users.add("grace", "pw123456", "cashier")
        assert db.users.count() == before + 1


# ---------------------------------------------------------------------------
# ProductRepository
# ---------------------------------------------------------------------------

class TestProductRepository:
    def test_add_and_get_all(self, db):
        db.products.add("Burger", "Food", 9.99, 50)
        names = [p["name"] for p in db.products.get_all()]
        assert "Burger" in names

    def test_get_by_id(self, db):
        db.products.add("Fries", "Food", 3.50, 100)
        pid = next(p["id"] for p in db.products.get_all() if p["name"] == "Fries")
        row = db.products.get_by_id(pid)
        assert row is not None
        assert row["price"] == 3.50

    def test_update(self, db):
        db.products.add("Cola", "Beverage", 2.00, 30)
        pid = db.products.get_all()[0]["id"]
        db.products.update(pid, "Cola Zero", "Beverage", 2.50, 25)
        row = db.products.get_by_id(pid)
        assert row["name"] == "Cola Zero"
        assert row["price"] == 2.50

    def test_delete(self, db):
        db.products.add("Chips", "Snack", 1.50, 20)
        pid = next(p["id"] for p in db.products.get_all() if p["name"] == "Chips")
        db.products.delete(pid)
        assert db.products.get_by_id(pid) is None

    def test_delete_blocked_when_in_orders(self, db):
        """Deleting a product that appears in order_items must raise ValidationError."""
        from db import ValidationError
        db.products.add("InOrder", "Food", 5.00, 10)
        pid = next(p["id"] for p in db.products.get_all() if p["name"] == "InOrder")
        db.orders.create(
            1, "admin", 5.0, "Cash",
            [{"product_id": pid, "product_name": "InOrder",
              "quantity": 1, "unit_price": 5.0, "subtotal": 5.0}],
        )
        with pytest.raises(ValidationError):
            db.products.delete(pid)

    def test_duplicate_raises(self, db):
        db.products.add("Pizza", "Food", 10.0, 5)
        with pytest.raises(DuplicateError):
            db.products.add("Pizza", "Food", 12.0, 3)

    def test_get_low_stock(self, db):
        db.products.add("LowItem", "Other", 1.00, 2)
        low = [p["name"] for p in db.products.get_low_stock(threshold=5)]
        assert "LowItem" in low

    def test_count(self, db):
        before = db.products.count()
        db.products.add("Widget", "Other", 1.00, 10)
        assert db.products.count() == before + 1

    def test_get_top(self, db):
        db.products.add("TopItem", "Food", 5.00, 50)
        pid = next(p["id"] for p in db.products.get_all() if p["name"] == "TopItem")
        db.orders.create(1, "admin", 5.0, "Cash", [
            {"product_id": pid, "product_name": "TopItem",
             "quantity": 3, "unit_price": 5.0, "subtotal": 15.0}
        ])
        top = db.products.get_top(limit=5)
        names = [r["product_name"] for r in top]
        assert "TopItem" in names


# ---------------------------------------------------------------------------
# OrderRepository
# ---------------------------------------------------------------------------

class TestOrderRepository:
    def _add_product(self, db, name="Pizza", stock=10) -> int:
        db.products.add(name, "Food", 12.00, stock)
        return next(p["id"] for p in db.products.get_all() if p["name"] == name)

    def test_create_returns_id(self, db):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Pizza",
                  "quantity": 2, "unit_price": 12.00, "subtotal": 24.00}]
        oid = db.orders.create(1, "admin", 24.00, "Cash", items)
        assert oid is not None and oid >= 1

    def test_stock_decremented(self, db):
        pid = self._add_product(db, "Soda", stock=5)
        items = [{"product_id": pid, "product_name": "Soda",
                  "quantity": 3, "unit_price": 2.00, "subtotal": 6.00}]
        db.orders.create(1, "admin", 6.00, "Cash", items)
        assert db.products.get_by_id(pid)["stock"] == 2

    def test_order_items_stored(self, db):
        pid = self._add_product(db, "Tea", stock=10)
        items = [{"product_id": pid, "product_name": "Tea",
                  "quantity": 1, "unit_price": 3.00, "subtotal": 3.00}]
        oid = db.orders.create(1, "admin", 3.00, "Card", items)
        stored = db.orders.get_items(oid)
        assert len(stored) == 1
        assert stored[0]["product_name"] == "Tea"

    def test_discount_stored(self, db):
        pid = self._add_product(db, "Juice", stock=10)
        items = [{"product_id": pid, "product_name": "Juice",
                  "quantity": 1, "unit_price": 5.00, "subtotal": 5.00}]
        oid = db.orders.create(1, "admin", 4.50, "Cash", items, discount_amount=0.50)
        order = db.orders.get_by_id(oid)
        assert order["discount_amount"] == 0.50
        assert order["total"] == 4.50

    def test_get_all(self, db):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Pizza",
                  "quantity": 1, "unit_price": 12.00, "subtotal": 12.00}]
        db.orders.create(1, "admin", 12.00, "Cash", items)
        assert len(db.orders.get_all()) >= 1

    def test_get_filtered_by_cashier(self, db):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Pizza",
                  "quantity": 1, "unit_price": 12.00, "subtotal": 12.00}]
        db.orders.create(1, "admin", 12.00, "Cash", items)
        orders = db.orders.get_filtered(cashier="admin")
        assert len(orders) >= 1

    def test_get_today_stats(self, db):
        stats = db.orders.get_today_stats("2099-01-01")
        assert stats["orders"] == 0
        assert stats["revenue"] == 0

    def test_get_all_time_revenue_empty(self, db):
        assert db.orders.get_all_time_revenue() == 0.0

    def test_get_all_time_revenue_after_order(self, db):
        pid = self._add_product(db, "Wrap", stock=5)
        items = [{"product_id": pid, "product_name": "Wrap",
                  "quantity": 1, "unit_price": 8.00, "subtotal": 8.00}]
        db.orders.create(1, "admin", 8.00, "Cash", items)
        assert db.orders.get_all_time_revenue() == 8.00

    def test_stock_race_condition_raises_on_zero_stock(self, db):
        """Ordering more than available stock must raise ValueError (race guard)."""
        pid = self._add_product(db, "RaceItem", stock=0)
        items = [{"product_id": pid, "product_name": "RaceItem",
                  "quantity": 1, "unit_price": 5.00, "subtotal": 5.00}]
        with pytest.raises(ValueError, match="Insufficient stock"):
            db.orders.create(1, "admin", 5.00, "Cash", items)
        # Stock must remain 0 (transaction rolled back)
        assert db.products.get_by_id(pid)["stock"] == 0

    def test_stock_race_condition_exact_stock_succeeds(self, db):
        """Ordering exactly the available stock should succeed."""
        pid = self._add_product(db, "ExactItem", stock=3)
        items = [{"product_id": pid, "product_name": "ExactItem",
                  "quantity": 3, "unit_price": 5.00, "subtotal": 15.00}]
        db.orders.create(1, "admin", 15.00, "Cash", items)
        assert db.products.get_by_id(pid)["stock"] == 0


# ---------------------------------------------------------------------------
# DiscountRepository
# ---------------------------------------------------------------------------

class TestDiscountRepository:
    def test_add_and_get_by_code(self, db):
        db.discounts.add("SAVE10", "percent", 10)
        row = db.discounts.get_by_code("SAVE10")
        assert row is not None
        assert row["value"] == 10

    def test_code_normalised_uppercase(self, db):
        db.discounts.add("hello", "fixed", 5)
        row = db.discounts.get_by_code("hello")
        assert row is not None

    def test_inactive_not_returned(self, db):
        db.discounts.add("DEAD", "percent", 50, active=False)
        assert db.discounts.get_by_code("DEAD") is None

    def test_get_all(self, db):
        db.discounts.add("ALL10", "percent", 10)
        rows = db.discounts.get_all()
        assert any(r["code"] == "ALL10" for r in rows)

    def test_update(self, db):
        db.discounts.add("UPD", "percent", 10)
        row = db.discounts.get_by_code("UPD")
        db.discounts.update(row["id"], "UPD", "fixed", 20, True)
        updated = db.discounts.get_by_code("UPD")
        assert updated["value"] == 20
        assert updated["type"] == "fixed"

    def test_delete(self, db):
        db.discounts.add("GONE", "fixed", 3)
        row = db.discounts.get_by_code("GONE")
        db.discounts.delete(row["id"])
        assert db.discounts.get_by_code("GONE") is None

    def test_duplicate_raises(self, db):
        db.discounts.add("UNIQ", "percent", 5)
        with pytest.raises(DuplicateError):
            db.discounts.add("UNIQ", "fixed", 3)


# ---------------------------------------------------------------------------
# AuditRepository
# ---------------------------------------------------------------------------

class TestAuditRepository:
    def test_add_and_get_recent(self, db):
        db.audit.add(1, "admin", "login", "ok")
        logs = db.audit.get_recent()
        assert any(lg["action"] == "login" for lg in logs)

    def test_limit_respected(self, db):
        for i in range(10):
            db.audit.add(None, "system", f"action_{i}")
        logs = db.audit.get_recent(limit=3)
        assert len(logs) <= 3


# ---------------------------------------------------------------------------
# ReportRepository
# ---------------------------------------------------------------------------

class TestReportRepository:
    def _create_order(self, db):
        db.products.add("Rep", "Food", 10.0, 50)
        pid = db.products.get_all()[0]["id"]
        items = [{"product_id": pid, "product_name": "Rep",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        db.orders.create(1, "admin", 10.0, "Cash", items)

    def test_daily_revenue_structure(self, db):
        self._create_order(db)
        rows = db.report.daily_revenue(days=7)
        assert isinstance(rows, list)
        if rows:
            assert "day" in rows[0] and "revenue" in rows[0]

    def test_daily_revenue_date_range(self, db):
        self._create_order(db)
        rows = db.report.daily_revenue(date_from="2000-01-01", date_to="2099-12-31")
        assert len(rows) >= 1

    def test_daily_revenue_empty_range(self, db):
        self._create_order(db)
        rows = db.report.daily_revenue(date_from="2099-01-01", date_to="2099-01-02")
        assert rows == []

    def test_revenue_by_payment(self, db):
        self._create_order(db)
        rows = db.report.revenue_by_payment()
        assert isinstance(rows, list)
        if rows:
            assert "payment_method" in rows[0]

    def test_sales_by_category(self, db):
        self._create_order(db)
        rows = db.report.sales_by_category()
        assert isinstance(rows, list)

    def test_top_cashiers(self, db):
        self._create_order(db)
        rows = db.report.top_cashiers(limit=5)
        assert isinstance(rows, list)
        if rows:
            assert "cashier_name" in rows[0]
            assert "revenue" in rows[0]

    def test_hourly_distribution(self, db):
        self._create_order(db)
        rows = db.report.hourly_distribution()
        assert isinstance(rows, list)
        if rows:
            assert "hour" in rows[0]
            assert "orders" in rows[0]
