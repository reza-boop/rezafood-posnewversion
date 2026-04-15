"""Shared Tkinter widget factory helpers for RezaFood POS.

These functions/classes are used by multiple tab modules and by the main
application window to keep styling consistent and avoid duplication.
"""

from __future__ import annotations

from typing import List, Optional

import tkinter as tk
from tkinter import ttk

from config import FONT, THEME


# ---------------------------------------------------------------------------
# Treeview
# ---------------------------------------------------------------------------

def styled_tree(
    parent: tk.Widget,
    columns: List[str],
    col_widths: Optional[List[int]] = None,
    height: int = 14,
) -> ttk.Treeview:
    """Return a dark-themed :class:`ttk.Treeview` with a vertical scrollbar.

    The Treeview is packed into a wrapping ``tk.Frame`` together with its
    scrollbar; the frame itself is packed inside *parent*.
    """
    style = ttk.Style()
    uid = f"Custom{id(parent)}.Treeview"
    style.configure(
        uid,
        background=THEME["tree_bg"],
        foreground=THEME["tree_fg"],
        fieldbackground=THEME["tree_bg"],
        rowheight=24,
        font=FONT["default"],
    )
    style.configure(
        f"{uid}.Heading",
        background=THEME["tree_heading_bg"],
        foreground=THEME["tree_heading_fg"],
        font=FONT["bold"],
    )
    style.map(uid, background=[("selected", THEME["select_bg"])])

    frame = tk.Frame(parent, bg=THEME["bg"])
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        height=height,
        style=uid,
    )
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    if col_widths:
        for col, w in zip(columns, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")
    else:
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="center")

    tree.tag_configure("odd", background=THEME["tree_row_odd"])
    tree.tag_configure("even", background=THEME["tree_row_even"])

    return tree


# ---------------------------------------------------------------------------
# Buttons / labels
# ---------------------------------------------------------------------------

def btn(
    parent: tk.Widget,
    text: str,
    command,
    danger: bool = False,
    width: int = 14,
) -> tk.Button:
    """Return a styled action button."""
    bg = THEME["danger"] if danger else THEME["button_bg"]
    return tk.Button(
        parent,
        text=text,
        font=FONT["bold"],
        bg=bg,
        fg=THEME["bg"],
        activebackground=THEME["surface2"],
        activeforeground=THEME["fg"],
        relief="flat",
        padx=10,
        pady=6,
        cursor="hand2",
        width=width,
        command=command,
    )


def section_label(parent: tk.Widget, text: str) -> tk.Label:
    """Return a section-heading label."""
    return tk.Label(
        parent,
        text=text,
        font=FONT["heading"],
        bg=THEME["bg"],
        fg=THEME["accent"],
    )
