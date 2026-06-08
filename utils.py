"""Utility helpers: time, money, hashing, printing, folder operations, CSV export."""

from __future__ import annotations

import csv
import hashlib
import hmac
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any, Optional, Sequence

from config import BACKUPS_DIR, DB_NAME, EXPORTS_DIR, LOGIN_LOCKOUT_SECONDS, MAX_LOGIN_ATTEMPTS, RECEIPTS_DIR

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

    def idle_seconds(self) -> float:
        """Return current idle duration in seconds (0 when logged out)."""
        with self._lock:
            if self._user_id is None:
                return 0.0
            return time.monotonic() - self._last_active

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
