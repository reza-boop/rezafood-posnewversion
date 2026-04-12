"""Dashboard tab — statistics cards, top products, low-stock alert."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Dict

from config import FONT, LOW_STOCK_THRESHOLD, THEME
from ui.tabs import BaseTab
from ui.widgets import btn, section_label, styled_tree
from utils import date_str, fmt_currency

if TYPE_CHECKING:
    from ui.main import PosApp


class DashboardTab(BaseTab):

    def __init__(self, notebook, app: "PosApp") -> None:
        super().__init__(notebook, app, " 📊 Dashboard ")

    def _build(self) -> None:
        # Stat cards row
        stats_row = tk.Frame(self, bg=THEME["bg"])
        stats_row.pack(fill="x", padx=12, pady=12)

        self._stat_vars: Dict[str, tk.StringVar] = {}
        stats_defs = [
            ("Today Orders",  "today_orders",   THEME["accent"]),
            ("Today Revenue", "today_revenue",  THEME["accent2"]),
            ("Total Revenue", "all_revenue",    THEME["warning"]),
            ("Total Products","total_products", THEME["fg"]),
            ("Total Users",   "total_users",    THEME["fg"]),
        ]
        for label, key, color in stats_defs:
            card = tk.Frame(stats_row, bg=THEME["surface"], padx=16, pady=12)
            card.pack(side="left", expand=True, fill="both", padx=6)
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            tk.Label(
                card, text=label, font=FONT["bold"],
                bg=THEME["surface"], fg=THEME["fg"],
            ).pack()
            tk.Label(
                card, textvariable=var, font=FONT["large"],
                bg=THEME["surface"], fg=color,
            ).pack()

        # Mid section: top products + low stock
        mid = tk.Frame(self, bg=THEME["bg"])
        mid.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        left = tk.Frame(mid, bg=THEME["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        section_label(left, "Top-Selling Products").pack(anchor="w", pady=(0, 4))
        self._top_tree = styled_tree(
            left, ["Product", "Qty Sold", "Revenue"], [200, 100, 120], height=10
        )

        right = tk.Frame(mid, bg=THEME["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        section_label(right, f"Low Stock (≤ {LOW_STOCK_THRESHOLD})").pack(
            anchor="w", pady=(0, 4)
        )
        self._low_tree = styled_tree(
            right, ["ID", "Name", "Category", "Stock"], [50, 180, 120, 70], height=10
        )

        btn(self, "Refresh Dashboard", self.refresh, width=20).pack(pady=6)

    def refresh(self) -> None:
        today = date_str()
        stats = self.db.get_today_stats(today)
        self._stat_vars["today_orders"].set(str(stats["orders"]))
        self._stat_vars["today_revenue"].set(fmt_currency(stats["revenue"]))
        self._stat_vars["all_revenue"].set(fmt_currency(self.db.get_all_time_revenue()))
        self._stat_vars["total_products"].set(str(self.db.get_total_products()))
        self._stat_vars["total_users"].set(str(self.db.get_total_users()))

        self._top_tree.delete(*self._top_tree.get_children())
        for i, p in enumerate(self.db.get_top_products()):
            tag = "even" if i % 2 == 0 else "odd"
            self._top_tree.insert(
                "", "end",
                values=(p["product_name"], p["total_qty"], fmt_currency(p["total_revenue"])),
                tags=(tag,),
            )

        self._low_tree.delete(*self._low_tree.get_children())
        for i, p in enumerate(self.db.get_low_stock_products(LOW_STOCK_THRESHOLD)):
            tag = "even" if i % 2 == 0 else "odd"
            self._low_tree.insert(
                "", "end",
                values=(p["id"], p["name"], p["category"], p["stock"]),
                tags=(tag,),
            )
