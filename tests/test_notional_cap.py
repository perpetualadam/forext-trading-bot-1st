"""Per-trade notional sizing vs portfolio gross notional cap (separate env vars)."""

from __future__ import annotations

import pytest

from forex_bot.orders import LocalOrder, OrderStatus, orders_by_client_id
from forex_bot.portfolio_exposure import (
    account_ccy_to_usd,
    approx_gross_usd_notional_for,
    configured_max_gross_usd,
    format_notional_cap_report,
    format_notional_cap_skip_alert,
    notional_cap_decision,
    notional_pct_of_nav,
    portfolio_gross_notional_pct_of_nav,
    would_exceed_cap_if_opening,
)
from forex_bot.positions import Position, positions
from forex_bot.state import record_mid, set_broker_account, state
from forex_bot.trading import position_sizing


@pytest.fixture(autouse=True)
def _reset_exposure_state():
    positions.clear()
    orders_by_client_id.clear()
    state["broker_nav"] = None
    state["broker_currency"] = ""
    state["last_mids"] = {}
    state["equity_curve"] = []
    yield
    positions.clear()
    orders_by_client_id.clear()
    state["broker_nav"] = None
    state["broker_currency"] = ""
    state["last_mids"] = {}
    state["equity_curve"] = []


def _gbp_book(monkeypatch, *, position_pct="0.02", portfolio_pct=None) -> float:
    """97.37 GBP NAV, GBP_USD=1.35. Unset portfolio pct inherits position pct."""
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", position_pct)
    if portfolio_pct is None:
        monkeypatch.delenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", raising=False)
    else:
        monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", portfolio_pct)
    set_broker_account(97.37, "GBP")
    record_mid("GBP_USD", 1.35)
    return configured_max_gross_usd()


def _pos(symbol: str, units: float, entry_price: float, direction: str = "BUY") -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=units,
        entry_price=entry_price,
        stop_loss=entry_price * 0.99,
        take_profit=entry_price * 1.01,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
    )


def test_gbp_nav_converts_to_usd(monkeypatch):
    cap = _gbp_book(monkeypatch)
    assert account_ccy_to_usd(97.37) == pytest.approx(97.37 * 1.35)
    assert cap == pytest.approx(97.37 * 0.02 * 1.35, abs=1e-4)


def test_gbp_usd_notional_is_units_times_quote():
    assert approx_gross_usd_notional_for("GBP_USD", 1.0, 1.35) == pytest.approx(1.35)


def test_eur_usd_notional_is_units_times_quote():
    assert approx_gross_usd_notional_for("EUR_USD", 1.0, 1.17) == pytest.approx(1.17)


def test_usd_jpy_notional_is_units_as_usd_face():
    assert approx_gross_usd_notional_for("USD_JPY", 1.0, 150.0) == pytest.approx(1.0)
    assert approx_gross_usd_notional_for("USD_JPY", 1000.0, 150.0) == pytest.approx(1000.0)


def test_1_empty_below_cap_allows(monkeypatch):
    cap = _gbp_book(monkeypatch)
    d = notional_cap_decision(1.35)
    assert d["existing_gross_usd"] == 0.0
    assert d["resulting_gross_usd"] < cap
    assert d["exceeds"] is False


def test_2_empty_exactly_at_cap_allows(monkeypatch):
    cap = _gbp_book(monkeypatch)
    d = notional_cap_decision(cap)
    assert d["exceeds"] is False


def test_3_empty_above_cap_rejects(monkeypatch):
    cap = _gbp_book(monkeypatch)
    d = notional_cap_decision(cap + 0.01)
    assert d["exceeds"] is True


def test_4_existing_plus_new_below_cap_allows(monkeypatch):
    _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    d = notional_cap_decision(1.35)
    assert d["existing_gross_usd"] == pytest.approx(1.17)
    assert d["resulting_gross_usd"] == pytest.approx(2.52)
    assert d["resulting_gross_usd"] < d["cap_usd"]
    assert d["exceeds"] is False


def test_5_existing_plus_new_exactly_at_cap_allows(monkeypatch):
    _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    room = configured_max_gross_usd() - 1.17
    d = notional_cap_decision(room)
    assert d["resulting_gross_usd"] == pytest.approx(d["cap_usd"])
    assert d["exceeds"] is False


def test_6_existing_plus_new_above_cap_rejects(monkeypatch):
    cap = _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    positions["USD_JPY"] = _pos("USD_JPY", 1.0, 150.0)
    d = notional_cap_decision(1.35)
    assert d["existing_gross_usd"] == pytest.approx(2.17)
    assert d["resulting_gross_usd"] == pytest.approx(3.52)
    assert d["resulting_gross_usd"] > cap
    assert d["exceeds"] is True


def test_7_multiple_symbols_sum_gross(monkeypatch):
    _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    positions["USD_JPY"] = _pos("USD_JPY", 1.0, 150.0)
    positions["GBP_USD"] = _pos("GBP_USD", 1.0, 1.35)
    d = notional_cap_decision(0.0)
    assert d["existing_by_symbol"]["EUR_USD"] == pytest.approx(1.17)
    assert d["existing_by_symbol"]["USD_JPY"] == pytest.approx(1.0)
    assert d["existing_by_symbol"]["GBP_USD"] == pytest.approx(1.35)
    assert d["existing_gross_usd"] == pytest.approx(3.52)


