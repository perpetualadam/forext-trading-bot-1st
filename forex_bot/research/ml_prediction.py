"""Research-only prediction contract. Production voting does not import this module."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RESEARCH_ONLY = True
STATUSES = frozenset({"approved", "abstain", "unavailable"})
VALIDATION_STATUSES = frozenset({"unvalidated", "validated_offline", "rejected"})
SIDES = frozenset({"BUY", "SELL"})


class PredictionRejected(ValueError):
    """The payload cannot be treated as a model prediction."""


@dataclass(frozen=True)
class PredictionRecord:
    model_id: str
    model_version: str
    artifact_sha256: str
    feature_schema_version: str
    instrument: str
    timeframe: str
    predicted_at: datetime
    direction: str | None
    probabilities: dict[str, float] | None
    confidence: float | None
    status: str
    validation_status: str
    reason: str


def _text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise PredictionRejected(f"missing_{name}")
    return value.strip()


def _stamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise PredictionRejected("missing_predicted_at")
    if stamp.tzinfo is None:
        raise PredictionRejected("naive_predicted_at")
    return stamp.astimezone(timezone.utc)


def _probability_map(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise PredictionRejected("malformed_probabilities")
    parsed: dict[str, float] = {}
    for key, item in value.items():
        side = str(key).strip().upper()
        if side not in SIDES:
            raise PredictionRejected("unknown_probability_class")
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise PredictionRejected("nonfinite_probability") from exc
        if not math.isfinite(number) or number < 0.0:
            raise PredictionRejected("nonfinite_probability")
        parsed[side] = number
    if abs(sum(parsed.values()) - 1.0) > 1e-6:
        raise PredictionRejected("probabilities_do_not_sum_to_one")
    return parsed


def validate_prediction(
    payload: dict[str, Any],
    *,
    evaluated_at: datetime,
    max_age_seconds: int = 3600,
) -> PredictionRecord:
    """Accept one explicit prediction. This function does not create one."""
    if not isinstance(payload, dict):
        raise PredictionRejected("malformed_prediction")
    if evaluated_at.tzinfo is None:
        raise PredictionRejected("naive_evaluated_at")
    status = _text(payload, "status")
    validation_status = _text(payload, "validation_status")
    if status not in STATUSES:
        raise PredictionRejected("unsupported_status")
    if validation_status not in VALIDATION_STATUSES:
        raise PredictionRejected("unsupported_validation_status")
    artifact = _text(payload, "artifact_sha256").lower()
    if len(artifact) != 64 or any(character not in "0123456789abcdef" for character in artifact):
        raise PredictionRejected("invalid_artifact_hash")
    predicted_at = _stamp(payload.get("predicted_at"))
    age = (evaluated_at.astimezone(timezone.utc) - predicted_at).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise PredictionRejected("stale_or_future_prediction")
    raw_direction = payload.get("direction")
    direction = None if raw_direction in (None, "") else str(raw_direction).strip().upper()
    if direction not in (None, "BUY", "SELL"):
        raise PredictionRejected("invalid_direction")
    probabilities = _probability_map(payload.get("probabilities"))
    raw_confidence = payload.get("confidence")
    confidence: float | None
    if raw_confidence is None:
        confidence = None
    else:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError) as exc:
            raise PredictionRejected("nonfinite_confidence") from exc
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise PredictionRejected("nonfinite_confidence")
    if status == "approved":
        if validation_status != "validated_offline":
            raise PredictionRejected("unvalidated_approval")
        if direction not in SIDES or confidence is None:
            raise PredictionRejected("approval_without_direction")
        if probabilities is not None:
            winner = max(probabilities, key=probabilities.get)
            if winner != direction or list(probabilities.values()).count(probabilities[winner]) != 1:
                raise PredictionRejected("probability_direction_mismatch")
    elif direction is not None:
        raise PredictionRejected("abstention_has_direction")
    return PredictionRecord(
        model_id=_text(payload, "model_id"),
        model_version=_text(payload, "model_version"),
        artifact_sha256=artifact,
        feature_schema_version=_text(payload, "feature_schema_version"),
        instrument=_text(payload, "instrument"),
        timeframe=_text(payload, "timeframe"),
        predicted_at=predicted_at,
        direction=direction,
        probabilities=probabilities,
        confidence=confidence,
        status=status,
        validation_status=validation_status,
        reason=str(payload.get("reason") or ""),
    )
