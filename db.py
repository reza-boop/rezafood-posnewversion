"""Database layer: connection, schema, migrations, and all CRUD operations.

The CRUD logic lives in domain-specific repository classes under
``repositories/``.  :class:`Database` wires everything together and exposes
the same public API it always has, so no callers need to change.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from config import DB_NAME, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from utils import check_password, hash_password, now_str


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DatabaseError(Exception):
    """Base class for all database-layer errors."""


class NotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""


class DuplicateError(DatabaseError):
    """Raised when a unique-constraint violation would occur."""


class ValidationError(DatabaseError):
    """Raised when supplied data fails a database-level constraint."""


class Database:
    """Manages the SQLite connection and coordinates all repositories.

    All public methods are kept identical to the original implementation so
    that existing callers (UI tabs, services, tests) require no changes.
    Internally each method delegates to the appropriate repository.
    """

    def __init__(self, db_name: Optional[str] = None) -> None:
        """Create the database.

        Args:
            db_name: Path to the SQLite file, or ``":memory:"`` for tests.
                     Defaults to the value of :data:`config.DB_NAME`.
        """
        self._db_name = db_name or DB_NAME
        self._conn: Optional[sqlite3.Connection] = None
        self.connect()
        self.init_schema()
        self._migrate_schema()
        self._init_repositories()
        self.seed_default_admin()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open (or re-open) the SQLite connection."""
        self._conn = sqlite3.connect(self._db_name, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def conn(self) -> sqlite3.Connection:
        assert self._conn is not None, "Database connection is not open."
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def _init_repositories(self) -> None:
        """Instantiate all repository objects, sharing the open connection."""
        # Import here to avoid circular imports at module level (repositories
        # import DuplicateError from db).
        from repositories.audit import AuditRepository
        from repositories.discount import DiscountRepository
        from repositories.order import OrderRepository
        from repositories.product import ProductRepository
        from repositories.report import ReportRepository
        from repositories.user import UserRepository

        self.users = UserRepository(self.conn)
        self.products = ProductRepository(self.conn)
        self.orders = OrderRepository(self.conn)
        self.discounts = DiscountRepository(self.conn)
        self.audit = AuditRepository(self.conn)
        self.report = ReportRepository(self.conn)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Create all tables if they do not already exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    UNIQUE NOT NULL,
            password_hash TEXT   NOT NULL,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            role         TEXT    NOT NULL DEFAULT 'cashier',
            created_at   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            category   TEXT    NOT NULL DEFAULT 'Other',
            price      REAL    NOT NULL DEFAULT 0,
            vat_rate   REAL    NOT NULL DEFAULT 7,
            stock      INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cashier_id      INTEGER NOT NULL,
            cashier_name    TEXT    NOT NULL,
            total           REAL    NOT NULL DEFAULT 0,
            discount_amount REAL    NOT NULL DEFAULT 0,
            payment_method  TEXT    NOT NULL,
            order_type      TEXT    NOT NULL DEFAULT 'take_away',
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id          INTEGER NOT NULL REFERENCES orders(id),
            product_id        INTEGER,
            product_name      TEXT    NOT NULL,
            quantity          INTEGER NOT NULL,
            unit_price        REAL    NOT NULL,
            applied_vat_rate  REAL    NOT NULL DEFAULT 7,
            subtotal          REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS discounts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT    UNIQUE NOT NULL,
            type       TEXT    NOT NULL CHECK(type IN ('percent','fixed')),
            value      REAL    NOT NULL,
            active     INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT NOT NULL,
            action     TEXT NOT NULL,
            details    TEXT,
            created_at TEXT NOT NULL
        );
        """
        self.conn.executescript(sql)
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Apply incremental schema migrations for older databases."""
        # 1. discount_amount in orders
        existing_orders_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(orders)")
        }
        if "discount_amount" not in existing_orders_cols:
            self.conn.execute(
                "ALTER TABLE orders ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0"
            )
            self.conn.commit()

        # 2. vat_rate in products
        existing_products_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(products)")
        }
        if "vat_rate" not in existing_products_cols:
            self.conn.execute(
                "ALTER TABLE products ADD COLUMN vat_rate REAL NOT NULL DEFAULT 7"
            )
            self.conn.commit()

        # 3. order_type in orders
        if "order_type" not in existing_orders_cols:
            self.conn.execute(
                "ALTER TABLE orders ADD COLUMN order_type TEXT NOT NULL DEFAULT 'take_away'"
            )
            self.conn.commit()

        # 4. applied_vat_rate in order_items
        existing_items_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(order_items)")
        }
        if "applied_vat_rate" not in existing_items_cols:
            self.conn.execute(
                "ALTER TABLE order_items ADD COLUMN applied_vat_rate REAL NOT NULL DEFAULT 7"
            )
            self.conn.commit()

        # 5. must_change_password in users
        existing_users_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(users)")
        }
        if "must_change_password" not in existing_users_cols:
            self.conn.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )
            self.conn.commit()

        # Ensure legacy databases also enforce password rotation for unchanged
        # seeded admin credentials.
        admin = self.conn.execute(
            "SELECT id, password_hash FROM users WHERE username=?",
            (DEFAULT_ADMIN_USERNAME,),
        ).fetchone()
        if admin and check_password(DEFAULT_ADMIN_PASSWORD, admin["password_hash"]):
            self.conn.execute(
                "UPDATE users SET must_change_password=1 WHERE id=?",
                (admin["id"],),
            )
            self.conn.commit()

    def seed_default_admin(self) -> None:
        """Insert the default admin account if it does not exist."""
        row = self.conn.execute(
            "SELECT id FROM users WHERE username=?",
            (DEFAULT_ADMIN_USERNAME,),
        ).fetchone()
        if not row:
            ts = now_str()
            self.conn.execute(
                "INSERT INTO users (username, password_hash, must_change_password, role, created_at)"
                " VALUES (?,?,?,?,?)",
                (
                    DEFAULT_ADMIN_USERNAME,
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    1,
                    "admin",
                    ts,
                ),
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    # Users — delegate to UserRepository
    # ------------------------------------------------------------------

    def get_user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        return self.users.get_by_username(username)

    def get_all_users(self) -> List[sqlite3.Row]:
        return self.users.get_all()

    def add_user(self, username: str, password: str, role: str) -> None:
        self.users.add(username, password, role)

    def update_user(
        self,
        user_id: int,
        username: str,
        password: Optional[str],
        role: str,
    ) -> None:
        self.users.update(user_id, username, password, role)

    def delete_user(self, user_id: int) -> None:
        self.users.delete(user_id)

    # ------------------------------------------------------------------
    # Products — delegate to ProductRepository
    # ------------------------------------------------------------------

    def get_all_products(self) -> List[sqlite3.Row]:
        return self.products.get_all()

    def get_product_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        return self.products.get_by_id(product_id)

    def add_product(
        self, name: str, category: str, price: float, stock: int, vat_rate: float = 7.0
    ) -> None:
        self.products.add(name, category, price, stock, vat_rate)

    def update_product(
        self,
        product_id: int,
        name: str,
        category: str,
        price: float,
        stock: int,
        vat_rate: float = 7.0,
    ) -> None:
        self.products.update(product_id, name, category, price, stock, vat_rate)

    def delete_product(self, product_id: int) -> None:
        self.products.delete(product_id)

    # ------------------------------------------------------------------
    # Orders — delegate to OrderRepository
    # ------------------------------------------------------------------

    def create_order(
        self,
        cashier_id: int,
        cashier_name: str,
        total: float,
        payment_method: str,
        items: List[Dict[str, Any]],
        discount_amount: float = 0.0,
        order_type: str = 'take_away',
    ) -> int:
        return self.orders.create(
            cashier_id, cashier_name, total, payment_method, items, discount_amount, order_type
        )

    def get_all_orders(self) -> List[sqlite3.Row]:
        return self.orders.get_all()

    def get_orders_filtered(
        self,
        date_from: str = "",
        date_to: str = "",
        cashier: str = "",
        payment: str = "",
    ) -> List[sqlite3.Row]:
        return self.orders.get_filtered(date_from, date_to, cashier, payment)

    def get_order_by_id(self, order_id: int) -> Optional[sqlite3.Row]:
        return self.orders.get_by_id(order_id)

    def get_order_items(self, order_id: int) -> List[sqlite3.Row]:
        return self.orders.get_items(order_id)

    # ------------------------------------------------------------------
    # Discounts — delegate to DiscountRepository
    # ------------------------------------------------------------------

    def get_discount_by_code(self, code: str) -> Optional[sqlite3.Row]:
        return self.discounts.get_by_code(code)

    def get_all_discounts(self) -> List[sqlite3.Row]:
        return self.discounts.get_all()

    def add_discount(
        self, code: str, dtype: str, value: float, active: bool = True
    ) -> None:
        self.discounts.add(code, dtype, value, active)

    def update_discount(
        self,
        discount_id: int,
        code: str,
        dtype: str,
        value: float,
        active: bool,
    ) -> None:
        self.discounts.update(discount_id, code, dtype, value, active)

    def delete_discount(self, discount_id: int) -> None:
        self.discounts.delete(discount_id)

    # ------------------------------------------------------------------
    # Dashboard statistics — delegate to OrderRepository / ProductRepository / UserRepository
    # ------------------------------------------------------------------

    def get_today_stats(self, date: str) -> Dict[str, Any]:
        return self.orders.get_today_stats(date)

    def get_low_stock_products(self, threshold: int = 5) -> List[sqlite3.Row]:
        return self.products.get_low_stock(threshold)

    def get_top_products(self, limit: int = 5) -> List[sqlite3.Row]:
        return self.products.get_top(limit)

    def get_total_products(self) -> int:
        return self.products.count()

    def get_total_users(self) -> int:
        return self.users.count()

    def get_all_time_revenue(self) -> float:
        return self.orders.get_all_time_revenue()

    # ------------------------------------------------------------------
    # Audit logs — delegate to AuditRepository
    # ------------------------------------------------------------------

    def add_audit_log(
        self,
        user_id: Optional[int],
        username: str,
        action: str,
        details: str = "",
    ) -> None:
        self.audit.add(user_id, username, action, details)

    def get_audit_logs(self, limit: int = 500) -> List[sqlite3.Row]:
        return self.audit.get_recent(limit)
