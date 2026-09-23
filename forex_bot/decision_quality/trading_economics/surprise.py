"""Surprise helper. Computes only after PIT vintage validation passes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from forex_bot.decision_quality.trading_economics.schema import NormalizedEvent, normalize_record
from forex_bot.decision_quality.trading_economics.validate import PitVerdict, validate_event_vintages


@dataclass(frozen=True)
class SurpriseResult:
    accepted: bool
    surprise_raw: float | None
    reason: str
    actual_first_print: float | None
    consensus_pre_release: float | None
    te_forecast_used: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_numeric(value: Any) -> float | None:
    """Parse a provider number. Does not invent units beyond K/M/B suffixes."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    mult = 1.0
    if text.endswith("%"):
        text = text[:-1].strip()
    last = text[-1:].upper() if text else ""
    if last in {"K", "M", "B"} and len(text) > 1:
        mult = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}[last]
        text = text[:-1].strip()
    try:
        return float(text) * mult
    except ValueError:
        return None


def _consensus_number(row: NormalizedEvent) -> float | None:
    if row.forecast_consensus_value is not None:
        parsed = parse_numeric(row.forecast_consensus_value)
        if parsed is not None:
            return parsed
    return parse_numeric(row.forecast_consensus)


def _actual_number(row: NormalizedEvent) -> float | None:
    if row.actual_value is not None:
        parsed = parse_numeric(row.actual_value)
        if parsed is not None:
            return parsed
    return parse_numeric(row.actual)


def surprise_raw(
    records: list[dict[str, Any] | NormalizedEvent],
    *,
    verdict: PitVerdict | None = None,
) -> SurpriseResult:
    """surprise_raw = actual_first_print - consensus_pre_release.

    Rejects TEForecast, revised actuals, later consensus, and missing values.
    """
    rows = [r if isinstance(r, NormalizedEvent) else normalize_record(r) for r in records]
    pit = verdict or validate_event_vintages(rows)
    if not pit.vintage_ok:
        return SurpriseResult(
            accepted=False,
            surprise_raw=None,
            reason="vintage_validation_failed",
            actual_first_print=None,
            consensus_pre_release=None,
            te_forecast_used=False,
        )
    if not pit.consensus_pre_release_ok or not pit.first_print_actual_ok:
        return SurpriseResult(
            accepted=False,
            surprise_raw=None,
            reason="required_pit_fields_failed",
            actual_first_print=None,
            consensus_pre_release=None,
            te_forecast_used=False,
        )

    consensus_row = None
    for row in rows:
        if row.forecast_consensus is not None:
            consensus_row = row
            break
    if consensus_row is None:
        return SurpriseResult(False, None, "forecast_missing", None, None, False)

    if consensus_row.forecast_consensus is None and consensus_row.te_forecast is not None:
        return SurpriseResult(False, None, "refusing_teforecast_as_consensus", None, None, True)

    consensus = _consensus_number(consensus_row)
    if consensus is None:
        return SurpriseResult(False, None, "consensus_not_numeric", None, None, False)

    # First print = earliest Actual among snapshots that disagree, else first Actual.
    actuals = [(i, _actual_number(row), row.actual) for i, row in enumerate(rows) if row.actual is not None]
    if not actuals:
        return SurpriseResult(False, None, "actual_missing", None, None, False)
    first_actual = actuals[0][1]
    if first_actual is None:
        return SurpriseResult(False, None, "actual_not_numeric", None, None, False)

    return SurpriseResult(
        accepted=True,
        surprise_raw=first_actual - consensus,
        reason="ok",
        actual_first_print=first_actual,
        consensus_pre_release=consensus,
        te_forecast_used=False,
    )
