"""Audit log tab — activity history and CSV export (admin only)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from config import AUDIT_LOG_LIMIT, EXPORTS_DIR, THEME
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree
from utils import export_to_csv, time_stamp

if TYPE_CHECKING:
    from ui.main import PosApp


class AuditTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📝 Audit Log ")

    def _build(self) -> None:
        section_label(self, f"Audit Log (last {AUDIT_LOG_LIMIT})").pack(
            anchor="w", padx=8, pady=(8, 4)
        )

        self._tree = styled_tree(
            self,
            ["ID", "Date", "User", "Action", "Details"],
            [50, 160, 110, 130, 350],
            height=20,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Refresh",    self.refresh).pack(side="left", padx=4)
        btn(btn_row, "Export CSV", self._export_csv).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, log in enumerate(self.db.get_audit_logs(AUDIT_LOG_LIMIT)):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(
                    log["id"],
                    log["created_at"],
                    log["username"],
                    log["action"],
                    log["details"] or "",
                ),
                tags=(tag,),
            )

    def _export_csv(self) -> None:
        logs = self.db.get_audit_logs(AUDIT_LOG_LIMIT)
        headers = ["ID", "Date", "User ID", "Username", "Action", "Details"]
        rows = [
            (lg["id"], lg["created_at"], lg["user_id"],
             lg["username"], lg["action"], lg["details"])
            for lg in logs
        ]
        path = os.path.join(EXPORTS_DIR, f"audit_log_{time_stamp()}.csv")
        export_to_csv(path, headers, rows)
        messagebox.showinfo(
            "Export", f"Audit log exported to:\n{os.path.abspath(path)}", parent=self.root
        )
