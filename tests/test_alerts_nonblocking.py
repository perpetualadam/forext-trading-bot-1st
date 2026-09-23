"""Telegram must not delay live opens when api.telegram.org hangs."""

from __future__ import annotations

import time

from forex_bot import alerts
from forex_bot.config import Config


def test_alert_returns_immediately_when_telegram_hangs(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(Config, "DISCORD_WEBHOOK_URL", "")

    def hang(*_a, **_k):
        time.sleep(2.0)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(alerts.requests, "post", hang)
    t0 = time.monotonic()
    alerts.alert("open USD_CAD")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.4


def test_deliver_telegram_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(alerts, "_cooldown_until", 0.0)
    monkeypatch.setattr(alerts, "_fail_streak", 0)

    def boom(*_a, **_k):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(alerts.requests, "post", boom)
    assert alerts._deliver_telegram("x") is False


class _FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"{}" if payload is not None else b""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_deliver_telegram_429_honors_retry_after(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(alerts, "_cooldown_until", 0.0)
    monkeypatch.setattr(alerts, "_fail_streak", 0)
    monkeypatch.setattr(alerts, "_cooldown_logged", False)

    def rate_limited(*_a, **_k):
        return _FakeResp(
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 7",
                "parameters": {"retry_after": 7},
            },
        )

    monkeypatch.setattr(alerts.requests, "post", rate_limited)
    before = time.monotonic()
    assert alerts._deliver_telegram("fill USD_JPY") is False
    remaining = alerts._cooldown_until - before
    assert 6.0 <= remaining <= 8.0
    assert alerts._fail_streak == 0


def test_queued_alert_waits_out_cooldown_instead_of_dropping(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(alerts, "_fail_streak", 0)
    monkeypatch.setattr(alerts, "_cooldown_logged", False)
    monkeypatch.setattr(alerts, "_cooldown_until", time.monotonic() + 7.0)

    sleeps: list[float] = []
    posts: list[str] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        alerts._cooldown_until = 0.0

    def ok_post(*_a, **_k):
        posts.append("sent")
        return _FakeResp(200, {"ok": True})

    monkeypatch.setattr(alerts.requests, "post", ok_post)
    assert alerts._process_alert_item("tg", "queued after 429", sleeper=fake_sleep) is True
    assert sleeps and sleeps[0] >= 6.0
    assert posts == ["sent"]
