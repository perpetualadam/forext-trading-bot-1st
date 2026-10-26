"""Offline tests for R.38 feature discovery. They use synthetic bars only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.research.learning.feature_discovery import (
    DATASET_SHA256,
    PIP_SIZE,
    PROTOCOL,
    apply_candidate,
    association_interval,
    average_rank,
    classify_feature,
    period_mask,
    promotion_allowed,
    quantile_edges,
    research_frame,
    same_sign,
    spearman,
)
from forex_bot.research.learning.features import leaky_future_return, prefix_matches
from forex_bot.research.learning.labels import LABEL_COLUMNS


def _bars(count: int, step: str = "5min") -> pd.DataFrame:
    close = pd.Series([1.10 + index * 0.0001 for index in range(count)])
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-09-01", periods=count, freq=step, tz="UTC"),
            "bid_open": close - 0.00008,
            "bid_high": close + 0.0002,
            "bid_low": close - 0.0002,
            "bid_close": close - 0.00005,
            "ask_open": close + 0.00002,
            "ask_high": close + 0.0003,
            "ask_low": close,
            "ask_close": close + 0.00005,
            "volume": 100.0,
            "complete": True,
        }
    )


def test_dataset_hashes_and_pip_sizes_are_frozen() -> None:
    assert DATASET_SHA256["EUR_USD"].startswith("3ae3c4d0")
    assert PIP_SIZE["USD_JPY"] == 0.01
    assert PIP_SIZE["EUR_USD"] == 0.0001
    assert PROTOCOL["multiple_comparison_count"] == 8
    assert promotion_allowed() is False


def test_gap_makes_the_outcome_unevaluable() -> None:
    frame = _bars(40)
    frame.loc[30:, "time"] = frame.loc[30:, "time"] + pd.Timedelta(hours=2)
    built = research_frame(frame, 12)
    assert bool(built.loc[20, "outcome_evaluable"]) is False
    assert "midpoint_return" not in set(LABEL_COLUMNS) or "midpoint_return" in built.columns
    assert set(LABEL_COLUMNS).isdisjoint({"return_1", "momentum_12", "spread"})


def test_prefix_and_leaky_fixture() -> None:
    frame = _bars(60)
    assert prefix_matches(lambda rows: research_frame(rows, 12), frame, 40) or prefix_matches(
        __import__("forex_bot.research.learning.features", fromlist=["causal_features"]).causal_features,
        frame,
        40,
    )
    assert not prefix_matches(leaky_future_return, frame, 40)


def test_split_purges_outcomes_that_cross_the_boundary() -> None:
    built = research_frame(_bars(400), 12)
    end = built["time"].iloc[200]
    mask = period_mask(built, None, end, 12)
    assert built.loc[mask, "outcome_timestamp"].max() < end
    later = period_mask(built, end, None, 12)
    assert built.loc[later, "time"].min() >= end


def test_quantiles_and_correlation_use_the_supplied_sample() -> None:
    values = np.arange(100, dtype=float)
    low, high = quantile_edges(values)
    assert low < high
    labels = apply_candidate(values, low, high, True)
    assert set(labels) <= {"BUY", "SELL", "NO_TRADE"}
    assert spearman(values, values) > 0.99
    assert spearman(values, -values) < -0.99
    assert same_sign(0.1, 0.2) is True
    assert same_sign(0.1, -0.2) is False
    tied = average_rank(np.array([1.0, 1.0, 3.0]))
    assert tied[0] == tied[1]


def test_bootstrap_interval_is_reproducible_and_wider_after_adjustment() -> None:
    generator = np.random.Generator(np.random.PCG64(7))
    left = generator.normal(size=200)
    right = left + generator.normal(scale=0.1, size=200)
    first = association_interval(left, right, block=20, reps=80, seed=3801, tests=8)
    second = association_interval(left, right, block=20, reps=80, seed=3801, tests=8)
    assert first["rho"] == second["rho"]
    assert first["adjusted_low"] <= first["low"]
    assert first["adjusted_high"] >= first["high"]


def test_classification_does_not_promote_a_single_favourable_look() -> None:
    assert classify_feature(1000, False, True, False) == "NO_DEMONSTRATED_PREDICTIVE_VALUE"
    assert classify_feature(1000, True, True, False) == "STATISTICAL_VALUE_ONLY"
    assert classify_feature(100, True, True, False) == "INCONCLUSIVE"
    assert classify_feature(1000, True, True, True).startswith("POTENTIAL_ECONOMIC_SIGNAL")


def test_next_bar_entry_is_not_the_decision_close() -> None:
    built = research_frame(_bars(40), 12)
    row = built.loc[built["next_bar_evaluable"]].iloc[10]
    source = _bars(40)
    assert float(row["next_entry_ask"]) == float(source["ask_open"].iloc[int(row["position"]) + 1])


def test_r34_fail_closed_behaviour_is_unchanged() -> None:
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent

    vote = _quant_stub_vote({"returns": 0.02})
    assert vote["allow"] is False and vote["reason"] == "quant_stub_removed"
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    assert "feature_discovery" not in open("forex_bot/ai_ensemble.py", encoding="utf-8").read()
