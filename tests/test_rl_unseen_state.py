"""The operational RL agent no longer approves from an empty table."""

from __future__ import annotations

from forex_bot.rl_agent import RLAgent, _ACTIONS


def test_unverified_agent_cannot_approve() -> None:
    agent = RLAgent(epsilon=0.0)
    assert agent.persisted_ok is False
    assert agent.q == {}
    for index in range(20):
        assert agent.decide(f"missing-{index}") == "UNAVAILABLE"
    assert agent.q == {}


def test_empty_verified_table_and_ties_cannot_approve() -> None:
    agent = RLAgent(epsilon=1.0)
    agent.persisted_ok = True
    assert agent.decide("absent") == "UNAVAILABLE"
    agent.q["zero"] = {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}
    assert agent.decide("zero") == "UNAVAILABLE"
    agent.q["tie"] = {"BUY": 0.4, "SELL": 0.4, "SKIP": 0.1}
    assert agent.decide("tie") == "UNAVAILABLE"


def test_unique_learned_action_is_stable() -> None:
    agent = RLAgent(epsilon=1.0)
    agent.persisted_ok = True
    agent.q["s"] = {"BUY": 0.2, "SELL": 0.0, "SKIP": 0.1}
    assert agent.decide("s") == "BUY"
    assert agent.decide("s") == "BUY"
    assert _ACTIONS == ("BUY", "SELL", "SKIP")
