"""Live execution manager: broker fills inside the window, fail closed if orders are off."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from forex_bot.execution import close_fill_path, open_fill_path


def _london_inside_window():
    # 14:00 UTC on a September weekday = 15:00 Europe/London (BST) → inside 13:00–17:00.
    return datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)


def _london_outside_window():
    return datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)


def test_open_fill_path_live_broker_inside_window(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    monkeypatch.setenv("LIVE_EUR_USD_START", "13:00")
    monkeypatch.setenv("LIVE_EUR_USD_END", "17:00")
    assert open_fill_path("EUR_USD", at_utc=_london_inside_window()) == "broker"


def test_open_fill_path_paper_never_sends_orders(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    assert open_fill_path("EUR_USD", at_utc=_london_inside_window()) == "simulate"


def test_open_fill_path_abort_if_live_window_but_legacy_orders_off(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("USE_OANDA_LIVE", "false")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    from forex_bot.config import Config

    monkeypatch.setattr(Config, "PAPER_TRADING", False)
    monkeypatch.setattr(Config, "TRADING_MODE", "live")
    assert open_fill_path("EUR_USD", at_utc=_london_inside_window()) == "abort_broker_disabled"


def test_open_fill_path_window_paper_outside_hours(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    assert open_fill_path("EUR_USD", at_utc=_london_outside_window()) == "simulate"


def test_close_fill_path_live_position_always_broker(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    assert close_fill_path("EUR_USD", "live") == "broker"


def test_close_fill_path_live_aborts_if_orders_off(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    assert close_fill_path("EUR_USD", "live") == "abort_broker_disabled"


def test_execute_trade_live_close_requires_broker(monkeypatch):
    import asyncio

    from forex_bot import trading as trading_mod

    monkeypatch.setenv("EXECUTION_MODE", "paper")

    async def _run():
        return await trading_mod.execute_trade(
            "EUR_USD",
            "trend",
            "BUY",
            10.0,
            1.1,
            1.09,
            1.12,
            realized_pnl=1.0,
            execution_kind="live",
            exit_price=1.101,
        )

    with pytest.raises(RuntimeError, match="broker"):
        asyncio.run(_run())
