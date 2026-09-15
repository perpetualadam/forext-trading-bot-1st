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
