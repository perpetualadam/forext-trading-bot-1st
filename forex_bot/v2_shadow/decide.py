"""Default V2 policy: SKIP until a validated directional model exists."""

from __future__ import annotations

from forex_bot.v2_shadow.contract import (
    FEATURE_SCHEMA_VERSION,
    MODEL_NAME_NONE,
    MODEL_VERSION_NONE,
    REASON_NO_MODEL,
)


def propose_action() -> str:
    """Only implemented policy. Never copies or inverts the production stub."""
    return "SKIP"


def default_v2_decision() -> dict[str, object]:
    return {
        "proposed_action": propose_action(),
        "direction_probability_up": None,
        "direction_probability_down": None,
        "confidence": None,
        "model_name": MODEL_NAME_NONE,
        "model_version": MODEL_VERSION_NONE,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "reason_codes": [REASON_NO_MODEL],
    }
