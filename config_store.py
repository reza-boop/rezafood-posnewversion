"""Persistent user-configurable settings backed by a JSON file.

Settings that users adjust at runtime (backup paths, sync preferences,
auto-backup schedules) are stored here rather than in ``config.py`` so
that they survive application restarts without editing source code.

The file is protected by an HMAC-SHA256 integrity tag so that out-of-band
edits are detected on the next load.  The secret key is generated once and
stored in *rezafood_settings.key* (next to the settings JSON).  If the key
or the tag is missing or invalid the file is considered untrusted and the
application falls back to safe defaults.

Usage::

    import config_store

    # Read a value
    path = config_store.get("remote_backup_path")

    # Write a value
    config_store.set("auto_backup_enabled", True)

    # Read or write the whole dict at once
    all_settings = config_store.load()
    config_store.save(all_settings)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
from typing import Any, Dict

_SETTINGS_FILE = "rezafood_settings.json"
_KEY_FILE = "rezafood_settings.key"

_logger = logging.getLogger(__name__)

# Module-level lock so that concurrent set() calls never interleave their
# read-modify-write cycle and lose each other's updates.
_lock = threading.Lock()

# Default values for every recognised key.
_DEFAULTS: Dict[str, Any] = {
    # Cloud / remote backup
    "auto_backup_enabled": False,
    "auto_backup_interval_minutes": 60,
    "remote_backup_path": "",
    # Multi-terminal sync
    "sync_enabled": False,
    "sync_shared_db_path": "",
    "sync_poll_interval_seconds": 30,
}


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------

def _load_key() -> bytes:
    """Return the HMAC key, generating and persisting one on the first call."""
    if os.path.isfile(_KEY_FILE):
        try:
            with open(_KEY_FILE, "rb") as f:
                return bytes.fromhex(f.read().decode("ascii").strip())
        except Exception:
            _logger.warning(
                "Settings key file '%s' is corrupted — generating a new key. "
                "All previously signed settings files will fail integrity checks "
                "and fall back to defaults.",
                _KEY_FILE,
            )
    key = os.urandom(32)
    try:
        with open(_KEY_FILE, "wb") as f:
            f.write(key.hex().encode("ascii"))
    except Exception:
        _logger.critical(
            "Could not persist settings key to '%s'. "
            "Integrity verification will fail on every restart until the key "
            "file can be written.",
            _KEY_FILE,
        )
    return key


def _compute_mac(data_bytes: bytes) -> str:
    """Return the HMAC-SHA256 hex digest of *data_bytes*."""
    return hmac.new(_load_key(), data_bytes, hashlib.sha256).hexdigest()


def _canonical(settings: Dict[str, Any]) -> bytes:
    """Return a stable JSON encoding of *settings* suitable for signing."""
    return json.dumps(settings, indent=2, ensure_ascii=False, sort_keys=True).encode()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load() -> Dict[str, Any]:
    """Return all settings, merging persisted values with defaults.

    If the file is missing, corrupt, or fails the integrity check the
    application falls back to safe defaults.
    """
    if os.path.isfile(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, encoding="utf-8") as f:
                raw: Any = json.load(f)

            # New format: {"_mac": "...", "settings": {...}}
            if isinstance(raw, dict) and "_mac" in raw and "settings" in raw:
                settings: Dict[str, Any] = raw["settings"]
                expected = _compute_mac(_canonical(settings))
                if not hmac.compare_digest(raw["_mac"], expected):
                    # Integrity check failed — tampered or key rotated
                    return dict(_DEFAULTS)
                return {**_DEFAULTS, **settings}

            # Legacy plain-dict format (first run after upgrade) — accept once
            if isinstance(raw, dict):
                return {**_DEFAULTS, **raw}

        except Exception:
            pass  # corrupt file → fall back to defaults
    return dict(_DEFAULTS)


def save(settings: Dict[str, Any]) -> None:
    """Persist *settings* to disk with an HMAC integrity tag."""
    payload = _canonical(settings)
    mac = _compute_mac(payload)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"_mac": mac, "settings": settings}, f, indent=2, ensure_ascii=False)


def get(key: str) -> Any:
    """Return the current value of *key*, falling back to its default."""
    return load().get(key, _DEFAULTS.get(key))


def set(key: str, value: Any) -> None:  # noqa: A001
    """Persist a single *key* / *value* pair (thread-safe)."""
    with _lock:
        data = load()
        data[key] = value
        save(data)
