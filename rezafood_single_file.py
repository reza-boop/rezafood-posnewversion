# ============================================================
# RezaFood POS — Single-File Bundle
# Generated from: https://github.com/reza-boop/rezafood-posnewversion
# Run with: python3 rezafood_single_file.py
# Requires: pip3 install bcrypt  (optional, for stronger password hashing)
#           sudo apt install python3-tk  (on Ubuntu/Debian)
# ============================================================

from __future__ import annotations

from datetime import datetime
from tkinter import messagebox
from tkinter import messagebox, simpledialog
from tkinter import messagebox, ttk
from tkinter import ttk
from typing import Any, Dict, List, Literal
from typing import Any, Dict, List, Optional
from typing import Any, Dict, List, Optional, Tuple
from typing import Any, Dict, List, Tuple
from typing import Any, Optional, Sequence
from typing import Callable, ClassVar, Dict
from typing import Dict, Optional
from typing import List, Optional
from typing import Optional
from typing import TYPE_CHECKING
from typing import TYPE_CHECKING, Any, Dict, List
from typing import TYPE_CHECKING, Dict
import csv
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk


# ============================================================
# === config.py ===
# ============================================================
APP_NAME = "RezaFood POS"
APP_VERSION = "11.3"

DB_NAME = "rezafood.db"
RECEIPTS_DIR = "receipts"
BACKUPS_DIR = "backups"
EXPORTS_DIR = "exports"

# ---------------------------------------------------------------------------
# Colour palette (dark Catppuccin-Mocha inspired)
# ---------------------------------------------------------------------------
THEME = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#89b4fa",
    "accent2": "#a6e3a1",
    "danger": "#f38ba8",
    "warning": "#fab387",
    "surface": "#313244",
    "surface2": "#45475a",
    "button_bg": "#89b4fa",
    "button_fg": "#1e1e2e",
    "entry_bg": "#313244",
    "entry_fg": "#cdd6f4",
    "select_bg": "#585b70",
    "tree_bg": "#1e1e2e",
    "tree_fg": "#cdd6f4",
    "tree_heading_bg": "#313244",
    "tree_heading_fg": "#89b4fa",
    "tree_row_odd": "#1e1e2e",
    "tree_row_even": "#26273a",
    "green": "#a6e3a1",
    "red": "#f38ba8",
}

# ---------------------------------------------------------------------------
# Fonts (Segoe UI looks great on Windows; fallback to system font elsewhere)
# ---------------------------------------------------------------------------
FONT = {
    "default": ("Segoe UI", 10),
    "bold": ("Segoe UI", 10, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "title": ("Segoe UI", 14, "bold"),
    "large": ("Segoe UI", 18, "bold"),
    "mono": ("Consolas", 10),
    "mono_small": ("Consolas", 9),
}

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["Cash", "Card", "QR/E-Wallet"]
ROLES = ["admin", "cashier"]
CATEGORIES = ["Food", "Beverage", "Snack", "Dessert", "Other"]
LOW_STOCK_THRESHOLD = 5
AUDIT_LOG_LIMIT = 500

# ---------------------------------------------------------------------------
# Security / session
# ---------------------------------------------------------------------------
SESSION_TIMEOUT_MINUTES = 15   # auto-logout after this many minutes idle
MAX_LOGIN_ATTEMPTS = 5         # failed logins before lockout
LOGIN_LOCKOUT_SECONDS = 300    # lockout duration in seconds (5 min)
MIN_PASSWORD_LENGTH = 6        # minimum password length enforced on new accounts

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
import os as _os

LOG_FILE = "logs/rezafood.log"
LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per log file
LOG_BACKUP_COUNT = 5               # keep up to 5 rotated files
LOG_JSON = _os.getenv("REZAFOOD_LOG_JSON", "0") == "1"  # set to "1" for JSON logs

# "development" → DEBUG level; anything else → INFO
ENVIRONMENT = _os.getenv("REZAFOOD_ENV", "production").lower()
LOG_LEVEL = "DEBUG" if ENVIRONMENT == "development" else "INFO"


# ============================================================
# === logger.py ===
# ============================================================
class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _setup() -> logging.Logger:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    handler: logging.Handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    if LOG_JSON:
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))

    numeric_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    handler.setLevel(logging.DEBUG)  # handler accepts all; root controls level

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
        root.setLevel(numeric_level)

    return logging.getLogger("rezafood")


logger: logging.Logger = _setup()


# ============================================================
# === utils.py ===
# ============================================================
# Number of PBKDF2 iterations used as the fallback when bcrypt is not installed.
# High enough to be computationally expensive; bcrypt (when installed) is preferred.
_PBKDF2_ITERATIONS = 400_000


# ---------------------------------------------------------------------------
# Directory management
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """Create required application directories if they do not exist."""
    for d in (RECEIPTS_DIR, BACKUPS_DIR, EXPORTS_DIR):
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def now_str() -> str:
    """Return current local time as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_str() -> str:
    """Return current date as 'YYYY-MM-DD'."""
    return datetime.now().strftime("%Y-%m-%d")


def time_stamp() -> str:
    """Return a compact timestamp string suitable for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Money helpers
# ---------------------------------------------------------------------------

