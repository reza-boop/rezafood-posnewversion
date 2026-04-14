"""Cloud / remote backup management with optional auto-backup scheduling.

Responsibilities
----------------
* Create local ``.zip`` backups (wraps :func:`utils.backup_db`).
* Copy (upload) a backup archive to a user-configured remote path (e.g.
  a network share, mounted cloud drive, or any directory the OS can
  write to).
* Run a background thread that performs automatic backups at a
  configurable interval.

This is intentionally decoupled from the UI and the database layer: the
Settings tab calls methods here; the service emits no GUI events and
accesses no Tkinter widgets.
"""

from __future__ import annotations

import os
import shutil
import threading
import zipfile
from typing import Optional

import config_store
from config import BACKUPS_DIR, DB_NAME
from utils import ensure_dirs, now_str, time_stamp


class BackupService:
    """Manages local ZIP backups, remote-path uploads, and auto-backup.

    Args:
        db_name: Path to the SQLite database file to back up.
                 Defaults to :data:`config.DB_NAME`.
    """

    def __init__(self, db_name: str = DB_NAME) -> None:
        self._db_name = db_name
        self._last_backup_path: Optional[str] = None
        self._last_backup_time: Optional[str] = None
        self._auto_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Backup creation
    # ------------------------------------------------------------------

    def create_zip_backup(self) -> str:
        """Create a timestamped ZIP archive of the database in *backups/*.

        Returns the path to the newly created ``.zip`` file.

        Raises:
            FileNotFoundError: If the database file does not exist.
        """
        if not os.path.isfile(self._db_name):
            raise FileNotFoundError(f"Database not found: {self._db_name}")

        ensure_dirs()
        stamp = time_stamp()
        zip_path = os.path.join(BACKUPS_DIR, f"rezafood_backup_{stamp}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(self._db_name, os.path.basename(self._db_name))

        self._last_backup_path = zip_path
        self._last_backup_time = now_str()
        return zip_path

    # ------------------------------------------------------------------
    # Remote upload
    # ------------------------------------------------------------------

    def upload_to_remote_path(self, remote_path: str) -> str:
        """Create a ZIP backup and copy it to *remote_path*.

        *remote_path* must be a directory that already exists (e.g. a
        network share or a mounted cloud-sync folder).

        Returns the full destination path of the uploaded archive.

        Raises:
            ValueError: If *remote_path* is empty.
            FileNotFoundError: If *remote_path* is not an accessible directory.
        """
        remote_path = remote_path.strip()
        if not remote_path:
            raise ValueError("Remote backup path is not configured.")
        if not os.path.isdir(remote_path):
            raise FileNotFoundError(
                f"Remote backup directory does not exist or is not accessible:\n{remote_path}"
            )

        zip_path = self.create_zip_backup()
        dst = os.path.join(remote_path, os.path.basename(zip_path))
        shutil.copy2(zip_path, dst)
        return dst

    # ------------------------------------------------------------------
    # Auto-backup (background thread)
    # ------------------------------------------------------------------

    def start_auto_backup(
        self,
        interval_minutes: int,
        remote_path: str = "",
    ) -> None:
        """Start a background thread that backs up every *interval_minutes*.

        If *remote_path* is set and accessible, each cycle also uploads
        to that path; otherwise only a local ZIP is created.

        Calling this while already running first stops the previous thread.
        """
        self.stop_auto_backup()
        self._stop_event.clear()
        self._auto_thread = threading.Thread(
            target=self._auto_loop,
            args=(interval_minutes, remote_path),
            daemon=True,
            name="BackupService-auto",
        )
        self._auto_thread.start()

    def stop_auto_backup(self) -> None:
        """Stop the auto-backup background thread (if running)."""
        self._stop_event.set()
        if self._auto_thread and self._auto_thread.is_alive():
            self._auto_thread.join(timeout=2)
        self._auto_thread = None

    @property
    def auto_backup_running(self) -> bool:
        """True if the auto-backup thread is currently active."""
        return self._auto_thread is not None and self._auto_thread.is_alive()

    # ------------------------------------------------------------------
    # Last-backup metadata
    # ------------------------------------------------------------------

    @property
    def last_backup_path(self) -> Optional[str]:
        """Path of the most recently created backup archive, or ``None``."""
        return self._last_backup_path

    @property
    def last_backup_time(self) -> Optional[str]:
        """Timestamp string of the last backup, or ``None``."""
        return self._last_backup_time

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _auto_loop(self, interval_minutes: int, remote_path: str) -> None:
        """Background loop: sleep then backup, until stopped."""
        interval_seconds = interval_minutes * 60
        while not self._stop_event.wait(timeout=interval_seconds):
            try:
                if remote_path and os.path.isdir(remote_path):
                    self.upload_to_remote_path(remote_path)
                else:
                    self.create_zip_backup()
            except Exception:
                pass  # never crash the background thread
