"""Unit + integration tests for the per-user token-bucket rate limiter."""
from __future__ import annotations

import time

import pytest

from app.core.rate_limit import (
    TokenBucketLimiter,
    get_limiter,
    reset_for_tests,
)


def test_allows_up_to_capacity_then_denies() -> None:
    limiter = TokenBucketLimiter()
    now = 1_000_000.0
    for _ in range(5):
        assert limiter.check(key=1, route="r", capacity=5, per_minute=5, now=now) is True
    assert limiter.check(key=1, route="r", capacity=5, per_minute=5, now=now) is False


def test_refill_over_time() -> None:
    limiter = TokenBucketLimiter()
    now = 1_000_000.0
    # Burn the bucket
    for _ in range(3):
        limiter.check(key=1, route="r", capacity=3, per_minute=3, now=now)
    assert limiter.check(key=1, route="r", capacity=3, per_minute=3, now=now) is False
    # 20s later -> 1 token refilled (3/min = 0.05/s, 20s = 1 token)
    now += 20.0
    assert limiter.check(key=1, route="r", capacity=3, per_minute=3, now=now) is True
    assert limiter.check(key=1, route="r", capacity=3, per_minute=3, now=now) is False


def test_independent_buckets_per_key() -> None:
    limiter = TokenBucketLimiter()
    now = 1_000_000.0
    for _ in range(3):
        limiter.check(key=1, route="r", capacity=3, per_minute=3, now=now)
    # User 2 still has full bucket
    assert limiter.check(key=2, route="r", capacity=3, per_minute=3, now=now) is True


def test_independent_buckets_per_route() -> None:
    limiter = TokenBucketLimiter()
    now = 1_000_000.0
    for _ in range(3):
        limiter.check(key=1, route="login", capacity=3, per_minute=3, now=now)
    # Different route for same user
    assert limiter.check(key=1, route="generate", capacity=3, per_minute=3, now=now) is True


def test_disabled_when_zero() -> None:
    limiter = TokenBucketLimiter()
    now = 1_000_000.0
    for _ in range(100):
        assert limiter.check(key=1, route="r", capacity=0, per_minute=0, now=now) is True


def test_reset_for_tests_clears_state() -> None:
    reset_for_tests()
    limiter = get_limiter()
    limiter.check(key=99, route="r", capacity=1, per_minute=1, now=time.time())
    reset_for_tests()
    # After reset, key 99 should have a fresh bucket.
    assert limiter.check(key=99, route="r", capacity=1, per_minute=1, now=time.time()) is True


# --- Integration: 429 on /api/auth/login -------------------------------------

def test_login_rate_limit_returns_429(test_client, monkeypatch, test_settings) -> None:
    """Hammer /api/auth/login with bad creds -> eventually 429 with Retry-After."""
    # Shrink the limit so the test is fast.  Patch the conftest test_settings
    # (which is what `get_settings` returns inside the route).
    monkeypatch.setattr(test_settings, "rate_limit_login_per_minute", 2)
    reset_for_tests()
    for _ in range(2):
        r = test_client.post("/api/auth/login", json={"username": "x", "password": "y"})
        assert r.status_code == 401
    # Third attempt -> 429
    r = test_client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    reset_for_tests()


def test_login_rate_limit_records_audit(test_client, monkeypatch, test_settings) -> None:
    """The 429 from login also writes a 'rate_limited' audit row."""
    import sqlite3
    monkeypatch.setattr(test_settings, "rate_limit_login_per_minute", 1)
    reset_for_tests()
    test_client.post("/api/auth/login", json={"username": "x", "password": "y"})
    r = test_client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429
    conn = sqlite3.connect(test_settings.auth_db_path)
    cur = conn.execute(
        "SELECT action, target_id, outcome FROM audit_log "
        "WHERE target_id='auth.login' ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "rate_limited"
    assert row[2] == "denied"
    reset_for_tests()