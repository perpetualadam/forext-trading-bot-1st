"""Offline tests for R.37 diagnosis. They do not fit the full EUR_USD year."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.research.learning.diagnosis import (
    DIAGNOSTIC_PROTOCOL,
    assert_no_test_rows,
    ev_policy,
    outcome_reaches,
    promising,
    reconcile_populations,
    side_bins,
)
from forex_bot.research.learning.features import leaky_future_return, prefix_matches
from forex_bot.research.learning.supervised import apply_policy


def _bars(count: int) -> pd.DataFrame:
    close = pd.Series([1.10 + index * 0.00015 for index in range(count)])
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-01-05", periods=count, freq="5min", tz="UTC"),
            "bid_open": close - 0.00008,
            "bid_high": close + 0.0002,
            "bid_low": close - 0.0002,
            "bid_close": close - 0.00005,
            "ask_open": close + 0.00002,
            "ask_high": close + 0.0003,
            "ask_low": close,
            "ask_close": close + 0.00005,
            "volume": 80.0,
            "complete": True,
        }
    )


def test_stride_actions_are_a_subset_of_full_bar_calls() -> None:
    positions = np.arange(36)
    labels = np.array(["NO_TRADE"] * 36, dtype=object)
    labels[[1, 12, 13, 24]] = "BUY"
    counts = reconcile_populations(positions, labels, np.ones(36, dtype=bool), stride=12)
    assert counts["full_directional_calls"] == 4
    assert counts["stride_actions"] == 2
    assert counts["directional_calls_outside_stride"] == 2
    assert counts["population_full_eligible_rows"] == 36


def test_training_cannot_include_the_r36_test_slice() -> None:
    assert_no_test_rows(np.array([20, 44730]))
    try:
        assert_no_test_rows(np.array([59657]))
    except RuntimeError as exc:
        assert str(exc) == "test_rows_in_training"
    else:
        raise AssertionError("test row was accepted")


def test_embargo_and_leaky_feature_are_rejected() -> None:
    assert outcome_reaches(14999, 15012, 12) is False
    assert outcome_reaches(15000, 15012, 12) is True
    assert outcome_reaches(44694, 44743, 48) is False
    frame = _bars(50)
    assert not prefix_matches(leaky_future_return, frame, 30)


def test_probability_bins_do_not_invent_a_trade_without_evidence() -> None:
    probability = np.linspace(0.2, 0.8, 120)
    returns = np.full(120, -0.001)
    bins = side_bins(probability, returns, [0.35, 0.50, 1.01])
    assert all(not item["tradeable"] for item in bins)
    proba = np.tile(np.array([0.2, 0.2, 0.6]), (4, 1))
    labels = ev_policy(proba, bins, bins)
    assert set(labels) == {"NO_TRADE"}


def test_promising_requires_every_window_and_does_not_promote() -> None:
    weak = {"recorded_bid_ask": {"n_actions": 10, "mean_including_abstentions": 0.01, "bootstrap_low": 0.001}, "plus_half_pip": {"mean_including_abstentions": 0.01}}
    decision = promising([weak, weak])
    assert decision["qualifies"] is False
    assert decision["production_authorised"] is False
    assert DIAGNOSTIC_PROTOCOL["uses_r36_test_for_candidate_selection"] is False
    assert DIAGNOSTIC_PROTOCOL["maximum_candidate_changes"] == 2


def test_policy_probabilities_stay_valid() -> None:
    proba = np.array([[0.2, 0.3, 0.5], [0.8, 0.1, 0.1]])
    labels, confidence = apply_policy(proba, 0.50)
    assert list(labels) == ["BUY", "SELL"]
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert float(confidence[0]) == 0.5


def test_r34_fail_closed_behaviour_is_unchanged() -> None:
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent

    vote = _quant_stub_vote({"returns": 0.01})
    assert vote["allow"] is False and vote["direction"] is None and vote["reason"] == "quant_stub_removed"
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    source = open("forex_bot/ai_ensemble.py", encoding="utf-8").read()
    assert "diagnosis" not in source
