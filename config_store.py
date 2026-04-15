"""Persistent user-configurable settings backed by a JSON file.

Settings that users adjust at runtime (backup paths, sync preferences,
auto-backup schedules) are stored here rather than in ``config.py`` so
that they survive application restarts without editing source code.

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

import json
import os
import threading
from typing import Any, Dict

_SETTINGS_FILE = "rezafood_settings.json"

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
# Public API
# ---------------------------------------------------------------------------

def load() -> Dict[str, Any]:
    """Return all settings, merging persisted values with defaults."""
    if os.path.isfile(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            return {**_DEFAULTS, **data}
        except Exception:
            pass  # corrupt file → fall back to defaults
    return dict(_DEFAULTS)


def save(settings: Dict[str, Any]) -> None:
    """Persist *settings* to disk (full replacement)."""
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get(key: str) -> Any:
    """Return the current value of *key*, falling back to its default."""
    return load().get(key, _DEFAULTS.get(key))


def set(key: str, value: Any) -> None:  # noqa: A001
    """Persist a single *key* / *value* pair (thread-safe)."""
    with _lock:
        data = load()
        data[key] = value
        save(data)
