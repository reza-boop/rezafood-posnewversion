"""Unit tests for the services layer."""

import pytest

from db import Database, DuplicateError
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

    def test_place_order_invalid_payment_raises(self, db, order_svc):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        with pytest.raises(ValueError, match="payment method"):
            order_svc.place_order(1, "admin", "Bitcoin", items)

    def test_place_order_insufficient_stock_raises(self, db, order_svc):
        pid = self._add_product(db, stock=2)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 5, "unit_price": 10.0, "subtotal": 50.0}]
        with pytest.raises(ValueError, match="Insufficient stock"):
            order_svc.place_order(1, "admin", "Cash", items)

    def test_place_order_zero_quantity_raises(self, db, order_svc):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 0, "unit_price": 10.0, "subtotal": 0.0}]
        with pytest.raises(ValueError, match="invalid quantity"):
            order_svc.place_order(1, "admin", "Cash", items)

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

    def test_all_valid_payment_methods_accepted(self, db, order_svc):
        from config import PAYMENT_METHODS
        pid = self._add_product(db, stock=100)
        for method in PAYMENT_METHODS:
            items = [{"product_id": pid, "product_name": "Widget",
                      "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
            oid = order_svc.place_order(1, "admin", method, items)
            assert oid >= 1

    def test_place_order_with_order_type(self, db, order_svc):
        from config import ORDER_TYPES
        pid = self._add_product(db, stock=100)
        for otype in ORDER_TYPES:
            items = [{"product_id": pid, "product_name": "Widget",
                      "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
            oid = order_svc.place_order(1, "admin", "Cash", items, order_type=otype)
            order = db.get_order_by_id(oid)
            assert order["order_type"] == otype

    def test_place_order_invalid_order_type_raises(self, db, order_svc):
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        with pytest.raises(ValueError, match="order type"):
            order_svc.place_order(1, "admin", "Cash", items, order_type="InvalidType")

    def test_place_order_default_order_type(self, db, order_svc):
        """Default order_type should be 'Take Away'."""
        pid = self._add_product(db)
        items = [{"product_id": pid, "product_name": "Widget",
                  "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}]
        oid = order_svc.place_order(1, "admin", "Cash", items)
        order = db.get_order_by_id(oid)
        assert order["order_type"] == "Take Away"


# ---------------------------------------------------------------------------
# ProductService
# ---------------------------------------------------------------------------

class TestProductService:
    def test_valid_product(self, product_svc):
        assert product_svc.validate("Burger", "Food", 9.99, 50) == ""

    def test_empty_name(self, product_svc):
        err = product_svc.validate("", "Food", 9.99, 50)
        assert err != ""

    def test_name_too_long(self, product_svc):
        err = product_svc.validate("x" * 101, "Food", 1.0, 1)
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

    def test_get_all_products_cached(self, db, product_svc):
        db.add_product("P1", "Food", 1.0, 10)
        result1 = product_svc.get_all_products()
        result2 = product_svc.get_all_products()
        assert result1 is result2  # same object from cache

    def test_invalidate_cache(self, db, product_svc):
        db.add_product("P1", "Food", 1.0, 10)
        result1 = product_svc.get_all_products()
        product_svc.invalidate_cache()
        result2 = product_svc.get_all_products()
        # After invalidation, a fresh list is fetched (not the same object)
        assert result1 is not result2

    def test_search_by_name(self, db, product_svc):
        db.add_product("ChocolateCake", "Dessert", 5.0, 10)
        results = product_svc.search("chocolate")
        assert any(p["name"] == "ChocolateCake" for p in results)

    def test_search_by_category(self, db, product_svc):
        db.add_product("Espresso", "Beverage", 3.0, 20)
        results = product_svc.search("beverage")
        assert any(p["name"] == "Espresso" for p in results)

    def test_search_empty_returns_all(self, db, product_svc):
        db.add_product("AnyItem", "Other", 1.0, 5)
        all_products = product_svc.get_all_products()
        search_results = product_svc.search("")
        assert len(search_results) == len(all_products)

    def test_add_product_invalidates_cache(self, db, product_svc):
        """add_product() must invalidate the cache so get_all_products() reflects the new item."""
        result_before = product_svc.get_all_products()
        product_svc.add_product("NewItem", "Other", 1.5, 5)
        result_after = product_svc.get_all_products()
        assert result_before is not result_after
        assert any(p["name"] == "NewItem" for p in result_after)

    def test_update_product_invalidates_cache(self, db, product_svc):
        """update_product() must invalidate the cache."""
        product_svc.add_product("UpdItem", "Food", 2.0, 10)
        pid = next(p["id"] for p in product_svc.get_all_products() if p["name"] == "UpdItem")
        product_svc.update_product(pid, "UpdItemNew", "Food", 3.0, 20)
        result_after = product_svc.get_all_products()
        assert any(p["name"] == "UpdItemNew" for p in result_after)

    def test_delete_product_invalidates_cache(self, db, product_svc):
        """delete_product() must invalidate the cache."""
        product_svc.add_product("DelItem", "Other", 1.0, 1)
        pid = next(p["id"] for p in product_svc.get_all_products() if p["name"] == "DelItem")
        product_svc.delete_product(pid)
        result_after = product_svc.get_all_products()
        assert not any(p["name"] == "DelItem" for p in result_after)


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

    def test_top_cashiers(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.top_cashiers(limit=5)
        assert isinstance(rows, list)
        if rows:
            assert "cashier_name" in rows[0]
            assert "revenue" in rows[0]
            assert "orders" in rows[0]

    def test_hourly_distribution(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.hourly_distribution()
        assert isinstance(rows, list)
        if rows:
            assert "hour" in rows[0]
            assert "orders" in rows[0]

    def test_daily_revenue_date_range(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.daily_revenue(date_from="2000-01-01", date_to="2099-12-31")
        assert isinstance(rows, list)
        assert len(rows) >= 1

    def test_daily_revenue_empty_range(self, db, report_svc):
        self._create_order(db)
        rows = report_svc.daily_revenue(date_from="2099-01-01", date_to="2099-01-02")
        assert rows == []


# ---------------------------------------------------------------------------
# DuplicateError from db
# ---------------------------------------------------------------------------

class TestDbCustomExceptions:
    def test_duplicate_user_raises_duplicate_error(self, db):
        db.add_user("uniqueuser", "pw123456", "cashier")
        with pytest.raises(DuplicateError):
            db.add_user("uniqueuser", "other1234", "cashier")

    def test_duplicate_product_raises_duplicate_error(self, db):
        db.add_product("UniqueItem", "Food", 1.0, 10)
        with pytest.raises(DuplicateError):
            db.add_product("UniqueItem", "Food", 2.0, 5)

    def test_duplicate_discount_raises_duplicate_error(self, db):
        db.add_discount("UNIQ10", "percent", 10)
        with pytest.raises(DuplicateError):
            db.add_discount("UNIQ10", "fixed", 5)
