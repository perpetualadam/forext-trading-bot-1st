"""Focused mapping tests for production _quant_stub_vote (read-only behaviour check)."""

from __future__ import annotations

import math

from forex_bot.ai_ensemble import _quant_stub_vote


def _payload(**overrides):
    base = {
        "price": 1.1000,
        "ma_fast": 1.1010,
        "ma_slow": 1.0990,
        "returns": 0.0005,
        "atr": 0.0008,
        "strategy": "trend",
    }
    base.update(overrides)
    return base


def test_quant_buy_when_fast_above_slow_and_momentum():
    v = _quant_stub_vote(_payload(ma_fast=1.1010, ma_slow=1.0990, returns=0.0005, atr=0.0008))
    assert v["direction"] == "BUY"
    assert v["allow"] is True
    assert 0.0 < v["confidence"] <= 1.0


def test_quant_sell_when_fast_below_slow_and_momentum():
    v = _quant_stub_vote(_payload(ma_fast=1.0990, ma_slow=1.1010, returns=-0.0005, atr=0.0008))
    assert v["direction"] == "SELL"
    assert v["allow"] is True


def test_quant_no_signal_when_mas_within_epsilon():
    v = _quant_stub_vote(_payload(ma_fast=1.1000, ma_slow=1.1000, returns=0.001, atr=0.001))
    assert v["allow"] is False
    assert v["confidence"] == 0.0
    assert v["direction"] is None


def test_quant_direction_set_but_disallowed_when_momentum_weak():
    v = _quant_stub_vote(_payload(ma_fast=1.1010, ma_slow=1.0990, returns=0.00005, atr=0.001))
    assert v["direction"] == "BUY"
    assert v["allow"] is False


def test_quant_direction_set_but_disallowed_when_atr_zero():
    v = _quant_stub_vote(_payload(ma_fast=1.1010, ma_slow=1.0990, returns=0.001, atr=0.0))
    assert v["direction"] == "BUY"
    assert v["allow"] is False


def test_quant_nan_mas_are_no_signal():
    v = _quant_stub_vote(_payload(ma_fast=float("nan"), ma_slow=1.1, returns=0.001, atr=0.001))
    assert v["allow"] is False
    assert v["direction"] is None
    assert v["confidence"] == 0.0


def test_quant_strategy_label_does_not_change_formula():
    buy_base = dict(ma_fast=1.102, ma_slow=1.100, returns=0.0004, atr=0.0007)
    seen = [
        _quant_stub_vote(_payload(strategy=name, **buy_base))
        for name in (
            "trend",
            "scalp",
            "mean_reversion",
            "swing_mean_reversion",
            "swing_breakout",
            "swing_trend",
            "unused_label",
        )
    ]
    assert all(v["direction"] == "BUY" and v["allow"] is True for v in seen)
    assert len({round(v["confidence"], 12) for v in seen}) == 1


def test_quant_uses_sma_aliases_before_ma_when_present():
    v = _quant_stub_vote(
        _payload(
            sma_fast=1.090,
            sma_slow=1.100,
            ma_fast=1.200,
            ma_slow=1.000,
            returns=-0.0004,
            atr=0.001,
        )
    )
    assert v["direction"] == "SELL"
    assert v["allow"] is True


def test_quant_confidence_is_abs_return_times_scale_capped():
    v = _quant_stub_vote(_payload(returns=0.0004, atr=0.001))
    assert math.isclose(v["confidence"], 0.4, rel_tol=0, abs_tol=1e-12)
    v2 = _quant_stub_vote(_payload(returns=0.002, atr=0.001))
    assert v2["confidence"] == 1.0


def test_quant_side_follows_ma_when_momentum_disagrees():
    buy_vs_down = _quant_stub_vote(_payload(ma_fast=1.102, ma_slow=1.100, returns=-0.0005, atr=0.001))
    assert buy_vs_down["direction"] == "BUY"
    assert buy_vs_down["allow"] is True
    sell_vs_up = _quant_stub_vote(_payload(ma_fast=1.098, ma_slow=1.100, returns=0.0005, atr=0.001))
    assert sell_vs_up["direction"] == "SELL"
    assert sell_vs_up["allow"] is True


def test_quant_jpy_orientation_uses_same_price_comparison():
    buy = _quant_stub_vote(_payload(price=154.30, ma_fast=154.31, ma_slow=154.20, returns=0.0002, atr=0.04))
    sell = _quant_stub_vote(_payload(price=154.30, ma_fast=154.20, ma_slow=154.31, returns=-0.0002, atr=0.04))
    assert buy["direction"] == "BUY"
    assert sell["direction"] == "SELL"
