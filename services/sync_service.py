"""Multi-terminal sync via a shared SQLite database file.

Strategy
--------
Multiple POS terminals can share a single SQLite file stored on a
network drive (NFS, SMB/CIFS, etc.).  SQLite's WAL journal mode
(already enabled via ``PRAGMA journal_mode=WAL`` in :class:`db.Database`)
makes concurrent access safe for multiple readers / one writer.

:class:`SyncService` watches the shared database file's modification
time in a background thread.  When it detects that another terminal
has written to the file it calls the registered *on_change* callback so
the local UI can refresh stale data.

Usage::

    sync = SyncService(on_change=app.refresh_all_tabs)
    sync.start("/mnt/shared/rezafood.db", poll_seconds=30)
    ...
    sync.stop()
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional


class SyncService:
    """Poll a shared SQLite file for external modifications.

    Args:
        on_change: Zero-argument callable invoked (from the polling thread)
                   whenever the shared file's mtime changes.  The callback
                   is responsible for thread-safely scheduling any UI
                   updates (e.g. via ``root.after(0, ...)``) because
                   Tkinter widgets may only be touched from the main thread.
    """

    def __init__(self, on_change: Callable[[], None]) -> None:
        self._on_change = on_change
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._shared_path: Optional[str] = None
        self._last_mtime: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, shared_db_path: str, poll_seconds: int = 30) -> None:
        """Begin polling *shared_db_path* for changes every *poll_seconds*.

        Raises:
            FileNotFoundError: If *shared_db_path* does not point to an
                               existing file at call time.
        """
        self.stop()
        if not os.path.isfile(shared_db_path):
            raise FileNotFoundError(
                f"Shared database not found: {shared_db_path}"
            )
        self._shared_path = shared_db_path
        self._last_mtime = os.path.getmtime(shared_db_path)
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            args=(shared_db_path, poll_seconds),
            daemon=True,
            name="SyncService-poll",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the polling thread gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._shared_path = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """``True`` if the sync thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def shared_path(self) -> Optional[str]:
        """The path being monitored, or ``None`` when stopped."""
        return self._shared_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll_loop(self, path: str, poll_seconds: int) -> None:
        while not self._stop_event.wait(timeout=poll_seconds):
            try:
                mtime = os.path.getmtime(path)
                if mtime != self._last_mtime:
                    self._last_mtime = mtime
                    self._on_change()
            except FileNotFoundError:
                pass  # shared drive temporarily unmounted — keep trying
            except Exception:
                pass  # never crash the background thread
