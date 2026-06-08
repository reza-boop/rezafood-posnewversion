"""Unit tests for the Database class using an in-memory SQLite database."""

import pytest

from db import Database


@pytest.fixture
def db():
    database = Database(db_name=":memory:")
    yield database
    database.close()


# ---------------------------------------------------------------------------
# Schema / seeding
# ---------------------------------------------------------------------------

class TestSchema:
    def test_admin_seeded(self, db):
        row = db.get_user_by_username("admin")
        assert row is not None
        assert row["role"] == "admin"
        assert row["must_change_password"] == 1

    def test_tables_exist(self, db):
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for t in ("users", "products", "orders", "order_items", "discounts",
                  "audit_logs", "schema_migrations"):
            assert t in tables

    def test_schema_migrations_populated(self, db):
        """All known migrations should be recorded after init."""
        from db import _SCHEMA_MIGRATIONS
        applied = {
            r[0] for r in db.conn.execute("SELECT name FROM schema_migrations")
        }
        for name, _ in _SCHEMA_MIGRATIONS:
            assert name in applied, f"Migration '{name}' not recorded"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestUsers:
    def test_add_and_get(self, db):
        db.add_user("alice", "pw123456", "cashier")
        row = db.get_user_by_username("alice")
        assert row is not None
        assert row["role"] == "cashier"

    def test_get_all(self, db):
        db.add_user("bob", "pw123456", "admin")
        users = db.get_all_users()
        usernames = [u["username"] for u in users]
        assert "bob" in usernames

    def test_update_user(self, db):
        db.add_user("charlie", "oldpass1", "cashier")
        row = db.get_user_by_username("charlie")
        db.update_user(row["id"], "charlie2", "newpass1", "admin")
        updated = db.get_user_by_username("charlie2")
        assert updated is not None
        assert updated["role"] == "admin"
        assert updated["must_change_password"] == 0

    def test_delete_user(self, db):
        db.add_user("dave", "pw123456", "cashier")
        row = db.get_user_by_username("dave")
        db.delete_user(row["id"])
        assert db.get_user_by_username("dave") is None

    def test_duplicate_username_raises(self, db):
        db.add_user("eve", "pw123456", "cashier")
        with pytest.raises(Exception):
            db.add_user("eve", "other1234", "cashier")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

class TestProducts:
    def test_add_and_list(self, db):
        db.add_product("Burger", "Food", 9.99, 50)
        products = db.get_all_products()
        assert any(p["name"] == "Burger" for p in products)

    def test_get_by_id(self, db):
        db.add_product("Fries", "Food", 3.50, 100)
        products = db.get_all_products()
        pid = next(p["id"] for p in products if p["name"] == "Fries")
        row = db.get_product_by_id(pid)
        assert row is not None
        assert row["price"] == 3.50

    def test_update_product(self, db):
        db.add_product("Cola", "Beverage", 2.00, 30)
        pid = db.get_all_products()[0]["id"]
        db.update_product(pid, "Cola Zero", "Beverage", 2.50, 25)
        row = db.get_product_by_id(pid)
        assert row["name"] == "Cola Zero"
        assert row["price"] == 2.50

    def test_delete_product(self, db):
        db.add_product("Chips", "Snack", 1.50, 20)
        products = db.get_all_products()
        pid = next(p["id"] for p in products if p["name"] == "Chips")
        db.delete_product(pid)
        assert db.get_product_by_id(pid) is None


# ---------------------------------------------------------------------------
# Orders — atomicity
# ---------------------------------------------------------------------------

