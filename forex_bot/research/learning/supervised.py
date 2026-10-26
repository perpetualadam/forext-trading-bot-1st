"""Offline supervised research models. Not an operational voter."""

from __future__ import annotations

import hashlib
import importlib
import json
import math

import numpy as np
import pandas as pd

from forex_bot.research.learning.features import FEATURE_COLUMNS, causal_features
from forex_bot.research.learning.labels import LABEL_COLUMNS, label_outcomes
from forex_bot.research.learning.protocol import (
    BAR_SECONDS,
    EMBARGO_BARS,
    EUR_USD_PIP,
    EVALUATION_PROTOCOL_SHA256,
    FEATURE_SCHEMA_SHA256,
    HIGH_CONFIDENCE,
    LABEL_PROTOCOL_SHA256,
    PRIMARY_HORIZON_BARS,
    canonical_hash,
)

RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
VALIDATION_STATUS = "unvalidated"
INDEX_TO_CLASS = ("SELL", "NO_TRADE", "BUY")
CLASS_TO_INDEX = {name: index for index, name in enumerate(INDEX_TO_CLASS)}
BANNED_COLUMNS = set(LABEL_COLUMNS) | {
    "target",
    "next_buy_return",
    "next_sell_return",
    "next_entry_ask",
    "next_entry_bid",
    "decision_ask",
    "decision_bid",
    "mid_close",
}

FROZEN_PROTOCOL = {
    "stage": "R36",
    "selection_uses_test": False,
    "validation_status": VALIDATION_STATUS,
    "production_authorised": False,
    "feature_schema_version": "r35.features.v1",
    "feature_schema_sha256": FEATURE_SCHEMA_SHA256,
    "label_protocol_sha256": LABEL_PROTOCOL_SHA256,
    "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
    "horizon_bars": PRIMARY_HORIZON_BARS,
    "target": {
        "name": "r36.cost_adjusted_three_class.v1",
        "buy": "close_to_close_buy_return > 0 and buy_return > sell_return",
        "sell": "close_to_close_sell_return > 0 and sell_return > buy_return",
        "no_trade": "otherwise, including exact ties",
        "price_unit": "fractional_return",
        "entry": "decision_bar_ask_or_bid_close",
        "exit": "bid_or_ask_close_12_bars_later",
        "threshold_rule": "strictly_positive_cost_adjusted_return",
        "threshold_not_fit_on_test": True,
    },
    "next_bar_execution": {
        "decision": "after_completed_candle",
        "entry": "next_candle_open_bid_ask",
        "exit": "close_12_bars_after_the_decision_candle",
        "gap": "unevaluable_unless_next_bar_is_exactly_300_seconds_later",
    },
    "policy": {
        "a_priori_confidence": 0.50,
        "validation_threshold_grid": [0.40, 0.50, 0.60],
        "threshold_selection": "highest_stride12_next_bar_mean_with_at_least_30_actions_else_0.50",
        "tie_break": "higher_threshold",
        "advancement_uses_threshold": 0.50,
        "high_confidence": HIGH_CONFIDENCE,
    },
    "models": {
        "logistic": {
            "family": "logistic_regression",
            "C": 1.0,
            "solver": "lbfgs",
            "max_iter": 500,
            "seed": 36,
            "preprocessing": "median_imputer_and_standard_scaler_fit_on_training_rows_only",
        },
        "lightgbm": {"family": "lightgbm", "status": "use_only_if_already_installed"},
        "xgboost": {
            "family": "xgboost",
            "n_estimators": 60,
            "max_depth": 3,
            "learning_rate": 0.05,
            "min_child_weight": 20.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_lambda": 1.0,
            "seed": 36,
            "device": "cpu",
            "n_jobs": 1,
        },
    },
    "splits": {
        "train": [20, 44731],
        "validation": [44743, 59645],
        "test": [59657, 74560],
        "embargo_bars": EMBARGO_BARS,
        "warmup_bars": 20,
    },
    "walk_forward": [
        {"name": "wf1", "train": [20, 15000], "eval": [15012, 25000]},
        {"name": "wf2", "train": [20, 25000], "eval": [25012, 35000]},
        {"name": "wf3", "train": [20, 35000], "eval": [35012, 44731]},
    ],
    "advancement_requires": [
        "validation_log_loss_below_frequency_baseline",
        "validation_brier_below_frequency_baseline",
        "validation_ece_at_most_0.10",
        "at_least_30_stride12_validation_actions",
        "stride12_next_bar_mean_above_zero",
        "block_bootstrap_lower_bound_above_zero",
        "half_pip_adverse_mean_above_zero",
        "at_least_two_walk_forward_folds_not_worse_than_frequency_baseline",
        "reproducible_refit",
    ],
    "bootstrap": {"block": 20, "reps": 200, "seed": 3601, "interval": [0.025, 0.975]},
    "adverse_price_units": [0.0, 0.5 * EUR_USD_PIP, EUR_USD_PIP],
    "research_exposed": True,
}

