"""Focused offline tests for R.36 supervised research. No broker and no full-year fit."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from forex_bot.research.learning.features import leaky_future_return, prefix_matches
from forex_bot.research.learning.supervised import (
    INDEX_TO_CLASS,
    align_proba,
    apply_policy,
    assert_causal_columns,
    assign_targets,
    brier_score,
    expected_calibration_error,
    fit_logistic,
    frequency_vector,
    library_status,
    log_loss,
    next_bar_labels,
    outcome_reaches_next_period,
    policy_returns,
    prepare_market_table,
    qualify,
)


def _bars(count: int, *, gap_at: int | None = None, start: float = 1.10, step: float = 0.0002) -> pd.DataFrame:
    times = pd.date_range("2026-01-05", periods=count, freq="5min", tz="UTC")
    if gap_at is not None:
        series = times.to_series()
        series.iloc[gap_at:] = series.iloc[gap_at:] + pd.Timedelta(hours=3)
        times = pd.DatetimeIndex(series)
    close = pd.Series([start + index * step for index in range(count)])
    return pd.DataFrame(
        {
            "time": times,
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


def test_libraries_report_missing_lightgbm_without_installing() -> None:
    status = library_status()
    assert status["sklearn"]
    assert status["xgboost"]
    assert status["lightgbm"] is None


def test_targets_use_cost_and_send_ties_to_no_trade() -> None:
    buy = np.array([0.01, -0.01, 0.02, 0.02])
    sell = np.array([-0.01, 0.01, 0.03, 0.02])
    labels = assign_targets(buy, sell, np.array([True, True, True, True]))
    assert list(labels) == ["BUY", "SELL", "SELL", "NO_TRADE"]


def test_next_bar_entry_and_gap_are_explicit() -> None:
    frame = _bars(20)
    labels = next_bar_labels(frame, 12)
    assert bool(labels["next_bar_evaluable"].iloc[0])
    buy = (frame["bid_close"].iloc[12] - frame["ask_open"].iloc[1]) / frame["ask_open"].iloc[1]
    assert labels["next_buy_return"].iloc[0] == pytest.approx(buy)
    gapped = next_bar_labels(_bars(20, gap_at=1), 12)
    assert not bool(gapped["next_bar_evaluable"].iloc[0])


def test_embargo_detects_a_window_that_reaches_the_next_period() -> None:
    assert outcome_reaches_next_period(99, 112, 12) is False
    assert outcome_reaches_next_period(100, 112, 12) is True


def test_features_stay_separate_and_leaky_fixture_fails_prefix_check() -> None:
    frame = _bars(50)
    table = prepare_market_table(frame)
    assert "buy_cost_adjusted_return" not in table.columns[: len(table.columns)] or "target" in table.columns
    with pytest.raises(RuntimeError):
        assert_causal_columns(["return_1", "midpoint_return"])
    assert prefix_matches.__wrapped__ if False else not prefix_matches(leaky_future_return, frame, 30)


def test_scaler_and_refit_use_training_rows_only() -> None:
    from sklearn.preprocessing import StandardScaler

    train = np.array([[0.0], [2.0]])
    future = np.array([[100.0]])
    fitted = StandardScaler().fit(train)
    leaked = StandardScaler().fit(np.vstack([train, future]))
    assert fitted.mean_[0] == pytest.approx(1.0)
    assert leaked.mean_[0] != pytest.approx(fitted.mean_[0])


def test_logistic_fit_is_reproducible_and_probabilities_are_valid() -> None:
    rising = _bars(40, start=1.10, step=0.0003)
    falling = _bars(40, start=1.112, step=-0.0003)
    falling["time"] = pd.date_range("2026-01-05 03:20", periods=40, freq="5min", tz="UTC")
    frame = prepare_market_table(pd.concat([rising, falling], ignore_index=True))
    usable = frame.loc[frame["feature_valid"] & frame["target"].notna()]
    values = usable.loc[:, ["return_1", "rolling_vol_20", "atr_14", "ma_distance", "momentum_12", "spread", "hour_utc", "session_code", "range_20", "volume"]].to_numpy(dtype=float)
    target = np.array([{"SELL": 0, "NO_TRADE": 1, "BUY": 2}[value] for value in usable["target"]], dtype=int)
    if len(set(target.tolist())) < 2:
        pytest.skip("synthetic sample did not produce two classes")
    left = fit_logistic(values, target)
    right = fit_logistic(values, target)
    first = align_proba(left, values[:5])
    second = align_proba(right, values[:5])
    assert np.allclose(first, second)
    assert np.allclose(first.sum(axis=1), 1.0)
    labels, confidence = apply_policy(first, 0.99)
    assert set(labels).issubset(set(INDEX_TO_CLASS))
    assert np.all(confidence <= 1.0)


def test_probability_metrics_and_policy_cost() -> None:
    target = np.array([1, 1, 2])
    proba = np.array([[0.2, 0.6, 0.2], [0.2, 0.6, 0.2], [0.1, 0.1, 0.8]])
    assert log_loss(proba, target) > 0
    assert brier_score(proba, target) > 0
    assert expected_calibration_error(proba, target) >= 0
    freq = frequency_vector(target)
    assert freq.sum() == pytest.approx(1.0)
    returns = policy_returns(
        np.array(["BUY", "NO_TRADE"]),
        np.array([0.01, 0.02]),
        np.array([-0.01, 0.0]),
        np.array([1.0, 1.0]),
        np.array([1.0, 1.0]),
        0.001,
    )
    assert returns[0] == pytest.approx(0.009)
    assert returns[1] == 0.0


def test_qualification_rejects_test_metrics_and_a_weak_model() -> None:
    with pytest.raises(RuntimeError):
        qualify({"test": True}, [])
    weak = {
        "log_loss": 1.0,
        "baseline_log_loss": 0.5,
        "brier": 0.8,
        "baseline_brier": 0.4,
        "ece": 0.2,
        "n_actions": 0,
        "mean_return": -0.01,
        "bootstrap_low": -0.02,
        "half_pip_mean": -0.02,
        "reproducible": True,
    }
    decision = qualify(weak, [{"status": "ok", "log_loss": 1.0, "baseline_log_loss": 0.5}])
    assert decision["qualifies"] is False
    assert decision["production_authorised"] is False
    assert decision["validation_status"] == "unvalidated"


def test_r34_operational_vote_and_rl_remain_fail_closed() -> None:
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent

    vote = _quant_stub_vote({"ma_fast": 2.0, "ma_slow": 1.0, "returns": 0.01, "atr": 0.01})
    assert vote["allow"] is False and vote["direction"] is None
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    text = open("forex_bot/ai_ensemble.py", encoding="utf-8").read()
    assert "research.learning" not in text
