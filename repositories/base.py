"""Base class shared by all repository classes."""

from __future__ import annotations

import sqlite3


class BaseRepository:
    """Holds the shared SQLite connection used by all repositories."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn
