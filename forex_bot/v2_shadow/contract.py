"""V2 shadow decision contract. Research-only; never an execution ticket."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PROPOSED_ACTIONS = ("BUY", "SELL", "SKIP")
AVAIL = ("AVAILABLE", "MISSING", "NOT_COMPUTED")
VALIDATION_STATES = (
    "VERIFIED_PRE_RELEASE",
    "PRE_RELEASE_DATE_ONLY",
    "POST_RELEASE",
    "CONFLICTING",
    "UNKNOWN",
)

MODEL_NAME_NONE = "v2_none"
MODEL_VERSION_NONE = "0"
FEATURE_SCHEMA_VERSION = "v2_shadow_input_v1"
REASON_NO_MODEL = "NO_VALIDATED_DIRECTIONAL_MODEL"


def _status_value(value: Any, status: str) -> dict[str, Any]:
    if status not in AVAIL:
        raise ValueError(f"invalid availability status: {status}")
    return {"value": value, "status": status}


@dataclass
class ProvenanceSlot:
    provider: str | None = None
    source: str | None = None
    publication_time_utc: str | None = None
    retrieved_at_utc: str | None = None
    asof_time_utc: str | None = None
    source_identifier: str | None = None
    validation_status: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FundamentalSlots:
    """Optional future-research fields. Unpopulated in this framework stage."""

    macro_event_id: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    macro_event_type: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    official_release_time_utc: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    consensus_value: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    consensus_provider: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    consensus_asof_utc: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    actual_first_print: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    surprise_raw: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    surprise_standardized: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    consensus_revision: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    news_sentiment: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    market_implied_expectation: Any = field(default_factory=lambda: _status_value(None, "NOT_COMPUTED"))
    external_data_provenance: list[dict[str, Any]] = field(default_factory=list)
    external_data_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class V2ShadowDecision:
    decision_id: str
    timestamp_utc: str
    symbol: str
    candidate_source: str
    strategy_label: str
    market_price_reference: float | None
    proposed_action: Literal["BUY", "SELL", "SKIP"]
    direction_probability_up: float | None
    direction_probability_down: float | None
    confidence: float | None
    model_name: str
    model_version: str
    feature_schema_version: str
    reason_codes: list[str]
    data_available: list[str]
    data_missing: list[str]
    data_not_computed: list[str]
    shadow_only: bool = True
    inputs: dict[str, Any] = field(default_factory=dict)
    fundamentals: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    rl: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.proposed_action not in PROPOSED_ACTIONS:
            raise ValueError(f"invalid proposed_action: {self.proposed_action}")
        if not self.shadow_only:
            raise ValueError("V2ShadowDecision.shadow_only must remain true")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShadowOutcome:
    decision_id: str
    scored_at_utc: str
    model_name: str
    model_version: str
    horizons: dict[str, Any]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
