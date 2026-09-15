"""Process-wide OANDA REST pacing stays at or below the official 120/s cap."""

from __future__ import annotations

import time

from forex_bot.oanda_rate_limit import (
    OANDA_DEFAULT_RPS,
    OANDA_OFFICIAL_MAX_RPS,
    acquire_oanda_rest_slot,
    oanda_max_requests_per_sec,
    reset_oanda_rate_limiter_for_tests,
)


def test_default_rate_is_under_official_cap(monkeypatch):
    monkeypatch.delenv("OANDA_MAX_REQUESTS_PER_SEC", raising=False)
    assert oanda_max_requests_per_sec() == OANDA_DEFAULT_RPS
    assert oanda_max_requests_per_sec() < OANDA_OFFICIAL_MAX_RPS


def test_cannot_configure_above_official_120(monkeypatch):
    monkeypatch.setenv("OANDA_MAX_REQUESTS_PER_SEC", "500")
    assert oanda_max_requests_per_sec() == OANDA_OFFICIAL_MAX_RPS


def test_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("OANDA_MAX_REQUESTS_PER_SEC", "fast")
    assert oanda_max_requests_per_sec() == OANDA_DEFAULT_RPS


def test_acquire_spaces_requests(monkeypatch):
    monkeypatch.setenv("OANDA_MAX_REQUESTS_PER_SEC", "20")
    reset_oanda_rate_limiter_for_tests()
    t0 = time.monotonic()
    waits = [acquire_oanda_rest_slot() for _ in range(5)]
    elapsed = time.monotonic() - t0
    assert waits[0] == 0.0
    assert elapsed >= 0.15  # 4 gaps at 20/s = 0.20s, allow scheduler slack
    assert elapsed < 1.0


def test_oanda_request_uses_limiter(monkeypatch):
    from forex_bot.oanda_client import _oanda_request

    monkeypatch.setenv("OANDA_MAX_REQUESTS_PER_SEC", "50")
    reset_oanda_rate_limiter_for_tests()
    hits = {"n": 0}

    class FakeAPI:
        def request(self, _r):
            hits["n"] += 1
            return {"ok": True}

    monkeypatch.setattr(
        "forex_bot.oanda_rate_limit.acquire_oanda_rest_slot",
        lambda: hits.__setitem__("limited", hits.get("limited", 0) + 1) or 0.0,
    )
    out = _oanda_request(FakeAPI(), object(), context="latest EUR_USD")
    assert out == {"ok": True}
    assert hits["n"] == 1
    assert hits.get("limited") == 1
