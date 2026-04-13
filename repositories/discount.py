"""Discount CRUD operations."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from utils import now_str
from db import DuplicateError
from repositories.base import BaseRepository


class DiscountRepository(BaseRepository):
    """Manages all persistence operations for the *discounts* table."""

    def get_by_code(self, code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts WHERE code=? AND active=1",
            (code.strip().upper(),),
        ).fetchone()

    def get_all(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM discounts ORDER BY id DESC"
        ).fetchall()

    def add(
        self, code: str, dtype: str, value: float, active: bool = True
    ) -> None:
        ts = now_str()
        try:
            self.conn.execute(
                "INSERT INTO discounts (code, type, value, active, created_at)"
                " VALUES (?,?,?,?,?)",
                (code.strip().upper(), dtype, value, int(active), ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(
                f"Discount code '{code.strip().upper()}' already exists."
            ) from exc

    def update(
        self,
        discount_id: int,
        code: str,
        dtype: str,
        value: float,
        active: bool,
    ) -> None:
        self.conn.execute(
            "UPDATE discounts SET code=?, type=?, value=?, active=? WHERE id=?",
            (code.strip().upper(), dtype, value, int(active), discount_id),
        )
        self.conn.commit()

    def delete(self, discount_id: int) -> None:
        self.conn.execute("DELETE FROM discounts WHERE id=?", (discount_id,))
        self.conn.commit()
