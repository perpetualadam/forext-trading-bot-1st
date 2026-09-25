"""Read-only Telegram commands must not touch trading."""

from __future__ import annotations

from forex_bot import telegram_commands as tcmd
from forex_bot.telegram_commands import (
    BLOCKED_COMMANDS,
    HELP_TEXT,
    chat_allowed,
    decide_command,
    handle_pending_updates,
    local_command_menu,
)
from forex_bot.config import Config


def test_only_configured_chat_is_allowed(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "6306660314")
    assert chat_allowed(6306660314) is True
    assert chat_allowed("6306660314") is True
    assert chat_allowed(1) is False


def test_help_and_status_are_read_only(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "9")
    help_decision = decide_command({"chat_id": "9", "command": "help", "is_command": True}, lambda: "unused")
    assert help_decision["action"] == "reply"
    assert help_decision["reply"] == HELP_TEXT
    status_decision = decide_command({"chat_id": "9", "command": "status", "is_command": True}, lambda: "BOT STATUS ok")
    assert status_decision["reply"] == "BOT STATUS ok"


def test_blocked_commands_do_not_trade(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "9")
    for name in BLOCKED_COMMANDS:
        decision = decide_command({"chat_id": "9", "command": name, "is_command": True}, lambda: "no")
        assert decision["action"] == "reject"
        assert "cannot change trades" in decision["reply"]


def test_menu_matches_local_readonly_commands():
    names = [row["command"] for row in local_command_menu()]
    assert names == ["help", "status"]
    assert "halt" not in names
    assert "close" not in names


def test_inbound_disabled_when_command_listener_owns_getupdates(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "9")
    monkeypatch.setenv("TELEGRAM_COMMANDS", "true")
    monkeypatch.setenv("TELEGRAM_INBOUND", "1")
    assert tcmd.inbound_enabled() is False


def test_handle_pending_updates_replies_only_to_safe_commands(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "9")
    monkeypatch.setenv("TELEGRAM_COMMANDS", "false")
    monkeypatch.setenv("TELEGRAM_INBOUND", "1")
    sent: list[str] = []
    monkeypatch.setattr(
        tcmd,
        "fetch_pending_updates",
        lambda *_a, **_k: {
            "ok": True,
            "n_updates": 3,
            "updates": [
                {"chat_id": "9", "command": "help", "is_command": True, "text": "/help"},
                {"chat_id": "9", "command": "halt", "is_command": True, "text": "/halt"},
                {"chat_id": "8", "command": "status", "is_command": True, "text": "/status"},
            ],
        },
    )
    result = handle_pending_updates(lambda: "STATUS", send=sent.append)
    assert result["replies_sent"] == 2
    assert HELP_TEXT in sent
    assert any("cannot change trades" in msg for msg in sent)
    assert "STATUS" not in sent
