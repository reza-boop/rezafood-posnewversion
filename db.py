"""Database layer: connection, schema, migrations, and all CRUD operations."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from config import DB_NAME
from utils import hash_password, now_str


class Database:
    """Manages the SQLite connection and all data operations."""

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
    # Schema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Create all tables if they do not already exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    UNIQUE NOT NULL,
            password_hash TEXT   NOT NULL,
            role         TEXT    NOT NULL DEFAULT 'cashier',
            created_at   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            category   TEXT    NOT NULL DEFAULT 'Other',
            price      REAL    NOT NULL DEFAULT 0,
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
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES orders(id),
            product_id   INTEGER,
            product_name TEXT    NOT NULL,
            quantity     INTEGER NOT NULL,
            unit_price   REAL    NOT NULL,
            subtotal     REAL    NOT NULL
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
        existing_orders_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(orders)")
        }
        if "discount_amount" not in existing_orders_cols:
            self.conn.execute(
                "ALTER TABLE orders ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0"
            )
            self.conn.commit()

    def seed_default_admin(self) -> None:
        """Insert the default admin account if it does not exist."""
        row = self.conn.execute(
            "SELECT id FROM users WHERE username='admin'"
        ).fetchone()
        if not row:
            ts = now_str()
            self.conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at)"
                " VALUES (?,?,?,?)",
                ("admin", hash_password("admin123"), "admin", ts),
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

    def get_all_users(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()

    def add_user(self, username: str, password: str, role: str) -> None:
        ts = now_str()
        self.conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at)"
            " VALUES (?,?,?,?)",
            (username, hash_password(password), role, ts),
        )
        self.conn.commit()

    def update_user(
        self,
        user_id: int,
        username: str,
        password: Optional[str],
        role: str,
    ) -> None:
        if password:
            self.conn.execute(
                "UPDATE users SET username=?, password_hash=?, role=? WHERE id=?",
                (username, hash_password(password), role, user_id),
            )
        else:
            self.conn.execute(
                "UPDATE users SET username=?, role=? WHERE id=?",
                (username, role, user_id),
            )
        self.conn.commit()

    def delete_user(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def get_all_products(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products ORDER BY category, name"
        ).fetchall()

    def get_product_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()

    def add_product(
        self, name: str, category: str, price: float, stock: int
    ) -> None:
        ts = now_str()
        self.conn.execute(
            "INSERT INTO products"
            " (name, category, price, stock, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (name, category, price, stock, ts, ts),
        )
        self.conn.commit()

    def update_product(
        self,
        product_id: int,
        name: str,
        category: str,
        price: float,
        stock: int,
    ) -> None:
        ts = now_str()
        self.conn.execute(
            "UPDATE products"
            " SET name=?, category=?, price=?, stock=?, updated_at=?"
            " WHERE id=?",
            (name, category, price, stock, ts, product_id),
        )
        self.conn.commit()

    def delete_product(self, product_id: int) -> None:
        self.conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_order(
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

    def get_all_orders(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM orders ORDER BY id DESC"
        ).fetchall()

    def get_orders_filtered(
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

    def get_order_by_id(self, order_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()

    def get_order_items(self, order_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (order_id,)
        ).fetchall()

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def get_discount_by_code(self, code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts WHERE code=? AND active=1",
            (code.strip().upper(),),
        ).fetchone()

    def get_all_discounts(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts ORDER BY id DESC"
        ).fetchall()

    def add_discount(
        self, code: str, dtype: str, value: float, active: bool = True
    ) -> None:
        ts = now_str()
        self.conn.execute(
            "INSERT INTO discounts (code, type, value, active, created_at)"
            " VALUES (?,?,?,?,?)",
            (code.strip().upper(), dtype, value, int(active), ts),
        )
        self.conn.commit()

    def update_discount(
        self,
        discount_id: int,
        code: str,
        dtype: str,
        value: float,
        active: bool,
    ) -> None:
        self.conn.execute(
            "UPDATE discounts SET code=?, type=?, value=?, active=? WHERE id=?",
            (code.strip().upper(), dtype, value, int(active), discount_id),
        )
        self.conn.commit()

    def delete_discount(self, discount_id: int) -> None:
        self.conn.execute("DELETE FROM discounts WHERE id=?", (discount_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Dashboard statistics
    # ------------------------------------------------------------------

    def get_today_stats(self, date: str) -> Dict[str, Any]:
        """Return order count and total revenue for *date* ('YYYY-MM-DD')."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(total), 0) AS revenue"
            " FROM orders WHERE created_at LIKE ?",
            (f"{date}%",),
        ).fetchone()
        return {"orders": row["cnt"], "revenue": row["revenue"]}

    def get_low_stock_products(self, threshold: int = 5) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE stock <= ? ORDER BY stock",
            (threshold,),
        ).fetchall()

    def get_top_products(self, limit: int = 5) -> List[sqlite3.Row]:
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

    def get_total_products(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM products").fetchone()
        return row["cnt"]

    def get_total_users(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"]

    def get_all_time_revenue(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS revenue FROM orders"
        ).fetchone()
        return row["revenue"]

    # ------------------------------------------------------------------
    # Audit logs
    # ------------------------------------------------------------------

    def add_audit_log(
        self,
        user_id: Optional[int],
        username: str,
        action: str,
        details: str = "",
    ) -> None:
        ts = now_str()
        self.conn.execute(
            "INSERT INTO audit_logs (user_id, username, action, details, created_at)"
            " VALUES (?,?,?,?,?)",
            (user_id, username, action, details, ts),
        )
        self.conn.commit()

    def get_audit_logs(self, limit: int = 500) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