FROZEN_PROTOCOL_SHA256 = canonical_hash(FROZEN_PROTOCOL)


def library_status() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in ("numpy", "pandas", "sklearn", "lightgbm", "xgboost", "joblib"):
        try:
            module = importlib.import_module(name)
        except Exception:
            found[name] = None
            continue
        found[name] = str(getattr(module, "__version__", "present"))
    return found


def assert_causal_columns(names: list[str] | tuple[str, ...]) -> None:
    if list(names) != list(FEATURE_COLUMNS) or set(names) & BANNED_COLUMNS:
        raise RuntimeError("feature_columns_rejected")


def outcome_reaches_next_period(last_train_index: int, eval_start: int, horizon: int = EMBARGO_BARS) -> bool:
    """True when the last training label's future bar lands inside the next period."""
    return last_train_index + horizon >= eval_start


def assign_targets(buy: np.ndarray, sell: np.ndarray, evaluable: np.ndarray) -> np.ndarray:
    """Map cost-adjusted returns to BUY, SELL, or NO_TRADE. Non-evaluable rows stay None."""
    target = np.empty(len(buy), dtype=object)
    target[:] = None
    usable = np.asarray(evaluable, dtype=bool) & np.isfinite(buy) & np.isfinite(sell)
    target[usable] = "NO_TRADE"
    target[usable & (buy > 0.0) & (buy > sell)] = "BUY"
    target[usable & (sell > 0.0) & (sell > buy)] = "SELL"
    return target


def next_bar_labels(frame: pd.DataFrame, horizon: int = PRIMARY_HORIZON_BARS) -> pd.DataFrame:
    """Entry is the next candle open. Exit is the close `horizon` bars after the decision."""
    step = pd.to_timedelta(BAR_SECONDS, unit="s")
    exit_step = pd.to_timedelta(horizon * BAR_SECONDS, unit="s")
    next_ok = frame["time"].shift(-1) - frame["time"] == step
    exit_ok = frame["time"].shift(-horizon) - frame["time"] == exit_step
    ask_entry = frame["ask_open"].shift(-1)
    bid_entry = frame["bid_open"].shift(-1)
    future_bid = frame["bid_close"].shift(-horizon)
    future_ask = frame["ask_close"].shift(-horizon)
    usable = (
        next_ok.fillna(False)
        & exit_ok.fillna(False)
        & ask_entry.notna()
        & bid_entry.notna()
        & future_bid.notna()
        & future_ask.notna()
        & (ask_entry > 0)
        & (bid_entry > 0)
    )
    buy = (future_bid - ask_entry) / ask_entry
    sell = (bid_entry - future_ask) / bid_entry
    return pd.DataFrame(
        {
            "next_bar_evaluable": usable,
            "next_buy_return": buy.where(usable),
            "next_sell_return": sell.where(usable),
            "next_entry_ask": ask_entry.where(usable),
            "next_entry_bid": bid_entry.where(usable),
        }
    )


def prepare_market_table(clean: pd.DataFrame) -> pd.DataFrame:
    """Join causal features and future labels without putting labels into the feature columns."""
    assert_causal_columns(FEATURE_COLUMNS)
    features = causal_features(clean)
    labels = label_outcomes(clean, PRIMARY_HORIZON_BARS)
    nxt = next_bar_labels(clean, PRIMARY_HORIZON_BARS)
    if set(features.columns) & set(LABEL_COLUMNS):
        raise RuntimeError("label_columns_entered_features")
    target = assign_targets(
        labels["buy_cost_adjusted_return"].to_numpy(dtype=float),
        labels["sell_cost_adjusted_return"].to_numpy(dtype=float),
        labels["outcome_evaluable"].to_numpy(dtype=bool),
    )
    mid = (clean["bid_close"].to_numpy(dtype=float) + clean["ask_close"].to_numpy(dtype=float)) / 2.0
    table = pd.concat(
        [
            pd.DataFrame(
                {
                    "position": np.arange(len(clean), dtype=int),
                    "time": clean["time"].to_numpy(),
                    "mid_close": mid,
                    "decision_ask": clean["ask_close"].to_numpy(dtype=float),
                    "decision_bid": clean["bid_close"].to_numpy(dtype=float),
                    "target": target,
                }
            ),
            features.reset_index(drop=True),
            labels.reset_index(drop=True),
            nxt.reset_index(drop=True),
        ],
        axis=1,
    )
    return table


