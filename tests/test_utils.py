"""Unit tests for utils.py helpers."""

import re
import time

import pytest

from utils import (
    RateLimiter,
    Session,
    check_password,
    date_str,
    export_to_csv,
    fmt_currency,
    hash_password,
    now_str,
    sanitize_input,
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


class TestSanitizeInput:
    def test_strips_control_chars(self):
        assert sanitize_input("hello\x00world") == "helloworld"

    def test_strips_newlines(self):
        assert sanitize_input("line1\nline2") == "line1line2"

    def test_truncates_to_max_length(self):
        assert sanitize_input("a" * 300, max_length=10) == "a" * 10

    def test_normal_text_unchanged(self):
        text = "Normal text 123"
        assert sanitize_input(text) == text

    def test_unicode_preserved(self):
        text = "سلام دنیا"
        assert sanitize_input(text) == text


class TestRateLimiter:
    def test_not_locked_initially(self):
        rl = RateLimiter(max_attempts=3, lockout_seconds=60)
        assert not rl.is_locked("user1")

    def test_locked_after_max_attempts(self):
        rl = RateLimiter(max_attempts=3, lockout_seconds=60)
        for _ in range(3):
            rl.record_failure("user1")
        assert rl.is_locked("user1")

    def test_not_locked_before_max_attempts(self):
        rl = RateLimiter(max_attempts=3, lockout_seconds=60)
        rl.record_failure("user1")
        rl.record_failure("user1")
        assert not rl.is_locked("user1")

    def test_reset_clears_lock(self):
        rl = RateLimiter(max_attempts=3, lockout_seconds=60)
        for _ in range(3):
            rl.record_failure("user1")
        rl.reset("user1")
        assert not rl.is_locked("user1")

    def test_different_keys_independent(self):
        rl = RateLimiter(max_attempts=3, lockout_seconds=60)
        for _ in range(3):
            rl.record_failure("user1")
        assert not rl.is_locked("user2")

    def test_lockout_expires(self):
        rl = RateLimiter(max_attempts=2, lockout_seconds=0)
        rl.record_failure("u")
        rl.record_failure("u")
        # lockout_seconds=0 → should expire immediately
        time.sleep(0.01)
        assert not rl.is_locked("u")

    def test_remaining_lockout_positive_when_locked(self):
        rl = RateLimiter(max_attempts=2, lockout_seconds=60)
        rl.record_failure("u")
        rl.record_failure("u")
        assert rl.remaining_lockout("u") > 0

    def test_remaining_lockout_zero_when_not_locked(self):
        rl = RateLimiter(max_attempts=5, lockout_seconds=60)
        assert rl.remaining_lockout("u") == 0.0


class TestSession:
    def test_not_authenticated_initially(self):
        s = Session()
        assert not s.is_authenticated

    def test_login_sets_attributes(self):
        s = Session()
        s.login(1, "alice", "admin")
        assert s.is_authenticated
        assert s.user_id == 1
        assert s.username == "alice"
        assert s.role == "admin"

    def test_logout_clears_session(self):
        s = Session()
        s.login(1, "alice", "admin")
        s.logout()
        assert not s.is_authenticated
        assert s.user_id is None

    def test_is_admin(self):
        s = Session()
        s.login(1, "alice", "admin")
        assert s.is_admin()

    def test_cashier_not_admin(self):
        s = Session()
        s.login(2, "bob", "cashier")
        assert not s.is_admin()

    def test_not_expired_when_fresh(self):
        s = Session(timeout_minutes=1)
        s.login(1, "alice", "admin")
        assert not s.is_expired()

    def test_expired_after_timeout(self):
        s = Session(timeout_minutes=0)  # 0 minutes = expires immediately
        s.login(1, "alice", "admin")
        time.sleep(0.01)
        assert s.is_expired()

    def test_touch_resets_timer(self):
        s = Session(timeout_minutes=1)
        s.login(1, "alice", "admin")
        s.touch()
        assert not s.is_expired()

    def test_not_expired_when_not_logged_in(self):
        s = Session(timeout_minutes=0)
        assert not s.is_expired()

    def test_idle_seconds_zero_when_logged_out(self):
        s = Session()
        assert s.idle_seconds() == 0.0

    def test_idle_seconds_positive_when_logged_in(self):
        s = Session()
        s.login(1, "alice", "admin")
        time.sleep(0.01)
        assert s.idle_seconds() > 0
