"""Secrets must not appear in log lines."""

from __future__ import annotations

import logging

from forex_bot import alerts
from forex_bot.config import Config
from forex_bot.log_redact import redact_log_text
from forex_bot.oanda_client import _format_oanda_error


TOKEN = "7527052874:AAGrwHFzuRM5tfwsdubKBdFdZU9mhRwfeho"
OANDA = "0123456789abcdef0123456789abcdef-0123456789abcdef"
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwx"


def test_redact_log_text_strips_telegram_bot_url_and_known_token(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", TOKEN)
    raw = (
        "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded "
        f"with url: /bot{TOKEN}/getUpdates?timeout=20&offset=0 "
        "(Caused by SSLError(SSLEOFError(8, 'EOF')))"
    )
    cleaned = redact_log_text(raw)
    assert TOKEN not in cleaned
    assert "/bot<redacted>/getUpdates" in cleaned


def test_redact_log_text_strips_oanda_bearer_and_discord(monkeypatch):
    monkeypatch.setattr(Config, "OANDA_ACCESS_TOKEN", OANDA)
    monkeypatch.setattr(Config, "DISCORD_WEBHOOK_URL", WEBHOOK)
    raw = f"Authorization: Bearer {OANDA} webhook={WEBHOOK}"
    cleaned = redact_log_text(raw)
    assert OANDA not in cleaned
    assert WEBHOOK not in cleaned
    assert "Bearer <redacted>" in cleaned


def test_deliver_telegram_timeout_log_hides_token(monkeypatch, caplog):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", TOKEN)
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(alerts, "_cooldown_until", 0.0)
    monkeypatch.setattr(alerts, "_fail_streak", 0)

    def boom(*_a, **_k):
        raise TimeoutError(
            "HTTPSConnectionPool(host='api.telegram.org', port=443): "
            f"Max retries exceeded with url: /bot{TOKEN}/sendMessage"
        )

    monkeypatch.setattr(alerts.requests, "post", boom)
    with caplog.at_level(logging.WARNING, logger="forex_bot.alerts"):
        assert alerts._deliver_telegram("x") is False
    joined = "\n".join(caplog.messages)
    assert TOKEN not in joined
    assert "/bot<redacted>/" in joined or "<redacted>" in joined


def test_oanda_error_formatter_redacts_token(monkeypatch):
    monkeypatch.setattr(Config, "OANDA_ACCESS_TOKEN", OANDA)
    text = _format_oanda_error(RuntimeError(f"Authorization Bearer {OANDA} rejected"))
    assert OANDA not in text
    assert "Bearer <redacted>" in text


def test_redact_does_not_blank_ordinary_errors():
    msg = "Read timed out. (read timeout=8.0)"
    assert redact_log_text(msg) == msg