def slice_positions(table: pd.DataFrame, start: int, stop: int) -> pd.DataFrame:
    mask = (table["position"] >= start) & (table["position"] < stop) & table["feature_valid"] & table["target"].notna()
    return table.loc[mask].copy()


def matrix_of(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    assert_causal_columns(FEATURE_COLUMNS)
    values = frame.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float)
    target = np.array([CLASS_TO_INDEX[value] for value in frame["target"]], dtype=int)
    return values, target


def fit_logistic(values: np.ndarray, target: np.ndarray):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    solver="lbfgs",
                    max_iter=500,
                    random_state=36,
                ),
            ),
        ]
    )
    model.fit(values, target)
    return model


def fit_xgboost(values: np.ndarray, target: np.ndarray):
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=20.0,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="multi:softprob",
        num_class=3,
        random_state=36,
        n_jobs=1,
        tree_method="hist",
        device="cpu",
        verbosity=0,
    )
    model.fit(values, target)
    return model


def align_proba(model, values: np.ndarray) -> np.ndarray:
    proba = np.asarray(model.predict_proba(values), dtype=float)
    classes = model.named_steps["clf"].classes_ if hasattr(model, "named_steps") else model.classes_
    full = np.zeros((len(values), 3), dtype=float)
    for column, label in enumerate(classes):
        full[:, int(label)] = proba[:, column]
    if not np.all(np.isfinite(full)) or not np.allclose(full.sum(axis=1), 1.0, atol=1e-5):
        raise RuntimeError("invalid_probabilities")
    return full


