"""Live manage-price / MFE invariant: no pre-entry movement on broker-backed positions."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import pytest

from forex_bot.execution import is_broker_backed
from forex_bot.live_manage import (
    PRICE_SOURCE_OANDA_CURRENT,
    PRICE_SOURCE_PAPER_CANDLE,
    PRICE_SOURCE_UNAVAILABLE,
    ManageQuote,
    broker_sl_tp_hit,
    closeout_manage_price,
    format_close_decision_line,
    format_manage_price_line,
    resolve_broker_manage_price,
)
from forex_bot.positions import Position, import_position_from_broker, positions
from forex_bot.profit_protection import (
    apply_profit_protection,
    candle_vs_fill,
    raise_mfe_from_post_entry_ohlcv,
    reconstruct_mfe_from_ohlcv,
    seed_position_mfe,
)


FILL_1621 = datetime(2026, 9, 20, 23, 6, 26, tzinfo=timezone.utc).timestamp()


def _pos(
    *,
    symbol: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    open_time: float,
    kind: str = "live",
    broker_id: str = "",
    seeded: bool = True,
) -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=2.0,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        open_time=open_time,
        strategy_name="swing_trend",
        rl_state="s",
        execution_kind=kind,
        broker_order=kind == "live",
        broker_order_id=broker_id,
        max_profit_pips=0.0,
        profit_protection_seeded=seeded,
    )


def _partial_usd_jpy_ohlcv() -> pd.DataFrame:
    """23:00 pre-entry, 23:05 partial (high 156.876), 23:10 post-entry."""
    return pd.DataFrame(
        [
            {
                "time": "2026-09-20T23:00:00.000000000Z",
                "open": 156.80,
                "high": 156.90,
                "low": 156.70,
                "close": 156.736,
            },
            {
                "time": "2026-09-20T23:05:00.000000000Z",
                "open": 156.736,
                "high": 156.876,
                "low": 156.72,
                "close": 156.736,
            },
            {
                "time": "2026-09-20T23:10:00.000000000Z",
                "open": 156.76,
                "high": 156.78,
                "low": 156.75,
                "close": 156.77,
            },
        ]
    )


@pytest.fixture(autouse=True)
def _pp_defaults(monkeypatch):
    monkeypatch.setenv("PROFIT_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("PROFIT_PROTECTION_TRIGGER_PERCENT", "0.67")
    monkeypatch.setenv("PROFIT_GIVEBACK_ATR_MULTIPLIER", "0.5")
    monkeypatch.setenv("PROFIT_PROTECTION_ATR_PERIOD", "14")
    monkeypatch.setenv("PROFIT_GIVEBACK_PIPS", "4")
    positions.clear()
    yield
    positions.clear()


def test_candle_classifier_1621_partial_bar():
    fill = FILL_1621
    assert candle_vs_fill(datetime(2026, 9, 20, 23, 0, tzinfo=timezone.utc).timestamp(), fill) == "pre_entry"
    assert candle_vs_fill(datetime(2026, 9, 20, 23, 5, tzinfo=timezone.utc).timestamp(), fill) == "partial_entry"
    assert candle_vs_fill(datetime(2026, 9, 20, 23, 10, tzinfo=timezone.utc).timestamp(), fill) == "post_entry"


def test_1621_cannot_inherit_partial_bar_high_as_mfe():
    rec = reconstruct_mfe_from_ohlcv(
        "USD_JPY",
        "BUY",
        156.757,
        FILL_1621,
        _partial_usd_jpy_ohlcv(),
        include_partial_entry_bar=False,
    )
    assert rec is not None
    # Only 23:10 high 156.78 → 2.3 pips, not 11.9 from 156.876
    assert rec == pytest.approx(2.3, abs=0.05)
    rec_legacy = reconstruct_mfe_from_ohlcv(
        "USD_JPY",
        "BUY",
        156.757,
        FILL_1621,
        _partial_usd_jpy_ohlcv(),
        include_partial_entry_bar=True,
    )
    assert rec_legacy == pytest.approx(11.9, abs=0.05)


def test_1589_1597_1621_pp_cannot_activate_from_pre_entry_mfe():
    cases = [
        ("EUR_USD", 1.14803, 1.14769, 1.14871, 1.14783, 1.14800),
        ("EUR_USD", 1.14806, 1.14771, 1.14875, 1.14790, 1.14810),
        ("USD_JPY", 156.757, 156.6988, 156.8734, 156.766, 156.736),
    ]
    for symbol, entry, sl, tp, closeout, _stale in cases:
        pos = _pos(
            symbol=symbol,
            direction="BUY",
            entry=entry,
            sl=sl,
            tp=tp,
            open_time=FILL_1621,
            broker_id="x",
        )
        assert is_broker_backed(pos)
        seed = seed_position_mfe(pos, closeout, _partial_usd_jpy_ohlcv(), include_partial_entry_bar=False)
        assert seed == "already"
        raise_mfe_from_post_entry_ohlcv(pos, _partial_usd_jpy_ohlcv() if symbol == "USD_JPY" else None)
        d = apply_profit_protection(pos, closeout)
        assert d.should_close is False
        if symbol == "USD_JPY":
            assert pos.max_profit_pips < 7.80


def test_1629_stale_m5_cannot_trip_fill_based_sl():
    pos = _pos(
        symbol="USD_JPY",
        direction="BUY",
        entry=156.832,
        sl=156.7738,
        tp=156.9484,
        open_time=FILL_1621,
        broker_id="1629",
    )
    stale = 156.736
    assert stale <= pos.stop_loss
    assert broker_sl_tp_hit(pos) is False
    closeout = 156.834
    d = apply_profit_protection(pos, closeout)
    assert d.should_close is False
    assert d.active is False


def test_paper_kind_still_trips_sl_on_candle_close():
    pos = _pos(
        symbol="USD_JPY",
        direction="BUY",
        entry=156.832,
        sl=156.7738,
        tp=156.9484,
        open_time=FILL_1621,
        kind="simulated",
        seeded=False,
    )
    pos.broker_order = False
    assert is_broker_backed(pos) is False
    price = 156.736
    sl_tp = price <= pos.stop_loss or price >= pos.take_profit
    assert sl_tp is True


def test_genuine_post_entry_move_can_activate_pp():
    entry = 1.10000
    pos = _pos(
        symbol="EUR_USD",
        direction="BUY",
        entry=entry,
        sl=entry - 0.0010,
        tp=entry + 0.0010,
        open_time=time.time(),
    )
    # 67% of 10 pips = 6.7
    px = entry + 0.00068
    d = apply_profit_protection(pos, px, atr_price=0.0008)
    assert d.active is True
    assert d.should_close is False


def test_genuine_giveback_closes_after_activation():
    entry = 1.10000
    pos = _pos(
        symbol="EUR_USD",
        direction="BUY",
        entry=entry,
        sl=entry - 0.0010,
        tp=entry + 0.0010,
        open_time=time.time(),
    )
    apply_profit_protection(pos, entry + 0.00080, atr_price=0.0008)
    assert pos.profit_protection_active is True
    d = apply_profit_protection(pos, entry + 0.00020, atr_price=0.0008)
    assert d.should_close is True


def test_sell_is_symmetric_partial_bar_ignored():
    fill = datetime(2026, 9, 20, 23, 6, 26, tzinfo=timezone.utc).timestamp()
    ohlcv = pd.DataFrame(
        [
            {
                "time": "2026-09-20T23:05:00.000000000Z",
                "high": 1.1050,
                "low": 1.0900,
                "close": 1.1000,
            }
        ]
    )
    rec = reconstruct_mfe_from_ohlcv(
        "EUR_USD",
        "SELL",
        1.10000,
        fill,
        ohlcv,
        include_partial_entry_bar=False,
    )
    assert rec is None
    quote = ManageQuote(
        instrument="EUR_USD",
        closeout_bid=1.09950,
        closeout_ask=1.09960,
        time_epoch=time.time(),
        tradeable=True,
    )
    px, src = resolve_broker_manage_price(quote, "SELL")
    assert src == PRICE_SOURCE_OANDA_CURRENT
    assert px == pytest.approx(1.09960)
    pos = _pos(
        symbol="EUR_USD",
        direction="SELL",
        entry=1.10000,
        sl=1.10100,
        tp=1.09800,
        open_time=fill,
    )
    d = apply_profit_protection(pos, px)
    assert d.current_pips == pytest.approx(4.0, abs=0.05)
    assert d.should_close is False


def test_restart_import_does_not_manufacture_mfe():
    import_position_from_broker(
        "USD_JPY",
        2.0,
        156.757,
        156.6988,
        156.8734,
        open_time=FILL_1621,
        broker_order_id="1621",
    )
    pos = positions["USD_JPY"]
    assert pos.profit_protection_seeded is True
    assert pos.max_profit_pips == pytest.approx(0.0)
    raise_mfe_from_post_entry_ohlcv(pos, _partial_usd_jpy_ohlcv())
    # 23:10 high only (2.3 pips), not 11.9
    assert pos.max_profit_pips == pytest.approx(2.3, abs=0.05)
    d = apply_profit_protection(pos, 156.736)
    assert d.should_close is False


def test_closeout_side_buy_vs_sell():
    q = ManageQuote(
        instrument="EUR_USD",
        closeout_bid=1.10010,
        closeout_ask=1.10030,
        time_epoch=time.time(),
        tradeable=True,
    )
    assert closeout_manage_price(q, "BUY") == pytest.approx(1.10010)
    assert closeout_manage_price(q, "SELL") == pytest.approx(1.10030)


def test_missing_or_stale_quote_is_unavailable():
    assert resolve_broker_manage_price(None, "BUY") == (None, PRICE_SOURCE_UNAVAILABLE)
    stale = ManageQuote(
        instrument="EUR_USD",
        closeout_bid=1.1,
        closeout_ask=1.1,
        time_epoch=time.time() - 200,
        tradeable=True,
    )
    px, src = resolve_broker_manage_price(stale, "BUY", now=time.time())
    assert px is None
    assert src == PRICE_SOURCE_UNAVAILABLE
    dead = ManageQuote(
        instrument="EUR_USD",
        closeout_bid=1.1,
        closeout_ask=1.1,
        time_epoch=time.time(),
        tradeable=False,
    )
    assert resolve_broker_manage_price(dead, "BUY")[1] == PRICE_SOURCE_UNAVAILABLE


def test_logging_helpers_include_price_source():
    line = format_manage_price_line(
        symbol="USD_JPY",
        broker_id="1621",
        side="BUY",
        source=PRICE_SOURCE_OANDA_CURRENT,
        current_price=156.766,
        fill=156.757,
        current_pips=0.9,
        mfe_pips=0.9,
        tp_progress=0.08,
    )
    assert "source=OANDA_CURRENT" in line
    assert "broker_id=1621" in line
    close = format_close_decision_line(
        symbol="USD_JPY",
        broker_id="1621",
        reason="profit_protection",
        entry=156.757,
        current_price=156.766,
        price_source=PRICE_SOURCE_OANDA_CURRENT,
        sl=156.6988,
        tp=156.8734,
        mfe_pips=8.2,
        tp_progress=0.70,
        protected_exit_pips=6.5,
        trigger="protect_hit",
        sl_tp_hit=False,
        weekend_flat=False,
        protect_hit=True,
        current_side="BUY",
    )
    assert "reason=profit_protection" in close
    assert "price_source=OANDA_CURRENT" in close
    assert PRICE_SOURCE_PAPER_CANDLE != PRICE_SOURCE_OANDA_CURRENT


def test_pricing_snapshot_parses_one_batched_response(monkeypatch):
    from forex_bot import oanda_client as oc

    class FakeAPI:
        pass

    def fake_request(_api, _r, **_k):
        return {
            "prices": [
                {
                    "instrument": "USD_JPY",
                    "time": "2026-09-20T23:07:27.000000000Z",
                    "status": "tradeable",
                    "closeoutBid": "156.766",
                    "closeoutAsk": "156.770",
                    "bids": [{"price": "156.766"}],
                    "asks": [{"price": "156.770"}],
                }
            ]
        }

    monkeypatch.setattr(oc, "get_api", lambda: FakeAPI())
    monkeypatch.setattr(oc.Config, "OANDA_ACCOUNT_ID", "ACC")
    monkeypatch.setattr(oc, "_oanda_request", fake_request)
    snap = oc.fetch_pricing_snapshot(["USD_JPY"])
    assert "USD_JPY" in snap
    q = snap["USD_JPY"]
    assert q.closeout_bid == pytest.approx(156.766)
    px, src = resolve_broker_manage_price(q, "BUY", now=q.time_epoch)
    assert src == PRICE_SOURCE_OANDA_CURRENT
    assert px == pytest.approx(156.766)
