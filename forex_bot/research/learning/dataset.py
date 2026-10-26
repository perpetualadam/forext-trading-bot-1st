"""Build an in-memory research summary from one local CSV. The CSV is not modified."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.features import FEATURE_COLUMNS, causal_features
from forex_bot.research.learning.journal import journal_digest, research_decision_id, unavailable_decision
from forex_bot.research.learning.labels import label_outcomes, labels_isolated
from forex_bot.research.learning.protocol import (
    EVALUATION_PROTOCOL_SHA256,
    FEATURE_SCHEMA_SHA256,
    LABEL_PROTOCOL_SHA256,
    PRIMARY_HORIZON_BARS,
    WARMUP_BARS,
)
from forex_bot.research.learning.splits import chronological_split


def build_research_summary(path: Path, *, instrument: str, timeframe: str, horizon: int = PRIMARY_HORIZON_BARS) -> dict:
    dataset_sha = file_sha256(path)
    raw = pd.read_csv(path)
    clean, quality = validate_frame(raw)
    features = causal_features(clean)
    labels = label_outcomes(clean, horizon)
    if not labels_isolated(features, labels):
        raise RuntimeError("label_columns_entered_features")
    decision_ids = [
        research_decision_id(dataset_sha, instrument, timeframe, stamp.to_pydatetime())
        for stamp in clean["time"]
    ]
    sample_rows = []
    for position in (WARMUP_BARS, len(clean) // 2, len(clean) - horizon - 1):
        if position < 0 or position >= len(clean):
            continue
        sample_rows.append(_row(clean, features, labels, position, dataset_sha, instrument, timeframe))
    decisions = [unavailable_decision(item) for item in sample_rows]
    feature_valid = int(features["feature_valid"].sum())
    warmup_exclusions = int((~features["feature_valid"].iloc[:WARMUP_BARS]).sum()) if len(features) >= WARMUP_BARS else int(len(features))
    labelled = int(labels["outcome_evaluable"].sum())
    split = chronological_split(len(clean))
    summary = {
        "source_path": str(path),
        "dataset_sha256": dataset_sha,
        "instrument": instrument,
        "timeframe": timeframe,
        "rows_read": quality["rows_read"],
        "rows_kept": quality["rows_kept"],
        "first_timestamp": quality["first_timestamp"],
        "last_timestamp": quality["last_timestamp"],
        "quality": quality,
        "feature_rows_valid": feature_valid,
        "warmup_exclusions": warmup_exclusions,
        "labelled_observations": labelled,
        "unevaluable_observations": int(len(labels) - labelled),
        "journal_entries": len(decision_ids),
        "journal_id_sha256": journal_digest([{"id": item} for item in decision_ids]),
        "validated_journal_sample": len(decisions),
        "prediction_unavailable_count": len(decision_ids),
        "feature_schema_sha256": FEATURE_SCHEMA_SHA256,
        "label_protocol_sha256": LABEL_PROTOCOL_SHA256,
        "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
        "chronological_split": {key: list(value) if isinstance(value, tuple) else value for key, value in split.items()},
        "sample_feature_at_warmup": {name: float(features.iloc[WARMUP_BARS][name]) for name in FEATURE_COLUMNS},
        "sample_decisions": decisions,
        "labels_isolated": True,
        "research_exposed": True,
        "profitability_claim": False,
    }
    summary["summary_sha256"] = journal_digest(
        [
            {key: summary[key] for key in (
                "dataset_sha256",
                "rows_read",
                "feature_rows_valid",
                "labelled_observations",
                "sample_feature_at_warmup",
                "sample_decisions",
            )}
        ]
    )
    return summary


def _row(clean, features, labels, position: int, dataset_sha: str, instrument: str, timeframe: str) -> dict:
    label = labels.iloc[position]
    feature = features.iloc[position]
    stamp = label["outcome_timestamp"]
    return {
        "decision_at": clean["time"].iloc[position].to_pydatetime(),
        "instrument": instrument,
        "timeframe": timeframe,
        "dataset_sha256": dataset_sha,
        "feature_valid": bool(feature["feature_valid"]),
        "spread": float(feature["spread"]),
        "volatility": float(feature["rolling_vol_20"]) if bool(feature["feature_valid"]) else None,
        "outcome_evaluable": bool(label["outcome_evaluable"]),
        "outcome_timestamp": None if pd.isna(stamp) else stamp.to_pydatetime(),
        "midpoint_return": None if not bool(label["outcome_evaluable"]) else float(label["midpoint_return"]),
        "directional_outcome": None if not bool(label["outcome_evaluable"]) else label["directional_outcome"],
    }