class TestOrders:
    def _add_product(self, db, name="Pizza", stock=10) -> int:
        db.add_product(name, "Food", 12.00, stock)
        return next(p["id"] for p in db.get_all_products() if p["name"] == name)

    def _cashier_id(self, db) -> int:
        return db.get_user_by_username("admin")["id"]

    def test_create_order_returns_id(self, db):
        pid = self._add_product(db)
        items = [
            {"product_id": pid, "product_name": "Pizza",
             "quantity": 2, "unit_price": 12.00, "subtotal": 24.00}
        ]
        order_id = db.create_order(
            self._cashier_id(db), "admin", 24.00, "Cash", items
        )
        assert order_id is not None
        assert order_id >= 1

    def test_stock_decremented_atomically(self, db):
        pid = self._add_product(db, "Soda", stock=5)
        items = [
            {"product_id": pid, "product_name": "Soda",
             "quantity": 3, "unit_price": 2.00, "subtotal": 6.00}
        ]
        db.create_order(self._cashier_id(db), "admin", 6.00, "Cash", items)
        row = db.get_product_by_id(pid)
        assert row["stock"] == 2

    def test_order_items_stored(self, db):
        pid = self._add_product(db, "Tea", stock=10)
        items = [
            {"product_id": pid, "product_name": "Tea",
             "quantity": 1, "unit_price": 3.00, "subtotal": 3.00}
        ]
        oid = db.create_order(self._cashier_id(db), "admin", 3.00, "Card", items)
        stored = db.get_order_items(oid)
        assert len(stored) == 1
        assert stored[0]["product_name"] == "Tea"

    def test_discount_stored(self, db):
        pid = self._add_product(db, "Juice", stock=10)
        items = [
            {"product_id": pid, "product_name": "Juice",
             "quantity": 1, "unit_price": 5.00, "subtotal": 5.00}
        ]
        oid = db.create_order(
            self._cashier_id(db), "admin", 4.50, "Cash", items, discount_amount=0.50
        )
        order = db.get_order_by_id(oid)
        assert order["discount_amount"] == 0.50
        assert order["total"] == 4.50

    def test_get_recent_orders_limits_results(self, db):
        pid = self._add_product(db, "Recent", stock=20)
        items = [
            {
                "product_id": pid,
                "product_name": "Recent",
                "quantity": 1,
                "unit_price": 12.00,
                "subtotal": 12.00,
            }
        ]
        for _ in range(3):
            db.create_order(self._cashier_id(db), "admin", 12.00, "Cash", items)

        orders = db.get_recent_orders(2)

        assert len(orders) == 2
        assert orders[0]["id"] > orders[1]["id"]


# ---------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------

class TestDiscounts:
    def test_add_and_get_by_code(self, db):
        db.add_discount("SAVE10", "percent", 10)
        row = db.get_discount_by_code("SAVE10")
        assert row is not None
        assert row["value"] == 10

    def test_code_normalised_to_uppercase(self, db):
        db.add_discount("hello", "fixed", 5)
        row = db.get_discount_by_code("hello")
        assert row is not None

    def test_inactive_not_returned(self, db):
        db.add_discount("DEAD", "percent", 50, active=False)
        row = db.get_discount_by_code("DEAD")
        assert row is None

    def test_delete_discount(self, db):
        db.add_discount("GONE", "fixed", 3)
        row = db.get_discount_by_code("GONE")
        db.delete_discount(row["id"])
        assert db.get_discount_by_code("GONE") is None


# ---------------------------------------------------------------------------
# Filtered orders
# ---------------------------------------------------------------------------

class TestOrdersFiltered:
    def _setup(self, db):
        db.add_product("Item", "Food", 10.00, 100)
        pid = db.get_all_products()[0]["id"]
        items = [{"product_id": pid, "product_name": "Item",
                  "quantity": 1, "unit_price": 10.00, "subtotal": 10.00}]
        cid = db.get_user_by_username("admin")["id"]
        return cid, items

    def test_filter_by_cashier(self, db):
        cid, items = self._setup(db)
        db.create_order(cid, "admin", 10.00, "Cash", items)
        orders = db.get_orders_filtered(cashier="admin")
        assert len(orders) >= 1

    def test_filter_by_payment(self, db):
        cid, items = self._setup(db)
        db.create_order(cid, "admin", 10.00, "Card", items)
        db.create_order(cid, "admin", 10.00, "Cash", [
            {"product_id": items[0]["product_id"], "product_name": "Item",
             "quantity": 1, "unit_price": 10.00, "subtotal": 10.00}
        ])
        card_orders = db.get_orders_filtered(payment="Card")
        assert all(o["payment_method"] == "Card" for o in card_orders)


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------

class TestAuditLogs:
    def test_add_and_retrieve(self, db):
        db.add_audit_log(1, "admin", "login", "details")
        logs = db.get_audit_logs()
        assert any(lg["action"] == "login" for lg in logs)


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

class TestDashboardStats:
    def test_get_today_stats_empty(self, db):
        stats = db.get_today_stats("2099-01-01")
        assert stats["orders"] == 0
        assert stats["revenue"] == 0

    def test_get_total_products(self, db):
        before = db.get_total_products()
        db.add_product("Widget", "Other", 1.00, 1)
        assert db.get_total_products() == before + 1

    def test_get_all_time_revenue_empty(self, db):
        assert db.get_all_time_revenue() == 0.0

    def test_get_low_stock(self, db):
        db.add_product("LowItem", "Other", 1.00, 2)
        low = db.get_low_stock_products(threshold=5)
        names = [p["name"] for p in low]
        assert "LowItem" in names
