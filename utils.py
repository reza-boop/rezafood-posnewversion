"""Utility helpers: time, money, hashing, printing, folder operations, CSV export."""

from __future__ import annotations

import csv
import hashlib
import hmac
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Any, Sequence

from config import BACKUPS_DIR, DB_NAME, EXPORTS_DIR, RECEIPTS_DIR

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
