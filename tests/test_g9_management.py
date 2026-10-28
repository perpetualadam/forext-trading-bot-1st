"""Stage G.9 candle-failure management tests. Broker calls are mocked."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from forex_bot import bot_loop
from forex_bot.execution import halt_trading, resume_trading
from forex_bot.live_manage import ManageQuote
from forex_bot.live_manage import resolve_broker_manage_price as _real_resolve
from forex_bot.live_safety import AUTH_BLOCKED, live_order_auth_state
from forex_bot.market_provenance import (
    CACHED_UNVERIFIED,
    REPLAYED_DATA,
    bind_historical_frame,
    bind_live_frame,
    bind_synthetic_frame,
    decision_frame_rejection,
    mint_live_quote,
    untrusted,
)
from forex_bot.oanda_client import official_rest_host
from forex_bot.oanda_exec import _place_market_order_open_sync, _place_market_order_sync
from forex_bot.positions import Position
from forex_bot.profit_protection import ProtectionDecision
from forex_bot.strategy_meta import strategies

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
G7 = ROOT / "data" / "research" / "adaptive_ensemble" / "g7"


def _bars(*, close: float = 1.1, stale: bool = False) -> pd.DataFrame:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    if stale:
        end = end - timedelta(days=30)
    idx = pd.date_range(end - timedelta(minutes=25), periods=6, freq="5min", tz="UTC")
    px = [close + i * 0.0001 for i in range(6)]
    return pd.DataFrame(
        {
            "time": list(idx),
            "open": px,
            "high": [v + 0.0002 for v in px],
            "low": [v - 0.0002 for v in px],
            "close": [v + 0.00005 for v in px],
            "complete": [True] * 6,
            "volume": [10] * 6,
        }
    )


def _position(symbol: str, direction: str, *, kind: str = "live", units: float = 1.0) -> Position:
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
        execution_kind=kind,
        broker_order=kind == "live",
    )


def _quote(
    symbol: str,
    *,
    fresh: bool = True,
    bid: float | None = 1.1,
    ask: float | None = 1.1002,
    instrument: str | None = None,
) -> ManageQuote:
    return ManageQuote(
        instrument=symbol if instrument is None else instrument,
        bid=bid,
        ask=ask,
        closeout_bid=None if bid is None else bid - 0.0001,
        closeout_ask=None if ask is None else ask + 0.0001,
        time_epoch=None if fresh is None else time.time() - (0 if fresh else 500),
        tradeable=True,
    )


class _Seen:
    def __init__(self) -> None:
        self.position: list[str] = []
        self.execute: list[tuple] = []
        self.closed: list[str] = []
        self.resolve: list[object] = []
        self.selected: list[str] = []
        self.mids: list[str] = []
        self.synthetic = 0


@pytest.fixture(autouse=True)
def _current_close_context(monkeypatch, managed_close_transport):
    monkeypatch.setitem(globals(), "_CURRENT_CLOSE_TRANSPORT", managed_close_transport)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    seen: _Seen,
    *,
    candles,
    positions: dict[str, Position | None],
    weekend: bool = False,
    session: bool = True,
    quote_for=None,
    quote_error: BaseException | None = None,
    close_error: BaseException | None = None,
    fill_path: str = "broker",
    protect: bool = False,
) -> None:
    def _fetch(symbol, *_args, **_kwargs):
        if isinstance(candles, Exception):
            raise candles
        if isinstance(candles, dict):
            item = candles[symbol]
            if isinstance(item, Exception):
                raise item
            return item
        return candles

    def _get(symbol: str):
        seen.position.append(symbol)
        if isinstance(positions.get(symbol), Exception):
            raise positions[symbol]
        return positions.get(symbol)

    async def _execute(*args, **kwargs):
        seen.execute.append((args, kwargs))
        if close_error is not None:
            raise close_error
        return 0.0

    def _resolve(quote, direction, **kwargs):
        seen.resolve.append(quote)
        return _real_resolve(quote, direction, **kwargs)

    def _select(*_args, **_kwargs):
        seen.selected.append("selected")
        raise AssertionError("new entry was evaluated")

    monkeypatch.setattr(bot_loop, "fetch_ohlcv", _fetch)
    monkeypatch.setattr(bot_loop, "get_position", _get)
    monkeypatch.setattr(bot_loop, "flatten_for_weekend", lambda: weekend)
    monkeypatch.setattr(bot_loop, "in_active_session", lambda *_a, **_k: session)
    monkeypatch.setattr(bot_loop, "execute_trade", _execute)
    monkeypatch.setattr(bot_loop, "close_position", lambda symbol: seen.closed.append(symbol))
    monkeypatch.setattr(bot_loop, "close_fill_path", lambda *_a, **_k: fill_path)
    monkeypatch.setattr(bot_loop, "select_strategy", _select)
    monkeypatch.setattr(bot_loop, "_persist_v2_shadow_market_m5", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_safe_audit", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_reject", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "_audit_close", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "record_mid", lambda symbol, _price: seen.mids.append(symbol))
    def _count_synthetic(frame):
        seen.synthetic += 1
        return bind_synthetic_frame(frame)

    monkeypatch.setattr(bot_loop, "alert", lambda *_a, **_k: None)
    monkeypatch.setenv("POSITION_LOG", "0")
    monkeypatch.setenv("MIN_POSITION_HOLD_SEC", "0")
    monkeypatch.setattr("forex_bot.live_manage.resolve_broker_manage_price", _resolve)
    monkeypatch.setattr("forex_bot.market_provenance.bind_synthetic_frame", _count_synthetic)

    def _snap():
        if quote_error is not None:
            raise quote_error
        if quote_for is None:
            return {}
        return quote_for()

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
    _CURRENT_CLOSE_TRANSPORT(positions, seen, close_error, with_kwargs=True)


def _no_quotes() -> dict:
    return {}


def _fresh(symbol: str = "EUR_USD"):
    return lambda: {symbol: _quote(symbol)}


def _run(symbol: str = "EUR_USD") -> None:
    asyncio.run(bot_loop._evaluate_impl(symbol))


def test_missing_empty_exception_and_incomplete_frames_block_entries_and_keep_management(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = _bars()
    incomplete.loc[incomplete.index[-1], "close"] = float("nan")
    cases = {
        "none": None,
        "empty": pd.DataFrame(),
        "network": TimeoutError("down"),
        "parse": ValueError("bad candle"),
        "incomplete": incomplete,
    }
    for candles in cases.values():
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=candles,
            positions={"EUR_USD": _position("EUR_USD", "BUY")},
            weekend=True,
            quote_for=_fresh(),
        )
        _run()
        assert seen.position == ["EUR_USD"]
        assert len(seen.resolve) == 1
        assert len(seen.execute) == 1
        assert seen.closed == ["EUR_USD"]
        assert seen.selected == []
        assert seen.synthetic == 0
        assert seen.execute[0][0][2] == "BUY"
        assert seen.execute[0][0][3] == 1.0


def test_no_position_and_bad_frames_do_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    for candles in (None, pd.DataFrame(), TimeoutError("down"), ValueError("parse")):
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=candles,
            positions={"EUR_USD": None},
            weekend=False,
            session=True,
        )
        _run()
        assert seen.position == ["EUR_USD"]
        assert seen.execute == []
        assert seen.closed == []
        assert seen.selected == []
        assert seen.mids == []
        assert seen.synthetic == 0


def test_long_and_short_closes_keep_the_open_side(monkeypatch: pytest.MonkeyPatch) -> None:
    for direction, units in (("BUY", 3.0), ("SELL", 2.0)):
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=None,
            positions={"EUR_USD": _position("EUR_USD", direction, units=units)},
            weekend=True,
            quote_for=_fresh(),
        )
        _run()
        assert seen.execute[0][0][2] == direction
        assert seen.execute[0][0][3] == units
        assert seen.closed == ["EUR_USD"]


def test_fresh_stale_missing_and_invalid_management_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = _Seen()
    _install(
        monkeypatch,
        fresh,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=False,
        quote_for=_fresh(),
        protect=True,
    )
    _run()
    assert fresh.resolve[0] is not None
    assert len(fresh.execute) == 1
    assert fresh.closed == ["EUR_USD"]

    stale = _Seen()
    _install(
        monkeypatch,
        stale,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=False,
        quote_for=lambda: {"EUR_USD": _quote("EUR_USD", fresh=False)},
        protect=True,
    )
    _run()
    assert stale.execute == []
    assert stale.closed == []

    missing = _Seen()
    _install(
        monkeypatch,
        missing,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=False,
        quote_for=_no_quotes,
    )
    _run()
    assert missing.resolve == [None]
    assert missing.execute == []

    invalid = _Seen()
    _install(
        monkeypatch,
        invalid,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=False,
        quote_for=lambda: {"EUR_USD": _quote("EUR_USD", bid=1.2, ask=1.1)},
    )
    _run()
    assert invalid.resolve == [None]
    assert invalid.execute == []

    wrong = _Seen()
    _install(
        monkeypatch,
        wrong,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=False,
        quote_for=lambda: {"EUR_USD": _quote("EUR_USD", instrument="GBP_USD")},
    )
    _run()
    assert wrong.resolve == [None]
    assert wrong.execute == []


def test_software_stop_uses_a_paper_price_and_not_a_missing_candle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _Seen()
    pos = _position("EUR_USD", "BUY", kind="simulated")
    pos.stop_loss = 1.2
    _install(
        monkeypatch,
        seen,
        candles=_bars(close=1.05),
        positions={"EUR_USD": pos},
        weekend=False,
        fill_path="mid",
    )
    _run()
    assert len(seen.execute) == 1
    assert seen.closed == ["EUR_USD"]

    blocked = _Seen()
    _install(
        monkeypatch,
        blocked,
        candles=None,
        positions={"EUR_USD": pos},
        weekend=True,
        fill_path="simulate",
    )
    _run()
    assert blocked.execute == []
    assert blocked.closed == []
    assert blocked.synthetic == 0


def test_weekend_flatten_and_emergency_halt_do_not_need_candles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    halt_trading()
    try:
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=None,
            positions={"EUR_USD": _position("EUR_USD", "SELL", units=4.0)},
            weekend=True,
            quote_for=_no_quotes,
        )
        _run()
        assert seen.execute[0][0][2] == "SELL"
        assert seen.closed == ["EUR_USD"]
        assert live_order_auth_state() == AUTH_BLOCKED
    finally:
        resume_trading()


def test_failed_and_unconfirmed_closes_do_not_clear_the_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for error in (TimeoutError("read timed out"), RuntimeError("broker rejected close")):
        seen = _Seen()
        _install(
            monkeypatch,
            seen,
            candles=None,
            positions={"EUR_USD": _position("EUR_USD", "BUY")},
            weekend=True,
            quote_for=_fresh(),
            close_error=error,
        )
        _run()
        assert len(seen.execute) == 1
        assert seen.closed == []


def test_position_lookup_and_quote_lookup_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    unavailable = _Seen()
    _install(
        monkeypatch,
        unavailable,
        candles=_bars(),
        positions={"EUR_USD": RuntimeError("book unreadable")},
        weekend=False,
        session=True,
    )
    _run()
    assert unavailable.execute == []
    assert unavailable.selected == []

    lookup = _Seen()
    _install(
        monkeypatch,
        lookup,
        candles=None,
        positions={"EUR_USD": _position("EUR_USD", "BUY")},
        weekend=True,
        quote_error=RuntimeError("pricing down"),
    )
    _run()
    assert lookup.resolve == [None]
    assert len(lookup.execute) == 1
    assert lookup.closed == ["EUR_USD"]


def test_uncertain_position_is_not_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _Seen()
    pos = _position("EUR_USD", "BUY")
    pos.direction = "FLAT"
    _install(
        monkeypatch,
        seen,
        candles=None,
        positions={"EUR_USD": pos},
        weekend=True,
        quote_for=_fresh(),
    )
    _run()
    assert seen.execute == []
    assert seen.closed == []


def test_multi_instrument_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
    seen = _Seen()
    _install(
        monkeypatch,
        seen,
        candles={
            "EUR_USD": TimeoutError("eur down"),
            "GBP_USD": _bars(),
            "USD_JPY": _bars(),
        },
        positions={
            "EUR_USD": _position("EUR_USD", "BUY"),
            "GBP_USD": None,
            "USD_JPY": _position("USD_JPY", "SELL", units=5.0),
        },
        weekend=True,
        quote_for=lambda: {
            "EUR_USD": _quote("EUR_USD"),
            "USD_JPY": _quote("USD_JPY"),
        },
    )
    asyncio.run(bot_loop._cycle_symbols(symbols))
    assert seen.position == symbols
    assert [call[0][0] for call in seen.execute] == ["EUR_USD", "USD_JPY"]
    assert seen.closed == ["EUR_USD", "USD_JPY"]
    assert seen.synthetic == 0

    middle = _Seen()
    _install(
        monkeypatch,
        middle,
        candles={
            "EUR_USD": _bars(),
            "GBP_USD": ValueError("parse"),
            "USD_JPY": None,
        },
        positions={
            "EUR_USD": _position("EUR_USD", "BUY"),
            "GBP_USD": _position("GBP_USD", "SELL"),
            "USD_JPY": _position("USD_JPY", "BUY"),
        },
        weekend=True,
        quote_for=lambda: {name: _quote(name) for name in symbols},
    )
    asyncio.run(bot_loop._cycle_symbols(symbols))
    assert middle.position == symbols
    assert len(middle.execute) == 3

    failed_close = _Seen()
    failing_book = {name: _position(name, "BUY") for name in symbols}

    async def _execute(symbol, *_args, **_kwargs):
        failed_close.execute.append((symbol,))
        if symbol == "EUR_USD":
            raise TimeoutError("unconfirmed")
        return 0.0

    _install(
        monkeypatch,
        failed_close,
        candles={"EUR_USD": None, "GBP_USD": None, "USD_JPY": None},
        positions=failing_book,
        weekend=True,
        quote_for=lambda: {name: _quote(name) for name in symbols},
    )
    _CURRENT_CLOSE_TRANSPORT(failing_book, failed_close, lambda symbol: TimeoutError("unconfirmed") if symbol == "EUR_USD" else None, with_kwargs=True)
    asyncio.run(bot_loop._cycle_symbols(symbols))
    assert [item[0][0] for item in failed_close.execute] == symbols
    assert failed_close.closed == ["GBP_USD", "USD_JPY"]


def test_shared_state_failure_stops_the_remaining_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def _impl(symbol: str) -> None:
        seen.append(symbol)
        if symbol == "EUR_USD":
            raise bot_loop.CycleIntegrityError("position book diverged")

    monkeypatch.setattr(bot_loop, "_evaluate_impl", _impl)
    with pytest.raises(bot_loop.CycleIntegrityError):
        asyncio.run(bot_loop._cycle_symbols(["EUR_USD", "GBP_USD", "USD_JPY"]))
    assert seen == ["EUR_USD"]


def test_programming_error_is_recorded_and_later_symbols_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    async def _impl(symbol: str) -> None:
        seen.append(symbol)
        if symbol == "GBP_USD":
            raise RuntimeError("injected evaluation error")

    monkeypatch.setattr(bot_loop, "_evaluate_impl", _impl)
    asyncio.run(bot_loop._cycle_symbols(["EUR_USD", "GBP_USD", "USD_JPY"]))
    assert seen == ["EUR_USD", "GBP_USD", "USD_JPY"]


def test_repeated_candle_failures_do_not_fabricate_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _Seen()
    _install(monkeypatch, seen, candles=None, positions={"EUR_USD": None}, weekend=False)
    _run()
    _run()
    assert seen.mids == []
    assert seen.synthetic == 0
    assert seen.execute == []


def _indicator_frame() -> pd.DataFrame:
    frame = _bars()
    frame["ma_fast"] = frame["close"] + 0.001
    frame["ma_slow"] = frame["close"]
    frame["atr"] = 0.001
    frame["trend"] = 0.1
    frame["volatility"] = 0.01
    return frame


def _sealed() -> pd.DataFrame:
    return bind_live_frame(_bars(), instrument="EUR_USD", host=official_rest_host())


def _drive_entry(monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame) -> list[str]:
    # Isolate the downstream provenance gate; no production producer is granted.
    monkeypatch.setattr(bot_loop, "dispatch_production_iteration", lambda *_a, **_k: {"status": "continue_existing_production_broker"})
    monkeypatch.setattr("forex_bot.database.exposure_entry_block_reason", lambda *_a, **_k: None)
    reasons: list[str] = []
    reached: list[str] = []
    real = decision_frame_rejection

    def _reject(raw, symbol, **kwargs):
        reason = real(raw, symbol, **kwargs)
        reasons.append(reason or "accepted")
        return reason

    async def _vote(*_args, **_kwargs):
        return {"allow": True, "direction": "BUY", "confidence": 0.9, "model": "stub"}

    def _reserve(**_kwargs):
        reached.append("reserve")
        return False

    monkeypatch.setattr(bot_loop, "fetch_ohlcv", lambda *_a, **_k: frame)
    monkeypatch.setattr(bot_loop, "get_position", lambda _symbol: None)
    monkeypatch.setattr(bot_loop, "flatten_for_weekend", lambda: False)
    monkeypatch.setattr(bot_loop, "in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr(
        "forex_bot.broker_exit.broker_exit_open_blocked_reason",
        lambda _symbol: None,
    )
    monkeypatch.setattr(bot_loop, "pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr(bot_loop, "compute_indicators", lambda *_a, **_k: _indicator_frame())
    monkeypatch.setattr(bot_loop, "volatility_ok", lambda _df: True)
    monkeypatch.setattr(bot_loop, "select_strategy", lambda *_a, **_k: ("trend", 20, "legacy"))
    monkeypatch.setattr(bot_loop.ai, "vote", _vote)
    monkeypatch.setattr(bot_loop.rl_agent, "decide", lambda _state: "BUY")
    monkeypatch.setattr(bot_loop, "position_sizing", lambda *_a, **_k: 100.0)
    monkeypatch.setattr(bot_loop, "cap_position_units", lambda units: units)
    monkeypatch.setattr(bot_loop, "current_equity", lambda: 100000.0)
    monkeypatch.setattr(bot_loop, "pre_close_adjustment", lambda _symbol: False)
    monkeypatch.setattr(bot_loop, "open_fill_path", lambda _symbol: "broker")
    monkeypatch.setattr(bot_loop, "is_live_trading", lambda _symbol: True)
    monkeypatch.setattr(bot_loop, "sl_tp_distance_for_entry", lambda *_a, **_k: (0.001, 0.002))
    monkeypatch.setattr(bot_loop.portfolio, "get_weight", lambda _symbol: 1.0)
    monkeypatch.setattr(bot_loop, "_observe_v2_shadow_candidate", lambda **_k: None)
    monkeypatch.setattr(bot_loop, "_persist_v2_shadow_market_m5", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "alert", lambda *_a, **_k: None)
    monkeypatch.setattr(bot_loop, "try_begin_order_submission", _reserve)
    monkeypatch.setattr("forex_bot.market_provenance.decision_frame_rejection", _reject)
    monkeypatch.setattr(
        "forex_bot.oanda_exec.get_api",
        lambda: (_ for _ in ()).throw(AssertionError("broker client requested")),
    )
    strat = strategies["trend"]
    previous = (strat.active, strat.authorised_for_live)
    strat.active = True
    strat.authorised_for_live = True
    try:
        asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
    finally:
        strat.active, strat.authorised_for_live = previous
    assert reached == []
    return reasons


def test_untrusted_frames_reach_provenance_and_submit_no_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical = bind_historical_frame(_bars(), instrument="EUR_USD", host=official_rest_host())
    replayed = _bars()
    replayed.attrs["market_provenance"] = untrusted(REPLAYED_DATA, endpoint="replay")
    cached = _bars()
    cached.attrs["market_provenance"] = untrusted(CACHED_UNVERIFIED, endpoint="process_cache")
    tampered = _sealed()
    tampered.loc[tampered.index[0], "open"] = 9.9
    stale = bind_live_frame(
        _bars(),
        instrument="EUR_USD",
        host=official_rest_host(),
        acquired_mono=time.monotonic() - 10_000,
    )
    cases = [
        bind_synthetic_frame(_bars()),
        historical,
        replayed,
        _bars(),
        cached,
        stale,
        tampered,
    ]
    for frame in cases:
        reasons = _drive_entry(monkeypatch, frame)
        assert reasons
        assert reasons[0] != "accepted"
        assert live_order_auth_state() == AUTH_BLOCKED


def test_direct_open_stays_blocked_and_close_cannot_reverse(monkeypatch: pytest.MonkeyPatch, entry_intent_factory, close_intent_factory) -> None:
    calls: list[dict] = []

    class FakeAPI:
        def request(self, req):
            calls.append(dict(req.data))
            side = "shortOrderFillTransaction" if "shortUnits" in req.data else "longOrderFillTransaction"
            return {side: {"price": "1.1", "pl": "0.1", "units": "1"}}

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "not-a-real-token")
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        _place_market_order_open_sync(
            "EUR_USD", 1.0, "BUY", "cid", entry_quote=mint_live_quote(), entry_permit=entry_intent_factory(units=1, client_order_id="cid")
        )
    assert calls == []
    _place_market_order_sync("EUR_USD", 3.0, "BUY", close_intent_factory(units=3.0, direction="BUY"))
    _place_market_order_sync("EUR_USD", 2.0, "SELL", close_intent_factory(units=2.0, direction="SELL"))
    assert calls == [{"longUnits": "3"}, {"shortUnits": "2"}]
    assert all("positionFill" not in item for item in calls)
    calls.clear()
    with pytest.raises(RuntimeError, match="uncertain position direction"):
        _place_market_order_sync("EUR_USD", 1.0, "FLAT", close_intent_factory())
    with pytest.raises(RuntimeError, match="uncertain position size"):
        _place_market_order_sync("EUR_USD", float("nan"), "BUY", close_intent_factory())
    assert calls == []
    assert live_order_auth_state() == AUTH_BLOCKED


def test_close_timeout_is_not_retried_inside_the_broker_call(monkeypatch: pytest.MonkeyPatch, entry_intent_factory, close_intent_factory) -> None:
    calls = {"n": 0}

    class FakeAPI:
        def request(self, _req):
            calls["n"] += 1
            raise TimeoutError("read timed out")

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    with pytest.raises(TimeoutError, match="timed out"):
        _place_market_order_sync("EUR_USD", 1.0, "BUY", close_intent_factory(units=1.0, direction="BUY"))
    assert calls["n"] == 1


def test_frozen_g7_snapshot_and_g8_dockerignore_are_unchanged() -> None:
    def _sha(path) -> str:
        payload = path.read_bytes()
        if path.name == ".dockerignore":
            payload = payload.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return hashlib.sha256(payload).hexdigest()

    manifest = json.loads((G7 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_sha256"] == (
        "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
    )
    assert _sha(G7 / "source_snapshot.tar") == (
        "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82"
    )
    assert _sha(ROOT / ".dockerignore") == (
        "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd"
    )
