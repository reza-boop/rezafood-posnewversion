"""Tests for config_store.py."""

from __future__ import annotations

import json
import os
import threading

import pytest

import config_store


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Redirect the settings file into a temp directory for each test."""
    settings_file = str(tmp_path / "rezafood_settings.json")
    monkeypatch.setattr(config_store, "_SETTINGS_FILE", settings_file)
    yield settings_file


class TestConfigStore:

    def test_load_returns_defaults_when_no_file(self):
        data = config_store.load()
        assert data["auto_backup_enabled"] is False
        assert data["auto_backup_interval_minutes"] == 60
        assert data["remote_backup_path"] == ""
        assert data["sync_enabled"] is False

    def test_save_and_load_round_trip(self):
        config_store.save({"auto_backup_enabled": True, "remote_backup_path": "/mnt/share"})
        data = config_store.load()
        assert data["auto_backup_enabled"] is True
        assert data["remote_backup_path"] == "/mnt/share"
        # Keys not in saved dict still come back with defaults
        assert data["auto_backup_interval_minutes"] == 60

    def test_get_returns_default_for_unknown_key(self):
        val = config_store.get("nonexistent_key_xyz")
        assert val is None

    def test_set_persists_single_value(self):
        config_store.set("auto_backup_interval_minutes", 120)
        assert config_store.get("auto_backup_interval_minutes") == 120

    def test_set_does_not_clobber_other_keys(self):
        config_store.set("sync_enabled", True)
        config_store.set("remote_backup_path", "/tmp/r")
        assert config_store.get("sync_enabled") is True
        assert config_store.get("remote_backup_path") == "/tmp/r"

    def test_corrupt_file_falls_back_to_defaults(self, _isolated_settings):
        with open(_isolated_settings, "w") as f:
            f.write("not valid json {{")
        data = config_store.load()
        assert data == config_store._DEFAULTS

    def test_set_is_thread_safe(self):
        """Concurrent set() calls must not lose each other's updates."""
        keys = [f"key_{i}" for i in range(20)]
        errors: list[Exception] = []

        def writer(key: str) -> None:
            try:
                config_store.set(key, True)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(k,)) for k in keys]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors during concurrent set(): {errors}"
        for key in keys:
            assert config_store.get(key) is True, f"Key '{key}' was lost after concurrent writes"
