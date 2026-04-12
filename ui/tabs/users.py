"""Users tab — CRUD for staff accounts (admin only)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from config import THEME
from ui.dialogs import UserDialog
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree

if TYPE_CHECKING:
    from ui.main import PosApp


class UsersTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 👤 Users ")

    def _build(self) -> None:
        section_label(self, "User Management").pack(anchor="w", padx=8, pady=(8, 4))

        self._tree = styled_tree(
            self,
            ["ID", "Username", "Role", "Created"],
            [50, 200, 100, 180],
            height=18,
        )

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=8, pady=(6, 0))
        btn(btn_row, "Add User",    self._add).pack(side="left", padx=4)
        btn(btn_row, "Edit User",   self._edit).pack(side="left", padx=4)
        btn(btn_row, "Delete User", self._delete, danger=True).pack(side="left", padx=4)
        btn(btn_row, "Refresh",     self.refresh).pack(side="left", padx=4)

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, u in enumerate(self.db.get_all_users()):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                iid=str(u["id"]),
                values=(u["id"], u["username"], u["role"], u["created_at"]),
                tags=(tag,),
            )

    def _add(self) -> None:
        dlg = UserDialog(self.root)
        if dlg.result:
            r = dlg.result
            try:
                self.db.add_user(r["username"], r["password"], r["role"])
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "add_user", f"username={r['username']} role={r['role']}",
                )
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _edit(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to edit.", parent=self.root)
            return
        user_id = int(sel[0])
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        dlg = UserDialog(self.root, user=dict(row))
        if dlg.result:
            r = dlg.result
            try:
                self.db.update_user(
                    user_id, r["username"], r["password"] or None, r["role"]
                )
                self.db.add_audit_log(
                    self.user["id"], self.user["username"],
                    "edit_user", f"id={user_id} username={r['username']}",
                )
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self.root)

    def _delete(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Select a user to delete.", parent=self.root)
            return
        user_id = int(sel[0])
        if user_id == self.user["id"]:
            messagebox.showwarning(
                "Cannot Delete", "You cannot delete your own account.", parent=self.root
            )
            return
        rows = self.db.get_all_users()
        row = next((r for r in rows if r["id"] == user_id), None)
        if not row:
            return
        if not messagebox.askyesno(
            "Confirm Delete", f"Delete user '{row['username']}'?", parent=self.root
        ):
            return
        self.db.delete_user(user_id)
        self.db.add_audit_log(
            self.user["id"], self.user["username"],
            "delete_user", f"id={user_id} username={row['username']}",
        )
        self.refresh()
