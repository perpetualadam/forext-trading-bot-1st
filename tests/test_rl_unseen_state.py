"""Verify empty-table / epsilon / reset behaviour of production RLAgent."""

from __future__ import annotations

import random
from collections import Counter
from unittest.mock import patch

from forex_bot.rl_agent import RLAgent, _ACTIONS


def test_unseen_state_defaults_all_q_to_zero():
    agent = RLAgent(epsilon=0.0)
    with patch("forex_bot.rl_agent.random.choice", return_value="SKIP"):
        agent.decide("never-seen")
    assert agent.q["never-seen"] == {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}


def test_action_order_is_buy_sell_skip():
    assert _ACTIONS == ("BUY", "SELL", "SKIP")
    agent = RLAgent()
    table = agent._ensure_state("x")
    assert list(table.keys()) == ["BUY", "SELL", "SKIP"]


def test_all_equal_q_greedy_chooses_among_all_three():
    agent = RLAgent(epsilon=0.0)
    seen = set()
    with patch("forex_bot.rl_agent.random.random", return_value=1.0):
        for i in range(60):
            seen.add(agent.decide(f"tie-{i}"))
    assert seen == {"BUY", "SELL", "SKIP"}


def test_epsilon_branch_uses_full_action_tuple():
    agent = RLAgent(epsilon=0.25)
    with (
        patch("forex_bot.rl_agent.random.random", return_value=0.0),
        patch("forex_bot.rl_agent.random.choice", return_value="SELL") as choice,
    ):
        assert agent.decide("e") == "SELL"
    choice.assert_called_once_with(_ACTIONS)


def test_below_epsilon_explores_at_boundary():
    """explore iff random() < epsilon; 0.25 < 0.25 is false."""
    agent = RLAgent(epsilon=0.25)
    agent.q["s"] = {"BUY": 5.0, "SELL": 0.0, "SKIP": 0.0}
    with patch("forex_bot.rl_agent.random.random", return_value=0.249999):
        with patch("forex_bot.rl_agent.random.choice", return_value="SKIP"):
            assert agent.decide("s") == "SKIP"
    with patch("forex_bot.rl_agent.random.random", return_value=0.25):
        assert agent.decide("s") == "BUY"


def test_unseen_state_empirical_frequencies_near_one_third():
    agent = RLAgent(alpha=0.15, epsilon=0.25)
    rng = random.Random(20260918)
    with (
        patch("forex_bot.rl_agent.random.random", rng.random),
        patch("forex_bot.rl_agent.random.choice", rng.choice),
    ):
        counts = Counter(agent.decide(f"u{i}") for i in range(3000))
    assert set(counts) == {"BUY", "SELL", "SKIP"}
    for action in _ACTIONS:
        assert 800 <= counts[action] <= 1200


def test_new_agent_has_empty_table_nothing_loaded():
    agent = RLAgent()
    assert agent.q == {}
    assert agent.epsilon == 0.25
    assert agent.alpha == 0.15
    assert agent.snapshot() == {"states": 0, "epsilon": 0.25}


def test_decide_does_not_return_hold():
    agent = RLAgent(epsilon=1.0)
    for i in range(40):
        assert agent.decide(f"h{i}") in ("BUY", "SELL", "SKIP")
