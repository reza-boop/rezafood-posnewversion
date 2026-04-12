"""Unit tests for utils.py helpers."""

import re

import pytest

from utils import (
    check_password,
    date_str,
    export_to_csv,
    fmt_currency,
    hash_password,
    now_str,
    time_stamp,
)


class TestFmtCurrency:
    def test_integer(self):
        assert fmt_currency(1000) == "1,000.00"

    def test_decimal(self):
        assert fmt_currency(12.5) == "12.50"

    def test_zero(self):
        assert fmt_currency(0) == "0.00"

    def test_large(self):
        assert fmt_currency(1_000_000) == "1,000,000.00"


class TestTimeHelpers:
    def test_now_str_format(self):
        s = now_str()
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", s)

    def test_date_str_format(self):
        s = date_str()
        assert re.match(r"\d{4}-\d{2}-\d{2}", s)

    def test_time_stamp_format(self):
        s = time_stamp()
        assert re.match(r"\d{8}_\d{6}", s)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        h = hash_password("Secret1!")
        assert check_password("Secret1!", h)

    def test_wrong_password_fails(self):
        h = hash_password("correct")
        assert not check_password("wrong", h)

    def test_unique_hashes(self):
        h1 = hash_password("abc")
        h2 = hash_password("abc")
        # Random salt means different hashes (overwhelmingly likely)
        assert h1 != h2

    def test_empty_password(self):
        h = hash_password("")
        assert check_password("", h)


class TestExportCsv:
    def test_creates_file(self, tmp_path):
        path = str(tmp_path / "test.csv")
        export_to_csv(path, ["A", "B"], [[1, 2], [3, 4]])
        content = open(path).read()
        assert "A,B" in content
        assert "1,2" in content

    def test_creates_parent_dir(self, tmp_path):
        path = str(tmp_path / "sub" / "out.csv")
        export_to_csv(path, ["X"], [["val"]])
        assert open(path).read().strip() == "X\nval"
