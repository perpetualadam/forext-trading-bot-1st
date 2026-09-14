"""2% of NAV notional sizing (account currency → units)."""

from __future__ import annotations

from forex_bot.portfolio_exposure import account_ccy_to_usd, units_for_account_notional
from forex_bot.state import record_mid, set_broker_account
from forex_bot.trading import position_sizing


def test_gbp_nav_two_percent_gbpusd(monkeypatch):
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", "0.02")
    set_broker_account(97.37, "GBP")
    record_mid("GBP_USD", 1.35)
    # 2% of 97.37 GBP = 1.9474 GBP ≈ 1.9474 units on GBP_USD
    u = position_sizing("GBP_USD", 1.35, 1.34, 97.37)
    assert 1.4 < u < 2.1
    assert abs(account_ccy_to_usd(97.37 * 0.02) - 97.37 * 0.02 * 1.35) < 0.01


def test_units_usd_jpy_are_usd_face():
    set_broker_account(100.0, "USD")
    u = units_for_account_notional("USD_JPY", 150.0, 2.0)
    assert abs(u - 2.0) < 1e-9
