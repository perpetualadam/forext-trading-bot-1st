"""Field map and normalization. Forecast and TEForecast stay strictly separate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PROVIDER = "trading_economics"

FORECAST_FIELD = "Forecast"
TE_FORECAST_FIELD = "TEForecast"

# Official schema names → normalized names. Never map TEForecast onto consensus.
FIELD_MAP = {
    "CalendarId": "event_id",
    "CalendarID": "event_id",
    "Date": "scheduled_time_raw",
    "Country": "country",
    "Category": "category",
    "Event": "event",
    "Actual": "actual",
    "Forecast": "forecast_consensus",
    "TEForecast": "te_forecast",
    "Previous": "previous",
    "Revised": "revised",
    "Importance": "importance",
    "LastUpdate": "last_update_raw",
    "Ticker": "ticker",
    "Symbol": "symbol",
    "Source": "source",
    "SourceURL": "source_url",
    "Reference": "reference",
    "ReferenceDate": "reference_date_raw",
    "Unit": "unit",
    "Currency": "currency",
    "URL": "te_url",
    "DateSpan": "date_span",
    "ActualValue": "actual_value",
    "PreviousValue": "previous_value",
    "ForecastValue": "forecast_consensus_value",
    "TEForecastValue": "te_forecast_value",
}


@dataclass(frozen=True)
class NormalizedEvent:
    provider: str
    event_id: str | None
    country: str | None
    category: str | None
    event: str | None
    scheduled_time_raw: str | None
    actual: str | None
    forecast_consensus: str | None
    te_forecast: str | None
    previous: str | None
    revised: str | None
    importance: Any
    last_update_raw: str | None
    ticker: str | None
    symbol: str | None
    source: str | None
    source_url: str | None
    reference: str | None
    reference_date_raw: str | None
    unit: str | None
    currency: str | None
    te_url: str | None
    date_span: str | None
    actual_value: Any
    previous_value: Any
    forecast_consensus_value: Any
    te_forecast_value: Any
    retrieved_at: str | None
    raw_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def raw_get(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    lower = {str(k).lower(): v for k, v in record.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def forecast_consensus_raw(record: dict[str, Any]) -> Any:
    """Survey/economist consensus only. Never TEForecast."""
    return raw_get(record, FORECAST_FIELD, "forecast")


def te_forecast_raw(record: dict[str, Any]) -> Any:
    return raw_get(record, TE_FORECAST_FIELD, "teforecast")


def normalize_record(
    record: dict[str, Any],
    *,
    retrieved_at: str | None = None,
    raw_sha256: str | None = None,
) -> NormalizedEvent:
    """Copy documented fields. Missing Forecast stays missing — no TEForecast fallback."""
    if not isinstance(record, dict):
        raise TypeError("calendar record must be an object")
    return NormalizedEvent(
        provider=PROVIDER,
        event_id=_blank_to_none(raw_get(record, "CalendarId", "CalendarID", "calendarId")),
        country=_blank_to_none(raw_get(record, "Country")),
        category=_blank_to_none(raw_get(record, "Category")),
        event=_blank_to_none(raw_get(record, "Event")),
        scheduled_time_raw=_blank_to_none(raw_get(record, "Date")),
        actual=_blank_to_none(raw_get(record, "Actual")),
        forecast_consensus=_blank_to_none(forecast_consensus_raw(record)),
        te_forecast=_blank_to_none(te_forecast_raw(record)),
        previous=_blank_to_none(raw_get(record, "Previous")),
        revised=_blank_to_none(raw_get(record, "Revised")),
        importance=raw_get(record, "Importance"),
        last_update_raw=_blank_to_none(raw_get(record, "LastUpdate")),
        ticker=_blank_to_none(raw_get(record, "Ticker")),
        symbol=_blank_to_none(raw_get(record, "Symbol")),
        source=_blank_to_none(raw_get(record, "Source")),
        source_url=_blank_to_none(raw_get(record, "SourceURL")),
        reference=_blank_to_none(raw_get(record, "Reference")),
        reference_date_raw=_blank_to_none(raw_get(record, "ReferenceDate")),
        unit=_blank_to_none(raw_get(record, "Unit")),
        currency=_blank_to_none(raw_get(record, "Currency")),
        te_url=_blank_to_none(raw_get(record, "URL")),
        date_span=_blank_to_none(raw_get(record, "DateSpan")),
        actual_value=raw_get(record, "ActualValue"),
        previous_value=raw_get(record, "PreviousValue"),
        forecast_consensus_value=raw_get(record, "ForecastValue"),
        te_forecast_value=raw_get(record, "TEForecastValue"),
        retrieved_at=retrieved_at,
        raw_sha256=raw_sha256,
    )
