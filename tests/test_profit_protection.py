"""MFE profit protection: %-of-TP activate, ratchet, close, SELL, restart, retry."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from forex_bot.positions import Position
from forex_bot.profit_protection import (
    activation_trigger_pips,
    apply_profit_protection,
    atr_to_pips,
    mark_protection_close_attempt,
    original_tp_distance_pips,
    pip_size,
    protection_close_allowed,
    reconstruct_mfe_from_ohlcv,
    resolve_giveback_pips,
    seed_position_mfe,
    unrealized_profit_pips,
)


def _px(entry: float, pips: float, *, direction: str = "BUY", symbol: str = "EUR_USD") -> float:
    pip = pip_size(symbol)
    if direction == "SELL":
        return entry - pips * pip
    return entry + pips * pip


def _pos(
    *,
    symbol: str = "EUR_USD",
    direction: str = "BUY",
    entry: float = 1.10000,
    sl: float | None = None,
    tp: float | None = None,
    tp_pips: float | None = None,
    open_time: float | None = None,
) -> Position:
    if sl is None:
        sl = entry - 0.0023 if direction == "BUY" else entry + 0.0023
    if tp is None:
        if tp_pips is not None:
            tp = _px(entry, tp_pips, direction=direction, symbol=symbol)
        else:
            tp = entry + 0.0024 if direction == "BUY" else entry - 0.0024
    return Position(
        symbol=symbol,
        direction=direction,
        units=2.0,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        open_time=open_time if open_time is not None else time.time(),
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
    )


@pytest.fixture(autouse=True)
def _pp_defaults(monkeypatch):
    monkeypatch.setenv("PROFIT_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("PROFIT_PROTECTION_TRIGGER_PERCENT", "0.67")
    monkeypatch.setenv("PROFIT_GIVEBACK_ATR_MULTIPLIER", "0.5")
    monkeypatch.setenv("PROFIT_PROTECTION_ATR_PERIOD", "14")
    monkeypatch.setenv("PROFIT_GIVEBACK_PIPS", "4")
    monkeypatch.setenv("PROFIT_PROTECTION_CLOSE_RETRY_SEC", "30")
    monkeypatch.setenv("PROFIT_PROTECTION_LOG_RATCHET_PIPS", "1")


def test_pip_size_majors_and_jpy():
    assert pip_size("EUR_USD") == 0.0001
    assert pip_size("GBP_USD") == 0.0001
    assert pip_size("USD_JPY") == 0.01


def test_only_reaches_plus_10_no_protection():
    pos = _pos()
    d = apply_profit_protection(pos, _px(1.10000, 10))
    assert d.current_pips == pytest.approx(10.0)
    assert d.active is False
    assert d.should_close is False
    assert pos.max_profit_pips == pytest.approx(10.0)


def test_reaches_15_9_no_activation():
    pos = _pos()
    d = apply_profit_protection(pos, _px(1.10000, 15.9))
    assert d.current_pips == pytest.approx(15.9)
    assert d.active is False
    assert d.should_close is False


def test_24pip_tp_activates_around_16_1():
    pos = _pos(tp_pips=24)
    assert original_tp_distance_pips(pos) == pytest.approx(24.0)
    assert activation_trigger_pips(pos) == pytest.approx(16.08)
    d = apply_profit_protection(pos, _px(1.10000, 16.1))
    assert d.just_activated is True
    assert d.active is True
    assert d.exit_threshold_pips == pytest.approx(12.1)
    assert d.should_close is False


def test_reaches_16_activates_around_12_does_not_close():
    """Kept from the 16-pip suite: 24-pip TP, ~67% ≈ 16.1, giveback still 4."""
    pos = _pos()
    d = apply_profit_protection(pos, _px(1.10000, 16.1))
    assert d.just_activated is True
    assert d.active is True
    assert d.exit_threshold_pips == pytest.approx(12.1)
    assert d.should_close is False


def test_reaches_16_then_12_closes():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1))
    d = apply_profit_protection(pos, _px(1.10000, 12.1))
    assert pos.max_profit_pips == pytest.approx(16.1)
    assert d.should_close is True
    assert d.exit_threshold_pips == pytest.approx(12.1)


def test_reaches_16_then_20_ratchets_threshold_to_16():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1))
    d = apply_profit_protection(pos, _px(1.10000, 20))
    assert pos.max_profit_pips == pytest.approx(20.0)
    assert d.exit_threshold_pips == pytest.approx(16.0)
    assert d.should_close is False


def test_reaches_20_then_17_stays_open():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 20))
    d = apply_profit_protection(pos, _px(1.10000, 17))
    assert pos.max_profit_pips == pytest.approx(20.0)
    assert d.current_pips == pytest.approx(17.0)
    assert d.should_close is False


def test_reaches_20_then_16_closes():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 20))
    d = apply_profit_protection(pos, _px(1.10000, 16))
    assert pos.max_profit_pips == pytest.approx(20.0)
    assert d.exit_threshold_pips == pytest.approx(16.0)
    assert d.should_close is True


def test_normal_tp_price_does_not_protect_close_at_tp():
    """+24 pips is the example TP; protection must not close just for reaching TP."""
    pos = _pos()
    sl0, tp0 = pos.stop_loss, pos.take_profit
    tp_price = 1.10240
    d = apply_profit_protection(pos, tp_price)
    assert d.current_pips == pytest.approx(24.0)
    assert d.active is True
    assert d.exit_threshold_pips == pytest.approx(20.0)
    assert d.should_close is False
    assert tp_price >= pos.take_profit
    assert pos.stop_loss == sl0
    assert pos.take_profit == tp0


def test_sell_reaches_16_then_12_closes():
    pos = _pos(direction="SELL", entry=1.10000)
    d16 = apply_profit_protection(pos, _px(1.10000, 16.1, direction="SELL"))
    assert d16.current_pips == pytest.approx(16.1)
    assert d16.active is True
    assert d16.should_close is False
    d12 = apply_profit_protection(pos, _px(1.10000, 12.1, direction="SELL"))
    assert d12.current_pips == pytest.approx(12.1)
    assert pos.max_profit_pips == pytest.approx(16.1)
    assert d12.should_close is True


def test_sell_down_move_is_positive_mfe_and_progress():
    pos = _pos(direction="SELL", entry=1.2500, tp_pips=24)
    assert original_tp_distance_pips(pos) == pytest.approx(24.0)
    px = _px(1.2500, 16.1, direction="SELL")
    assert px < 1.2500
    d = apply_profit_protection(pos, px)
    assert d.current_pips == pytest.approx(16.1)
    assert d.current_pips > 0
    assert d.active is True


def test_multiple_positions_independent_mfe():
    a = _pos(symbol="EUR_USD")
    b = _pos(symbol="GBP_USD", entry=1.25000)
    apply_profit_protection(a, _px(1.10000, 16.1))
    apply_profit_protection(b, _px(1.25000, 10, symbol="GBP_USD"))
    assert a.max_profit_pips == pytest.approx(16.1)
    assert a.profit_protection_active is True
    assert b.max_profit_pips == pytest.approx(10.0)
    assert b.profit_protection_active is False


def test_simultaneous_positions_use_own_tp_distance():
    short_tp = _pos(symbol="EUR_USD", tp_pips=24)
    long_tp = _pos(symbol="GBP_USD", entry=1.25000, tp_pips=40)
    apply_profit_protection(short_tp, _px(1.10000, 16.1))
    apply_profit_protection(long_tp, _px(1.25000, 16.0, symbol="GBP_USD"))
    assert short_tp.profit_protection_active is True
    assert long_tp.profit_protection_active is False
    assert long_tp.max_profit_pips == pytest.approx(16.0)


def test_mfe_never_moves_backwards():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 20))
    apply_profit_protection(pos, 1.10050)
    apply_profit_protection(pos, 1.09900)
    assert pos.max_profit_pips == pytest.approx(20.0)


def test_restart_reconstructs_mfe_from_candle_highs():
    open_ts = datetime_utc_epoch("2026-09-15T12:00:00+00:00")
    pos = _pos(open_time=open_ts)
    pos.profit_protection_seeded = False
    ohlcv = pd.DataFrame(
        [
            {"time": "2026-09-15T11:55:00.000000000Z", "open": 1.1, "high": 1.1030, "low": 1.0990, "close": 1.1},
            {"time": "2026-09-15T12:00:00.000000000Z", "open": 1.1, "high": 1.10200, "low": 1.0998, "close": 1.1010},
            {"time": "2026-09-15T12:05:00.000000000Z", "open": 1.1010, "high": 1.10180, "low": 1.10150, "close": 1.10170},
        ]
    )
    source = seed_position_mfe(pos, 1.10170, ohlcv)
    assert source == "ohlcv"
    assert pos.max_profit_pips == pytest.approx(20.0)
    assert pos.profit_protection_active is True
    d = apply_profit_protection(pos, 1.10170)
    assert d.should_close is False
    d2 = apply_profit_protection(pos, 1.10160)
    assert d2.should_close is True


def test_restart_fallback_seeds_from_current_not_zero():
    pos = _pos()
    pos.profit_protection_seeded = False
    source = seed_position_mfe(pos, _px(1.10000, 13), ohlcv=None)
    assert source == "current"
    assert pos.max_profit_pips == pytest.approx(13.0)
    assert pos.max_profit_pips != 0.0
    assert pos.profit_protection_active is False


def test_failed_close_does_not_retry_immediately():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1))
    now = 1_000_000.0
    assert protection_close_allowed(pos, now) is True
    mark_protection_close_attempt(pos, now)
    assert protection_close_allowed(pos, now + 1.0) is False
    assert protection_close_allowed(pos, now + 30.0) is True


def test_jpy_sell_pips():
    assert unrealized_profit_pips("USD_JPY", "SELL", 150.00, 149.80) == pytest.approx(20.0)
    assert reconstruct_mfe_from_ohlcv(
        "USD_JPY",
        "BUY",
        150.00,
        0.0,
        pd.DataFrame([{"time": "2026-09-15T12:00:00Z", "high": 150.16, "low": 149.90}]),
    ) == pytest.approx(16.0)


def test_40pip_tp_does_not_activate_at_16():
    pos = _pos(tp_pips=40)
    sl0, tp0 = pos.stop_loss, pos.take_profit
    d = apply_profit_protection(pos, _px(1.10000, 16))
    assert original_tp_distance_pips(pos) == pytest.approx(40.0)
    assert d.active is False
    assert d.should_close is False
    assert pos.stop_loss == sl0
    assert pos.take_profit == tp0


def test_40pip_tp_activates_around_26_8():
    pos = _pos(tp_pips=40)
    assert activation_trigger_pips(pos) == pytest.approx(26.8)
    d = apply_profit_protection(pos, _px(1.10000, 26.8))
    assert d.active is True
    assert d.just_activated is True
    assert d.exit_threshold_pips == pytest.approx(22.8)
    assert d.should_close is False


def test_15pip_tp_activates_around_10_05():
    pos = _pos(tp_pips=15)
    assert activation_trigger_pips(pos) == pytest.approx(10.05)
    d = apply_profit_protection(pos, _px(1.10000, 10.05))
    assert d.active is True
    assert d.exit_threshold_pips == pytest.approx(6.05)
    assert d.should_close is False


def test_invalid_tp_does_not_activate_or_divide():
    pos = _pos(tp=1.10000)
    assert original_tp_distance_pips(pos) is None
    d = apply_profit_protection(pos, _px(1.10000, 20))
    assert d.active is False
    assert d.should_close is False
    assert pos.max_profit_pips == pytest.approx(20.0)

    wrong_side = _pos(direction="BUY", tp=1.09800)
    assert original_tp_distance_pips(wrong_side) is None
    d2 = apply_profit_protection(wrong_side, 1.10200)
    assert d2.active is False


def _atr_px(atr_pips: float, symbol: str = "EUR_USD") -> float:
    return atr_pips * pip_size(symbol)


def test_atr_8_pips_half_mult_is_4_pip_giveback():
    pos = _pos()
    gb, src = resolve_giveback_pips(pos, atr_price=_atr_px(8))
    assert src == "atr"
    assert gb == pytest.approx(4.0)
    d = apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(8))
    assert d.exit_threshold_pips == pytest.approx(12.1)


def test_atr_16_pips_half_mult_is_8_pip_giveback():
    pos = _pos()
    gb, _ = resolve_giveback_pips(pos, atr_price=_atr_px(16))
    assert gb == pytest.approx(8.0)
    d = apply_profit_protection(pos, _px(1.10000, 20), atr_price=_atr_px(16))
    assert d.active is True
    assert d.exit_threshold_pips == pytest.approx(12.0)


def test_atr_4_pips_half_mult_is_2_pip_giveback():
    pos = _pos()
    gb, _ = resolve_giveback_pips(pos, atr_price=_atr_px(4))
    assert gb == pytest.approx(2.0)
    d = apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(4))
    assert d.exit_threshold_pips == pytest.approx(14.1)


def test_atr_giveback_buy_and_sell_same_pips():
    buy = _pos(direction="BUY")
    sell = _pos(direction="SELL")
    b = apply_profit_protection(buy, _px(1.10000, 16.1), atr_price=_atr_px(8))
    s = apply_profit_protection(
        sell, _px(1.10000, 16.1, direction="SELL"), atr_price=_atr_px(8)
    )
    assert b.exit_threshold_pips == pytest.approx(12.1)
    assert s.exit_threshold_pips == pytest.approx(12.1)
    assert s.current_pips == pytest.approx(16.1)


def test_increasing_mfe_ratchets_atr_protection_up():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(8))
    d = apply_profit_protection(pos, _px(1.10000, 20), atr_price=_atr_px(8))
    assert pos.max_profit_pips == pytest.approx(20.0)
    assert d.exit_threshold_pips == pytest.approx(16.0)


def test_increasing_atr_does_not_loosen_protection():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(8))
    assert pos.profit_protection_exit_pips == pytest.approx(12.1)
    d = apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(16))
    assert d.exit_threshold_pips == pytest.approx(12.1)
    assert pos.profit_protection_exit_pips == pytest.approx(12.1)
    assert d.should_close is False


def test_falling_atr_may_tighten_protection():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(8))
    assert pos.profit_protection_exit_pips == pytest.approx(12.1)
    d = apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=_atr_px(4))
    assert d.exit_threshold_pips == pytest.approx(14.1)
    assert d.should_close is False


def test_invalid_atr_falls_back_safely_no_force_close():
    pos = _pos()
    sl0, tp0 = pos.stop_loss, pos.take_profit
    d = apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=float("nan"))
    assert d.active is True
    assert d.should_close is False
    assert d.exit_threshold_pips == pytest.approx(12.1)
    assert pos.stop_loss == sl0
    assert pos.take_profit == tp0
    d0 = apply_profit_protection(_pos(), _px(1.10000, 16.1), atr_price=0.0)
    assert d0.active is True
    assert d0.should_close is False


def test_multiple_positions_independent_atr_giveback():
    a = _pos(symbol="EUR_USD", tp_pips=24)
    b = _pos(symbol="GBP_USD", entry=1.25000, tp_pips=40)
    da = apply_profit_protection(a, _px(1.10000, 16.1), atr_price=_atr_px(8))
    db = apply_profit_protection(
        b, _px(1.25000, 27.0, symbol="GBP_USD"), atr_price=_atr_px(16, "GBP_USD")
    )
    assert da.active is True
    assert da.exit_threshold_pips == pytest.approx(12.1)
    assert db.active is True
    assert db.exit_threshold_pips == pytest.approx(19.0)
    assert a.profit_protection_exit_pips != b.profit_protection_exit_pips


def test_atr_to_pips_jpy():
    assert atr_to_pips("USD_JPY", 0.08) == pytest.approx(8.0)


def datetime_utc_epoch(iso: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(iso).timestamp()
