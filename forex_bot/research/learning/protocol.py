"""Frozen R.35 research constants. These are not a trained model."""

from __future__ import annotations

import hashlib
import json

FEATURE_SCHEMA_VERSION = "r35.features.v1"
LABEL_PROTOCOL_VERSION = "r35.labels.v1"
JOURNAL_PROTOCOL_VERSION = "r35.journal.v1"
EVALUATION_PROTOCOL_VERSION = "r35.evaluation.v1"

BAR_SECONDS = 300
PRIMARY_HORIZON_BARS = 12
HORIZONS = (1, 6, 12, 48)
WARMUP_BARS = 20
MA_FAST = 5
MA_SLOW = 20
ATR_PERIOD = 14
VOLATILITY_WINDOW = 20
MOMENTUM_WINDOW = 12
RANGE_WINDOW = 20
EMBARGO_BARS = PRIMARY_HORIZON_BARS
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20
HIGH_CONFIDENCE = 0.70
EUR_USD_PIP = 0.0001

# The completed bar at the decision timestamp is included. Earlier completed
# bars are included. Later bars are not. An incomplete bar is excluded.
CANDLE_ALIGNMENT = "current_completed_candle_inclusive"

FEATURE_SCHEMA = {
    "version": FEATURE_SCHEMA_VERSION,
    "instrument_timeframe": "declared_by_caller",
    "candle_alignment": CANDLE_ALIGNMENT,
    "normalisation": "none_no_future_statistics",
    "missing_values": "row_feature_valid_false_when_any_required_value_is_missing",
    "rolling_std_ddof": 1,
    "warmup_bars": WARMUP_BARS,
    "features": [
        {"name": "return_1", "type": "float", "unit": "midpoint_fraction", "lookback": 1},
        {"name": "rolling_vol_20", "type": "float", "unit": "return_std", "lookback": 20},
        {"name": "atr_14", "type": "float", "unit": "price", "lookback": 14},
        {"name": "ma_distance", "type": "float", "unit": "fraction_of_midpoint", "lookback": 20},
        {"name": "momentum_12", "type": "float", "unit": "midpoint_fraction", "lookback": 12},
        {"name": "spread", "type": "float", "unit": "price", "lookback": 0},
        {"name": "hour_utc", "type": "float", "unit": "hour", "lookback": 0},
        {"name": "session_code", "type": "float", "unit": "bucket", "lookback": 0},
        {"name": "range_20", "type": "float", "unit": "fraction_of_midpoint", "lookback": 20},
        {"name": "volume", "type": "float", "unit": "source_volume", "lookback": 0},
    ],
}

LABEL_PROTOCOL = {
    "version": LABEL_PROTOCOL_VERSION,
    "primary_horizon_bars": PRIMARY_HORIZON_BARS,
    "horizons": list(HORIZONS),
    "bar_seconds": BAR_SECONDS,
    "entry": "decision_bar_close_bid_ask",
    "exit": "close_exactly_horizon_bars_later",
    "buy_cost_return": "(future_bid_close - decision_ask_close) / decision_ask_close",
    "sell_cost_return": "(decision_bid_close - future_ask_close) / decision_bid_close",
    "midpoint_return": "(future_midpoint - decision_midpoint) / decision_midpoint",
    "no_trade": "abstention_has_no_chosen_side_and_no_cost_adjusted_decision_outcome",
    "missing_price": "unevaluable",
    "time_gap": "unevaluable_unless_future_timestamp_is_exactly_horizon_times_bar_seconds",
    "end_of_data": "unevaluable",
    "overlapping_windows": "labels_may_overlap_evaluation_embargoes_them",
    "not_an_executed_trade": True,
    "difference_from_r30": "R.30 enters on a later bar inside the scalp simulator. R.35 labels the decision bar close to a later close.",
}

EVALUATION_PROTOCOL = {
    "version": EVALUATION_PROTOCOL_VERSION,
    "order": "chronological",
    "train_fraction": TRAIN_FRACTION,
    "validation_fraction": VALIDATION_FRACTION,
    "test_fraction": 0.20,
    "embargo_bars": EMBARGO_BARS,
    "warmup_bars": WARMUP_BARS,
    "model_selection": "training_and_validation_only",
    "held_out_test": "not_used_for_selection_or_tuning",
    "scalers": "fit_inside_each_training_prefix_only",
    "costs": "recorded_bid_ask_not_zero",
    "baselines": ["always_abstain", "majority_training_direction"],
    "probability_metrics": ["calibration_curve", "log_loss", "brier_score"],
    "coverage_metrics": ["abstention_rate", "class_balance", "regime_slices"],
    "research_exposed_warning": "The R.29-R.33 EUR_USD M5 year has already been researched. A new split of that file is not an untouched final test.",
}


def canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


FEATURE_SCHEMA_SHA256 = canonical_hash(FEATURE_SCHEMA)
LABEL_PROTOCOL_SHA256 = canonical_hash(LABEL_PROTOCOL)
EVALUATION_PROTOCOL_SHA256 = canonical_hash(EVALUATION_PROTOCOL)