def test_8_short_and_long_both_count_gross(monkeypatch):
    _gbp_book(monkeypatch)
    positions["GBP_USD"] = _pos("GBP_USD", 1.0, 1.35, direction="SELL")
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17, direction="BUY")
    d = notional_cap_decision(0.0)
    assert d["existing_by_symbol"]["GBP_USD"] == pytest.approx(1.35)
    assert d["existing_gross_usd"] == pytest.approx(2.52)


def test_13_pending_orders_excluded(monkeypatch):
    _gbp_book(monkeypatch)
    orders_by_client_id["cid-1"] = LocalOrder(
        client_order_id="cid-1",
        symbol="EUR_USD",
        direction="BUY",
        units_requested=100.0,
        units_filled=0.0,
        status=OrderStatus.PENDING,
        avg_fill_price=None,
        created_ts=0.0,
    )
    d = notional_cap_decision(1.35)
    assert d["existing_gross_usd"] == 0.0
    assert d["exceeds"] is False


def test_14_one_unit_cannot_bypass_cap(monkeypatch):
    _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    positions["USD_JPY"] = _pos("USD_JPY", 1.0, 150.0)
    one_unit = approx_gross_usd_notional_for("GBP_USD", 1.0, 1.35)
    assert one_unit == pytest.approx(1.35)
    assert would_exceed_cap_if_opening(one_unit) is True


def test_15_per_trade_pct_does_not_change_explicit_portfolio_cap(monkeypatch):
    _gbp_book(monkeypatch, position_pct="0.02", portfolio_pct="0.02")
    cap_before = configured_max_gross_usd()
    units_before = position_sizing("GBP_USD", 1.35, 1.34, 97.37)
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", "0.01")
    assert notional_pct_of_nav() == pytest.approx(0.01)
    assert portfolio_gross_notional_pct_of_nav() == pytest.approx(0.02)
    assert configured_max_gross_usd() == pytest.approx(cap_before)
    units_after = position_sizing("GBP_USD", 1.35, 1.34, 97.37)
    assert units_after < units_before


def test_16_portfolio_pct_does_not_change_per_trade_sizing(monkeypatch):
    _gbp_book(monkeypatch, position_pct="0.02", portfolio_pct="0.02")
    units_before = position_sizing("GBP_USD", 1.35, 1.34, 97.37)
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.10")
    assert notional_pct_of_nav() == pytest.approx(0.02)
    assert portfolio_gross_notional_pct_of_nav() == pytest.approx(0.10)
    assert configured_max_gross_usd() == pytest.approx(97.37 * 0.10 * 1.35, abs=1e-4)
    units_after = position_sizing("GBP_USD", 1.35, 1.34, 97.37)
    assert units_after == pytest.approx(units_before)


def test_unset_portfolio_pct_inherits_position_pct(monkeypatch):
    _gbp_book(monkeypatch, position_pct="0.02", portfolio_pct=None)
    assert portfolio_gross_notional_pct_of_nav() == pytest.approx(0.02)
    assert configured_max_gross_usd() == pytest.approx(97.37 * 0.02 * 1.35, abs=1e-4)


def test_explicit_zero_portfolio_pct_disables_percent_cap(monkeypatch):
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", "0.02")
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0")
    monkeypatch.delenv("MAX_GROSS_USD_NOTIONAL", raising=False)
    set_broker_account(97.37, "GBP")
    record_mid("GBP_USD", 1.35)
    assert portfolio_gross_notional_pct_of_nav() == 0.0
    assert configured_max_gross_usd() == 0.0
    assert would_exceed_cap_if_opening(1_000_000.0) is False
    assert position_sizing("GBP_USD", 1.35, 1.34, 97.37) > 0


def test_skip_and_pass_reports(monkeypatch):
    _gbp_book(monkeypatch)
    positions["EUR_USD"] = _pos("EUR_USD", 1.0, 1.17)
    positions["USD_JPY"] = _pos("USD_JPY", 1.0, 150.0)
    skip_d = notional_cap_decision(1.35)
    skip = format_notional_cap_skip_alert(
        "GBP_USD", skip_d, nav=97.37, currency="GBP", direction="BUY"
    )
    assert "Candidate symbol: GBP_USD" in skip
    assert "Candidate side: BUY" in skip
    assert "Existing counted gross exposure: 2.17 USD" in skip
    assert "Per-symbol existing exposure: [EUR_USD 1.17, USD_JPY 1.00]" in skip
    assert "Proposed additional exposure: 1.35 USD" in skip
    assert "Resulting gross exposure: 3.52 USD" in skip
    assert "Maximum portfolio gross exposure: 2.63 USD" in skip
    assert "Portfolio limit: 2.00% of NAV (inherited from POSITION_NOTIONAL_PCT_OF_NAV)" in skip
    assert "Account NAV: 97.37 GBP" in skip
    assert "Decision: SKIP because 3.52 > 2.63" in skip

    positions.clear()
    pass_d = notional_cap_decision(1.35)
    allow = format_notional_cap_report(
        "GBP_USD", pass_d, nav=97.37, currency="GBP", allowed=True
    )
    assert "notional cap check passed" in allow
    assert "Decision: ALLOW because 1.35 <= 2.63" in allow
