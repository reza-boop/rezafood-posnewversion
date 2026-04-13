"""Audit-log persistence operations."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from utils import now_str
from repositories.base import BaseRepository


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
