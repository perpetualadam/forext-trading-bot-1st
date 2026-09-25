"""Research-only V2 directional shadow. Zero execution authority."""

from forex_bot.v2_shadow.contract import (
    FEATURE_SCHEMA_VERSION,
    MODEL_NAME_NONE,
    MODEL_VERSION_NONE,
    PROPOSED_ACTIONS,
    ShadowOutcome,
    V2ShadowDecision,
)
from forex_bot.v2_shadow.decide import default_v2_decision, propose_action
from forex_bot.v2_shadow.market import maybe_record_completed_m5
from forex_bot.v2_shadow.observe import maybe_observe_candidate, v2_shadow_enabled
from forex_bot.v2_shadow.score import score_shadow_decision

__all__ = (
    "FEATURE_SCHEMA_VERSION",
    "MODEL_NAME_NONE",
    "MODEL_VERSION_NONE",
    "PROPOSED_ACTIONS",
    "ShadowOutcome",
    "V2ShadowDecision",
    "default_v2_decision",
    "maybe_observe_candidate",
    "maybe_record_completed_m5",
    "propose_action",
    "score_shadow_decision",
    "v2_shadow_enabled",
)
