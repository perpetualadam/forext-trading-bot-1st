"""Isolated tests for the missing-candle management defect. No broker calls."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pandas as pd
import pytest

from forex_bot import bot_loop
from forex_bot.live_manage import ManageQuote
from forex_bot.live_manage import resolve_broker_manage_price as _real_resolve
from forex_bot.market_provenance import order_quote_rejection
from forex_bot.positions import Position
from forex_bot.profit_protection import ProtectionDecision


def _frame() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    return pd.DataFrame(
        {
            "time": [now],
            "open": [1.1],
            "high": [1.102],
            "low": [1.098],
            "close": [1.1],
        }
    )


def _position(direction: str) -> Position:
    return Position(
        symbol="EUR_USD",
        direction=direction,
        units=1.0,
        entry_price=1.1,
        stop_loss=1.0 if direction == "BUY" else 1.2,
        take_profit=1.2 if direction == "BUY" else 1.0,
        open_time=time.time() - 3600,
        strategy_name="inactive",
        rl_state="",
        execution_kind="live",
        broker_order=True,
    )


def _quote(*, fresh: bool, direction: str) -> ManageQuote:
    age = 0 if fresh else 500
    return ManageQuote(
        instrument="EUR_USD",
        bid=1.1,
        ask=1.1002,
        closeout_bid=1.0999,
        closeout_ask=1.1003,
        time_epoch=time.time() - age,
        tradeable=True,
    )


@pytest.fixture(autouse=True)
def _current_close_context(monkeypatch, managed_close_transport):
    monkeypatch.setitem(globals(), "_CURRENT_CLOSE_TRANSPORT", managed_close_transport)


def _install(monkeypatch, *, candles, position, weekend: bool, fresh: bool, close_result):
    seen = {"position": 0, "execute": 0, "resolve": 0, "closed": 0}

    def _fetch(*_args, **_kwargs):
        if isinstance(candles, Exception):
            raise candles
        return candles

    async def _execute(*_args, **_kwargs):
        seen["execute"] += 1
        if isinstance(close_result, Exception):
            raise close_result
        return 0.0

    def _resolve(*args, **kwargs):
        seen["resolve"] += 1
        return _real_resolve(*args, **kwargs)

    monkeypatch.setattr(bot_loop, "fetch_ohlcv", _fetch)
    monkeypatch.setattr(bot_loop, "get_position", lambda _symbol: seen.__setitem__("position", seen["position"] + 1) or position)
    monkeypatch.setattr(bot_loop, "flatten_for_weekend", lambda: weekend)
    monkeypatch.setattr(bot_loop, "execute_trade", _execute)
    monkeypatch.setattr(
        bot_loop,
        "close_position",
        lambda _symbol: seen.__setitem__("closed", seen["closed"] + 1),
    )
    monkeypatch.setattr(bot_loop, "close_fill_path", lambda *_a, **_k: "broker")
    monkeypatch.setattr(bot_loop, "_persist_v2_shadow_market_m5", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_safe_audit", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_reject", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_close", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "record_mid", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "alert", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.live_manage.resolve_broker_manage_price", _resolve)
    monkeypatch.setattr(
        bot_loop,
        "pricing_snapshot",
        lambda: {"EUR_USD": _quote(fresh=fresh, direction="BUY")},
    )
    monkeypatch.setattr(bot_loop, "seed_position_mfe", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "raise_mfe_from_post_entry_ohlcv", lambda *_a, **_k: None)
    monkeypatch.setattr(
        bot_loop,
        "apply_profit_protection",
        lambda *_a, **_k: ProtectionDecision(
            enabled=True,
            current_pips=0.0,
            max_profit_pips=0.0,
            active=False,
            exit_threshold_pips=None,
            should_close=False,
            just_activated=False,
            just_ratcheted=False,
        ),
    )
    _CURRENT_CLOSE_TRANSPORT({"EUR_USD": position}, seen, close_result if isinstance(close_result, Exception) else None)
    return seen


def test_candle_failure_still_manages_existing_position(monkeypatch) -> None:
    """G.8 showed None, empty, and failed fetches returned before management.

    G.9 must look up the position, resolve a management quote, and still flatten.
    """
    for candles in (None, pd.DataFrame(), TimeoutError("candles down"), ValueError("parse")):
        seen = _install(
            monkeypatch,
            candles=candles,
            position=_position("BUY"),
            weekend=True,
            fresh=True,
            close_result=0.0,
        )
        asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        assert seen["position"] == 1
        assert seen["resolve"] == 1
        assert seen["execute"] == 1
        assert seen["closed"] == 1


def test_fresh_quote_monitors_without_closing(monkeypatch) -> None:
    for direction in ("BUY", "SELL"):
        seen = _install(
            monkeypatch,
            candles=_frame(),
            position=_position(direction),
            weekend=False,
            fresh=True,
            close_result=0.0,
        )
        asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        assert seen["position"] == 1
        assert seen["resolve"] == 1
        assert seen["execute"] == 0


def test_stale_quote_does_not_software_close(monkeypatch) -> None:
    seen = _install(
        monkeypatch,
        candles=_frame(),
        position=_position("BUY"),
        weekend=False,
        fresh=False,
        close_result=0.0,
    )
    asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
    assert seen["resolve"] == 1
    assert seen["execute"] == 0


def test_weekend_flatten_confirms_only_after_close_returns(monkeypatch) -> None:
    seen = _install(
        monkeypatch,
        candles=_frame(),
        position=_position("BUY"),
        weekend=True,
        fresh=True,
        close_result=0.0,
    )
    asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
    assert seen["execute"] == 1
    assert seen["closed"] == 1

    failed = _install(
        monkeypatch,
        candles=_frame(),
        position=_position("SELL"),
        weekend=True,
        fresh=True,
        close_result=TimeoutError("close failed"),
    )
    asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
    assert failed["execute"] == 1
    assert failed["closed"] == 0


def test_no_position_does_not_invent_exposure(monkeypatch) -> None:
    seen = _install(
        monkeypatch,
        candles=_frame(),
        position=None,
        weekend=True,
        fresh=True,
        close_result=0.0,
    )
    asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
    assert seen["position"] == 1
    assert seen["execute"] == 0
    assert order_quote_rejection(None, "EUR_USD") == "missing_provenance"
