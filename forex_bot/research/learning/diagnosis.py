"""Offline diagnosis and bounded learning checks. Not an operational voter."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.research.learning.features import FEATURE_COLUMNS, causal_features
from forex_bot.research.learning.labels import label_outcomes
from forex_bot.research.learning.mistakes import classify_mistake
from forex_bot.research.learning.protocol import (
    EMBARGO_BARS,
    EUR_USD_PIP,
    EVALUATION_PROTOCOL_SHA256,
    FEATURE_SCHEMA_SHA256,
    LABEL_PROTOCOL_SHA256,
    canonical_hash,
)
from forex_bot.research.learning.supervised import (
    INDEX_TO_CLASS,
    apply_policy,
    assign_targets,
    block_interval,
    fit_logistic,
    next_bar_labels,
    policy_returns,
)

RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
R36_TEST_START = 59657
R36_LOGISTIC_PREDICTION_SHA256 = "27a3eaa45b8d17482d3e70877921e536cd3a3e67bb29a44fc9cc2a07055c88b8"
R36_XGBOOST_PREDICTION_SHA256 = "49e4d191086a2568ffc25a75534ee9c38148517394191770e0b2b211e0f58e3f"

DIAGNOSTIC_PROTOCOL = {
    "stage": "R37",
    "uses_r36_test_for_candidate_selection": False,
    "uses_r36_test_labels_for_training": False,
    "maximum_candidate_changes": 2,
    "candidate_c_not_run": "No training or validation pattern identified a specific feature or hyperparameter defect. A third search is not authorised.",
    "questions": [
        "why_full_bar_directional_counts_differ_from_stride_action_counts",
        "whether_probability_bins_have_a_positive_cost_adjusted_return",
        "whether_a_pre_registered_48_bar_horizon_changes_the_economic_result",
    ],
    "permitted_periods": {
        "estimation_and_training_end_exclusive": 44743,
        "candidate_evaluation_end_exclusive": 59657,
        "r36_test_start": R36_TEST_START,
    },
    "candidates": {
        "A_expected_value_bins": {
            "model": "logistic_regression_same_hyperparameters_fit_only_on_positions_20_to_15000",
            "estimation_fold": [15012, 25000],
            "evaluation_folds": [[25012, 35000], [35012, 44731]],
            "bins": [0.35, 0.40, 0.45, 0.50, 1.01],
            "tradeable_if": "n_at_least_100_and_mean_next_bar_return_above_zero_and_bootstrap_low_above_zero",
            "if_no_tradeable_bin": "always_abstain_and_reject",
            "refit_after_evaluation": False,
            "r36_artifact_used_only_for_count_reconciliation": True,
        },
        "B_horizon_48": {
            "family": "logistic_regression_same_hyperparameters_as_r36",
            "horizon_bars": 48,
            "embargo_bars": 48,
            "reason": "R.35 already listed 48 bars. It is the one pre-registered alternative, not a horizon searched on the test slice.",
            "train": [20, 44695],
            "validation": [44743, 59609],
            "walk_forward": [
                {"train": [20, 12000], "eval": [12048, 20000]},
                {"train": [20, 20000], "eval": [20048, 28000]},
                {"train": [20, 28000], "eval": [28048, 36000]},
            ],
            "log_loss_not_comparable_to_r36_12_bar_target": True,
        },
    },
    "acceptance": [
        "causal_features_and_labels",
        "no_training_row_at_or_after_r36_test_start",
        "reproducible_specification",
        "at_least_30_nonoverlapping_actions_on_each_reported_evaluation_window",
        "next_bar_mean_including_abstentions_above_zero",
        "block_bootstrap_low_above_zero",
        "half_pip_mean_above_zero",
        "improvement_not_confined_to_one_window",
    ],
    "costs": {
        "entry": "next_bar_open_bid_ask",
        "adverse_price_units": [0.0, 0.5 * EUR_USD_PIP, EUR_USD_PIP],
        "not_a_full_oanda_spreadbet_cost_model": True,
    },
    "bootstrap": {"block": 20, "reps": 200, "seed": 3601},
    "multiple_comparisons": "Two pre-registered candidates. No search over thresholds or horizons after results.",
    "stop_conditions": [
        "prediction_hash_mismatch_stops_economic_claims",
        "no_tradeable_probability_bin_rejects_candidate_A",
        "candidate_B_fails_acceptance_on_validation_or_walk_forward",
    ],
    "feature_schema_sha256": FEATURE_SCHEMA_SHA256,
    "label_protocol_sha256": LABEL_PROTOCOL_SHA256,
    "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
    "r36_embargo_bars": EMBARGO_BARS,
    "production_authorised": False,
}

DIAGNOSTIC_PROTOCOL_SHA256 = canonical_hash(DIAGNOSTIC_PROTOCOL)


def assert_no_test_rows(positions: np.ndarray, test_start: int = R36_TEST_START) -> None:
    if np.any(np.asarray(positions) >= test_start):
        raise RuntimeError("test_rows_in_training")


def outcome_reaches(last_index: int, next_start: int, horizon: int) -> bool:
    return last_index + horizon >= next_start


def reconcile_populations(positions: np.ndarray, labels: np.ndarray, next_evaluable: np.ndarray, stride: int = 12) -> dict:
    """Count full-bar decisions and the non-overlapping economic subset separately."""
    positions = np.asarray(positions)
    labels = np.asarray(labels)
    nxt = np.asarray(next_evaluable, dtype=bool)
    directional = labels != "NO_TRADE"
    on_stride = (positions % stride == 0) & nxt
    return {
        "population_full_eligible_rows": int(len(labels)),
        "full_abstentions": int((~directional).sum()),
        "full_directional_calls": int(directional.sum()),
        "next_bar_unevaluable": int((~nxt).sum()),
        "stride": stride,
        "stride_opportunities": int(on_stride.sum()),
        "stride_actions": int((directional & on_stride).sum()),
        "directional_calls_outside_stride": int((directional & ~on_stride).sum()),
        "overlapping_outcomes": True,
        "stride_actions_are_not_independent_of_nearby_bars": True,
    }


def mistake_tally(frame: pd.DataFrame, labels: np.ndarray, confidence: np.ndarray) -> dict:
    counts: dict[str, int] = {}
    directional = 0
    for index, label in enumerate(labels):
        evaluable = bool(frame["next_bar_evaluable"].iloc[index])
        side = None if label == "NO_TRADE" else str(label)
        if side is not None:
            directional += 1
        buy = float(frame["next_buy_return"].iloc[index]) if evaluable else None
        sell = float(frame["next_sell_return"].iloc[index]) if evaluable else None
        kind = classify_mistake(
            {
                "prediction_status": "abstain" if side is None else "directional",
                "outcome_evaluable": evaluable,
                "direction": side,
                "directional_outcome": None if not evaluable else frame["directional_outcome"].iloc[index],
                "cost_adjusted_return": None if side is None or not evaluable else (buy if side == "BUY" else sell),
                "confidence": float(confidence[index]),
                "best_hypothetical_cost_return": None if not evaluable else max(buy, sell),
            }
        )
        counts[kind] = counts.get(kind, 0) + 1
    counts["denominator_rows"] = int(len(labels))
    counts["denominator_directional_calls"] = directional
    return counts


def load_logistic(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = fit_logistic(np.zeros((3, len(FEATURE_COLUMNS))), np.array([0, 1, 2]))
    model.named_steps["imputer"].statistics_ = np.asarray(payload["imputer_statistics"], dtype=float)
    scaler = model.named_steps["scaler"]
    scaler.mean_ = np.asarray(payload["scaler_mean"], dtype=float)
    scaler.scale_ = np.asarray(payload["scaler_scale"], dtype=float)
    scaler.var_ = scaler.scale_ ** 2
    clf = model.named_steps["clf"]
    clf.coef_ = np.asarray(payload["coef"], dtype=float)
    clf.intercept_ = np.asarray(payload["intercept"], dtype=float)
    clf.classes_ = np.asarray(payload["classes"], dtype=int)
    return model


def load_xgboost(path: Path):
    from xgboost import XGBClassifier

    model = XGBClassifier()
    model.load_model(str(path))
    return model


def table_for_horizon(clean: pd.DataFrame, horizon: int) -> pd.DataFrame:
    features = causal_features(clean)
    labels = label_outcomes(clean, horizon)
    nxt = next_bar_labels(clean, horizon)
    target = assign_targets(
        labels["buy_cost_adjusted_return"].to_numpy(dtype=float),
        labels["sell_cost_adjusted_return"].to_numpy(dtype=float),
        labels["outcome_evaluable"].to_numpy(dtype=bool),
    )
    mid = (clean["bid_close"].to_numpy(dtype=float) + clean["ask_close"].to_numpy(dtype=float)) / 2.0
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "position": np.arange(len(clean), dtype=int),
                    "time": clean["time"].to_numpy(),
                    "mid_close": mid,
                    "target": target,
                }
            ),
            features.reset_index(drop=True),
            labels.reset_index(drop=True),
            nxt.reset_index(drop=True),
        ],
        axis=1,
    )


def eligible(table: pd.DataFrame, start: int, stop: int) -> pd.DataFrame:
    mask = (table["position"] >= start) & (table["position"] < stop) & table["feature_valid"] & table["target"].notna()
    return table.loc[mask].copy()


def side_bins(probability: np.ndarray, returns: np.ndarray, edges: list[float]) -> list[dict]:
    rows = []
    for left, right in zip(edges, edges[1:]):
        if right >= 1.0:
            mask = (probability >= left) & (probability <= right) & np.isfinite(returns)
        else:
            mask = (probability >= left) & (probability < right) & np.isfinite(returns)
        sample = returns[mask]
        interval = block_interval(sample) if len(sample) else None
        tradeable = bool(len(sample) >= 100 and interval is not None and interval["mean"] > 0.0 and interval["low"] > 0.0)
        rows.append(
            {
                "low": left,
                "high": right,
                "n": int(len(sample)),
                "mean": None if len(sample) == 0 else float(sample.mean()),
                "bootstrap_low": None if interval is None else interval["low"],
                "tradeable": tradeable,
            }
        )
    return rows


def ev_policy(proba: np.ndarray, buy_bins: list[dict], sell_bins: list[dict]) -> np.ndarray:
    labels = np.full(len(proba), "NO_TRADE", dtype=object)

    def _inside(probability: np.ndarray, bins: list[dict]) -> np.ndarray:
        allowed = np.zeros(len(probability), dtype=bool)
        for item in bins:
            if not item["tradeable"]:
                continue
            upper = item["high"] >= 1.0
            allowed |= (probability >= item["low"]) & (probability <= item["high"] if upper else probability < item["high"])
        return allowed

    buy_ok = _inside(proba[:, 2], buy_bins) & (proba[:, 2] > proba[:, 0])
    sell_ok = _inside(proba[:, 0], sell_bins) & (proba[:, 0] > proba[:, 2])
    labels[buy_ok] = "BUY"
    labels[sell_ok] = "SELL"
    return labels


def stride_economics(frame: pd.DataFrame, labels: np.ndarray, stride: int) -> dict:
    positions = frame["position"].to_numpy(dtype=int)
    evaluable = frame["next_bar_evaluable"].to_numpy(dtype=bool)
    chosen = (positions % stride == 0) & evaluable
    buy = frame["next_buy_return"].to_numpy(dtype=float)
    sell = frame["next_sell_return"].to_numpy(dtype=float)
    ask = frame["next_entry_ask"].to_numpy(dtype=float)
    bid = frame["next_entry_bid"].to_numpy(dtype=float)
    reports = {}
    for extra, name in ((0.0, "recorded_bid_ask"), (0.5 * EUR_USD_PIP, "plus_half_pip"), (EUR_USD_PIP, "plus_one_pip")):
        returns = policy_returns(labels[chosen], buy[chosen], sell[chosen], ask[chosen], bid[chosen], extra)
        actions = labels[chosen] != "NO_TRADE"
        interval = block_interval(returns) if len(returns) else None
        reports[name] = {
            "n_opportunities": int(chosen.sum()),
            "n_actions": int(actions.sum()),
            "mean_including_abstentions": float(returns.mean()) if len(returns) else None,
            "mean_actions_only": float(returns[actions].mean()) if np.any(actions) else None,
            "bootstrap_low": None if interval is None else interval["low"],
        }
    return reports


def promising(windows: list[dict]) -> dict:
    """A window passes only on its own next-bar economics. One window is not enough."""
    passed = []
    for item in windows:
        recorded = item["recorded_bid_ask"]
        half = item["plus_half_pip"]
        ok = (
            recorded["n_actions"] >= 30
            and recorded["mean_including_abstentions"] is not None
            and recorded["mean_including_abstentions"] > 0.0
            and recorded["bootstrap_low"] is not None
            and recorded["bootstrap_low"] > 0.0
            and half["mean_including_abstentions"] is not None
            and half["mean_including_abstentions"] > 0.0
        )
        passed.append(ok)
    return {
        "windows_passed": int(sum(passed)),
        "windows_required": len(windows),
        "qualifies": len(windows) > 1 and all(passed),
        "production_authorised": False,
        "validation_status": "unvalidated",
    }
