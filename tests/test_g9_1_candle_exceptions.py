"""Stage G.9.1 candle-exception boundary. Broker calls stay mocked."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from forex_bot import bot_loop
from forex_bot.execution import halt_trading, resume_trading
from forex_bot.live_manage import ManageQuote
from forex_bot.live_manage import resolve_broker_manage_price as _real_resolve
from forex_bot.live_safety import AUTH_BLOCKED, live_order_auth_state
from forex_bot.market_provenance import ProvenanceRejected, mint_live_quote
from forex_bot.oanda_exec import _place_market_order_open_sync, _place_market_order_sync
from forex_bot.positions import Position
from forex_bot.profit_protection import ProtectionDecision

ROOT = Path(__file__).resolve().parents[1]


def _position(symbol: str, direction: str, *, units: float = 1.0) -> Position:
    buy = direction == "BUY"
    return Position(
        symbol=symbol,
        direction=direction,
        units=units,
        entry_price=1.1,
        stop_loss=1.0 if buy else 1.2,
        take_profit=1.2 if buy else 1.0,
        open_time=time.time() - 3600,
        strategy_name="trend",
        rl_state="",
        execution_kind="live",
        broker_order=True,
    )


def _quote(symbol: str, *, fresh: bool = True, bid: float = 1.1, ask: float = 1.1002) -> ManageQuote:
    return ManageQuote(
        instrument=symbol,
        bid=bid,
        ask=ask,
        closeout_bid=bid - 0.0001,
        closeout_ask=ask + 0.0001,
        time_epoch=time.time() - (0 if fresh else 500),
        tradeable=True,
    )


def _frame() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    return pd.DataFrame(
        {"time": [now], "open": [1.1], "high": [1.101], "low": [1.099], "close": [1.1]}
    )


class _Seen:
    def __init__(self) -> None:
        self.position: list[str] = []
        self.execute: list[tuple] = []
        self.closed: list[str] = []
        self.selected = 0
        self.synthetic = 0


@pytest.fixture(autouse=True)
def _current_close_context(monkeypatch, managed_close_transport):
    monkeypatch.setitem(globals(), "_CURRENT_CLOSE_TRANSPORT", managed_close_transport)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    seen: _Seen,
    *,
    candles,
    positions: dict,
    weekend: bool = False,
    quotes: dict | None = None,
    quote_error: BaseException | None = None,
    close_error: BaseException | None = None,
    protect: bool = False,
) -> None:
    def _fetch(symbol, *_args, **_kwargs):
        item = candles[symbol] if isinstance(candles, dict) else candles
        if isinstance(item, Exception):
            raise item
        return item

    def _get(symbol: str):
        seen.position.append(symbol)
        found = positions.get(symbol)
        if isinstance(found, Exception):
            raise found
        return found

    async def _execute(*args, **_kwargs):
        seen.execute.append(args)
        if close_error is not None:
            raise close_error
        return 0.0

    def _select(*_args, **_kwargs):
        seen.selected += 1
        raise AssertionError("new entry was evaluated")

    monkeypatch.setattr(bot_loop, "fetch_ohlcv", _fetch)
    monkeypatch.setattr(bot_loop, "get_position", _get)
    monkeypatch.setattr(bot_loop, "flatten_for_weekend", lambda: weekend)
    monkeypatch.setattr(bot_loop, "in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr(bot_loop, "execute_trade", _execute)
    monkeypatch.setattr(bot_loop, "close_position", lambda symbol: seen.closed.append(symbol))
    monkeypatch.setattr(bot_loop, "close_fill_path", lambda *_a, **_k: "broker")
    monkeypatch.setattr(bot_loop, "select_strategy", _select)
    monkeypatch.setattr(bot_loop, "_persist_v2_shadow_market_m5", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_safe_audit", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_reject", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_close", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "record_mid", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "alert", lambda *_a, **_k: None)
    monkeypatch.setenv("POSITION_LOG", "0")
    monkeypatch.setenv("MIN_POSITION_HOLD_SEC", "0")
    monkeypatch.setattr(
        "forex_bot.live_manage.resolve_broker_manage_price",
        lambda quote, direction, **kwargs: (seen and _real_resolve(quote, direction, **kwargs)),
    )
    monkeypatch.setattr(
        "forex_bot.market_provenance.bind_synthetic_frame",
        lambda frame: seen.__setattr__("synthetic", seen.synthetic + 1) or frame,
    )

    def _snap():
        if quote_error is not None:
            raise quote_error
        return quotes or {}

    monkeypatch.setattr(bot_loop, "pricing_snapshot", _snap)
    monkeypatch.setattr(bot_loop, "seed_position_mfe", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "raise_mfe_from_post_entry_ohlcv", lambda *_a, **_k: None)
    monkeypatch.setattr(
        bot_loop,
        "apply_profit_protection",
        lambda *_a, **_k: ProtectionDecision(
            enabled=True,
            current_pips=1.0,
            max_profit_pips=1.0,
            active=protect,
            exit_threshold_pips=0.5,
            should_close=protect,
            just_activated=False,
            just_ratcheted=False,
        ),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec.get_api",
        lambda: (_ for _ in ()).throw(AssertionError("broker client requested")),
    )
    _CURRENT_CLOSE_TRANSPORT(positions, seen, close_error, with_kwargs=False)


def _run(symbol: str = "EUR_USD") -> None:
    asyncio.run(bot_loop._evaluate_impl(symbol))


def test_runtimeerror_from_fetch_still_manages_and_blocks_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles=RuntimeError("client exploded"),
        positions={"EUR_USD": _position("EUR_USD", "BUY", units=3.0)},
        weekend=True,
        quotes={"EUR_USD": _quote("EUR_USD")},
    )
    _run()
    assert seen.position == ["EUR_USD"]
    assert seen.execute[0][2] == "BUY"
    assert seen.execute[0][3] == 3.0
    assert seen.closed == ["EUR_USD"]
    assert seen.selected == 0
    assert seen.synthetic == 0
    assert live_order_auth_state() == AUTH_BLOCKED


def test_provenance_rejection_is_not_an_integrity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles=ProvenanceRejected("missing_protected_column"),
        positions={"EUR_USD": _position("EUR_USD", "SELL", units=2.0)},
        weekend=True,
        quotes={"EUR_USD": _quote("EUR_USD")},
    )
    _run()
    assert seen.execute[0][2] == "SELL"
    assert seen.closed == ["EUR_USD"]
    assert seen.selected == 0


def test_client_request_runtimeerror_becomes_missing_candles(monkeypatch: pytest.MonkeyPatch) -> None:
    class API:
        def request(self, _req):
            raise RuntimeError("broker response failed")

    monkeypatch.setattr("forex_bot.oanda_client.get_api", lambda: API())
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    from forex_bot.oanda_client import fetch_ohlcv

    assert fetch_ohlcv("EUR_USD", "M5", 5) is None

    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=True,
        quotes={"EUR_USD": _quote("EUR_USD")},
    )
    _run()
    assert seen.closed == ["EUR_USD"]
    assert seen.selected == 0


def test_connection_timeout_parse_and_incomplete_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    incomplete = _frame()
    incomplete.loc[incomplete.index[-1], "close"] = float("nan")
    cases = (
        ConnectionError("reset"),
        TimeoutError("read timed out"),
        ValueError("malformed"),
        KeyError("mid"),
        pd.DataFrame(),
        incomplete,
    )
    for candles in cases:
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=candles,
            positions={"EUR_USD": _position("EUR_USD", "BUY")},
            weekend=True,
            quotes={"EUR_USD": _quote("EUR_USD")},
        )
        _run()
        assert seen.position == ["EUR_USD"]
        assert seen.closed == ["EUR_USD"]
        assert seen.selected == 0
        assert seen.synthetic == 0


def test_no_position_runtimeerror_does_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles=RuntimeError("client exploded"),
        positions={"EUR_USD": None},
        weekend=False,
    )
    _run()
    assert seen.execute == []
    assert seen.closed == []
    assert seen.selected == 0


def test_quote_and_close_outcomes_with_runtimeerror(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = _Seen()
    _install(
        monkeypatch,
        fresh,
        candles=RuntimeError("down"),
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        quotes={"EUR_USD": _quote("EUR_USD")},
        protect=True,
    )
    _run()
    assert len(fresh.execute) == 1

    stale = _Seen()
    _install(
        monkeypatch,
        stale,
        candles=RuntimeError("down"),
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        quotes={"EUR_USD": _quote("EUR_USD", fresh=False)},
        protect=True,
    )
    _run()
    assert stale.execute == []

    missing = _Seen()
    _install(
        monkeypatch,
        missing,
        candles=RuntimeError("down"),
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        quotes={},
        weekend=True,
    )
    _run()
    assert missing.closed == ["EUR_USD"]

    failed = _Seen()
    _install(
        monkeypatch,
        failed,
        candles=RuntimeError("down"),
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        quotes={"EUR_USD": _quote("EUR_USD")},
        weekend=True,
        close_error=RuntimeError("broker rejected close"),
    )
    _run()
    assert len(failed.execute) == 1
    assert failed.closed == []

    ambiguous = _Seen()
    _install(
        monkeypatch,
        ambiguous,
        candles=RuntimeError("down"),
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        quotes={"EUR_USD": _quote("EUR_USD")},
        weekend=True,
        close_error=TimeoutError("read timed out"),
    )
    _run()
    assert len(ambiguous.execute) == 1
    assert ambiguous.closed == []


def test_weekend_flatten_survives_halt_and_runtimeerror(monkeypatch: pytest.MonkeyPatch) -> None:
    halt_trading()
    try:
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=RuntimeError("down"),
            positions={"EUR_USD": _position("EUR_USD", "SELL", units=4.0)},
            weekend=True,
            quotes={},
        )
        _run()
        assert seen.execute[0][2] == "SELL"
        assert seen.closed == ["EUR_USD"]
        assert live_order_auth_state() == AUTH_BLOCKED
    finally:
        resume_trading()


def test_position_book_failure_does_not_open_or_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles=_frame(),
        positions={"EUR_USD": RuntimeError("book unreadable")},
    )
    _run()
    assert seen.execute == []
    assert seen.selected == 0


def test_multi_symbol_acquisition_failures_and_integrity_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles={
            "EUR_USD": TimeoutError("eur"),
            "GBP_USD": ValueError("parse"),
            "USD_JPY": _frame(),
        },
        positions={
            "EUR_USD": _position("EUR_USD", "BUY"),
            "GBP_USD": _position("GBP_USD", "SELL", units=2.0),
            "USD_JPY": None,
        },
        weekend=True,
        quotes={name: _quote(name) for name in symbols},
    )
    asyncio.run(bot_loop._cycle_symbols(symbols))
    assert seen.position == symbols
    assert [call[0] for call in seen.execute] == ["EUR_USD", "GBP_USD"]
    assert seen.selected == 0

    both = _Seen()
    _install(
        monkeypatch,
        both,
        candles={
            "EUR_USD": RuntimeError("a"),
            "GBP_USD": ConnectionError("b"),
            "USD_JPY": ProvenanceRejected("seal"),
        },
        positions={name: _position(name, "BUY") for name in symbols},
        weekend=True,
        quotes={name: _quote(name) for name in symbols},
    )
    asyncio.run(bot_loop._cycle_symbols(symbols))
    assert both.position == symbols
    assert len(both.execute) == 3

    stopped: list[str] = []

    async def _impl(symbol: str) -> None:
        stopped.append(symbol)
        if symbol == "EUR_USD":
            raise bot_loop.CycleIntegrityError("book diverged")

    monkeypatch.setattr(bot_loop, "_evaluate_impl", _impl)
    with pytest.raises(bot_loop.CycleIntegrityError):
        asyncio.run(bot_loop._cycle_symbols(symbols))
    assert stopped == ["EUR_USD"]


def test_programming_error_after_candles_still_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_loop, "dispatch_production_iteration", lambda *_a, **_k: {"status": "continue_existing_production_broker"})
    monkeypatch.setattr(bot_loop, "fetch_ohlcv", lambda *_a, **_k: _frame())
    monkeypatch.setattr(bot_loop, "get_position", lambda _symbol: None)
    monkeypatch.setattr(bot_loop, "flatten_for_weekend", lambda: False)
    monkeypatch.setattr(bot_loop, "in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr(bot_loop, "pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr(
        "forex_bot.broker_exit.broker_exit_open_blocked_reason",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        bot_loop,
        "compute_indicators",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("indicator bug")),
    )
    with pytest.raises(RuntimeError, match="indicator bug"):
        asyncio.run(bot_loop.evaluate("EUR_USD"))


def test_cycle_integrity_from_fetch_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def _fetch(symbol, *_args, **_kwargs):
        seen.append(symbol)
        if symbol == "EUR_USD":
            raise bot_loop.CycleIntegrityError("shared latch")
        return _frame()

    monkeypatch.setattr(bot_loop, "fetch_ohlcv", _fetch)
    monkeypatch.setattr(bot_loop, "get_position", lambda _symbol: None)
    monkeypatch.setattr(bot_loop, "alert", lambda *_a, **_k: None)
    with pytest.raises(bot_loop.CycleIntegrityError):
        asyncio.run(bot_loop._cycle_symbols(["EUR_USD", "GBP_USD"]))
    assert seen == ["EUR_USD"]


def test_close_sides_timeout_and_blocked_open(monkeypatch: pytest.MonkeyPatch, entry_intent_factory, close_intent_factory) -> None:
    calls: list[dict] = []

    class FakeAPI:
        def request(self, req):
            calls.append(dict(req.data))
            if calls and "longUnits" in calls[-1]:
                raise TimeoutError("read timed out")
            side = "shortOrderFillTransaction" if "shortUnits" in req.data else "longOrderFillTransaction"
            return {side: {"price": "1.1", "pl": "0.1", "units": "1"}}

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "not-a-real-token")
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        _place_market_order_open_sync("EUR_USD", 1.0, "BUY", "cid", entry_quote=mint_live_quote(), entry_permit=entry_intent_factory(units=1, client_order_id="cid"))
    assert calls == []
    with pytest.raises(TimeoutError, match="timed out"):
        _place_market_order_sync("EUR_USD", 3.0, "BUY", close_intent_factory(units=3.0, direction="BUY"))
    assert calls == [{"longUnits": "3"}]
    calls.clear()
    _place_market_order_sync("EUR_USD", 2.0, "SELL", close_intent_factory(units=2.0, direction="SELL"))
    assert calls == [{"shortUnits": "2"}]
    assert live_order_auth_state() == AUTH_BLOCKED


def test_frozen_artifacts_remain() -> None:
    def _sha(path: Path) -> str:
        payload = path.read_bytes()
        if path.name == ".dockerignore":
            payload = payload.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return hashlib.sha256(payload).hexdigest()

    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g7/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["manifest_sha256"] == (
        "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
    )
    assert _sha(ROOT / "data/research/adaptive_ensemble/g7/source_snapshot.tar") == (
        "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82"
    )
    assert _sha(ROOT / ".dockerignore") == (
        "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd"
    )
