"""Normalized first-print event schema. Missing stays missing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class NormalizedEvent:
    provider: str
    source_agency: str
    event_id: str
    event_type: str
    release_name: str | None
    reference_period: str | None
    scheduled_time_local: str | None
    timezone: str | None
    scheduled_time_utc: str | None
    published_date: str | None
    release_number: str | None
    source_url: str | None
    retrieved_at: str | None
    raw_file: str | None
    raw_sha256: str | None
    validation_status: str
    extraction_locator: str | None
    # CPI
    headline_mom_first_print: float | None = None
    headline_yoy_first_print: float | None = None
    core_mom_first_print: float | None = None
    core_yoy_first_print: float | None = None
    previous_headline_mom_as_known: float | None = None
    previous_headline_yoy_as_known: float | None = None
    # Employment
    nfp_first_print: int | None = None
    unemployment_rate_first_print: float | None = None
    ahe_mom_first_print: float | None = None
    ahe_yoy_first_print: float | None = None
    participation_rate_first_print: float | None = None
    previous_nfp_as_presented: int | None = None
    previous_nfp_revision: int | None = None
    two_month_nfp_revision: int | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CSV_COLUMNS = [f.name for f in fields(NormalizedEvent)]
