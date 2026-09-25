"""Telegram inbound commands/buttons must not change trading gates except halt/resume."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from forex_bot import alerts
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.execution import halt_trading, is_trading_halted_runtime, resume_trading
from forex_bot.positions import Position, open_position, positions
from forex_bot.telegram_control import (
    BOT_COMMANDS,
    REPLY_BUTTON_ROWS,
    CommandReply,
    _HANDLERS,
    command_query,
    commands_enabled,
    dispatch_text,
    handle_command,
    inline_keyboard_markup,
    is_authorized_chat,
    normalize_command,
    process_update,
    process_updates,
    reply_keyboard_markup,
    reset_telegram_control_for_tests,
    start_telegram_control,
    telegram_configured,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.setenv("TELEGRAM_COMMANDS", "true")
    resume_trading()
    reset_telegram_control_for_tests()
    saved_trades = list(analytics.trades)
    analytics.trades.clear()
    positions.clear()
    from forex_bot.state import state as bot_state

    saved_mids = dict(bot_state.get("last_mids") or {})
    bot_state["last_mids"] = {}
    yield
    analytics.trades[:] = saved_trades
    positions.clear()
    bot_state["last_mids"] = saved_mids
    resume_trading()
    reset_telegram_control_for_tests()


def _pos(symbol: str = "EUR_USD") -> Position:
    return Position(
        symbol=symbol,
        direction="BUY",
        units=1000.0,
        entry_price=1.10000,
        stop_loss=1.09000,
        take_profit=1.12000,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="paper",
    )


def test_normalize_slash_and_buttons():
    assert normalize_command("/pnl") == "pnl"
    assert normalize_command("/pnl@MyBot extra") == "pnl"
    assert normalize_command("📊 P/L") == "pnl"
    assert normalize_command("P/L") == "pnl"
    assert normalize_command("📉 Drawdown") == "drawdown"
    assert normalize_command("/dd") == "drawdown"
    assert normalize_command("/start") == "menu"
    assert normalize_command(REPLY_BUTTON_ROWS[1][0]) == "start_trading"
    assert normalize_command("▶️ Start") == "start_trading"
    assert normalize_command("/resume") == "start_trading"
    assert normalize_command("⏹ Stop") == "stop"
    assert normalize_command("/halt") == "stop"
    assert normalize_command("❓ Help") == "help"
    assert normalize_command("/ping") == "ping"


def test_keyboard_covers_requested_controls():
    labels = [cell for row in REPLY_BUTTON_ROWS for cell in row]
    assert "📊 P/L" in labels
    assert "📉 Drawdown" in labels
    assert "▶️ Start" in labels
    assert "⏹ Stop" in labels
    kb = reply_keyboard_markup()
    assert kb["resize_keyboard"] is True
    assert kb["is_persistent"] is True
    inline = inline_keyboard_markup()
    callbacks = [
        btn["callback_data"] for row in inline["inline_keyboard"] for btn in row
    ]
    for needed in ("pnl", "drawdown", "start_trading", "stop", "status", "help"):
        assert needed in callbacks
    command_names = {name for name, _desc in BOT_COMMANDS}
    assert {"pnl", "drawdown", "start_trading", "stop", "status", "help"} <= command_names


def test_commands_enabled_requires_config_and_flag(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "42")
    assert telegram_configured() is False
    assert commands_enabled() is False
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_COMMANDS", "0")
    assert telegram_configured() is True
    assert commands_enabled() is False
    monkeypatch.setenv("TELEGRAM_COMMANDS", "true")
    assert commands_enabled() is True


def test_unauthorized_chat_rejected(monkeypatch):
    assert is_authorized_chat(42) is True
    assert is_authorized_chat("42") is True
    assert is_authorized_chat(99) is False
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "99, 100")
    assert is_authorized_chat(99) is True
    assert is_authorized_chat(7) is False


def test_start_stop_use_existing_halt_gate():
    assert is_trading_halted_runtime() is False
    stop = handle_command("stop")
    assert is_trading_halted_runtime() is True
    assert "STOPPED" in stop.text
    assert "POST /halt" in stop.text
    start = handle_command("start_trading")
    assert is_trading_halted_runtime() is False
    assert "STARTED" in start.text
    assert "POST /resume" in start.text


def test_slash_start_is_menu_not_resume():
    halt_trading()
    reply = dispatch_text("/start")
    assert reply is not None
    assert reply.show_inline_panel is True
    assert "Telegram control" in reply.text
    assert is_trading_halted_runtime() is True
    resume_trading()


def test_plain_start_button_resumes():
    halt_trading()
    reply = dispatch_text("▶️ Start")
    assert reply is not None
    assert is_trading_halted_runtime() is False
    assert "STARTED" in reply.text


def test_pnl_and_drawdown_include_open_and_closed(monkeypatch):
    analytics.trades.extend([10.0, -3.0])
    open_position(_pos())
    monkeypatch.setattr("forex_bot.state.last_mid", lambda _s: 1.10100)
    pnl = handle_command("pnl")
    assert "Current P/L" in pnl.text
    assert "Realized" in pnl.text
    assert "+7.00000" in pnl.text
    assert "Unrealized" in pnl.text
    assert "Drawdown" in pnl.text
    dd = handle_command("drawdown")
    assert "Drawdown" in dd.text
    assert "peak-to-trough" in dd.text


def test_positions_without_mid_does_not_crash(monkeypatch):
    monkeypatch.setattr("forex_bot.state.last_mid", lambda _s: None)
    open_position(_pos("GBP_USD"))
    reply = handle_command("positions")
    assert "GBP_USD" in reply.text
    assert "mtm=n/a" in reply.text


def test_unknown_slash_does_not_halt():
    reply = dispatch_text("/nope")
    assert reply is not None
    assert "Unknown" in reply.text
    assert is_trading_halted_runtime() is False


def test_non_command_text_ignored():
    assert dispatch_text("hello there") is None
    assert dispatch_text("") is None


def test_status_and_metrics_are_read_only():
    halt_trading()
    status = handle_command("status")
    metrics = handle_command("metrics")
    assert "Status" in status.text
    assert "Runtime halt: True" in status.text
    assert "Metrics" in metrics.text
    assert "Equity" in metrics.text
    assert is_trading_halted_runtime() is True


def test_process_update_ignores_other_chats():
    sent: list[tuple] = []

    def capture(text, reply_markup=None, chat_id=None):
        sent.append((text, chat_id))
        return True

    with patch("forex_bot.telegram_control.send_control_message", side_effect=capture):
        handled = process_update(
            {"update_id": 1, "message": {"chat": {"id": 99}, "text": "/stop"}}
        )
    assert handled is False
    assert sent == []
    assert is_trading_halted_runtime() is False


def test_process_update_authorized_stop_and_offset():
    sent: list[str] = []

    def capture(text, reply_markup=None, chat_id=None):
        sent.append(text)
        return True

    with patch("forex_bot.telegram_control.send_control_message", side_effect=capture):
        nxt = process_updates(
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 10,
                        "message": {"chat": {"id": 42}, "text": "⏹ Stop"},
                    }
                ],
            }
        )
    assert nxt == 11
    assert is_trading_halted_runtime() is True
    assert any("STOPPED" in t for t in sent)


def test_callback_query_runs_command():
    sent: list[str] = []

    def capture(text, reply_markup=None, chat_id=None):
        sent.append(text)
        return True

    with (
        patch("forex_bot.telegram_control.send_control_message", side_effect=capture),
        patch("forex_bot.telegram_control._answer_callback"),
    ):
        handled = process_update(
            {
                "update_id": 3,
                "callback_query": {
                    "id": "cb1",
                    "data": "pnl",
                    "message": {"chat": {"id": 42}},
                },
            }
        )
    assert handled is True
    assert any("Current P/L" in t for t in sent)


def test_help_sends_keyboard_and_inline_panel():
    calls: list[dict] = []

    def capture(text, reply_markup=None, chat_id=None):
        calls.append({"text": text, "reply_markup": reply_markup})
        return True

    with patch("forex_bot.telegram_control.send_control_message", side_effect=capture):
        process_update(
            {"update_id": 4, "message": {"chat": {"id": "42"}, "text": "/help"}}
        )
    assert len(calls) == 2
    assert "keyboard" in (calls[0]["reply_markup"] or {})
    assert "inline_keyboard" in (calls[1]["reply_markup"] or {})


def test_start_telegram_control_noop_without_token(monkeypatch):
    monkeypatch.setattr(Config, "TELEGRAM_TOKEN", "")
    start_telegram_control()
    from forex_bot import telegram_control as tc

    assert tc._poller_started is False


def test_failed_command_does_not_raise(monkeypatch):
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setitem(_HANDLERS, "pnl", boom)
    reply = handle_command("pnl")
    assert isinstance(reply, CommandReply)
    assert "failed" in reply.text.lower()
    assert is_trading_halted_runtime() is False


def test_every_handler_returns_text():
    for name in list(_HANDLERS):
        reply = handle_command(name)
        assert isinstance(reply, CommandReply)
        assert reply.text.strip()


def test_alert_path_unchanged_when_control_configured(monkeypatch):
    monkeypatch.setattr(Config, "DISCORD_WEBHOOK_URL", "")
    t0 = __import__("time").monotonic()
    alerts.alert("still non-blocking")
    assert __import__("time").monotonic() - t0 < 0.4


def test_search_usage_and_query_parsing():
    assert normalize_command("/search EUR_USD") == "search"
    assert normalize_command("/search@MyBot pnl") == "search"
    assert command_query("/search EUR_USD") == "EUR_USD"
    assert command_query("/search@MyBot pnl") == "pnl"
    assert command_query("/search") == ""
    reply = dispatch_text("/search")
    assert reply is not None
    assert "Usage" in reply.text
    assert is_trading_halted_runtime() is False


def test_search_lists_stop_but_does_not_halt():
    reply = dispatch_text("/search stop")
    assert reply is not None
    assert "/stop" in reply.text
    assert "not executed" in reply.text.lower()
    assert is_trading_halted_runtime() is False


def test_search_finds_open_position_symbol():
    open_position(_pos("EUR_USD"))
    reply = dispatch_text("/search EUR")
    assert reply is not None
    assert "EUR_USD" in reply.text
    assert is_trading_halted_runtime() is False


def test_search_unknown_query_stays_read_only():
    reply = dispatch_text("/search zzznomatch999")
    assert reply is not None
    assert "No matching" in reply.text
    assert dispatch_text("/ping") is not None
    assert dispatch_text("hello there") is None
    assert is_trading_halted_runtime() is False


def test_getupdates_wait_honors_retry_after():
    from forex_bot.telegram_control import getupdates_wait_sec

    assert getupdates_wait_sec(
        429, {"ok": False, "parameters": {"retry_after": 12}}
    ) == 12.0
    assert getupdates_wait_sec(502, {"ok": False, "description": "Bad Gateway"}) == 5.0
    assert getupdates_wait_sec(409, {}) == 15.0
    assert getupdates_wait_sec(200, {"ok": True, "result": []}) == 0.0


def test_409_log_is_rate_limited(monkeypatch, caplog):
    from forex_bot import telegram_control as tc

    tc._last_409_log = 0.0
    with caplog.at_level("WARNING"):
        tc._log_getupdates_409({"description": "terminated by other getUpdates request"})
        tc._log_getupdates_409({"description": "terminated by other getUpdates request"})
    lines = [r.message for r in caplog.records if "getUpdates 409" in r.message]
    assert len(lines) == 1
    assert "terminated by other getUpdates request" in lines[0]
