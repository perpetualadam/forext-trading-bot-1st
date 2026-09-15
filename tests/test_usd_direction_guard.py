"""Same-USD-direction entry guard (new entries only; paper excluded from live counts)."""

from __future__ import annotations

import pytest

from forex_bot.portfolio_exposure import (
    format_usd_direction_skip,
    max_same_usd_direction_positions,
    notional_cap_decision,
    usd_direction,
    usd_direction_guard_decision,
)
from forex_bot.positions import Position, close_position, positions
from forex_bot.state import set_broker_account
from forex_bot.trading import portfolio_risk_cap_exceeded


def _live(symbol: str, direction: str, entry: float = 1.10) -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=1.0,
        entry_price=entry,
        stop_loss=entry * 0.99 if direction == "BUY" else entry * 1.01,
        take_profit=entry * 1.01 if direction == "BUY" else entry * 0.99,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
        broker_order=True,
    )


def _paper(symbol: str, direction: str) -> Position:
    p = _live(symbol, direction)
    p.execution_kind = "window_paper"
    p.broker_order = False
    return p


@pytest.mark.parametrize(
    "symbol,side,expect",
    [
        ("EUR_USD", "BUY", "SHORT"),
        ("EUR_USD", "SELL", "LONG"),
        ("GBP_USD", "BUY", "SHORT"),
        ("GBP_USD", "SELL", "LONG"),
        ("AUD_USD", "BUY", "SHORT"),
        ("AUD_USD", "SELL", "LONG"),
        ("USD_JPY", "BUY", "LONG"),
        ("USD_JPY", "SELL", "SHORT"),
        ("USD_CAD", "BUY", "LONG"),
        ("USD_CAD", "SELL", "SHORT"),
        ("USD_CHF", "BUY", "LONG"),
        ("USD_CHF", "SELL", "SHORT"),
        ("EUR_GBP", "BUY", None),
        ("EUR_GBP", "SELL", None),
    ],
)
def test_usd_direction_from_base_quote(symbol, side, expect):
    assert usd_direction(symbol, side) == expect


def test_default_max_same_usd_direction_is_two(monkeypatch):
    monkeypatch.delenv("MAX_SAME_USD_DIRECTION_POSITIONS", raising=False)
    assert max_same_usd_direction_positions() == 2


def test_first_and_second_same_direction_allowed_third_rejected(monkeypatch):
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    positions.clear()
    d0 = usd_direction_guard_decision("EUR_USD", "SELL")
    assert d0["exceeds"] is False
    positions["EUR_USD"] = _live("EUR_USD", "SELL")
    d1 = usd_direction_guard_decision("GBP_USD", "SELL")
    assert d1["exceeds"] is False
    assert d1["same_direction_count"] == 1
    positions["GBP_USD"] = _live("GBP_USD", "SELL")
    d2 = usd_direction_guard_decision("AUD_USD", "SELL")
    assert d2["exceeds"] is True
    assert d2["same_direction_count"] == 2
    skip = format_usd_direction_skip(d2)
    assert "AUD_USD SELL" in skip
    assert "USD_DIRECTION=LONG" in skip
    assert "same_direction=2/2" in skip
    assert "EUR_USD:SELL" in skip
    assert "GBP_USD:SELL" in skip
    assert positions["EUR_USD"].direction == "SELL"
    assert positions["GBP_USD"].direction == "SELL"
    positions.clear()


def test_opposite_usd_direction_still_eligible(monkeypatch):
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    positions.clear()
    positions["EUR_USD"] = _live("EUR_USD", "SELL")
    positions["GBP_USD"] = _live("GBP_USD", "SELL")
    d = usd_direction_guard_decision("USD_JPY", "SELL")
    assert usd_direction("USD_JPY", "SELL") == "SHORT"
    assert d["exceeds"] is False
    positions.clear()


def test_paper_positions_do_not_count_toward_live_usd_guard(monkeypatch):
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    positions.clear()
    positions["EUR_USD"] = _paper("EUR_USD", "SELL")
    positions["GBP_USD"] = _paper("GBP_USD", "SELL")
    d = usd_direction_guard_decision("AUD_USD", "SELL")
    assert d["same_direction_count"] == 0
    assert d["exceeds"] is False
    positions.clear()


def test_guard_never_closes_existing(monkeypatch):
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    positions.clear()
    positions["EUR_USD"] = _live("EUR_USD", "SELL")
    positions["GBP_USD"] = _live("GBP_USD", "SELL")
    before = set(positions)
    usd_direction_guard_decision("AUD_USD", "SELL")
    assert set(positions) == before
    close_position("AUD_USD")
    assert "EUR_USD" in positions and "GBP_USD" in positions
    positions.clear()


def test_gross_cap_still_independent(monkeypatch):
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", "0.02")
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.06")
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    set_broker_account(100.0, "USD")
    positions.clear()
    positions["EUR_USD"] = _live("EUR_USD", "SELL", entry=1.0)
    positions["EUR_USD"].units = 2.0
    positions["GBP_USD"] = _live("GBP_USD", "SELL", entry=1.0)
    positions["GBP_USD"].units = 2.0
    positions["USD_JPY"] = _live("USD_JPY", "BUY", entry=150.0)
    positions["USD_JPY"].units = 2.0
    d = notional_cap_decision(1.3)
    assert d["exceeds"] is True
    assert usd_direction_guard_decision("USD_CAD", "SELL")["exceeds"] is False
    positions.clear()


def test_stop_risk_cap_still_independent(monkeypatch):
    monkeypatch.setenv("MAX_PORTFOLIO_RISK_PCT", "0.02")
    assert portfolio_risk_cap_exceeded(100.0, 3.0) is True
    assert portfolio_risk_cap_exceeded(100.0, 0.5) is False
