"""Unit tests for ReceiptBuilder."""

import os

import pytest

from receipts import ReceiptBuilder


ITEMS = [
    {"product_name": "Burger", "quantity": 2, "unit_price": 9.99, "subtotal": 19.98},
    {"product_name": "Cola",   "quantity": 1, "unit_price": 2.00, "subtotal": 2.00},
]


class TestReceiptBuild:
    def test_contains_order_id(self):
        r = ReceiptBuilder(42, "cashier1", "Cash", ITEMS, 21.98)
        text = r.build()
        assert "42" in text

    def test_contains_cashier(self):
        r = ReceiptBuilder(1, "alice", "Cash", ITEMS, 21.98)
        text = r.build()
        assert "alice" in text

    def test_contains_total(self):
        r = ReceiptBuilder(1, "cashier", "Card", ITEMS, 21.98)
        text = r.build()
        assert "21.98" in text

    def test_shows_change_when_paid(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98, paid=30.00)
        text = r.build()
        assert "CHANGE" in text
        assert "8.02" in text

    def test_no_change_line_when_not_paid(self):
        r = ReceiptBuilder(1, "cashier", "Card", ITEMS, 21.98)
        text = r.build()
        assert "CHANGE" not in text

    def test_discount_shown(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 19.98, discount_amount=2.00)
        text = r.build()
        assert "DISCOUNT" in text
        assert "2.00" in text

    def test_contains_all_items(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98)
        text = r.build()
        assert "Burger" in text
        assert "Cola" in text

    def test_thermal_width_default(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98)
        lines = r.build().splitlines()
        assert all(len(line) <= 42 for line in lines)

    def test_wide_format(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98, format="wide")
        assert r.width == 58
        text = r.build()
        assert "Burger" in text

    def test_a4_format(self):
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98, format="a4")
        assert r.width == 72
        text = r.build()
        assert "Burger" in text

    def test_no_negative_change(self):
        # paid less than total → change should be 0, not negative
        r = ReceiptBuilder(1, "cashier", "Cash", ITEMS, 21.98, paid=10.00)
        assert r.change == 0.0


class TestReceiptSave:
    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("receipts.RECEIPTS_DIR", str(tmp_path))
        r = ReceiptBuilder(7, "cashier", "Cash", ITEMS, 21.98)
        path = r.save()
        assert os.path.isfile(path)
        content = open(path).read()
        assert "Burger" in content

    def test_save_wide_format(self, tmp_path, monkeypatch):
        monkeypatch.setattr("receipts.RECEIPTS_DIR", str(tmp_path))
        r = ReceiptBuilder(8, "cashier", "Cash", ITEMS, 21.98, format="wide")
        path = r.save()
        assert os.path.isfile(path)