def fmt_currency(amount: float) -> str:
    """Format a number as a currency string, e.g. '12,500.00'."""
    return f"{amount:,.2f}"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password.

    Uses bcrypt when available (preferred); otherwise falls back to
    PBKDF2-HMAC-SHA256 with a random salt, which is a proper password KDF.
    The stored format for PBKDF2 is ``"pbkdf2:<hex-salt>:<hex-digest>"``.
    """
    try:
        import bcrypt  # type: ignore
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, _PBKDF2_ITERATIONS
        )
        return f"pbkdf2:{salt.hex()}:{digest.hex()}"


def check_password(password: str, stored_hash: str) -> bool:
    """Verify *password* against *stored_hash*.

    Handles bcrypt hashes (``$2…``) and PBKDF2-HMAC-SHA256 hashes (``pbkdf2:…``).
    """
    # bcrypt
    try:
        import bcrypt  # type: ignore
        if stored_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ImportError:
        pass

    # PBKDF2-HMAC-SHA256 fallback
    if stored_hash.startswith("pbkdf2:"):
        try:
            payload = stored_hash[len("pbkdf2:"):]
            salt_hex, digest_hex = payload.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt, _PBKDF2_ITERATIONS
            )
            return hmac.compare_digest(candidate, expected)
        except Exception:
            return False

    return False


# ---------------------------------------------------------------------------
# File-system / OS helpers
# ---------------------------------------------------------------------------

def open_folder(path: str) -> None:
    """Open *path* in the OS file explorer (cross-platform).

    Silently ignores errors if the OS command fails (e.g. no file manager
    available).
    """
    abs_path = os.path.abspath(path)
    try:
        if sys.platform == "win32":
            os.startfile(abs_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", abs_path])
        else:
            subprocess.Popen(["xdg-open", abs_path])
    except Exception:
        pass


def print_file(filepath: str) -> bool:
    """Attempt to send *filepath* to the system printer.

    Returns ``True`` if the print command was issued, ``False`` otherwise.
    """
    if not os.path.isfile(filepath):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(filepath, "print")  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["lpr", filepath])
        return True
    except Exception:
        return False


def backup_db() -> str:
    """Copy the SQLite database to *backups/* with a timestamp suffix.

    Returns the destination file path.
    """
    ensure_dirs()
    src = DB_NAME
    dst = os.path.join(BACKUPS_DIR, f"rezafood_backup_{time_stamp()}.db")
    shutil.copy2(src, dst)
    return dst


def export_to_csv(
    filepath: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> None:
    """Write *rows* (with *headers*) to a CSV file at *filepath*."""
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_input(value: str, max_length: int = 255) -> str:
    """Strip control characters and truncate *value* to *max_length*.

    This is a defence-in-depth measure; the database layer already uses
    parameterised queries, so SQL injection is already prevented.
    """
    cleaned = _CONTROL_RE.sub("", value)
    return cleaned[:max_length]


# ---------------------------------------------------------------------------
# Rate limiter (login protection)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Thread-safe rate limiter for tracking failed login attempts per key.

    After :attr:`max_attempts` failures within the observation window the key
    is *locked out* for :attr:`lockout_seconds` seconds.  Successful
    authentication should call :meth:`reset` to clear the counter.

    Usage::

        limiter = RateLimiter()
        if limiter.is_locked("alice"):
            show_error("Account temporarily locked.")
        elif not authenticate("alice", password):
            limiter.record_failure("alice")
        else:
            limiter.reset("alice")
    """

    def __init__(
        self,
        max_attempts: int = MAX_LOGIN_ATTEMPTS,
        lockout_seconds: int = LOGIN_LOCKOUT_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        # key → (failure_count, lockout_until_monotonic)
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str) -> bool:
        """Return ``True`` if *key* is currently in lockout."""
        with self._lock:
            count, until = self._state.get(key, (0, 0.0))
            if count >= self.max_attempts and time.monotonic() < until:
                return True
            return False

    def record_failure(self, key: str) -> int:
        """Increment the failure counter for *key* and return the new count."""
        with self._lock:
            count, _ = self._state.get(key, (0, 0.0))
            count += 1
            until = (
                time.monotonic() + self.lockout_seconds
                if count >= self.max_attempts
                else 0.0
            )
            self._state[key] = (count, until)
            return count

    def remaining_lockout(self, key: str) -> float:
        """Return seconds remaining in lockout for *key* (0 if not locked)."""
        with self._lock:
            count, until = self._state.get(key, (0, 0.0))
            if count >= self.max_attempts:
                remaining = until - time.monotonic()
                return max(0.0, remaining)
            return 0.0

    def reset(self, key: str) -> None:
        """Clear the failure counter for *key* (call after successful login)."""
        with self._lock:
            self._state.pop(key, None)


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

class Session:
    """Lightweight session holder with idle-timeout support.

    The session tracks the authenticated user and the timestamp of the last
    activity.  Call :meth:`touch` on every user interaction and check
    :meth:`is_expired` periodically to enforce auto-logout.

    Args:
        timeout_minutes: Minutes of inactivity before expiry.
    """

    def __init__(self, timeout_minutes: int = 15) -> None:
        self._timeout_seconds = timeout_minutes * 60
        self._user_id: Optional[int] = None
        self._username: Optional[str] = None
        self._role: Optional[str] = None
        self._last_active: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    def login(self, user_id: int, username: str, role: str) -> None:
        """Start a new authenticated session."""
        with self._lock:
            self._user_id = user_id
            self._username = username
            self._role = role
            self._last_active = time.monotonic()

    def logout(self) -> None:
        """Clear all session data."""
        with self._lock:
            self._user_id = None
            self._username = None
            self._role = None
            self._last_active = 0.0

    # ------------------------------------------------------------------
    # Activity tracking
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Reset the idle timer (call on every user interaction)."""
        with self._lock:
            if self._user_id is not None:
                self._last_active = time.monotonic()

    def is_expired(self) -> bool:
        """Return ``True`` if the session has timed out."""
        with self._lock:
            if self._user_id is None:
                return False
            return (time.monotonic() - self._last_active) > self._timeout_seconds

    # ------------------------------------------------------------------
    # Properties (read-only)
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        with self._lock:
            return self._user_id is not None

    @property
    def user_id(self) -> Optional[int]:
        with self._lock:
            return self._user_id

    @property
    def username(self) -> Optional[str]:
        with self._lock:
            return self._username

    @property
    def role(self) -> Optional[str]:
        with self._lock:
            return self._role

    def is_admin(self) -> bool:
        with self._lock:
            return self._role == "admin"


# ============================================================
# === db.py ===
# ============================================================
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
        self, name: str, category: str, price: float, stock: int
    ) -> None:
        self.products.add(name, category, price, stock)

    def update_product(
        self,
        product_id: int,
        name: str,
        category: str,
        price: float,
        stock: int,
    ) -> None:
        self.products.update(product_id, name, category, price, stock)

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
    ) -> int:
        return self.orders.create(
            cashier_id, cashier_name, total, payment_method, items, discount_amount
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


# ============================================================
# === repositories/base.py ===
# ============================================================
class BaseRepository:
    """Holds the shared SQLite connection used by all repositories."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn


# ============================================================
# === repositories/user.py ===
# ============================================================
class UserRepository(BaseRepository):
    """Manages all persistence operations for the *users* table."""

    def get_by_username(self, username: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()

    def add(self, username: str, password: str, role: str) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at)"
                " VALUES (?,?,?,?)",
                (username, hash_password(password), role, ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Username '{username}' already exists.") from exc

    def update(
        self,
        user_id: int,
        username: str,
        password: Optional[str],
        role: str,
    ) -> None:
        try:
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
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Username '{username}' already exists.") from exc

    def delete(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"]


# ============================================================
# === repositories/product.py ===
# ============================================================
class ProductRepository(BaseRepository):
    """Manages all persistence operations for the *products* table."""

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products ORDER BY category, name"
        ).fetchall()

    def get_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()

    def add(self, name: str, category: str, price: float, stock: int) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO products"
                " (name, category, price, stock, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (name, category, price, stock, ts, ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Product '{name}' already exists.") from exc

    def update(
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

    def delete(self, product_id: int) -> None:
        self.conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def get_low_stock(self, threshold: int = 5) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM products WHERE stock <= ? ORDER BY stock",
            (threshold,),
        ).fetchall()

    def get_top(self, limit: int = 5) -> List[sqlite3.Row]:
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

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM products").fetchone()
        return row["cnt"]


# ============================================================
# === repositories/order.py ===
# ============================================================
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


# ============================================================
# === repositories/discount.py ===
# ============================================================
class DiscountRepository(BaseRepository):
    """Manages all persistence operations for the *discounts* table."""

    def get_by_code(self, code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts WHERE code=? AND active=1",
            (code.strip().upper(),),
        ).fetchone()

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts ORDER BY id DESC"
        ).fetchall()

    def add(
        self, code: str, dtype: str, value: float, active: bool = True
    ) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO discounts (code, type, value, active, created_at)"
                " VALUES (?,?,?,?,?)",
                (code.strip().upper(), dtype, value, int(active), ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(
                f"Discount code '{code.strip().upper()}' already exists."
            ) from exc

    def update(
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

    def delete(self, discount_id: int) -> None:
        self.conn.execute("DELETE FROM discounts WHERE id=?", (discount_id,))
        self.conn.commit()


# ============================================================
# === repositories/audit.py ===
# ============================================================
class AuditRepository(BaseRepository):
    """Manages all persistence operations for the *audit_logs* table."""

    def add(
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

    def get_recent(self, limit: int = 500) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# ============================================================
# === repositories/report.py ===
# ============================================================
class ReportRepository(BaseRepository):
    """Encapsulates all cross-table aggregation queries used by reporting."""

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
            rows = self.conn.execute(
                f"SELECT substr(created_at,1,10) AS day,"
                f"       COUNT(*) AS orders,"
                f"       COALESCE(SUM(total),0) AS revenue"
                f" FROM orders {where}"
                f" GROUP BY day ORDER BY day DESC",
                params,
            ).fetchall()
        else:
            rows = self.conn.execute(
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
        rows = self.conn.execute(
            "SELECT payment_method,"
            "       COUNT(*) AS orders,"
            "       COALESCE(SUM(total),0) AS revenue"
            " FROM orders"
            " GROUP BY payment_method",
        ).fetchall()
        return [dict(r) for r in rows]

    def sales_by_category(self) -> List[Dict[str, Any]]:
        """Return quantity sold and revenue grouped by product category."""
        rows = self.conn.execute(
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
        rows = self.conn.execute(
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
        rows = self.conn.execute(
            "SELECT CAST(substr(created_at,12,2) AS INTEGER) AS hour,"
            "       COUNT(*) AS orders"
            " FROM orders"
            " GROUP BY hour"
            " ORDER BY hour",
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# === services/product_service.py ===
# ============================================================
# Products cache entry: (timestamp, data)
_CacheEntry = Tuple[float, List[Any]]
_CACHE_TTL_SECONDS = 30  # invalidate cached product list after 30 s


class ProductService:
    """Validation and stock queries for the product domain."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: Optional[_CacheEntry] = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_valid(self) -> bool:
        if self._cache is None:
            return False
        age = time.monotonic() - self._cache[0]
        return age < _CACHE_TTL_SECONDS

    def invalidate_cache(self) -> None:
        """Force the next :meth:`get_all_products` call to hit the database."""
        self._cache = None

    def get_all_products(self) -> List[Any]:
        """Return all products, using an in-process TTL cache.

        The cache is automatically invalidated after
        :data:`_CACHE_TTL_SECONDS` seconds or when :meth:`invalidate_cache`
        is called explicitly (e.g. after add / update / delete).
        """
        if not self._cache_valid():
            self._cache = (time.monotonic(), self.db.get_all_products())
        return self._cache[1]  # type: ignore[index]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self, name: str, category: str, price: float, stock: int
    ) -> str:
        """Return a human-readable error message, or ``''`` if valid."""
        if not name.strip():
            return "Product name is required."
        if len(name.strip()) > 100:
            return "Product name must be 100 characters or fewer."
        if category not in CATEGORIES:
            return f"Category must be one of: {', '.join(CATEGORIES)}."
        if price < 0:
            return "Price cannot be negative."
        if stock < 0:
            return "Stock cannot be negative."
        return ""

    def low_stock_count(self) -> int:
        """Return the number of products at or below the low-stock threshold."""
        return len(self.db.get_low_stock_products(LOW_STOCK_THRESHOLD))

    def search(self, query: str) -> List[Any]:
        """Return products whose name or category contains *query* (case-insensitive)."""
        q = query.strip().lower()
        if not q:
            return self.get_all_products()
        return [
            p for p in self.get_all_products()
            if q in p["name"].lower() or q in p["category"].lower()
        ]


# ============================================================
# === services/order_service.py ===
# ============================================================
class OrderService:
    """Orchestrates order placement with discount resolution."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def resolve_discount(self, code: str, subtotal: float) -> Tuple[float, float]:
        """Return ``(discount_amount, final_total)`` for the given coupon.

        If *code* is empty or not found the order proceeds at full price.
        """
        if not code or not code.strip():
            return 0.0, subtotal

        discount = self.db.get_discount_by_code(code)
        if not discount:
            return 0.0, subtotal

        if discount["type"] == "percent":
            amount = subtotal * discount["value"] / 100.0
        else:
            amount = float(discount["value"])

        amount = min(round(amount, 2), subtotal)
        return amount, round(subtotal - amount, 2)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_items(self, items: List[Dict[str, Any]]) -> None:
        """Raise :exc:`ValueError` if any item has invalid quantity or price."""
        for item in items:
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0))
            if qty <= 0:
                name = item.get("product_name", "?")
                raise ValueError(
                    f"Item '{name}' has invalid quantity {qty}. Must be ≥ 1."
                )
            if price < 0:
                name = item.get("product_name", "?")
                raise ValueError(
                    f"Item '{name}' has negative unit price {price}."
                )

    def _validate_stock(self, items: List[Dict[str, Any]]) -> None:
        """Raise :exc:`ValueError` if any product has insufficient stock."""
        for item in items:
            pid = item.get("product_id")
            if pid is None:
                continue
            product = self.db.get_product_by_id(int(pid))
            if product is None:
                raise ValueError(
                    f"Product ID {pid} not found."
                )
            qty = int(item.get("quantity", 0))
            if product["stock"] < qty:
                raise ValueError(
                    f"Insufficient stock for '{product['name']}': "
                    f"requested {qty}, available {product['stock']}."
                )

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_order(
        self,
        cashier_id: int,
        cashier_name: str,
        payment_method: str,
        items: List[Dict[str, Any]],
        discount_amount: float = 0.0,
    ) -> int:
        """Validate business rules and persist the order.

        Returns the new order ID.
        Raises :exc:`ValueError` for invalid input.
        """
        if not items:
            raise ValueError("Cannot create an empty order.")

        if payment_method not in PAYMENT_METHODS:
            raise ValueError(
                f"Invalid payment method '{payment_method}'. "
                f"Must be one of: {', '.join(PAYMENT_METHODS)}."
            )

        self._validate_items(items)
        self._validate_stock(items)

        subtotal = sum(float(i["subtotal"]) for i in items)
        total = max(0.0, round(subtotal - discount_amount, 2))

        return self.db.create_order(
            cashier_id,
            cashier_name,
            total,
            payment_method,
            items,
            discount_amount,
        )


# ============================================================
# === services/report_service.py ===
# ============================================================
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


# ============================================================
# === receipts.py ===
# ============================================================
# Supported receipt widths (characters)
_WIDTHS: Dict[str, int] = {
    "thermal": 42,   # 80 mm thermal printer
    "wide": 58,      # wider 80-column format
    "a4": 72,        # A4 paper (monospace)
}

ReceiptFormat = Literal["thermal", "wide", "a4"]


class ReceiptBuilder:
    """Builds and saves plain-text receipts for a completed order.

    Args:
        format: One of ``"thermal"`` (default, 42 chars), ``"wide"`` (58 chars),
                or ``"a4"`` (72 chars).
    """

    def __init__(
        self,
        order_id: int,
        cashier: str,
        payment_method: str,
        items: List[Dict[str, Any]],
        total: float,
        paid: float = 0.0,
        discount_amount: float = 0.0,
        format: ReceiptFormat = "thermal",
    ) -> None:
        self.order_id = order_id
        self.cashier = cashier
        self.payment_method = payment_method
        self.items = items
        self.total = total
        self.paid = paid
        self.discount_amount = discount_amount
        self.change = max(0.0, paid - total)
        self.timestamp = now_str()
        self.width = _WIDTHS.get(format, _WIDTHS["thermal"])

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self) -> str:
        """Return the receipt as a multi-line string."""
        W = self.width
        sep = "-" * W
        eq = "=" * W

        # Name column width scales with total width; always leave room for
        # Qty (4), Price (9), Sub (9) + 3 spaces = 25 chars minimum for W=42
        name_col = max(16, W - 25)
        header_row = (
            f"{'Item':<{name_col}} {'Qty':>4} {'Price':>9} {'Sub':>9}"
        )

        lines: List[str] = [
            eq,
            f"{APP_NAME} v{APP_VERSION}".center(W),
            eq,
            f"Order # : {self.order_id}",
            f"Date    : {self.timestamp}",
            f"Cashier : {self.cashier}",
            sep,
            header_row,
            sep,
        ]

        for item in self.items:
            name = str(item.get("product_name", ""))[:name_col]
            qty = int(item.get("quantity", 0))
            price = float(item.get("unit_price", 0))
            sub = float(item.get("subtotal", 0))
            lines.append(
                f"{name:<{name_col}} {qty:>4} {fmt_currency(price):>9}"
                f" {fmt_currency(sub):>9}"
            )

        lines += [
            sep,
            f"{'SUBTOTAL':>{W - 10}} {fmt_currency(self.total + self.discount_amount):>9}",
        ]

        if self.discount_amount > 0:
            lines.append(
                f"{'DISCOUNT':>{W - 10}} -{fmt_currency(self.discount_amount):>8}"
            )

        lines += [
            f"{'TOTAL':>{W - 10}} {fmt_currency(self.total):>9}",
        ]

        if self.paid > 0:
            lines += [
                f"{'PAID':>{W - 10}} {fmt_currency(self.paid):>9}",
                f"{'CHANGE':>{W - 10}} {fmt_currency(self.change):>9}",
            ]

        lines += [
            sep,
            f"Payment : {self.payment_method}",
            sep,
            "Thank you for your visit!".center(W),
            eq,
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(self) -> str:
        """Write the receipt to *receipts/receipt_XXXXXX.txt*.

        Returns the absolute file path.
        """
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        filename = f"receipt_{self.order_id:06d}.txt"
        filepath = os.path.join(RECEIPTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.build())
        return os.path.abspath(filepath)


# ============================================================
# === ui/widgets.py ===
# ============================================================
# ---------------------------------------------------------------------------
# Treeview
# ---------------------------------------------------------------------------

def styled_tree(
    parent: tk.Widget,
    columns: List[str],
    col_widths: Optional[List[int]] = None,
    height: int = 14,
) -> ttk.Treeview:
    """Return a dark-themed :class:`ttk.Treeview` with a vertical scrollbar.

    The Treeview is packed into a wrapping ``tk.Frame`` together with its
    scrollbar; the frame itself is packed inside *parent*.
    """
    style = ttk.Style()
    uid = f"Custom{id(parent)}.Treeview"
    style.configure(
        uid,
        background=THEME["tree_bg"],
        foreground=THEME["tree_fg"],
        fieldbackground=THEME["tree_bg"],
        rowheight=24,
        font=FONT["default"],
    )
    style.configure(
        f"{uid}.Heading",
        background=THEME["tree_heading_bg"],
        foreground=THEME["tree_heading_fg"],
        font=FONT["bold"],
    )
    style.map(uid, background=[("selected", THEME["select_bg"])])

    frame = tk.Frame(parent, bg=THEME["bg"])
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        height=height,
        style=uid,
    )
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    if col_widths:
        for col, w in zip(columns, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")
    else:
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="center")

    tree.tag_configure("odd", background=THEME["tree_row_odd"])
    tree.tag_configure("even", background=THEME["tree_row_even"])

    return tree


# ---------------------------------------------------------------------------
# Buttons / labels
# ---------------------------------------------------------------------------

def btn(
    parent: tk.Widget,
    text: str,
    command,
    danger: bool = False,
    width: int = 14,
) -> tk.Button:
    """Return a styled action button."""
    bg = THEME["danger"] if danger else THEME["button_bg"]
    return tk.Button(
        parent,
        text=text,
        font=FONT["bold"],
        bg=bg,
        fg=THEME["bg"],
        activebackground=THEME["surface2"],
        activeforeground=THEME["fg"],
        relief="flat",
        padx=10,
        pady=6,
        cursor="hand2",
        width=width,
        command=command,
    )


def section_label(parent: tk.Widget, text: str) -> tk.Label:
    """Return a section-heading label."""
    return tk.Label(
        parent,
        text=text,
        font=FONT["heading"],
        bg=THEME["bg"],
        fg=THEME["accent"],
    )


# ============================================================
# === ui/dialogs.py ===
# ============================================================
# ---------------------------------------------------------------------------
# Password validation helper
# ---------------------------------------------------------------------------

def validate_password_strength(password: str) -> str:
    """Return an error string, or ``''`` if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return ""


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class _BaseDialog(tk.Toplevel):
    """Shared base for modal CRUD dialogs."""

    def __init__(self, parent: tk.Widget, title: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=THEME["bg"])
        self.result: Optional[dict] = None
        self.grab_set()
        self.transient(parent)
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
        except Exception:
            px, py = 200, 200
        self.geometry(f"+{px + 60}+{py + 60}")

    # Styling helpers
    def _label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent, text=text, font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        )

    def _entry(self, parent: tk.Widget, textvariable: tk.Variable) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=textvariable,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
            width=28,
        )

    def _option_menu(
        self, parent: tk.Widget, variable: tk.StringVar, choices: list
    ) -> tk.OptionMenu:
        menu = tk.OptionMenu(parent, variable, *choices)
        menu.configure(
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            activebackground=THEME["surface2"],
            activeforeground=THEME["fg"],
            relief="flat",
            highlightthickness=0,
        )
        menu["menu"].configure(
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            font=FONT["default"],
            activebackground=THEME["select_bg"],
        )
        return menu

    def _button(
        self, parent: tk.Widget, text: str, command, danger: bool = False
    ) -> tk.Button:
        bg = THEME["danger"] if danger else THEME["button_bg"]
        return tk.Button(
            parent,
            text=text,
            font=FONT["bold"],
            bg=bg,
            fg=THEME["bg"],
            activebackground=THEME["surface2"],
            activeforeground=THEME["fg"],
            relief="flat",
            padx=18,
            pady=7,
            cursor="hand2",
            command=command,
        )


# ---------------------------------------------------------------------------
# Product dialog
# ---------------------------------------------------------------------------

class ProductDialog(_BaseDialog):
    """Add or edit a product."""

    def __init__(
        self, parent: tk.Widget, product: Optional[dict] = None
    ) -> None:
        title = "Edit Product" if product else "Add Product"
        super().__init__(parent, title)
        self._product = product
        self._build()
        if product:
            self._populate(product)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._name_var  = tk.StringVar()
        self._cat_var   = tk.StringVar(value=CATEGORIES[0])
        self._price_var = tk.StringVar()
        self._stock_var = tk.StringVar()

        rows = [
            ("Name:",     self._name_var,  "entry"),
            ("Category:", self._cat_var,   "combo"),
            ("Price:",    self._price_var, "entry"),
            ("Stock:",    self._stock_var, "entry"),
        ]

        for i, (lbl, var, kind) in enumerate(rows):
            self._label(card, lbl).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            if kind == "entry":
                self._entry(card, var).grid(row=i, column=1, sticky="ew", pady=5)
            else:
                self._option_menu(card, var, CATEGORIES).grid(
                    row=i, column=1, sticky="ew", pady=5
                )

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, product: dict) -> None:
        self._name_var.set(str(product.get("name", "")))
        self._cat_var.set(str(product.get("category", CATEGORIES[0])))
        self._price_var.set(str(product.get("price", "")))
        self._stock_var.set(str(product.get("stock", "")))

    def _save(self) -> None:
        name      = self._name_var.get().strip()
        cat       = self._cat_var.get().strip()
        price_str = self._price_var.get().strip()
        stock_str = self._stock_var.get().strip()

        if not name:
            messagebox.showwarning("Validation", "Product name is required.", parent=self)
            return

        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Validation", "Price must be a non-negative number.", parent=self
            )
            return

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Validation", "Stock must be a non-negative integer.", parent=self
            )
            return

        self.result = {"name": name, "category": cat, "price": price, "stock": stock}
        self.destroy()


# ---------------------------------------------------------------------------
# User dialog
# ---------------------------------------------------------------------------

class UserDialog(_BaseDialog):
    """Add or edit a user account."""

    def __init__(
        self, parent: tk.Widget, user: Optional[dict] = None
    ) -> None:
        title = "Edit User" if user else "Add User"
        super().__init__(parent, title)
        self._user = user
        self._build()
        if user:
            self._populate(user)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._username_var = tk.StringVar()
        self._password_var = tk.StringVar()
        self._role_var     = tk.StringVar(value=ROLES[1])

        pw_hint = " (blank = keep)" if self._user else ""

        self._label(card, "Username:").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 12))
        self._entry(card, self._username_var).grid(row=0, column=1, sticky="ew", pady=5)

        self._label(card, f"Password:{pw_hint}").grid(
            row=1, column=0, sticky="w", pady=5, padx=(0, 12)
        )
        tk.Entry(
            card,
            textvariable=self._password_var,
            show="*",
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
            width=28,
        ).grid(row=1, column=1, sticky="ew", pady=5)

        self._label(card, "Role:").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 12))
        self._option_menu(card, self._role_var, ROLES).grid(
            row=2, column=1, sticky="ew", pady=5
        )

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=3, column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, user: dict) -> None:
        self._username_var.set(str(user.get("username", "")))
        self._role_var.set(str(user.get("role", ROLES[1])))

    def _save(self) -> None:
        username = self._username_var.get().strip()
        password = self._password_var.get()
        role     = self._role_var.get().strip()

        if not username:
            messagebox.showwarning("Validation", "Username is required.", parent=self)
            return

        if not self._user and not password:
            messagebox.showwarning(
                "Validation", "Password is required for new users.", parent=self
            )
            return

        if password:
            err = validate_password_strength(password)
            if err:
                messagebox.showwarning("Validation", err, parent=self)
                return

        self.result = {"username": username, "password": password, "role": role}
        self.destroy()


# ---------------------------------------------------------------------------
# Discount dialog
# ---------------------------------------------------------------------------

_DISCOUNT_TYPES = ["percent", "fixed"]


class DiscountDialog(_BaseDialog):
    """Add or edit a discount/coupon code."""

    def __init__(
        self, parent: tk.Widget, discount: Optional[dict] = None
    ) -> None:
        title = "Edit Discount" if discount else "Add Discount"
        super().__init__(parent, title)
        self._discount = discount
        self._build()
        if discount:
            self._populate(discount)
        self.wait_window()

    def _build(self) -> None:
        surf = THEME["surface"]
        card = tk.Frame(self, bg=surf, padx=24, pady=24)
        card.pack(padx=10, pady=10, fill="both")

        self._code_var   = tk.StringVar()
        self._type_var   = tk.StringVar(value=_DISCOUNT_TYPES[0])
        self._value_var  = tk.StringVar()
        self._active_var = tk.BooleanVar(value=True)

        rows = [
            ("Code:",  self._code_var,  "entry"),
            ("Type:",  self._type_var,  "combo"),
            ("Value:", self._value_var, "entry"),
        ]

        for i, (lbl, var, kind) in enumerate(rows):
            self._label(card, lbl).grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            if kind == "entry":
                self._entry(card, var).grid(row=i, column=1, sticky="ew", pady=5)
            else:
                self._option_menu(card, var, _DISCOUNT_TYPES).grid(
                    row=i, column=1, sticky="ew", pady=5
                )

        tk.Checkbutton(
            card,
            text="Active",
            variable=self._active_var,
            font=FONT["bold"],
            bg=surf,
            fg=THEME["fg"],
            selectcolor=THEME["entry_bg"],
            activebackground=surf,
            activeforeground=THEME["fg"],
        ).grid(row=len(rows), column=1, sticky="w", pady=5)

        card.columnconfigure(1, weight=1)

        btn_row = tk.Frame(card, bg=surf)
        btn_row.grid(row=len(rows) + 1, column=0, columnspan=2, pady=(18, 0))
        self._button(btn_row, "Save", self._save).pack(side="left", padx=6)
        self._button(btn_row, "Cancel", self.destroy, danger=True).pack(side="left", padx=6)

    def _populate(self, discount: dict) -> None:
        self._code_var.set(str(discount.get("code", "")))
        self._type_var.set(str(discount.get("type", _DISCOUNT_TYPES[0])))
        self._value_var.set(str(discount.get("value", "")))
        self._active_var.set(bool(discount.get("active", True)))

    def _save(self) -> None:
        code  = self._code_var.get().strip().upper()
        dtype = self._type_var.get().strip()
        val_s = self._value_var.get().strip()
        active = self._active_var.get()

        if not code:
            messagebox.showwarning("Validation", "Coupon code is required.", parent=self)
            return

        if dtype == "percent":
            try:
                value = float(val_s)
                if not (0 < value <= 100):
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "Validation", "Percent discount must be between 0 and 100.", parent=self
                )
                return
        else:
            try:
                value = float(val_s)
                if value <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "Validation", "Fixed discount must be a positive number.", parent=self
                )
                return

        self.result = {
            "code": code,
            "type": dtype,
            "value": value,
            "active": active,
        }
        self.destroy()


# ============================================================
# === ui/tabs/base_tab.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class BaseTab(tk.Frame):
    """Abstract base for every tab panel in the notebook."""

    def __init__(
        self, notebook: ttk.Notebook, app: "PosApp", tab_text: str
    ) -> None:
        from config import THEME

        super().__init__(notebook, bg=THEME["bg"])
        self.app = app
        self.db = app.db
        self.user = app.user
        self.root = app.root

        notebook.add(self, text=tab_text)
        self._build()

    def _build(self) -> None:
        """Build tab contents. Override in subclasses."""

    def refresh(self) -> None:
        """Refresh displayed data. Override in subclasses."""


# ============================================================
# === ui/tabs/dashboard.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class DashboardTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📊 Dashboard ")

    def _build(self) -> None:
        # Stat cards row
        stats_row = tk.Frame(self, bg=THEME["bg"])
        stats_row.pack(fill="x", padx=12, pady=12)

        self._stat_vars: Dict[str, tk.StringVar] = {}
        stats_defs = [
            ("Today Orders",  "today_orders",   THEME["accent"]),
            ("Today Revenue", "today_revenue",  THEME["accent2"]),
            ("Total Revenue", "all_revenue",    THEME["warning"]),
            ("Total Products","total_products", THEME["fg"]),
            ("Total Users",   "total_users",    THEME["fg"]),
        ]
        for label, key, color in stats_defs:
            card = tk.Frame(stats_row, bg=THEME["surface"], padx=16, pady=12)
            card.pack(side="left", expand=True, fill="both", padx=6)
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            tk.Label(
                card, text=label, font=FONT["bold"],
                bg=THEME["surface"], fg=THEME["fg"],
            ).pack()
            tk.Label(
                card, textvariable=var, font=FONT["large"],
                bg=THEME["surface"], fg=color,
            ).pack()

        # Mid section: top products + low stock
        mid = tk.Frame(self, bg=THEME["bg"])
        mid.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        left = tk.Frame(mid, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        section_label(left, "Top-Selling Products").pack(anchor="w", pady=(0, 4))
        self._top_tree = styled_tree(
            left, ["Product", "Qty Sold", "Revenue"], [200, 100, 120], height=10
        )

        right = tk.Frame(mid, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        section_label(right, f"Low Stock (≤ {LOW_STOCK_THRESHOLD})").pack(
            anchor="w", pady=(0, 4)
        )
        self._low_tree = styled_tree(
            right, ["ID", "Name", "Category", "Stock"], [50, 180, 120, 70], height=10
        )

        btn(self, "Refresh Dashboard", self.refresh, width=20).pack(pady=6)

    def refresh(self) -> None:
        today = date_str()
        stats = self.db.get_today_stats(today)
        self._stat_vars["today_orders"].set(str(stats["orders"]))
        self._stat_vars["today_revenue"].set(fmt_currency(stats["revenue"]))
        self._stat_vars["all_revenue"].set(fmt_currency(self.db.get_all_time_revenue()))
        self._stat_vars["total_products"].set(str(self.db.get_total_products()))
        self._stat_vars["total_users"].set(str(self.db.get_total_users()))

        self._top_tree.delete(*self._top_tree.get_children())
        for i, p in enumerate(self.db.get_top_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._top_tree.insert(
                "", "end",
                values=(p["product_name"], p["total_qty"], fmt_currency(p["total_revenue"])),
                tags=(tag,),
            )

        self._low_tree.delete(*self._low_tree.get_children())
        for i, p in enumerate(self.db.get_low_stock_products(LOW_STOCK_THRESHOLD)):
            tag = "even" if i % 2 == 0 else "odd"
            self._low_tree.insert(
                "", "end",
                values=(p["id"], p["name"], p["category"], p["stock"]),
                tags=(tag,),
            )


# ============================================================
# === ui/tabs/pos.py ===
# ============================================================
if TYPE_CHECKING:
    from tkinter import ttk
    from ui.main import PosApp


class PosTab(BaseTab):
    """Cart + product grid + checkout."""

    def __init__(self, notebook, app: "PosApp") -> None:
        self._cart: List[Dict[str, Any]] = []
        self._cart_total: float = 0.0
        self._products_cache: List[sqlite3.Row] = []
        super().__init__(notebook, app, " 🛒 POS ")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Left: product grid + search
        left = tk.Frame(self, bg=THEME["bg"], width=480)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        search_row = tk.Frame(left, bg=THEME["bg"])
        search_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            search_row, text="Search:", font=FONT["bold"],
            bg=THEME["bg"], fg=THEME["fg"],
        ).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_products())
        self._search_entry = tk.Entry(
            search_row,
            textvariable=self._search_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=5,
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        section_label(left, "Products").pack(anchor="w")
        self._prod_tree = styled_tree(
            left,
            ["ID", "Name", "Category", "Price", "Stock"],
            [40, 180, 100, 80, 60],
            height=16,
        )
        self._prod_tree.bind("<Double-1>", lambda _e: self._add_to_cart())

        tk.Button(
            left,
            text="+ Add to Cart",
            font=FONT["bold"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._add_to_cart,
        ).pack(pady=(6, 0))

        # Right: cart
        right = tk.Frame(self, bg=THEME["surface"], width=380)
        right.pack(side="right", fill="y", padx=(4, 8), pady=8)
        right.pack_propagate(False)

        section_label(right, "  Cart").pack(anchor="w", padx=8, pady=(8, 4))

        self._cart_tree = styled_tree(
            right,
            ["#", "Product", "Qty", "Price", "Sub"],
            [28, 130, 40, 70, 80],
            height=10,
        )

        # Discount row
        disc_frame = tk.Frame(right, bg=THEME["surface"])
        disc_frame.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(
            disc_frame, text="Coupon:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._coupon_var = tk.StringVar()
        tk.Entry(
            disc_frame,
            textvariable=self._coupon_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=4,
            width=10,
        ).pack(side="left", padx=(4, 2))
        tk.Button(
            disc_frame,
            text="Apply",
            font=FONT["bold"],
            bg=THEME["accent"],
            fg=THEME["bg"],
            relief="flat",
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._apply_coupon,
        ).pack(side="left")
        self._discount_label = tk.Label(
            disc_frame, text="", font=FONT["default"],
            bg=THEME["surface"], fg=THEME["accent2"],
        )
        self._discount_label.pack(side="right")

        # Totals
        total_frame = tk.Frame(right, bg=THEME["surface"])
        total_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            total_frame, text="Total:", font=FONT["heading"],
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._cart_total_var = tk.StringVar(value="0.00")
        tk.Label(
            total_frame,
            textvariable=self._cart_total_var,
            font=FONT["heading"],
            bg=THEME["surface"],
            fg=THEME["accent"],
        ).pack(side="right")

        # Payment method
        pay_frame = tk.Frame(right, bg=THEME["surface"])
        pay_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(
            pay_frame, text="Payment:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._payment_var = tk.StringVar(value=PAYMENT_METHODS[0])
        pay_menu = tk.OptionMenu(pay_frame, self._payment_var, *PAYMENT_METHODS)
        pay_menu.configure(
            font=FONT["default"], bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            relief="flat", highlightthickness=0,
        )
        pay_menu["menu"].configure(
            bg=THEME["entry_bg"], fg=THEME["entry_fg"], font=FONT["default"],
        )
        pay_menu.pack(side="right")

        # Cash paid
        cash_frame = tk.Frame(right, bg=THEME["surface"])
        cash_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            cash_frame, text="Cash paid:", font=FONT["bold"],
            bg=THEME["surface"], fg=THEME["fg"],
        ).pack(side="left")
        self._cash_paid_var = tk.StringVar(value="0")
        tk.Entry(
            cash_frame,
            textvariable=self._cash_paid_var,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=4,
            width=12,
        ).pack(side="right")

        # Action buttons
        btn_frame = tk.Frame(right, bg=THEME["surface"])
        btn_frame.pack(fill="x", padx=8, pady=6)
        btn(btn_frame, "Remove Item", self._remove_item, danger=True, width=13).pack(
            side="left", padx=3
        )
        btn(btn_frame, "Clear Cart", self._clear_cart, danger=True, width=11).pack(
            side="left", padx=3
        )

        tk.Button(
            right,
            text="  Checkout  ",
            font=FONT["title"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            activebackground=THEME["accent"],
            relief="flat",
            pady=12,
            cursor="hand2",
            command=self._checkout,
        ).pack(fill="x", padx=8, pady=(4, 10))

    # ------------------------------------------------------------------
    # Public API (called by PosApp)
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._products_cache = list(self.db.get_all_products())
        self._filter_products()

    def focus_search(self) -> None:
        """Switch notebook to this tab and focus the search field."""
        self.app.notebook.select(self)
        self._search_entry.focus_set()

    def trigger_checkout(self) -> None:
        self._checkout()

    def clear_cart_cmd(self) -> None:
        self._clear_cart()

    # ------------------------------------------------------------------
    # Product list
    # ------------------------------------------------------------------

    def _filter_products(self) -> None:
        query = self._search_var.get().strip().lower()
        self._prod_tree.delete(*self._prod_tree.get_children())
        for i, p in enumerate(self._products_cache):
            if query and query not in p["name"].lower() and query not in p["category"].lower():
                continue
            tag = "even" if i % 2 == 0 else "odd"
            self._prod_tree.insert(
                "",
                "end",
                values=(
                    p["id"],
                    p["name"],
                    p["category"],
                    fmt_currency(p["price"]),
                    p["stock"],
                ),
                tags=(tag,),
            )

    # ------------------------------------------------------------------
    # Cart management
    # ------------------------------------------------------------------

    def _add_to_cart(self) -> None:
        sel = self._prod_tree.selection()
        if not sel:
            messagebox.showinfo(
                "Select Product", "Please select a product first.", parent=self.root
            )
            return
        values = self._prod_tree.item(sel[0], "values")
        product_id = int(values[0])
        product = self.db.get_product_by_id(product_id)
        if not product:
            return
        if product["stock"] <= 0:
            messagebox.showwarning(
                "Out of Stock",
                f"'{product['name']}' is out of stock.",
                parent=self.root,
            )
            return

        qty = simpledialog.askinteger(
            "Quantity",
            f"How many '{product['name']}'?",
            minvalue=1,
            maxvalue=product["stock"],
            parent=self.root,
        )
        if qty is None:
            return

        for item in self._cart:
            if item["product_id"] == product_id:
                new_qty = item["quantity"] + qty
                if new_qty > product["stock"]:
                    messagebox.showwarning(
                        "Insufficient Stock",
                        f"Only {product['stock']} units available.",
                        parent=self.root,
                    )
                    return
                item["quantity"] = new_qty
                item["subtotal"] = item["unit_price"] * new_qty
                self._render_cart()
                return

        self._cart.append(
            {
                "product_id": product_id,
                "product_name": product["name"],
                "quantity": qty,
                "unit_price": product["price"],
                "subtotal": product["price"] * qty,
            }
        )
        self._render_cart()

    def _render_cart(self) -> None:
        self._cart_tree.delete(*self._cart_tree.get_children())
        total = 0.0
        for i, item in enumerate(self._cart, 1):
            tag = "even" if i % 2 == 0 else "odd"
            self._cart_tree.insert(
                "",
                "end",
                values=(
                    i,
                    item["product_name"],
                    item["quantity"],
                    fmt_currency(item["unit_price"]),
                    fmt_currency(item["subtotal"]),
                ),
                tags=(tag,),
            )
            total += item["subtotal"]
        self._cart_total = total
        # Re-apply any active discount to update the displayed total
        self._recalc_total()

    def _remove_item(self) -> None:
        sel = self._cart_tree.selection()
        if not sel:
            return
        idx = self._cart_tree.index(sel[0])
        if 0 <= idx < len(self._cart):
            del self._cart[idx]
            self._render_cart()

    def _clear_cart(self) -> None:
        if self._cart and not messagebox.askyesno(
            "Clear Cart", "Remove all items from cart?", parent=self.root
        ):
            return
        self._cart.clear()
        self._coupon_var.set("")
        self._discount_amount = 0.0
        self._discount_label.configure(text="")
        self._render_cart()

    # ------------------------------------------------------------------
    # Discount / coupon
    # ------------------------------------------------------------------

    def _apply_coupon(self) -> None:
        code = self._coupon_var.get().strip()
        subtotal = sum(i["subtotal"] for i in self._cart)
        discount_amount, final = self.app.order_service.resolve_discount(
            code, subtotal
        )
        if code and discount_amount == 0.0:
            messagebox.showwarning(
                "Invalid Coupon",
                f"Coupon code '{code}' is not valid or has expired.",
                parent=self.root,
            )
            return
        self._discount_amount = discount_amount
        if discount_amount > 0:
            self._discount_label.configure(
                text=f"-{fmt_currency(discount_amount)}"
            )
        else:
            self._discount_label.configure(text="")
        self._recalc_total()

    def _recalc_total(self) -> None:
        discount = getattr(self, "_discount_amount", 0.0)
        subtotal = sum(i["subtotal"] for i in self._cart)
        final = max(0.0, subtotal - discount)
        self._cart_total = final
        self._cart_total_var.set(fmt_currency(final))

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def _checkout(self) -> None:
        if not self._cart:
            messagebox.showinfo(
                "Empty Cart", "Add items to the cart first.", parent=self.root
            )
            return

        payment = self._payment_var.get()
        paid_str = self._cash_paid_var.get().strip()
        paid = 0.0
        if payment == "Cash":
            try:
                paid = float(paid_str)
            except ValueError:
                messagebox.showwarning(
                    "Invalid Amount",
                    "Please enter a valid cash amount.",
                    parent=self.root,
                )
                return
            if paid < self._cart_total:
                messagebox.showwarning(
                    "Insufficient Cash",
                    f"Cash paid ({fmt_currency(paid)}) is less than"
                    f" total ({fmt_currency(self._cart_total)}).",
                    parent=self.root,
                )
                return

        discount_amount = getattr(self, "_discount_amount", 0.0)

        if not messagebox.askyesno(
            "Confirm Checkout",
            f"Total: {fmt_currency(self._cart_total)}\nPayment: {payment}\nProceed?",
            parent=self.root,
        ):
            return

        order_id = self.app.order_service.place_order(
            cashier_id=self.user["id"],
            cashier_name=self.user["username"],
            payment_method=payment,
            items=self._cart,
            discount_amount=discount_amount,
        )

        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=self.user["username"],
            payment_method=payment,
            items=self._cart,
            total=self._cart_total,
            paid=paid,
            discount_amount=discount_amount,
        )
        receipt_text = builder.build()
        receipt_path = builder.save()

        # Show preview and offer to print
        if self._show_receipt_preview(receipt_text):
            printed = print_file(receipt_path)
            print_note = (
                "" if printed else "\n(Print job could not be sent — receipt saved.)"
            )
        else:
            print_note = "\n(Printing skipped.)"

        self.db.add_audit_log(
            self.user["id"],
            self.user["username"],
            "checkout",
            f"Order #{order_id} total={fmt_currency(self._cart_total)} payment={payment}",
        )

        messagebox.showinfo(
            "Order Complete",
            f"Order #{order_id} saved!\nReceipt: {receipt_path}{print_note}",
            parent=self.root,
        )

        self._cart.clear()
        self._discount_amount = 0.0
        self._discount_label.configure(text="")
        self._coupon_var.set("")
        self._cash_paid_var.set("0")
        self._render_cart()
        self.refresh()

        # Refresh related tabs
        self.app.refresh_tab("orders")
        self.app.refresh_tab("dashboard")

    # ------------------------------------------------------------------
    # Receipt preview
    # ------------------------------------------------------------------

    def _show_receipt_preview(self, receipt_text: str) -> bool:
        """Show a receipt preview popup. Returns True if user wants to print."""
        result: Dict[str, bool] = {"print": False}

        dlg = tk.Toplevel(self.root)
        dlg.title("Receipt Preview")
        dlg.configure(bg=THEME["bg"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        txt = tk.Text(
            dlg,
            font=FONT["mono"],
            bg=THEME["surface"],
            fg=THEME["fg"],
            relief="flat",
            bd=8,
            width=46,
            height=28,
        )
        txt.pack(padx=12, pady=(12, 6))
        txt.insert("1.0", receipt_text)
        txt.configure(state="disabled")

        btn_row = tk.Frame(dlg, bg=THEME["bg"])
        btn_row.pack(pady=(0, 12))

        def _print_and_close() -> None:
            result["print"] = True
            dlg.destroy()

        tk.Button(
            btn_row,
            text="Print",
            font=FONT["bold"],
            bg=THEME["accent2"],
            fg=THEME["bg"],
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=_print_and_close,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_row,
            text="Close",
            font=FONT["bold"],
            bg=THEME["surface2"],
            fg=THEME["fg"],
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=dlg.destroy,
        ).pack(side="left", padx=6)

        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        dlg.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        dlg.wait_window()
        return result["print"]


# ============================================================
# === ui/tabs/products.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class ProductsTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 🥗 Products ")

    def _build(self) -> None:
        section_label(self, "Product Management").pack(anchor="w", padx=8, pady=(8, 4))

        self._tree = styled_tree(
            self,
            ["ID", "Name", "Category", "Price", "Stock", "Updated"],
            [50, 200, 110, 90, 70, 160],
            height=18,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Add Product",    self._add).pack(side="left", padx=4)
        btn(btn_row, "Edit Product",   self._edit).pack(side="left", padx=4)
        btn(btn_row, "Delete Product", self._delete, danger=True).pack(side="left", padx=4)
        btn(btn_row, "Refresh",        self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Export CSV",     self._export_csv).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, p in enumerate(self.db.get_all_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                iid=str(p["id"]),
                values=(
                    p["id"], p["name"], p["category"],
                    fmt_currency(p["price"]), p["stock"], p["updated_at"],
                ),
                tags=(tag,),
            )

    def _add(self) -> None:
        dlg = ProductDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.db.add_product(r["name"], r["category"], r["price"], r["stock"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_product", f"name={r['name']}",
                )
                self.refresh()
                self.app.refresh_tab("pos")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Select a product to edit.", parent=self.root)
            return
        product_id = int(sel[0])
        row = self.db.get_product_by_id(product_id)
        if not row:
            return
        dlg = ProductDialog(self.root, product=dict(row))
        if dlg.result:
            r = dlg.result
            try:
                self.db.update_product(
                    product_id, r["name"], r["category"], r["price"], r["stock"]
                )
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_product", f"id={product_id} name={r['name']}",
                )
                self.refresh()
                self.app.refresh_tab("pos")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Select a product to delete.", parent=self.root)
            return
        product_id = int(sel[0])
        row = self.db.get_product_by_id(product_id)
        if not row:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete product '{row['name']}'? This cannot be undone.",
            parent=self.root,
        ):
            return
        self.db.delete_product(product_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_product", f"id={product_id} name={row['name']}",
        )
        self.refresh()
        self.app.refresh_tab("pos")

    def _export_csv(self) -> None:
        products = self.db.get_all_products()
        headers = ["ID", "Name", "Category", "Price", "Stock", "Created", "Updated"]
        rows = [
            (p["id"], p["name"], p["category"], p["price"],
             p["stock"], p["created_at"], p["updated_at"])
            for p in products
        ]
        path = os.path.join(EXPORTS_DIR, f"products_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_products_csv", path
        )
        messagebox.showinfo(
            "Export", f"Products exported to:\n{os.path.abspath(path)}", parent=self.root
        )


# ============================================================
# === ui/tabs/orders.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class OrdersTab(BaseTab):
    """Order history with date/cashier/payment filters and inline detail."""

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📋 Orders ")

    def _build(self) -> None:
        top = tk.Frame(self, bg=THEME["bg"])
        top.pack(fill="both", expand=True, padx=8, pady=8)

        # ---- Filter bar ----
        filter_bar = tk.Frame(top, bg=THEME["surface"], padx=8, pady=6)
        filter_bar.pack(fill="x", pady=(0, 6))

        def _lbl(text: str) -> None:
            tk.Label(
                filter_bar, text=text, font=FONT["bold"],
                bg=THEME["surface"], fg=THEME["fg"],
            ).pack(side="left", padx=(8, 2))

        def _entry(var: tk.StringVar, width: int = 12) -> None:
            tk.Entry(
                filter_bar,
                textvariable=var,
                font=FONT["default"],
                bg=THEME["entry_bg"],
                fg=THEME["entry_fg"],
                insertbackground=THEME["fg"],
                relief="flat",
                bd=4,
                width=width,
            ).pack(side="left", padx=(0, 4))

        self._filter_from = tk.StringVar()
        self._filter_to = tk.StringVar()
        self._filter_cashier = tk.StringVar()
        self._filter_payment = tk.StringVar(value="")

        _lbl("From:")
        _entry(self._filter_from)
        _lbl("To:")
        _entry(self._filter_to)
        _lbl("Cashier:")
        _entry(self._filter_cashier, 10)
        _lbl("Payment:")
        pay_choices = [""] + list(PAYMENT_METHODS)
        pay_menu = tk.OptionMenu(filter_bar, self._filter_payment, *pay_choices)
        pay_menu.configure(
            font=FONT["default"], bg=THEME["entry_bg"], fg=THEME["entry_fg"],
            relief="flat", highlightthickness=0, width=10,
        )
        pay_menu["menu"].configure(
            bg=THEME["entry_bg"], fg=THEME["entry_fg"], font=FONT["default"],
        )
        pay_menu.pack(side="left", padx=4)

        tk.Button(
            filter_bar,
            text="Filter",
            font=FONT["bold"],
            bg=THEME["accent"],
            fg=THEME["bg"],
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._apply_filter,
        ).pack(side="left", padx=4)
        tk.Button(
            filter_bar,
            text="Clear",
            font=FONT["bold"],
            bg=THEME["surface2"],
            fg=THEME["fg"],
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._clear_filter,
        ).pack(side="left", padx=4)

        # ---- Order list ----
        left = tk.Frame(top, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True)

        section_label(left, "Order History").pack(anchor="w", pady=(0, 4))
        self._orders_tree = styled_tree(
            left,
            ["ID", "Date", "Cashier", "Total", "Payment"],
            [50, 160, 120, 100, 110],
            height=18,
        )
        self._orders_tree.bind("<ButtonRelease-1>", lambda _e: self._show_detail())

        btn_row = tk.Frame(left, bg=THEME["bg"])
        btn_row.pack(fill="x", pady=(6, 0))
        btn(btn_row, "Refresh", self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Reprint", self._reprint).pack(side="left", padx=4)

        # ---- Detail panel ----
        right = tk.Frame(top, bg=THEME["surface"], width=340)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        section_label(right, "  Order Detail").pack(anchor="w", padx=8, pady=(8, 4))

        self._detail_tree = styled_tree(
            right,
            ["Product", "Qty", "Price", "Sub"],
            [130, 50, 75, 75],
            height=14,
        )

        self._order_info_var = tk.StringVar(value="Select an order to view details.")
        tk.Label(
            right,
            textvariable=self._order_info_var,
            font=FONT["default"],
            bg=THEME["surface"],
            fg=THEME["fg"],
            justify="left",
            wraplength=320,
        ).pack(padx=8, pady=4)

    def refresh(self) -> None:
        self._orders_tree.delete(*self._orders_tree.get_children())
        orders = self.db.get_all_orders()
        for i, o in enumerate(orders):
            tag = "even" if i % 2 == 0 else "odd"
            self._orders_tree.insert(
                "",
                "end",
                iid=str(o["id"]),
                values=(
                    o["id"],
                    o["created_at"],
                    o["cashier_name"],
                    fmt_currency(o["total"]),
                    o["payment_method"],
                ),
                tags=(tag,),
            )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self) -> None:
        self._orders_tree.delete(*self._orders_tree.get_children())
        orders = self.db.get_orders_filtered(
            date_from=self._filter_from.get().strip(),
            date_to=self._filter_to.get().strip(),
            cashier=self._filter_cashier.get().strip(),
            payment=self._filter_payment.get().strip(),
        )
        for i, o in enumerate(orders):
            tag = "even" if i % 2 == 0 else "odd"
            self._orders_tree.insert(
                "",
                "end",
                iid=str(o["id"]),
                values=(
                    o["id"],
                    o["created_at"],
                    o["cashier_name"],
                    fmt_currency(o["total"]),
                    o["payment_method"],
                ),
                tags=(tag,),
            )

    def _clear_filter(self) -> None:
        self._filter_from.set("")
        self._filter_to.set("")
        self._filter_cashier.set("")
        self._filter_payment.set("")
        self.refresh()

    # ------------------------------------------------------------------
    # Detail / reprint
    # ------------------------------------------------------------------

    def _show_detail(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return

        self._detail_tree.delete(*self._detail_tree.get_children())
        for i, it in enumerate(self.db.get_order_items(order_id)):
            tag = "even" if i % 2 == 0 else "odd"
            self._detail_tree.insert(
                "",
                "end",
                values=(
                    it["product_name"],
                    it["quantity"],
                    fmt_currency(it["unit_price"]),
                    fmt_currency(it["subtotal"]),
                ),
                tags=(tag,),
            )

        discount = order["discount_amount"] if "discount_amount" in order.keys() else 0.0
        discount_line = (
            f"Discount: -{fmt_currency(discount)}\n" if discount else ""
        )
        self._order_info_var.set(
            f"Order #{order['id']}\n"
            f"Date : {order['created_at']}\n"
            f"By   : {order['cashier_name']}\n"
            f"Pay  : {order['payment_method']}\n"
            f"{discount_line}"
            f"Total: {fmt_currency(order['total'])}"
        )

    def _reprint(self) -> None:
        sel = self._orders_tree.selection()
        if not sel:
            messagebox.showinfo("Select Order", "Select an order first.", parent=self.root)
            return
        order_id = int(sel[0])
        order = self.db.get_order_by_id(order_id)
        if not order:
            return
        items = [dict(row) for row in self.db.get_order_items(order_id)]
        discount = order["discount_amount"] if "discount_amount" in order.keys() else 0.0
        builder = ReceiptBuilder(
            order_id=order_id,
            cashier=order["cashier_name"],
            payment_method=order["payment_method"],
            items=items,
            total=order["total"],
            discount_amount=discount,
        )
        path = builder.save()
        ok = print_file(path)
        msg = f"Receipt saved:\n{path}" + ("\n\nPrint job sent." if ok else "")
        messagebox.showinfo("Reprint", msg, parent=self.root)


# ============================================================
# === ui/tabs/users.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class UsersTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 👤 Users ")

    def _build(self) -> None:
        section_label(self, "User Management").pack(anchor="w", padx=8, pady=(8, 4))

        self._tree = styled_tree(
            self,
            ["ID", "Username", "Role", "Created"],
            [50, 200, 100, 180],
            height=18,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Add User",    self._add).pack(side="left", padx=4)
        btn(btn_row, "Edit User",   self._edit).pack(side="left", padx=4)
        btn(btn_row, "Delete User", self._delete, danger=True).pack(side="left", padx=4)
        btn(btn_row, "Refresh",     self.refresh).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, u in enumerate(self.db.get_all_users()):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                iid=str(u["id"]),
                values=(u["id"], u["username"], u["role"], u["created_at"]),
                tags=(tag,),
            )

    def _add(self) -> None:
        dlg = UserDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.db.add_user(r["username"], r["password"], r["role"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_user", f"username={r['username']} role={r['role']}",
                )
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to edit.", parent=self.root)
            return
        user_id = int(sel[0])
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        dlg = UserDialog(self.root, user=dict(row))
        if dlg.result:
            r = dlg.result
            try:
                self.db.update_user(
                    user_id, r["username"], r["password"] or None, r["role"]
                )
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_user", f"id={user_id} username={r['username']}",
                )
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to delete.", parent=self.root)
            return
        user_id = int(sel[0])
        if user_id == self.user["id"]:
            messagebox.showwarning(
                "Cannot Delete", "You cannot delete your own account.", parent=self.root
            )
            return
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        if not messagebox.askyesno(
            "Confirm Delete", f"Delete user '{row['username']}'?", parent=self.root
        ):
            return
        self.db.delete_user(user_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_user", f"id={user_id} username={row['username']}",
        )
        self.refresh()


# ============================================================
# === ui/tabs/audit.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class AuditTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📝 Audit Log ")

    def _build(self) -> None:
        section_label(self, f"Audit Log (last {AUDIT_LOG_LIMIT})").pack(
            anchor="w", padx=8, pady=(8, 4)
        )

        self._tree = styled_tree(
            self,
            ["ID", "Date", "User", "Action", "Details"],
            [50, 160, 110, 130, 350],
            height=20,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Refresh",    self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Export CSV", self._export_csv).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, log in enumerate(self.db.get_audit_logs(AUDIT_LOG_LIMIT)):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(
                    log["id"],
                    log["created_at"],
                    log["username"],
                    log["action"],
                    log["details"] or "",
                ),
                tags=(tag,),
            )

    def _export_csv(self) -> None:
        logs = self.db.get_audit_logs(AUDIT_LOG_LIMIT)
        headers = ["ID", "Date", "User ID", "Username", "Action", "Details"]
        rows = [
            (lg["id"], lg["created_at"], lg["user_id"],
             lg["username"], lg["action"], lg["details"])
            for lg in logs
        ]
        path = os.path.join(EXPORTS_DIR, f"audit_log_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        messagebox.showinfo(
            "Export", f"Audit log exported to:\n{os.path.abspath(path)}", parent=self.root
        )


# ============================================================
# === ui/tabs/settings.py ===
# ============================================================
if TYPE_CHECKING:
    from ui.main import PosApp


class SettingsTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " ⚙ Settings ")

    def _build(self) -> None:
        card = tk.Frame(self, bg=THEME["surface"], padx=30, pady=30)
        card.pack(padx=40, pady=40, anchor="nw")

        section_label(card, "Database").pack(anchor="w", pady=(0, 8))
        btn(card, "Backup Database", self._backup, width=22).pack(anchor="w", pady=4)

        section_label(card, "Folders").pack(anchor="w", pady=(16, 8))
        for label, folder in [
            ("Open Receipts Folder", RECEIPTS_DIR),
            ("Open Backups Folder",  BACKUPS_DIR),
            ("Open Exports Folder",  EXPORTS_DIR),
        ]:
            btn(card, label, lambda f=folder: open_folder(f), width=24).pack(
                anchor="w", pady=4
            )

        section_label(card, "Data Export").pack(anchor="w", pady=(16, 8))
        btn(card, "Export Orders CSV",   self._export_orders,   width=22).pack(anchor="w", pady=4)
        btn(card, "Export Products CSV", self._export_products, width=22).pack(anchor="w", pady=4)

    def refresh(self) -> None:
        pass  # static tab — nothing to refresh

    def _backup(self) -> None:
        try:
            path = backup_db()
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "backup_db", path
            )
            messagebox.showinfo(
                "Backup", f"Database backed up to:\n{os.path.abspath(path)}",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc), parent=self.root)

    def _export_orders(self) -> None:
        orders = self.db.get_all_orders()
        headers = ["ID", "Date", "Cashier ID", "Cashier", "Total", "Discount", "Payment"]
        rows = [
            (o["id"], o["created_at"], o["cashier_id"], o["cashier_name"],
             o["total"], o.get("discount_amount", 0), o["payment_method"])
            for o in orders
        ]
        path = os.path.join(EXPORTS_DIR, f"orders_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_orders_csv", path
        )
        messagebox.showinfo(
            "Export", f"Orders exported to:\n{os.path.abspath(path)}", parent=self.root
        )

    def _export_products(self) -> None:
        products = self.db.get_all_products()
        headers = ["ID", "Name", "Category", "Price", "Stock", "Created", "Updated"]
        rows = [
            (p["id"], p["name"], p["category"], p["price"],
             p["stock"], p["created_at"], p["updated_at"])
            for p in products
        ]
        path = os.path.join(EXPORTS_DIR, f"products_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        self.db.add_audit_log(
            self.user["id"], self.user["username"], "export_products_csv", path
        )
        messagebox.showinfo(
            "Export", f"Products exported to:\n{os.path.abspath(path)}", parent=self.root
        )


# ============================================================
# === ui/login.py ===
# ============================================================
class LoginWindow(tk.Toplevel):
    """Modal login dialog shown at application start."""

    # Class-level stores for rate limiting — shared across instances so that
    # re-showing the login dialog after logout preserves the counters.
    _failed_attempts: ClassVar[Dict[str, int]] = {}
    _lockout_until: ClassVar[Dict[str, float]] = {}

    def __init__(
        self,
        parent: tk.Tk,
        db: Database,
        on_success: Callable[[dict], None],
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.on_success = on_success

        self.title(f"{APP_NAME} — Login")
        self.resizable(False, False)
        self.configure(bg=THEME["bg"])

        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()
        self.transient(parent)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        self._username_entry.focus_set()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        surf = THEME["surface"]

        outer = tk.Frame(self, bg=THEME["bg"], padx=40, pady=40)
        outer.pack()

        card = tk.Frame(outer, bg=surf, padx=35, pady=35)
        card.pack()

        tk.Label(
            card, text=APP_NAME, font=FONT["large"],
            bg=surf, fg=THEME["accent"],
        ).pack()
        tk.Label(
            card, text=f"Point of Sale  v{APP_VERSION}", font=FONT["default"],
            bg=surf, fg=THEME["fg"],
        ).pack(pady=(0, 24))

        tk.Label(card, text="Username", font=FONT["bold"], bg=surf, fg=THEME["fg"]).pack(anchor="w")
        self._username_entry = tk.Entry(
            card,
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=6,
            width=26,
        )
        self._username_entry.pack(fill="x", pady=(2, 12))

        tk.Label(card, text="Password", font=FONT["bold"], bg=surf, fg=THEME["fg"]).pack(anchor="w")
        self._password_entry = tk.Entry(
            card,
            show="*",
            font=FONT["default"],
            bg=THEME["entry_bg"],
            fg=THEME["entry_fg"],
            insertbackground=THEME["fg"],
            relief="flat",
            bd=6,
            width=26,
        )
        self._password_entry.pack(fill="x", pady=(2, 22))

        tk.Button(
            card,
            text="  Login  ",
            font=FONT["bold"],
            bg=THEME["button_bg"],
            fg=THEME["button_fg"],
            activebackground=THEME["accent2"],
            activeforeground=THEME["bg"],
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2",
            command=self._attempt_login,
        ).pack(fill="x")

        self.bind("<Return>", lambda _e: self._attempt_login())

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _attempt_login(self) -> None:
        username = self._username_entry.get().strip()
        password = self._password_entry.get()

        if not username or not password:
            messagebox.showwarning(
                "Input Required",
                "Please enter both username and password.",
                parent=self,
            )
            return

        # --- Rate limiting ---
        now = time.monotonic()
        lockout_end = self._lockout_until.get(username, 0)
        if now < lockout_end:
            remaining = int(lockout_end - now)
            messagebox.showerror(
                "Account Locked",
                f"Too many failed attempts.\nTry again in {remaining} second(s).",
                parent=self,
            )
            self._password_entry.delete(0, "end")
            return

        # --- Credential check ---
        user_row = self.db.get_user_by_username(username)
        if not user_row or not check_password(password, user_row["password_hash"]):
            attempts = self._failed_attempts.get(username, 0) + 1
            self._failed_attempts[username] = attempts

            if attempts >= MAX_LOGIN_ATTEMPTS:
                self._lockout_until[username] = now + LOGIN_LOCKOUT_SECONDS
                self._failed_attempts[username] = 0
                minutes = LOGIN_LOCKOUT_SECONDS // 60
                messagebox.showerror(
                    "Account Locked",
                    f"Too many failed attempts.\n"
                    f"This username is locked for {minutes} minute(s).",
                    parent=self,
                )
                logger.warning(
                    "Account '%s' locked after %d failed login attempts.",
                    username, MAX_LOGIN_ATTEMPTS,
                )
            else:
                remaining_attempts = MAX_LOGIN_ATTEMPTS - attempts
                messagebox.showerror(
                    "Login Failed",
                    f"Invalid username or password.\n"
                    f"{remaining_attempts} attempt(s) remaining before lockout.",
                    parent=self,
                )
                logger.warning(
                    "Failed login attempt for '%s' (%d/%d).",
                    username, attempts, MAX_LOGIN_ATTEMPTS,
                )

            self._password_entry.delete(0, "end")
            return

        # --- Success ---
        self._failed_attempts.pop(username, None)
        self._lockout_until.pop(username, None)
        logger.info("User '%s' logged in successfully.", username)

        user = {
            "id": user_row["id"],
            "username": user_row["username"],
            "role": user_row["role"],
        }
        self.destroy()
        self.on_success(user)

    def _on_close(self) -> None:
        """Closing the login window exits the application."""
        self.master.destroy()


# ============================================================
# === ui/main.py ===
# ============================================================
class PosApp:
    """Root application controller — builds the window and all tabs."""

    _SESSION_CHECK_INTERVAL_MS = 30_000  # check every 30 s

    def __init__(self, root: tk.Tk, db: Database, user: dict) -> None:
        self.root = root
        self.db = db
        self.user = user
        self.is_admin = user["role"] == "admin"

        # Services
        self.order_service = OrderService(db)
        self.product_service = ProductService(db)
        self.report_service = ReportService(db)

        # Tab registry
        self._tabs: Dict[str, BaseTab] = {}

        self._configure_root()
        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._setup_session_timeout()
        self._initial_refresh()

        logger.info("User '%s' opened main window.", user["username"])

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title(
            f"{APP_NAME} v{APP_VERSION}  —  {self.user['username']}  [{self.user['role']}]"
        )
        self.root.configure(bg=THEME["bg"])
        self.root.geometry("1200x720")
        self.root.minsize(900, 600)
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 1200, 720
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ------------------------------------------------------------------
    # UI skeleton
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header bar
        header = tk.Frame(self.root, bg=THEME["surface"], height=48)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"  {APP_NAME}",
            font=FONT["heading"],
            bg=THEME["surface"],
            fg=THEME["accent"],
        ).pack(side="left", padx=10)

        tk.Label(
            header,
            text=f"Logged in: {self.user['username']}  ({self.user['role']})",
            font=FONT["default"],
            bg=THEME["surface"],
            fg=THEME["fg"],
        ).pack(side="right", padx=20)

        tk.Button(
            header,
            text="Logout",
            font=FONT["bold"],
            bg=THEME["danger"],
            fg=THEME["bg"],
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._logout,
        ).pack(side="right", padx=10)

        # Notebook
        style = ttk.Style()
        style.configure("Dark.TNotebook", background=THEME["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=THEME["surface"],
            foreground=THEME["fg"],
            font=FONT["bold"],
            padding=(12, 6),
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", THEME["accent"])],
            foreground=[("selected", THEME["bg"])],
        )

        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

        # Build tabs
        self._tabs["pos"] = PosTab(self.notebook, self)
        self._tabs["orders"] = OrdersTab(self.notebook, self)
        self._tabs["dashboard"] = DashboardTab(self.notebook, self)

        if self.is_admin:
            self._tabs["products"] = ProductsTab(self.notebook, self)
            self._tabs["users"] = UsersTab(self.notebook, self)
            self._tabs["audit"] = AuditTab(self.notebook, self)
            self._tabs["settings"] = SettingsTab(self.notebook, self)

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------

    def get_tab(self, name: str) -> Optional[BaseTab]:
        return self._tabs.get(name)

    def refresh_tab(self, name: str) -> None:
        tab = self._tabs.get(name)
        if tab:
            tab.refresh()

    def _initial_refresh(self) -> None:
        for tab in self._tabs.values():
            tab.refresh()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_keyboard_shortcuts(self) -> None:
        """Bind global hotkeys.

        F1  — switch to POS tab and focus product search
        F2  — trigger checkout (only when on POS tab)
        F5  — refresh the currently visible tab
        Esc — clear the cart (only when on POS tab)
        """
        self.root.bind("<F1>", self._kb_focus_search)
        self.root.bind("<F2>", self._kb_checkout)
        self.root.bind("<F5>", self._kb_refresh)
        self.root.bind("<Escape>", self._kb_clear_cart)

    def _kb_focus_search(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos:
            pos.focus_search()  # type: ignore[attr-defined]

    def _kb_checkout(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos and self._current_tab_name() == "pos":
            pos.trigger_checkout()  # type: ignore[attr-defined]

    def _kb_refresh(self, _event=None) -> None:
        name = self._current_tab_name()
        if name:
            self.refresh_tab(name)

    def _kb_clear_cart(self, _event=None) -> None:
        pos = self._tabs.get("pos")
        if pos and self._current_tab_name() == "pos":
            pos.clear_cart_cmd()  # type: ignore[attr-defined]

    def _current_tab_name(self) -> Optional[str]:
        """Return the key of the currently selected tab, or None."""
        try:
            selected = self.notebook.select()
            for name, tab in self._tabs.items():
                if str(tab) == selected:
                    return name
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Session timeout
    # ------------------------------------------------------------------

    def _setup_session_timeout(self) -> None:
        self._last_activity = time.monotonic()
        self.root.bind_all("<KeyPress>", self._on_activity, add=True)
        self.root.bind_all("<ButtonPress>", self._on_activity, add=True)
        self._session_after_id: Optional[str] = None
        self._schedule_session_check()

    def _on_activity(self, _event=None) -> None:
        self._last_activity = time.monotonic()

    def _schedule_session_check(self) -> None:
        self._session_after_id = self.root.after(
            self._SESSION_CHECK_INTERVAL_MS, self._check_session
        )

    def _check_session(self) -> None:
        elapsed_minutes = (time.monotonic() - self._last_activity) / 60
        if elapsed_minutes >= SESSION_TIMEOUT_MINUTES:
            logger.info(
                "Session timeout for user '%s' after %.1f min idle.",
                self.user["username"],
                elapsed_minutes,
            )
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "session_timeout", ""
            )
            messagebox.showinfo(
                "Session Expired",
                f"Your session expired after {SESSION_TIMEOUT_MINUTES} minutes of inactivity.\n"
                "Please log in again.",
                parent=self.root,
            )
            self.root.destroy()
            return
        self._schedule_session_check()

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def _logout(self) -> None:
        if messagebox.askyesno(
            "Logout", "Log out and return to login screen?", parent=self.root
        ):
            if self._session_after_id:
                self.root.after_cancel(self._session_after_id)
            self.db.add_audit_log(
                self.user["id"], self.user["username"], "logout", ""
            )
            logger.info("User '%s' logged out.", self.user["username"])
            self.root.destroy()


# ============================================================
# === app.py ===
# ============================================================
def main() -> None:
    """Initialise directories, database, and the Tkinter event loop."""
    ensure_dirs()
    logger.info("RezaFood POS starting up.")

    db = Database()

    # The root window is hidden; it is used as a transient parent for the
    # login dialog and later replaced by the main application window.
    root = tk.Tk()
    root.withdraw()

    def on_login_success(user: dict) -> None:
        """Callback fired when the user authenticates successfully."""
        db.add_audit_log(user["id"], user["username"], "login", "")

        # Build a fresh Tk window for the main app
        app_root = tk.Tk()
        PosApp(app_root, db, user)
        app_root.protocol("WM_DELETE_WINDOW", lambda: _on_close(app_root, db))
        app_root.mainloop()

        # After the main window closes, re-open the login dialog so another
        # user can log in without restarting the process.
        _restart_login(root, db)

    def _on_close(window: tk.Tk, database: Database) -> None:
        window.destroy()

    def _restart_login(parent: tk.Tk, database: Database) -> None:
        parent.deiconify()
        LoginWindow(parent, database, on_login_success)

    LoginWindow(root, db, on_login_success)
    root.mainloop()


if __name__ == "__main__":
    main()

