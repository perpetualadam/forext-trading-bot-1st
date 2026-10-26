"""The operational quant stub no longer maps indicators to BUY or SELL."""

from __future__ import annotations

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


def test_former_directional_payloads_now_abstain():
    payloads = [
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.0005, atr=0.0008),
        dict(ma_fast=1.0990, ma_slow=1.1010, returns=-0.0005, atr=0.0008),
        dict(ma_fast=1.1000, ma_slow=1.1000, returns=0.001, atr=0.001),
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.00005, atr=0.001),
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.001, atr=0.0),
        dict(ma_fast=float("nan"), ma_slow=1.1, returns=0.001, atr=0.001),
        dict(returns=0.0004, atr=0.001),
        dict(returns=0.002, atr=0.001),
        dict(ma_fast=1.102, ma_slow=1.100, returns=-0.0005, atr=0.001),
        dict(price=154.30, ma_fast=154.31, ma_slow=154.20, returns=0.0002, atr=0.04),
    ]
    for item in payloads:
        vote = _quant_stub_vote(_payload(**item))
        assert vote["allow"] is False
        assert vote["direction"] is None
        assert vote["reason"] == "quant_stub_removed"
