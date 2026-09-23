"""Cross-provider comparison interface. No Econoday parser — no sample schema in repo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from forex_bot.decision_quality.trading_economics.schema import NormalizedEvent


@dataclass(frozen=True)
class ComparisonKey:
    """Identity used to match the same official release across providers later."""

    country: str | None
    category_family: str | None
    reference_period: str | None
    scheduled_utc: str | None


@dataclass(frozen=True)
class ProviderPrint:
    provider: str
    event_id: str | None
    forecast_consensus: str | None
    actual_first_print: str | None
    vintage_ok: bool


@dataclass(frozen=True)
class CrossProviderRow:
    key: ComparisonKey
    trading_economics: ProviderPrint | None
    econoday: ProviderPrint | None
    consensus_match: str  # MATCH | MISMATCH | MISSING_ECONODAY | MISSING_TE | NOT_COMPARED
    actual_match: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": asdict(self.key),
            "trading_economics": asdict(self.trading_economics) if self.trading_economics else None,
            "econoday": asdict(self.econoday) if self.econoday else None,
            "consensus_match": self.consensus_match,
            "actual_match": self.actual_match,
        }


def comparison_key_from_te(event: NormalizedEvent, scheduled_utc: str | None, family: str | None) -> ComparisonKey:
    return ComparisonKey(
        country=event.country,
        category_family=family or event.category,
        reference_period=event.reference,
        scheduled_utc=scheduled_utc,
    )


def empty_econoday_slot(key: ComparisonKey, te: ProviderPrint) -> CrossProviderRow:
    """Reserve a comparison row. Econoday values stay empty until a real sample exists."""
    return CrossProviderRow(
        key=key,
        trading_economics=te,
        econoday=None,
        consensus_match="MISSING_ECONODAY",
        actual_match="MISSING_ECONODAY",
    )