def apply_policy(proba: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    choice = np.argmax(proba, axis=1)
    confidence = proba.max(axis=1)
    labels = np.array(INDEX_TO_CLASS, dtype=object)[choice]
    labels = np.where(confidence < threshold, "NO_TRADE", labels)
    return labels, confidence


def frequency_vector(target: np.ndarray) -> np.ndarray:
    counts = np.bincount(target, minlength=3).astype(float)
    if counts.sum() <= 0:
        raise RuntimeError("empty_training_target")
    return counts / counts.sum()


def log_loss(proba: np.ndarray, target: np.ndarray) -> float:
    chosen = np.clip(proba[np.arange(len(target)), target], 1e-15, 1.0)
    return float(-np.mean(np.log(chosen)))


def brier_score(proba: np.ndarray, target: np.ndarray) -> float:
    one_hot = np.eye(3)[target]
    return float(np.mean(np.sum((proba - one_hot) ** 2, axis=1)))


def expected_calibration_error(proba: np.ndarray, target: np.ndarray, bins: int = 10) -> float:
    confidence = proba.max(axis=1)
    predicted = proba.argmax(axis=1)
    correct = (predicted == target).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (confidence >= edges[index]) & (confidence <= edges[index + 1])
        else:
            mask = (confidence >= edges[index]) & (confidence < edges[index + 1])
        if not np.any(mask):
            continue
        total += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return total


def block_interval(values: np.ndarray, block: int = 20, reps: int = 200, seed: int = 3601) -> dict | None:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < block * 2:
        return None
    generator = np.random.Generator(np.random.PCG64(seed))
    blocks = int(math.ceil(len(clean) / block))
    means = np.empty(reps, dtype=float)
    for draw in range(reps):
        starts = generator.integers(0, len(clean) - block + 1, size=blocks)
        sample = np.concatenate([clean[start : start + block] for start in starts])[: len(clean)]
        means[draw] = float(sample.mean())
    low, high = np.quantile(means, [0.025, 0.975])
    return {"mean": float(clean.mean()), "low": float(low), "high": float(high), "n": int(len(clean))}


def policy_returns(labels: np.ndarray, buy: np.ndarray, sell: np.ndarray, entry_ask: np.ndarray, entry_bid: np.ndarray, extra: float) -> np.ndarray:
    out = np.zeros(len(labels), dtype=float)
    buy_mask = labels == "BUY"
    sell_mask = labels == "SELL"
    out[buy_mask] = buy[buy_mask] - extra / entry_ask[buy_mask]
    out[sell_mask] = sell[sell_mask] - extra / entry_bid[sell_mask]
    return out


def stride_mask(positions: np.ndarray, evaluable: np.ndarray) -> np.ndarray:
    return (positions % PRIMARY_HORIZON_BARS == 0) & evaluable


def momentum_baseline(frame: pd.DataFrame) -> np.ndarray:
    """Research-only directional rule. It is not registered as a production voter."""
    edge = frame["spread"].to_numpy(dtype=float) / frame["mid_close"].to_numpy(dtype=float)
    momentum = frame["momentum_12"].to_numpy(dtype=float)
    labels = np.full(len(frame), "NO_TRADE", dtype=object)
    labels[momentum > edge] = "BUY"
    labels[momentum < -edge] = "SELL"
    return labels


def classification_report(proba: np.ndarray, target: np.ndarray, labels: np.ndarray) -> dict:
    matrix = np.zeros((3, 3), dtype=int)
    predicted = np.array([CLASS_TO_INDEX[value] for value in labels], dtype=int)
    for truth, guess in zip(target, predicted):
        matrix[int(truth), int(guess)] += 1
    per_class = {}
    for index, name in enumerate(INDEX_TO_CLASS):
        support = int(matrix[index].sum())
        called = int(matrix[:, index].sum())
        hit = int(matrix[index, index])
        per_class[name] = {
            "precision": None if called == 0 else hit / called,
            "recall": None if support == 0 else hit / support,
            "support": support,
        }
    return {
        "log_loss": log_loss(proba, target),
        "brier": brier_score(proba, target),
        "ece": expected_calibration_error(proba, target),
        "accuracy": float((predicted == target).mean()),
        "abstention_rate": float((labels == "NO_TRADE").mean()),
        "confusion_truth_rows_predicted_columns": matrix.tolist(),
        "per_class": per_class,
        "class_balance": {name: int((target == index).sum()) for index, name in enumerate(INDEX_TO_CLASS)},
    }


def economic_report(frame: pd.DataFrame, labels: np.ndarray, price: str) -> dict:
    if price == "next":
        buy = frame["next_buy_return"].to_numpy(dtype=float)
        sell = frame["next_sell_return"].to_numpy(dtype=float)
        ask = frame["next_entry_ask"].to_numpy(dtype=float)
        bid = frame["next_entry_bid"].to_numpy(dtype=float)
        evaluable = frame["next_bar_evaluable"].to_numpy(dtype=bool)
    else:
        buy = frame["buy_cost_adjusted_return"].to_numpy(dtype=float)
        sell = frame["sell_cost_adjusted_return"].to_numpy(dtype=float)
        ask = frame["decision_ask"].to_numpy(dtype=float)
        bid = frame["decision_bid"].to_numpy(dtype=float)
        evaluable = np.isfinite(buy) & np.isfinite(sell)
    positions = frame["position"].to_numpy(dtype=int)
    chosen = stride_mask(positions, evaluable)
    reports = {}
    for extra, name in ((0.0, "recorded_bid_ask"), (0.5 * EUR_USD_PIP, "plus_half_pip"), (EUR_USD_PIP, "plus_one_pip")):
        returns = policy_returns(labels[chosen], buy[chosen], sell[chosen], ask[chosen], bid[chosen], extra)
        actions = labels[chosen] != "NO_TRADE"
        interval = block_interval(returns)
        reports[name] = {
            "n_opportunities": int(chosen.sum()),
            "n_actions": int(actions.sum()),
            "mean_including_abstentions": float(returns.mean()) if len(returns) else None,
            "mean_actions_only": float(returns[actions].mean()) if np.any(actions) else None,
            "block_interval": interval,
        }
    return reports


def qualify(validation: dict, walkforward: list[dict]) -> dict:
    """Apply the frozen rule. This function does not accept held-out test metrics."""
    if "test" in validation or any("test" in row for row in walkforward):
        raise RuntimeError("test_metrics_not_allowed_in_selection")
    folds_ok = 0
    for row in walkforward:
        if row.get("status") == "ok" and row["log_loss"] <= row["baseline_log_loss"]:
            folds_ok += 1
    checks = {
        "validation_log_loss_below_frequency_baseline": validation["log_loss"] < validation["baseline_log_loss"],
        "validation_brier_below_frequency_baseline": validation["brier"] < validation["baseline_brier"],
        "validation_ece_at_most_0.10": validation["ece"] <= 0.10,
        "at_least_30_stride12_validation_actions": validation["n_actions"] >= 30,
        "stride12_next_bar_mean_above_zero": validation["mean_return"] is not None and validation["mean_return"] > 0.0,
        "block_bootstrap_lower_bound_above_zero": validation["bootstrap_low"] is not None and validation["bootstrap_low"] > 0.0,
        "half_pip_adverse_mean_above_zero": validation["half_pip_mean"] is not None and validation["half_pip_mean"] > 0.0,
        "at_least_two_walk_forward_folds_not_worse_than_frequency_baseline": folds_ok >= 2,
        "reproducible_refit": bool(validation["reproducible"]),
    }
    return {
        "qualifies": all(checks.values()),
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "passed_checks": [name for name, passed in checks.items() if passed],
        "walk_forward_folds_not_worse": folds_ok,
        "validation_status": VALIDATION_STATUS,
        "production_authorised": False,
    }


def prediction_digest(proba: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(proba, dtype="<f8").tobytes()).hexdigest()


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=float).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
