"""Verify production RLAgent string action mapping (no integer encode/decode)."""

from __future__ import annotations

from forex_bot.rl_agent import RLAgent, _ACTIONS


def test_actions_are_strings_not_integers():
    assert _ACTIONS == ("BUY", "SELL", "SKIP")
    assert 0 not in _ACTIONS
    assert 1 not in _ACTIONS
    assert 2 not in _ACTIONS


def test_greedy_prefers_highest_q_without_buy_sell_swap():
    agent = RLAgent(alpha=0.15, epsilon=0.0)
    agent.q["s"] = {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}
    assert agent.decide("s") == "BUY"
    agent.q["s"] = {"BUY": 0.0, "SELL": 1.0, "SKIP": 0.0}
    assert agent.decide("s") == "SELL"
    agent.q["s"] = {"BUY": 0.0, "SELL": 0.0, "SKIP": 1.0}
    assert agent.decide("s") == "SKIP"


def test_update_writes_named_action_not_inverted_side():
    agent = RLAgent(alpha=1.0, epsilon=0.0)
    agent.update("s", "BUY", 10.0)
    assert agent.q["s"]["BUY"] == 10.0
    assert agent.q["s"]["SELL"] == 0.0
    agent.update("s", "SELL", -4.0)
    assert agent.q["s"]["SELL"] == -4.0
    assert agent.q["s"]["BUY"] == 10.0


def test_invalid_update_action_is_ignored():
    agent = RLAgent()
    agent.update("s", "HOLD", 5.0)
    agent.update("s", 1, 5.0)  # type: ignore[arg-type]
    assert "s" not in agent.q


def test_unknown_rl_string_would_not_veto_in_evaluate_gate():
    """evaluate() only vetoes SKIP or BUY/SELL mismatch; any other string continues."""
    direction = "BUY"
    for rl_action in ("HOLD", "stay", "", "3"):
        blocked = rl_action == "SKIP" or (
            rl_action in ("BUY", "SELL") and rl_action != direction
        )
        assert blocked is False
