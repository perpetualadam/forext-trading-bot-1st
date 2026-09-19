"""SL/TP path, MFE/MAE, R, ambiguity, spread, sessions, regime."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from forex_bot.decision_quality.execution_sim import (
    AMBIGUITY_POLICY,
    apply_entry_spread,
    bar_touches,
    excursion_pips,
    r_multiple,
    signed_pips,
)
from forex_bot.decision_quality.research_features import classify_regime, wilder_adx
from forex_bot.decision_quality.sessions import classify_session, hour_london


def test_buy_and_sell_bar_exits():
    buy_sl = bar_touches("BUY", 1.0990, 1.1020, high=1.1005, low=1.0985)
    assert buy_sl.exit_reason == "sl"
    assert buy_sl.exit_price == 1.0990
    buy_tp = bar_touches("BUY", 1.0990, 1.1020, high=1.1025, low=1.1000)
    assert buy_tp.exit_reason == "tp"
    sell_sl = bar_touches("SELL", 1.1010, 1.0980, high=1.1015, low=1.0995)
    assert sell_sl.exit_reason == "sl"
    sell_tp = bar_touches("SELL", 1.1010, 1.0980, high=1.1005, low=1.0975)
    assert sell_tp.exit_reason == "tp"


def test_same_candle_sl_tp_is_ambiguous_and_not_tp():
    assert AMBIGUITY_POLICY == "count_ambiguous_and_assume_stop"
    both = bar_touches("BUY", 1.0990, 1.1020, high=1.1030, low=1.0980)
    assert both.ambiguous is True
    assert both.hit_sl and both.hit_tp
    assert both.exit_reason == "ambiguous_sl_tp"
    assert both.exit_price == 1.0990


def test_mfe_mae_and_r():
    fav, adv = excursion_pips("EUR_USD", "BUY", 1.10000, 1.10020, 1.09970)
    assert fav == pytest.approx(2.0)
    assert adv == pytest.approx(3.0)
    fav_s, adv_s = excursion_pips("EUR_USD", "SELL", 1.10000, 1.10020, 1.09970)
    assert fav_s == pytest.approx(3.0)
    assert adv_s == pytest.approx(2.0)
    assert r_multiple(10.0, 5.0) == pytest.approx(2.0)
    assert signed_pips("EUR_USD", "BUY", 1.1, 1.1) == 0.0


def test_spread_buy_pays_offer_sell_hits_bid():
    buy, half = apply_entry_spread("EUR_USD", "BUY", 1.10000)
    sell, _ = apply_entry_spread("EUR_USD", "SELL", 1.10000)
    assert buy > 1.10000
    assert sell < 1.10000
    assert buy - 1.10000 == pytest.approx(half)
    assert 1.10000 - sell == pytest.approx(half)


def test_session_buckets_london_clock():
    # 07:00 UTC in January is 07:00 GMT = London.
    asia = datetime(2024, 1, 3, 3, 0, tzinfo=timezone.utc)
    london = datetime(2024, 1, 3, 8, 0, tzinfo=timezone.utc)
    overlap = datetime(2024, 1, 3, 13, 0, tzinfo=timezone.utc)
    late = datetime(2024, 1, 3, 18, 0, tzinfo=timezone.utc)
    roll = datetime(2024, 1, 3, 22, 0, tzinfo=timezone.utc)
    assert classify_session(asia) == "asia"
    assert classify_session(london) == "london"
    assert classify_session(overlap) == "london_ny_overlap"
    assert classify_session(late) == "late_new_york"
    assert classify_session(roll) == "rollover_low_liquidity"
    assert hour_london(london) == 8


def test_regime_classifier_is_explainable():
    assert classify_regime(adx=30, ema_slope=0.01, ema_sep_atr=0.4, atr_pct=50) == "TRENDING_UP"
    assert classify_regime(adx=30, ema_slope=-0.01, ema_sep_atr=-0.4, atr_pct=50) == "TRENDING_DOWN"
    assert classify_regime(adx=15, ema_slope=0.0, ema_sep_atr=0.0, atr_pct=50) == "RANGING"
    assert classify_regime(adx=22, ema_slope=0.0, ema_sep_atr=0.0, atr_pct=95) == "HIGH_VOLATILITY"
    assert classify_regime(adx=22, ema_slope=0.0, ema_sep_atr=0.0, atr_pct=5) == "LOW_VOLATILITY"
    assert classify_regime(adx=None, ema_slope=None, ema_sep_atr=None, atr_pct=50) == "UNCERTAIN"
    assert wilder_adx(None) is None
