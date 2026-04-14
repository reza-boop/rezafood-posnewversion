"""Tests for services/backup_service.py and services/sync_service.py."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import zipfile

import pytest

from services.backup_service import BackupService
from services.sync_service import SyncService


# ---------------------------------------------------------------------------
# BackupService
# ---------------------------------------------------------------------------


class TestBackupService:
    """Unit tests for BackupService using a temp directory."""

    @pytest.fixture()
    def tmp(self, tmp_path):
        """Return a temp dir with a minimal 'database' file."""
        db = tmp_path / "test.db"
        db.write_bytes(b"SQLite format 3\x00" + b"\x00" * 48)
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        return tmp_path, db, backups_dir

    @pytest.fixture()
    def svc(self, tmp, monkeypatch):
        """Return a BackupService wired to the temp db and backups dir."""
        tmp_path, db, backups_dir = tmp
        monkeypatch.setattr("services.backup_service.BACKUPS_DIR", str(backups_dir))
        monkeypatch.setattr(
            "services.backup_service.ensure_dirs",
            lambda: backups_dir.mkdir(exist_ok=True),
        )
        return BackupService(db_name=str(db))

    # -- create_zip_backup --------------------------------------------------

    def test_create_zip_backup_returns_zip_path(self, svc, tmp):
        tmp_path, db, backups_dir = tmp
        path = svc.create_zip_backup()
        assert path.endswith(".zip")
        assert os.path.isfile(path)

    def test_zip_backup_contains_db(self, svc, tmp):
        _, db, _ = tmp
        path = svc.create_zip_backup()
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert os.path.basename(str(db)) in names

    def test_last_backup_time_updated(self, svc):
        assert svc.last_backup_time is None
        svc.create_zip_backup()
        assert svc.last_backup_time is not None

    def test_last_backup_path_updated(self, svc):
        assert svc.last_backup_path is None
        path = svc.create_zip_backup()
        assert svc.last_backup_path == path

    def test_missing_db_raises(self, tmp, monkeypatch):
        tmp_path, db, backups_dir = tmp
        monkeypatch.setattr("services.backup_service.BACKUPS_DIR", str(backups_dir))
        monkeypatch.setattr(
            "services.backup_service.ensure_dirs",
            lambda: backups_dir.mkdir(exist_ok=True),
        )
        svc = BackupService(db_name=str(tmp_path / "nonexistent.db"))
        with pytest.raises(FileNotFoundError):
            svc.create_zip_backup()

    # -- upload_to_remote_path ----------------------------------------------

    def test_upload_copies_zip_to_remote(self, svc, tmp):
        tmp_path, _, _ = tmp
        remote = tmp_path / "remote"
        remote.mkdir()
        dst = svc.upload_to_remote_path(str(remote))
        assert os.path.isfile(dst)
        assert dst.endswith(".zip")

    def test_upload_empty_path_raises(self, svc):
        with pytest.raises(ValueError, match="not configured"):
            svc.upload_to_remote_path("")

    def test_upload_nonexistent_path_raises(self, svc):
        with pytest.raises(FileNotFoundError):
            svc.upload_to_remote_path("/nonexistent/path/xyz123")

    # -- auto-backup thread -------------------------------------------------

    def test_auto_backup_not_running_initially(self, svc):
        assert not svc.auto_backup_running

    def test_auto_backup_start_and_stop(self, svc):
        svc.start_auto_backup(interval_minutes=9999)
        assert svc.auto_backup_running
        svc.stop_auto_backup()
        assert not svc.auto_backup_running

    def test_stop_without_start_is_safe(self, svc):
        svc.stop_auto_backup()  # must not raise
        assert not svc.auto_backup_running


# ---------------------------------------------------------------------------
# SyncService
# ---------------------------------------------------------------------------


class TestSyncService:
    """Unit tests for SyncService using temp files."""

    @pytest.fixture()
    def shared_db(self, tmp_path):
        """A temp file that acts as the shared database."""
        f = tmp_path / "shared.db"
        f.write_bytes(b"data")
        return str(f)

    def test_not_running_initially(self, shared_db):
        svc = SyncService(on_change=lambda: None)
        assert not svc.is_running
        assert svc.shared_path is None

    def test_start_sets_running(self, shared_db):
        svc = SyncService(on_change=lambda: None)
        svc.start(shared_db, poll_seconds=9999)
        assert svc.is_running
        assert svc.shared_path == shared_db
        svc.stop()

    def test_stop_clears_running(self, shared_db):
        svc = SyncService(on_change=lambda: None)
        svc.start(shared_db, poll_seconds=9999)
        svc.stop()
        assert not svc.is_running
        assert svc.shared_path is None

    def test_start_nonexistent_file_raises(self, tmp_path):
        svc = SyncService(on_change=lambda: None)
        with pytest.raises(FileNotFoundError):
            svc.start(str(tmp_path / "no_such.db"))

    def test_stop_without_start_is_safe(self, shared_db):
        svc = SyncService(on_change=lambda: None)
        svc.stop()  # must not raise

    def test_double_start_replaces_thread(self, shared_db):
        svc = SyncService(on_change=lambda: None)
        svc.start(shared_db, poll_seconds=9999)
        thread1 = svc._thread
        svc.start(shared_db, poll_seconds=9999)
        assert svc._thread is not thread1
        svc.stop()

    def test_callback_fires_on_file_change(self, tmp_path):
        """Modify the shared file and verify the callback is invoked."""
        shared = tmp_path / "live.db"
        shared.write_bytes(b"initial")

        fired: list[int] = []
        svc = SyncService(on_change=lambda: fired.append(1))
        svc.start(str(shared), poll_seconds=1)

        # Wait briefly, then mutate the file
        time.sleep(0.2)
        shared.write_bytes(b"updated content")

        # Give the poll loop time to detect the change
        deadline = time.monotonic() + 4
        while not fired and time.monotonic() < deadline:
            time.sleep(0.05)

        svc.stop()
        assert fired, "Callback was not fired after file was modified"
