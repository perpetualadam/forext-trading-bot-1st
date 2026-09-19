"""BUY/SELL invariants and the two reported live fills."""

from __future__ import annotations

import pytest

from forex_bot.decision_quality.invariants import (
    assert_side_invariants,
    example_live_trades,
    expected_order_units_sign,
    pip_distance,
    side_invariants_ok,
    signed_pips,
    sl_tp_from_production_distances,
)
from forex_bot.oanda_exec import _order_units_for_open
from forex_bot.trading import sl_tp_distance_for_entry


def test_buy_sell_price_invariants():
    assert side_invariants_ok("BUY", 1.10, 1.09, 1.12)
    assert side_invariants_ok("SELL", 1.10, 1.11, 1.08)
    assert not side_invariants_ok("BUY", 1.10, 1.11, 1.12)
    assert not side_invariants_ok("SELL", 1.10, 1.09, 1.08)
    assert_side_invariants("BUY", 100.0, 99.0, 102.0)
    with pytest.raises(AssertionError):
        assert_side_invariants("BUY", 100.0, 101.0, 102.0)


def test_reported_live_fills_are_internally_consistent():
    rows = example_live_trades()
    gbp = rows[0]
    assert gbp["side"] == "SELL"
    assert_side_invariants(gbp["side"], gbp["entry"], gbp["stop_loss"], gbp["take_profit"])
    assert pip_distance("GBP_USD", gbp["entry"], gbp["stop_loss"]) == pytest.approx(4.1, abs=0.05)
    jpy = rows[1]
    assert jpy["side"] == "BUY"
    assert_side_invariants(jpy["side"], jpy["entry"], jpy["stop_loss"], jpy["take_profit"])
    assert pip_distance("USD_JPY", jpy["entry"], jpy["stop_loss"]) == pytest.approx(4.6, abs=0.05)


def test_production_sl_tp_respects_side(monkeypatch):
    monkeypatch.setenv("USE_ATR_STOPS", "false")
    monkeypatch.setenv("SL_FALLBACK_PIPS", "20")
    sl, tp = sl_tp_from_production_distances("EUR_USD", "BUY", 1.10000, None)
    assert_side_invariants("BUY", 1.10000, sl, tp)
    sl, tp = sl_tp_from_production_distances("EUR_USD", "SELL", 1.10000, None)
    assert_side_invariants("SELL", 1.10000, sl, tp)
    sl_d, tp_d = sl_tp_distance_for_entry("EUR_USD", None)
    assert tp_d == pytest.approx(sl_d * 2.0)


def test_signed_pips_buy_up_sell_down():
    assert signed_pips("EUR_USD", "BUY", 1.10000, 1.10010) == pytest.approx(1.0)
    assert signed_pips("EUR_USD", "SELL", 1.10000, 1.09990) == pytest.approx(1.0)
    assert signed_pips("EUR_USD", "BUY", 1.10000, 1.09990) == pytest.approx(-1.0)
    assert signed_pips("USD_JPY", "SELL", 150.00, 149.80) == pytest.approx(20.0)


def test_oanda_units_sign_matches_production():
    assert expected_order_units_sign("BUY") == 1
    assert expected_order_units_sign("SELL") == -1
    assert _order_units_for_open(3, "BUY") > 0
    assert _order_units_for_open(3, "SELL") < 0
    assert expected_order_units_sign("BUY") == (1 if _order_units_for_open(1, "BUY") > 0 else -1)
    assert expected_order_units_sign("SELL") == (1 if _order_units_for_open(1, "SELL") > 0 else -1)
