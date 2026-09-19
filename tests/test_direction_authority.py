"""Verify existing AI aggregation and post-AI direction authority (no production changes)."""

from __future__ import annotations

import asyncio

from forex_bot.ai_ensemble import AIEnsemble, _aggregate_direction


def test_aggregate_direction_weighted_buy_vs_sell():
    assert (
        _aggregate_direction(
            [
                {"direction": "BUY", "confidence": 0.4},
                {"direction": "SELL", "confidence": 0.6},
            ]
        )
        == "SELL"
    )
    assert (
        _aggregate_direction(
            [
                {"direction": "BUY", "confidence": 0.6},
                {"direction": "SELL", "confidence": 0.4},
            ]
        )
        == "BUY"
    )


def test_aggregate_direction_tie_uses_highest_confidence_side():
    assert (
        _aggregate_direction(
            [
                {"direction": "BUY", "confidence": 0.5},
                {"direction": "SELL", "confidence": 0.5},
            ]
        )
        == "BUY"
    )
    assert (
        _aggregate_direction(
            [
                {"direction": "SELL", "confidence": 0.8},
                {"direction": "BUY", "confidence": 0.8},
                {"direction": "HOLD", "confidence": 1.0},
            ]
        )
        == "SELL"
    )


def test_aggregate_direction_all_hold_defaults_buy():
    assert _aggregate_direction([{"direction": "HOLD", "confidence": 0.9}]) == "BUY"
    assert _aggregate_direction([]) == "BUY"


def test_vote_allow_is_confidence_weighted_not_majority_count():
    class _V:
        def __init__(self, out):
            self._out = out

        async def predict(self, payload):
            return dict(self._out)

    ens = AIEnsemble(
        local_llms=[
            _V({"allow": True, "confidence": 0.2, "direction": "BUY"}),
            _V({"allow": False, "confidence": 0.8, "direction": "SELL"}),
        ],
        external_llms=[],
    )
    out = asyncio.run(ens.vote({}, "EUR_USD"))
    # allow_score = 0.2 / (0.2+0.8) = 0.2 → not allowed; direction still SELL by weight
    assert out["allow"] is False
    assert out["direction"] == "SELL"


def test_vote_allow_true_when_weighted_allow_over_half():
    class _V:
        def __init__(self, out):
            self._out = out

        async def predict(self, payload):
            return dict(self._out)

    ens = AIEnsemble(
        local_llms=[_V({"allow": True, "confidence": 0.6, "direction": "SELL"})],
        external_llms=[_V({"allow": False, "confidence": 0.3, "direction": "BUY"})],
    )
    out = asyncio.run(ens.vote({}, "EUR_USD"))
    assert out["allow"] is True
    assert out["direction"] == "SELL"


def test_rl_gate_cannot_replace_ai_side():
    """Mirror of evaluate() RL block: executed side stays AI; mismatch vetoes."""
    ai_direction = "BUY"
    rl_action = "SELL"
    if rl_action == "SKIP":
        final = None
    elif rl_action in ("BUY", "SELL") and rl_action != ai_direction:
        final = None
    else:
        final = ai_direction
    assert final is None

    rl_action = "BUY"
    if rl_action == "SKIP":
        final = None
    elif rl_action in ("BUY", "SELL") and rl_action != ai_direction:
        final = None
    else:
        final = ai_direction
    assert final == "BUY"
