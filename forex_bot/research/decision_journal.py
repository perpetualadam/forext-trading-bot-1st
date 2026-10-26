"""Research-only decision journal schema. It does not collect or store decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

RESEARCH_ONLY = True
DECISIONS = frozenset({"accepted", "abstained", "rejected"})
PREDICTION_STATUSES = frozenset({"recorded", "unavailable"})


class JournalRejected(ValueError):
    """The row is not a usable research journal record."""


@dataclass(frozen=True)
class JournalRecord:
    decision_at: datetime
    instrument: str
    timeframe: str
    feature_schema_version: str
    model_id: str
    model_version: str
    artifact_sha256: str
    prediction_direction: str | None
    probabilities: dict[str, float] | None
    decision: str
    spread: float | None
    market_condition: str
    risk_rejection_reason: str
    outcome_return: float | None
    prediction_error: float | None
    outcome_evaluable: bool
    adverse_outcome: bool | None
    data_provenance: str
    model_provenance: str
    prediction_status: str = "recorded"


def _text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise JournalRejected(f"missing_{name}")
    return value.strip()


def _optional_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise JournalRejected(f"nonfinite_{name}") from exc
    if not math.isfinite(number):
        raise JournalRejected(f"nonfinite_{name}")
    return number


def validate_journal_record(payload: dict[str, Any]) -> JournalRecord:
    """Check one in-memory row. This function writes nothing."""
    if not isinstance(payload, dict):
        raise JournalRejected("malformed_journal_row")
    decision_at = payload.get("decision_at")
    if not isinstance(decision_at, datetime) or decision_at.tzinfo is None:
        raise JournalRejected("missing_decision_at")
    decision = _text(payload, "decision")
    if decision not in DECISIONS:
        raise JournalRejected("unsupported_decision")
    direction = payload.get("prediction_direction")
    if direction not in (None, "BUY", "SELL"):
        raise JournalRejected("invalid_prediction_direction")
    if decision == "accepted" and direction not in ("BUY", "SELL"):
        raise JournalRejected("accepted_without_direction")
    if decision != "accepted" and direction is not None:
        raise JournalRejected("abstention_has_direction")
    prediction_status = payload.get("prediction_status", "recorded")
    if prediction_status not in PREDICTION_STATUSES:
        raise JournalRejected("unsupported_prediction_status")
    if prediction_status == "unavailable" and decision == "accepted":
        raise JournalRejected("unavailable_prediction_accepted")
    evaluable = payload.get("outcome_evaluable")
    if not isinstance(evaluable, bool):
        raise JournalRejected("missing_outcome_evaluable")
    outcome_return = _optional_float(payload.get("outcome_return"), "outcome_return")
    prediction_error = _optional_float(payload.get("prediction_error"), "prediction_error")
    adverse = payload.get("adverse_outcome")
    if evaluable:
        if outcome_return is None:
            raise JournalRejected("evaluable_outcome_incomplete")
        if prediction_status == "recorded":
            if prediction_error is None or not isinstance(adverse, bool):
                raise JournalRejected("evaluable_outcome_incomplete")
        elif prediction_error is not None:
            raise JournalRejected("unavailable_prediction_has_error")
    elif outcome_return is not None or prediction_error is not None or adverse is not None:
        raise JournalRejected("unevaluable_outcome_has_values")
    spread = _optional_float(payload.get("spread"), "spread")
    if spread is not None and spread < 0:
        raise JournalRejected("negative_spread")
    probabilities = payload.get("probabilities")
    if probabilities is not None and not isinstance(probabilities, dict):
        raise JournalRejected("malformed_probabilities")
    if prediction_status == "unavailable" and (direction is not None or probabilities is not None):
        raise JournalRejected("unavailable_prediction_has_values")
    return JournalRecord(
        decision_at=decision_at,
        instrument=_text(payload, "instrument"),
        timeframe=_text(payload, "timeframe"),
        feature_schema_version=_text(payload, "feature_schema_version"),
        model_id=_text(payload, "model_id"),
        model_version=_text(payload, "model_version"),
        artifact_sha256=_text(payload, "artifact_sha256"),
        prediction_direction=direction,
        probabilities=None if probabilities is None else {str(key): float(value) for key, value in probabilities.items()},
        decision=decision,
        spread=spread,
        market_condition=_text(payload, "market_condition"),
        risk_rejection_reason=str(payload.get("risk_rejection_reason") or ""),
        outcome_return=outcome_return,
        prediction_error=prediction_error,
        outcome_evaluable=evaluable,
        adverse_outcome=adverse if evaluable else None,
        data_provenance=_text(payload, "data_provenance"),
        model_provenance=_text(payload, "model_provenance"),
        prediction_status=str(prediction_status),
    )
