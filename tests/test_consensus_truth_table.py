"""Important production consensus rows: AIEnsemble.vote + evaluate RL gate."""

from __future__ import annotations

import asyncio

from forex_bot.ai_ensemble import AIEnsemble


class _V:
    def __init__(self, out):
        self.out = out

    async def predict(self, payload):
        if isinstance(self.out, Exception):
            raise self.out
        return dict(self.out)


def _final(quant, api, rl: str) -> str:
    local = [_V(quant)] if quant is not None else []
    ext = [_V(api)] if api is not None else []
    ai = asyncio.run(AIEnsemble(local_llms=local, external_llms=ext).vote({}, "EUR_USD"))
    if not ai["allow"]:
        return "NO_TRADE"
    side = str(ai.get("direction", "BUY")).upper().strip()
    if side not in ("BUY", "SELL"):
        side = "BUY"
    if rl == "SKIP":
        return "NO_TRADE"
    if rl in ("BUY", "SELL") and rl != side:
        return "NO_TRADE"
    return side


BUY = {"allow": True, "confidence": 0.8, "direction": "BUY"}
SELL = {"allow": True, "confidence": 0.8, "direction": "SELL"}
HOLD_ALLOW = {"allow": True, "confidence": 0.8, "direction": "HOLD"}
DENY_BUY = {"allow": False, "confidence": 0.8, "direction": "BUY"}
DENY_SELL = {"allow": False, "confidence": 0.8, "direction": "SELL"}
WEAK_BUY = {"allow": True, "confidence": 0.2, "direction": "BUY"}
STRONG_SELL = {"allow": True, "confidence": 0.9, "direction": "SELL"}


def test_quant_only_buy_rl_match():
    assert _final(BUY, None, "BUY") == "BUY"


def test_quant_only_buy_rl_skip_or_sell_is_no_trade():
    assert _final(BUY, None, "SKIP") == "NO_TRADE"
    assert _final(BUY, None, "SELL") == "NO_TRADE"


def test_quant_only_deny_is_no_trade_even_if_rl_buy():
    assert _final(DENY_BUY, None, "BUY") == "NO_TRADE"


def test_quant_buy_api_buy():
    assert _final(BUY, BUY, "BUY") == "BUY"


def test_quant_buy_api_hold_allow_still_buy_then_rl():
    # HOLD does not add side weight; BUY weight from quant; allow from both
    assert _final(BUY, HOLD_ALLOW, "BUY") == "BUY"


def test_quant_buy_api_sell_stronger_flips_side():
    assert _final(WEAK_BUY, STRONG_SELL, "SELL") == "SELL"
    assert _final(WEAK_BUY, STRONG_SELL, "BUY") == "NO_TRADE"


def test_quant_sell_api_sell():
    assert _final(SELL, SELL, "SELL") == "SELL"


def test_quant_buy_api_deny_sell_allow_score_can_fail():
    # allow_score = 0.8 / (0.8+0.8) = 0.5 → NOT > 0.5
    assert _final(BUY, DENY_SELL, "BUY") == "NO_TRADE"


def test_api_failure_quant_remains():
    assert _final(BUY, RuntimeError("down"), "BUY") == "BUY"


def test_both_missing_fail_closed():
    assert _final(None, None, "BUY") == "NO_TRADE"
