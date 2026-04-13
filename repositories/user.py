"""User CRUD operations."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from utils import hash_password, now_str
from db import DuplicateError
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Manages all persistence operations for the *users* table."""

    def get_by_username(self, username: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()

    def add(self, username: str, password: str, role: str) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at)"
                " VALUES (?,?,?,?)",
                (username, hash_password(password), role, ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Username '{username}' already exists.") from exc

    def update(
        self,
        user_id: int,
        username: str,
        password: Optional[str],
        role: str,
    ) -> None:
        try:
            if password:
                self.conn.execute(
                    "UPDATE users SET username=?, password_hash=?, role=? WHERE id=?",
                    (username, hash_password(password), role, user_id),
                )
            else:
                self.conn.execute(
                    "UPDATE users SET username=?, role=? WHERE id=?",
                    (username, role, user_id),
                )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Username '{username}' already exists.") from exc

    def delete(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"]
