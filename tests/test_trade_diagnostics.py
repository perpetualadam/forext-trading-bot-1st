"""Measurement-only profit-protection trade diagnostics."""

from __future__ import annotations

import time

import pytest

from forex_bot.positions import Position
from forex_bot.profit_protection import apply_profit_protection, pip_size
from forex_bot.trade_diagnostics import (
    finalize_diagnostics,
    format_trade_result_line,
    snapshot_from_position,
)


def _px(entry: float, pips: float, *, direction: str = "BUY") -> float:
    pip = pip_size("EUR_USD")
    return entry - pips * pip if direction == "SELL" else entry + pips * pip


def _pos(*, direction: str = "BUY", entry: float = 1.10000) -> Position:
    sl = entry - 0.0023 if direction == "BUY" else entry + 0.0023
    tp = entry + 0.0024 if direction == "BUY" else entry - 0.0024
    return Position(
        symbol="EUR_USD",
        direction=direction,
        units=2.0,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        open_time=time.time(),
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
        atr_at_entry_pips=8.0,
    )


def test_mae_tracks_adverse_without_changing_mfe():
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, -5), atr_price=0.0008)
    apply_profit_protection(pos, _px(1.10000, 10), atr_price=0.0008)
    assert pos.max_adverse_pips == 5.0
    assert pos.max_profit_pips == 10.0
    assert pos.profit_protection_active is False


def test_snapshot_protection_exit_fields(monkeypatch):
    monkeypatch.setenv("PROFIT_PROTECTION_TRIGGER_PERCENT", "0.67")
    monkeypatch.setenv("PROFIT_GIVEBACK_ATR_MULTIPLIER", "0.5")
    pos = _pos()
    apply_profit_protection(pos, _px(1.10000, 16.1), atr_price=0.0008)
    apply_profit_protection(pos, _px(1.10000, 12.1), atr_price=0.0008)
    snap = snapshot_from_position(pos, exit_reason="profit_protection", exit_price=_px(1.10000, 12.1))
    assert snap["symbol"] == "EUR_USD"
    assert snap["direction"] == "BUY"
    assert snap["original_tp_pips"] == 24.0
    assert snap["original_sl_pips"] == 23.0
    assert snap["profit_protection_activated"] is True
    assert snap["exited_on_profit_protection"] is True
    assert snap["mfe_pips"] == 16.1
    assert snap["mfe_at_activation_pips"] == 16.1
    assert snap["atr_at_activation_pips"] == 8.0
    assert snap["atr_giveback_at_activation_pips"] == 4.0
    assert snap["atr_fallback_used"] is False
    assert snap["mfe_r"] == pytest.approx(16.1 / 23.0)
    assert snap["settings"]["trigger_percent"] == 0.67
    assert snap["settings"]["atr_multiplier"] == 0.5


def test_sell_mae_and_result_line():
    pos = _pos(direction="SELL")
    apply_profit_protection(pos, _px(1.10000, -6, direction="SELL"), atr_price=0.0008)
    apply_profit_protection(pos, _px(1.10000, 16.1, direction="SELL"), atr_price=0.0008)
    assert pos.max_adverse_pips == 6.0
    snap = snapshot_from_position(
        pos, exit_reason="profit_protection", exit_price=_px(1.10000, 12.1, direction="SELL")
    )
    snap = finalize_diagnostics(
        snap,
        symbol="EUR_USD",
        direction="SELL",
        entry_price=1.10000,
        exit_price=_px(1.10000, 12.1, direction="SELL"),
    )
    assert snap["realised_pips"] == 12.1
    assert snap["mfe_giveback_pips"] == 4.0
    line = format_trade_result_line(snap)
    assert line is not None
    assert line.startswith("[TRADE RESULT] EUR_USD SELL")
    assert "Exit=PROFIT_PROTECTION" in line
    assert "Protected=True" in line


def test_missing_diagnostics_does_not_break():
    assert format_trade_result_line(None) is None
    assert snapshot_from_position(
        _pos(), exit_reason="sl_tp", exit_price=1.0977
    )["exited_on_profit_protection"] is False


def test_clamps_are_env_not_hardcoded(monkeypatch):
    monkeypatch.setenv("PROFIT_GIVEBACK_MIN_PIPS", "1.5")
    monkeypatch.setenv("PROFIT_GIVEBACK_MAX_PIPS", "9")
    from forex_bot.profit_protection import profit_giveback_max_pips, profit_giveback_min_pips

    assert profit_giveback_min_pips() == 1.5
    assert profit_giveback_max_pips() == 9.0
