"""Cost-aware feature research. This module is not a trading voter."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from forex_bot.research.learning.features import FEATURE_COLUMNS, causal_features
from forex_bot.research.learning.labels import label_outcomes, labels_isolated
from forex_bot.research.learning.protocol import (
    BAR_SECONDS,
    FEATURE_SCHEMA_SHA256,
    LABEL_PROTOCOL_SHA256,
    WARMUP_BARS,
    canonical_hash,
)
from forex_bot.research.learning.supervised import block_interval, next_bar_labels, policy_returns

RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
PRIMARY_INSTRUMENT = "EUR_USD"
PRIMARY_HORIZON = 12
SENSITIVITY_HORIZON = 48
NUMERIC_FEATURES = (
    "return_1",
    "rolling_vol_20",
    "atr_14",
    "ma_distance",
    "momentum_12",
    "spread",
    "range_20",
    "volume",
)
CATEGORICAL_FEATURES = ("hour_utc", "session_code")
PIP_SIZE = {
    "AUD_USD": 0.0001,
    "EUR_USD": 0.0001,
    "GBP_USD": 0.0001,
    "USD_CAD": 0.0001,
    "USD_CHF": 0.0001,
    "USD_JPY": 0.01,
}
DATASET_SHA256 = {
    "AUD_USD": "e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0",
    "EUR_USD": "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091",
    "GBP_USD": "ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58",
    "USD_CAD": "a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60",
    "USD_CHF": "3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc",
    "USD_JPY": "e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c",
}

PROTOCOL = {
    "stage": "R38",
    "feature_schema_sha256": FEATURE_SCHEMA_SHA256,
    "label_protocol_sha256": LABEL_PROTOCOL_SHA256,
    "datasets": DATASET_SHA256,
    "pip_size": PIP_SIZE,
    "features": list(FEATURE_COLUMNS),
    "numeric_features": list(NUMERIC_FEATURES),
    "categorical_features": list(CATEGORICAL_FEATURES),
    "horizons": [PRIMARY_HORIZON, SENSITIVITY_HORIZON],
    "primary_horizon": PRIMARY_HORIZON,
    "warmup_bars": WARMUP_BARS,
    "train_end_exclusive": "2026-03-01T00:00:00Z",
    "confirmation_start": "2026-05-01T00:00:00Z",
    "walk_forward_eval_starts": ["2025-11-01T00:00:00Z", "2025-12-01T00:00:00Z", "2026-01-01T00:00:00Z"],
    "primary_instrument": PRIMARY_INSTRUMENT,
    "primary_tests": "eight_numeric_features_by_signed_midpoint_return_on_eurusd_horizon_12",
    "multiple_comparison_count": 8,
    "bonferroni_alpha": 0.05,
    "association_bootstrap": {"block": "max(20, horizon)", "reps": 800, "seed": 3801},
    "economic_bootstrap": {"block": "max(20, horizon)", "reps": 200, "seed": 3801},
    "minimum_confirmation_rows": 500,
    "minimum_actions": 30,
    "candidate_rule": "largest_absolute_training_spearman_whose_unadjusted_interval_excludes_zero; tie_breaks_to_earlier_feature; no_second_try",
    "candidate_thresholds": "training_20th_and_80th_percentiles",
    "magnitude_model": "ridge_alpha_1_median_imputer_standard_scaler_fit_on_training_only",
    "magnitude_baseline": "training_mean_absolute_midpoint_return",
    "other_instruments": "exploratory_replication_not_independent_confirmations",
    "pooled_model": False,
    "production_authorised": False,
}

PROTOCOL_SHA256 = canonical_hash(PROTOCOL)


def promotion_allowed() -> bool:
    return False


def same_sign(left: float, right: float) -> bool:
    if left == 0.0 or right == 0.0 or not math.isfinite(left) or not math.isfinite(right):
        return False
    return (left > 0.0) == (right > 0.0)


def average_rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ordered = values[order]
    change = np.empty(len(values), dtype=bool)
    change[0] = True
    change[1:] = ordered[1:] != ordered[:-1]
    group = np.cumsum(change)
    counts = np.bincount(group)[1:]
    starts = np.cumsum(counts) - counts
    average = (starts + 1.0 + starts + counts) / 2.0
    ranked = np.empty(len(values), dtype=float)
    ranked[order] = average[group - 1]
    return ranked


def spearman(left: np.ndarray, right: np.ndarray) -> float:
    ranked_left = average_rank(left)
    ranked_right = average_rank(right)
    ranked_left -= ranked_left.mean()
    ranked_right -= ranked_right.mean()
    scale = math.sqrt(float((ranked_left * ranked_left).sum()) * float((ranked_right * ranked_right).sum()))
    if scale == 0.0:
        return 0.0
    return float((ranked_left * ranked_right).sum() / scale)


def association_interval(left: np.ndarray, right: np.ndarray, block: int, reps: int = 800, seed: int = 3801, tests: int = 8) -> dict:
    paired = np.isfinite(left) & np.isfinite(right)
    x = np.asarray(left[paired], dtype=float)
    y = np.asarray(right[paired], dtype=float)
    empty = {"n": int(len(x)), "rho": None, "low": None, "high": None, "adjusted_low": None, "adjusted_high": None, "excludes_zero": False}
    if len(x) < block * 2:
        return empty
    point = spearman(x, y)
    generator = np.random.Generator(np.random.PCG64(seed))
    draws = int(math.ceil(len(x) / block))
    replicates = np.empty(reps, dtype=float)
    for index in range(reps):
        starts = generator.integers(0, len(x) - block + 1, size=draws)
        chosen = np.concatenate([np.arange(start, start + block) for start in starts])[: len(x)]
        replicates[index] = spearman(x[chosen], y[chosen])
    low, high = np.quantile(replicates, [0.025, 0.975])
    tail = 0.025 / tests
    adjusted_low, adjusted_high = np.quantile(replicates, [tail, 1.0 - tail])
    return {
        "n": int(len(x)),
        "rho": point,
        "low": float(low),
        "high": float(high),
        "adjusted_low": float(adjusted_low),
        "adjusted_high": float(adjusted_high),
        "excludes_zero": bool(adjusted_low > 0.0 or adjusted_high < 0.0),
    }


def quantile_edges(values: np.ndarray) -> tuple[float, float]:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < 50:
        raise RuntimeError("too_few_training_rows_for_thresholds")
    low, high = np.quantile(clean, [0.20, 0.80])
    return float(low), float(high)


def apply_candidate(values: np.ndarray, low: float, high: float, positive_association: bool) -> np.ndarray:
    labels = np.full(len(values), "NO_TRADE", dtype=object)
    above = values >= high
    below = values <= low
    if positive_association:
        labels[above] = "BUY"
        labels[below] = "SELL"
    else:
        labels[below] = "BUY"
        labels[above] = "SELL"
    return labels


def research_frame(clean: pd.DataFrame, horizon: int) -> pd.DataFrame:
    features = causal_features(clean)
    labels = label_outcomes(clean, horizon)
    if not labels_isolated(features, labels):
        raise RuntimeError("label_columns_entered_features")
    nxt = next_bar_labels(clean, horizon)
    mid = (clean["bid_close"].to_numpy(dtype=float) + clean["ask_close"].to_numpy(dtype=float)) / 2.0
    frame = pd.concat(
        [
            pd.DataFrame({"position": np.arange(len(clean), dtype=int), "time": clean["time"].to_numpy(), "mid": mid}),
            features.reset_index(drop=True),
            labels.reset_index(drop=True),
            nxt.reset_index(drop=True),
        ],
        axis=1,
    )
    frame["absolute_midpoint_return"] = frame["midpoint_return"].abs()
    buy = frame["buy_cost_adjusted_return"].to_numpy(dtype=float)
    sell = frame["sell_cost_adjusted_return"].to_numpy(dtype=float)
    frame["hindsight_best_side"] = np.fmax(buy, sell)
    return frame


def period_mask(frame: pd.DataFrame, start: pd.Timestamp | None, end: pd.Timestamp | None, horizon: int) -> pd.Series:
    """Keep rows whose decision and completed outcome sit inside the period."""
    ok = frame["feature_valid"] & frame["outcome_evaluable"]
    if start is not None:
        cutoff = start + pd.Timedelta(seconds=horizon * BAR_SECONDS)
        ok = ok & (frame["time"] >= cutoff)
    if end is not None:
        ok = ok & (frame["time"] < end) & (frame["outcome_timestamp"] < end)
    return ok


def classify_feature(n: int, excludes_zero: bool, stable: bool, candidate_passes: bool) -> str:
    if candidate_passes:
        return "POTENTIAL_ECONOMIC_SIGNAL_REQUIRES_INDEPENDENT_VALIDATION"
    if n < PROTOCOL["minimum_confirmation_rows"]:
        return "INCONCLUSIVE"
    if excludes_zero and stable:
        return "STATISTICAL_VALUE_ONLY"
    if excludes_zero and not stable:
        return "INCONCLUSIVE"
    return "NO_DEMONSTRATED_PREDICTIVE_VALUE"


def stride_mean(frame: pd.DataFrame, labels: np.ndarray, horizon: int, pip: float) -> dict:
    chosen = (frame["position"].to_numpy(dtype=int) % horizon == 0) & frame["next_bar_evaluable"].to_numpy(dtype=bool)
    buy = frame["next_buy_return"].to_numpy(dtype=float)
    sell = frame["next_sell_return"].to_numpy(dtype=float)
    ask = frame["next_entry_ask"].to_numpy(dtype=float)
    bid = frame["next_entry_bid"].to_numpy(dtype=float)
    reports = {}
    for extra, name in ((0.0, "recorded"), (0.5 * pip, "half_pip"), (pip, "one_pip")):
        returns = policy_returns(labels[chosen], buy[chosen], sell[chosen], ask[chosen], bid[chosen], extra)
        actions = labels[chosen] != "NO_TRADE"
        interval = block_interval(returns, block=max(20, horizon), reps=200, seed=3801)
        reports[name] = {
            "n_opportunities": int(chosen.sum()),
            "n_actions": int(actions.sum()),
            "mean": float(returns.mean()) if len(returns) else None,
            "bootstrap_low": None if interval is None else interval["low"],
        }
    return reports


def fit_magnitude(train_x: np.ndarray, train_y: np.ndarray, eval_x: np.ndarray, eval_y: np.ndarray) -> dict:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]
    )
    model.fit(train_x, train_y)
    predicted = model.predict(eval_x)
    baseline = float(np.mean(train_y))
    model_mae = float(np.mean(np.abs(eval_y - predicted)))
    baseline_mae = float(np.mean(np.abs(eval_y - baseline)))
    return {
        "n_train": int(len(train_y)),
        "n_eval": int(len(eval_y)),
        "model_mae": model_mae,
        "baseline_mae": baseline_mae,
        "beats_training_average": bool(model_mae < baseline_mae),
        "scaler_fit_on_training_only": True,
    }
