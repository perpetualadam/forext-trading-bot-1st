"""Research decision rows. No model prediction is invented."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from forex_bot.research.decision_journal import validate_journal_record
from forex_bot.research.learning.protocol import (
    FEATURE_SCHEMA_VERSION,
    JOURNAL_PROTOCOL_VERSION,
    LABEL_PROTOCOL_VERSION,
)

UNAVAILABLE_ARTIFACT = "0" * 64


def research_decision_id(
    dataset_sha256: str,
    instrument: str,
    timeframe: str,
    decision_at: datetime,
    feature_schema_version: str = FEATURE_SCHEMA_VERSION,
) -> str:
    stamp = decision_at.astimezone(timezone.utc).isoformat()
    raw = "|".join([dataset_sha256, instrument, timeframe, stamp, feature_schema_version])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def unavailable_decision(row: dict) -> dict:
    """Build one journal row when no trained model has made a prediction."""
    decision_at = row["decision_at"]
    if decision_at.tzinfo is None:
        raise ValueError("naive_decision_at")
    evaluable = bool(row["outcome_evaluable"])
    payload = {
        "decision_at": decision_at.astimezone(timezone.utc),
        "instrument": row["instrument"],
        "timeframe": row["timeframe"],
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_id": "unavailable",
        "model_version": "unavailable",
        "artifact_sha256": UNAVAILABLE_ARTIFACT,
        "prediction_direction": None,
        "probabilities": None,
        "decision": "abstained",
        "spread": row.get("spread"),
        "market_condition": "unclassified",
        "risk_rejection_reason": "prediction_unavailable",
        "outcome_return": row.get("midpoint_return") if evaluable else None,
        "prediction_error": None,
        "outcome_evaluable": evaluable,
        "adverse_outcome": None,
        "data_provenance": row["dataset_sha256"],
        "model_provenance": "prediction_unavailable",
        "prediction_status": "unavailable",
    }
    record = validate_journal_record(payload)
    decision_id = research_decision_id(
        row["dataset_sha256"],
        row["instrument"],
        row["timeframe"],
        payload["decision_at"],
    )
    return {
        "research_decision_id": decision_id,
        "prediction_status": "prediction_unavailable",
        "feature_valid": bool(row["feature_valid"]),
        "decision": record.decision,
        "prediction_direction": record.prediction_direction,
        "probabilities": None,
        "confidence": None,
        "spread": record.spread,
        "volatility": row.get("volatility"),
        "outcome_evaluable": record.outcome_evaluable,
        "outcome_timestamp": None if row.get("outcome_timestamp") is None else row["outcome_timestamp"].isoformat(),
        "directional_outcome": row.get("directional_outcome") if evaluable else None,
        "hypothetical_cost_adjusted_outcome": None,
        "mistake_class": "insufficient_information" if evaluable else "unevaluable_outcome",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_protocol_version": LABEL_PROTOCOL_VERSION,
        "journal_protocol_version": JOURNAL_PROTOCOL_VERSION,
        "dataset_sha256": row["dataset_sha256"],
    }


def journal_digest(rows: list[dict]) -> str:
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
