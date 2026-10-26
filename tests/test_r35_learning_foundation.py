"""Offline R.35 learning-foundation tests. No model is trained."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from forex_bot.research.decision_journal import JournalRejected, validate_journal_record
from forex_bot.research.learning.data_validation import validate_frame
from forex_bot.research.learning.features import causal_features, leaky_future_return, prefix_matches
from forex_bot.research.learning.journal import research_decision_id, unavailable_decision
from forex_bot.research.learning.labels import label_outcomes, labels_isolated
from forex_bot.research.learning.mistakes import classify_mistake, probabilistic_scores
from forex_bot.research.learning.protocol import (
    EVALUATION_PROTOCOL_SHA256,
    FEATURE_SCHEMA_SHA256,
    LABEL_PROTOCOL_SHA256,
    canonical_hash,
)
from forex_bot.research.learning.splits import chronological_split


def _bars(count: int, *, gap_at: int | None = None, price: float = 1.10) -> pd.DataFrame:
    times = pd.date_range("2026-01-05", periods=count, freq="5min", tz="UTC")
    if gap_at is not None:
        times = times.to_series()
        times.iloc[gap_at:] = times.iloc[gap_at:] + pd.Timedelta(hours=2)
        times = pd.DatetimeIndex(times)
    close = pd.Series([price + i * 0.0001 for i in range(count)])
    return pd.DataFrame(
        {
            "time": times,
            "bid_open": close - 0.00005,
            "bid_high": close + 0.0001,
            "bid_low": close - 0.0001,
            "bid_close": close - 0.00005,
            "ask_open": close + 0.00005,
            "ask_high": close + 0.0002,
            "ask_low": close,
            "ask_close": close + 0.00005,
            "volume": 100.0,
            "complete": True,
        }
    )


def test_validation_rejects_duplicates_nonfinite_and_negative_spread() -> None:
    frame = _bars(6)
    frame.loc[2, "time"] = frame.loc[1, "time"]
    frame.loc[3, "bid_close"] = float("nan")
    frame.loc[4, "ask_close"] = frame.loc[4, "bid_close"] - 0.01
    clean, report = validate_frame(frame)
    assert report["duplicate_timestamps"] == 1
    assert report["non_finite_prices"]["bid_close"] == 1
    assert report["negative_spread_rows"] == 1
    assert len(clean) == 3


def test_out_of_order_timestamps_are_counted_and_sorted() -> None:
    frame = _bars(4)
    frame.loc[0, "time"], frame.loc[1, "time"] = frame.loc[1, "time"], frame.loc[0, "time"]
    clean, report = validate_frame(frame)
    assert report["out_of_order_steps"] == 1
    assert clean["time"].is_monotonic_increasing


def test_causal_features_are_prefix_invariant_and_warmup_is_invalid() -> None:
    frame = _bars(40)
    features = causal_features(frame)
    assert not bool(features["feature_valid"].iloc[19])
    assert bool(features["feature_valid"].iloc[20])
    assert prefix_matches(causal_features, frame, 25)
    assert not prefix_matches(leaky_future_return, frame, 25)


def test_labels_do_not_enter_features_and_respect_horizon() -> None:
    frame = _bars(30)
    features = causal_features(frame)
    labels = label_outcomes(frame, 12)
    assert labels_isolated(features, labels)
    assert bool(labels["outcome_evaluable"].iloc[0])
    assert not bool(labels["outcome_evaluable"].iloc[-1])
    expected = frame["time"].iloc[12]
    assert labels["outcome_timestamp"].iloc[0] == expected
    buy = (frame["bid_close"].iloc[12] - frame["ask_close"].iloc[0]) / frame["ask_close"].iloc[0]
    assert labels["buy_cost_adjusted_return"].iloc[0] == pytest.approx(buy)


def test_gap_makes_overlapping_window_unevaluable() -> None:
    frame = _bars(20, gap_at=10)
    labels = label_outcomes(frame, 12)
    assert not bool(labels["outcome_evaluable"].iloc[0])
    assert int(labels["outcome_evaluable"].sum()) < 20


def test_journal_id_is_deterministic_and_prediction_stays_unavailable() -> None:
    stamp = pd.Timestamp("2026-01-05T00:00:00Z").to_pydatetime()
    left = research_decision_id("abc", "EUR_USD", "M5", stamp)
    right = research_decision_id("abc", "EUR_USD", "M5", stamp)
    other = research_decision_id("abc", "EUR_USD", "M5", stamp + pd.Timedelta(minutes=5).to_pytimedelta())
    assert left == right and left != other
    row = unavailable_decision(
        {
            "decision_at": stamp,
            "instrument": "EUR_USD",
            "timeframe": "M5",
            "dataset_sha256": "abc",
            "feature_valid": True,
            "spread": 0.0001,
            "volatility": 0.001,
            "outcome_evaluable": True,
            "outcome_timestamp": stamp + pd.Timedelta(hours=1).to_pytimedelta(),
            "midpoint_return": 0.001,
            "directional_outcome": "up",
        }
    )
    assert row["prediction_status"] == "prediction_unavailable"
    assert row["probabilities"] is None
    assert row["hypothetical_cost_adjusted_outcome"] is None
    assert row["mistake_class"] == "insufficient_information"


def test_unavailable_prediction_cannot_carry_an_invented_error() -> None:
    stamp = pd.Timestamp("2026-01-05T00:00:00Z").to_pydatetime()
    payload = {
        "decision_at": stamp,
        "instrument": "EUR_USD",
        "timeframe": "M5",
        "feature_schema_version": "r35.features.v1",
        "model_id": "unavailable",
        "model_version": "unavailable",
        "artifact_sha256": "0" * 64,
        "prediction_direction": None,
        "probabilities": None,
        "decision": "abstained",
        "spread": 0.0001,
        "market_condition": "unclassified",
        "risk_rejection_reason": "prediction_unavailable",
        "outcome_return": 0.001,
        "prediction_error": 0.2,
        "outcome_evaluable": True,
        "adverse_outcome": None,
        "data_provenance": "abc",
        "model_provenance": "prediction_unavailable",
        "prediction_status": "unavailable",
    }
    with pytest.raises(JournalRejected):
        validate_journal_record(payload)


def test_mistake_taxonomy_does_not_treat_every_loss_as_a_model_error() -> None:
    assert classify_mistake({"prediction_status": "unavailable", "outcome_evaluable": True}) == "insufficient_information"
    assert classify_mistake({"prediction_status": "invalid", "outcome_evaluable": True}) == "invalid_prediction"
    assert classify_mistake({"prediction_status": "directional", "outcome_evaluable": False}) == "unevaluable_outcome"
    assert (
        classify_mistake(
            {
                "prediction_status": "directional",
                "outcome_evaluable": True,
                "direction": "BUY",
                "directional_outcome": "up",
                "cost_adjusted_return": -0.0002,
                "confidence": 0.9,
            }
        )
        == "correct_direction_negative_cost"
    )
    assert (
        classify_mistake(
            {
                "prediction_status": "directional",
                "outcome_evaluable": True,
                "direction": "BUY",
                "directional_outcome": "down",
                "confidence": 0.95,
            }
        )
        == "high_confidence_incorrect"
    )
    assert (
        classify_mistake(
            {
                "prediction_status": "abstain",
                "outcome_evaluable": True,
                "best_hypothetical_cost_return": 0.001,
            }
        )
        == "missed_opportunity"
    )
    assert (
        classify_mistake(
            {
                "prediction_status": "directional",
                "outcome_evaluable": True,
                "direction": "SELL",
                "directional_outcome": "down",
                "cost_adjusted_return": 0.001,
                "confidence": 0.4,
            }
        )
        == "low_confidence_correct"
    )
    scores = probabilistic_scores(None, "up")
    assert scores["status"] == "unavailable"
    scored = probabilistic_scores({"up": 0.8, "down": 0.2}, "up")
    assert scored["status"] == "computed"
    assert math.isfinite(scored["log_loss"])


def test_protocol_hashes_and_embargoed_split() -> None:
    assert len(FEATURE_SCHEMA_SHA256) == 64
    assert canonical_hash({"a": 1}) == canonical_hash({"a": 1})
    assert LABEL_PROTOCOL_SHA256 != EVALUATION_PROTOCOL_SHA256
    split = chronological_split(1000)
    train_stop, valid_start = split["train"][1], split["validation"][0]
    valid_stop, test_start = split["validation"][1], split["test"][0]
    assert train_stop + split["embargo_bars"] <= valid_start
    assert valid_stop + split["embargo_bars"] <= test_start
    assert split["research_exposed_not_an_untouched_holdout"] is True


def test_r34_fail_closed_vote_and_rl_remain() -> None:
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent

    vote = _quant_stub_vote({"ma_fast": 2.0, "ma_slow": 1.0, "returns": 0.01, "atr": 0.01})
    assert vote["allow"] is False and vote["direction"] is None and vote["reason"] == "quant_stub_removed"
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
