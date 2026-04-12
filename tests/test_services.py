"""Unit tests for the services layer."""

import pytest

from db import Database
from services.order_service import OrderService
from services.product_service import ProductService
from services.report_service import ReportService


@pytest.fixture
def db():
    database = Database(db_name=":memory:")
    yield database
    database.close()


@pytest.fixture
def order_svc(db):
    return OrderService(db)


@pytest.fixture
def product_svc(db):
    return ProductService(db)


@pytest.fixture
def report_svc(db):
    return ReportService(db)


# ---------------------------------------------------------------------------
# OrderService
# ---------------------------------------------------------------------------

class TestOrderService:
    def _add_product(self, db, name="Widget", price=10.0, stock=20) -> int:
        db.add_product(name, "Other", price, stock)
        return next(p["id"] for p in db.get_all_products() if p["name"] == name)

    def test_place_order_basic(self, db, order_svc):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        oid = order_svc.place_order(1, "admin", "Cash", items)
        assert oid >= 1

    def test_place_order_empty_raises(self, order_svc):
        with pytest.raises(ValueError, match="empty"):
            order_svc.place_order(1, "admin", "Cash", [])

    def test_resolve_discount_percent(self, db, order_svc):
        db.add_discount("PCT20", "percent", 20)
        amount, total = order_svc.resolve_discount("PCT20", 100.0)
        assert amount == 20.0
        assert total == 80.0

    def test_resolve_discount_fixed(self, db, order_svc):
        db.add_discount("FLAT5", "fixed", 5)
        amount, total = order_svc.resolve_discount("FLAT5", 30.0)
        assert amount == 5.0
        assert total == 25.0

    def test_resolve_discount_invalid_code(self, db, order_svc):
        amount, total = order_svc.resolve_discount("BADCODE", 50.0)
        assert amount == 0.0
        assert total == 50.0

    def test_resolve_discount_empty_code(self, order_svc):
        amount, total = order_svc.resolve_discount("", 50.0)
        assert amount == 0.0
        assert total == 50.0

    def test_discount_cannot_exceed_total(self, db, order_svc):
        db.add_discount("BIG", "fixed", 9999)
        amount, total = order_svc.resolve_discount("BIG", 20.0)
        assert amount == 20.0
        assert total == 0.0

    def test_place_order_with_discount(self, db, order_svc):
        pid = self._add_product(db, "Soda", price=5.0, stock=10)
        items = [{"product_id": pid, "product_name": "Soda",
                  "quantity": 2, "unit_price": 5.0, "subtotal": 10.0}]
        oid = order_svc.place_order(1, "admin", "Cash", items, discount_amount=2.0)
        order = db.get_order_by_id(oid)
        assert order["total"] == 8.0
        assert order["discount_amount"] == 2.0


# ---------------------------------------------------------------------------
# ProductService
# ---------------------------------------------------------------------------

class TestProductService:
    def test_valid_product(self, product_svc):
        assert product_svc.validate("Burger", "Food", 9.99, 50) == ""

    def test_empty_name(self, product_svc):
        err = product_svc.validate("", "Food", 9.99, 50)
        assert err != ""

    def test_invalid_category(self, product_svc):
        err = product_svc.validate("Item", "NotACategory", 1.0, 1)
        assert err != ""

    def test_negative_price(self, product_svc):
        err = product_svc.validate("Item", "Food", -1, 1)
        assert err != ""

    def test_negative_stock(self, product_svc):
        err = product_svc.validate("Item", "Food", 1.0, -1)
        assert err != ""

    def test_low_stock_count(self, db, product_svc):
        db.add_product("LowP", "Food", 1.0, 2)
        assert product_svc.low_stock_count() >= 1


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------

class TestReportService:
    def _create_order(self, db):
        db.add_product("Rep", "Food", 10.0, 50)
        pid = db.get_all_products()[0]["id"]
        items = [{"product_id": pid, "product_name": "Rep",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        db.create_order(1, "admin", 10.0, "Cash", items)

    def test_daily_revenue_structure(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.daily_revenue(days=7)
        assert isinstance(rows, list)
        if rows:
            assert "day" in rows[0]
            assert "revenue" in rows[0]

    def test_revenue_by_payment(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.revenue_by_payment()
        assert isinstance(rows, list)
        if rows:
            assert "payment_method" in rows[0]

    def test_sales_by_category(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.sales_by_category()
        assert isinstance(rows, list)
