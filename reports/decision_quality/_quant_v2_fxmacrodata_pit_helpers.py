"""Small FXMacroData provenance helpers. No FX join. No live paid calls."""

from __future__ import annotations

from datetime import datetime, timezone

CONSENSUS_CLASSES = frozenset({"compiled_consensus", "forecaster_survey"})
CLASS_MAP = {
    "compiled_consensus": "COMPILED_CONSENSUS",
    "forecaster_survey": "FORECASTER_SURVEY",
    "model_nowcast": "MODEL_GENERATED",
    "fxmacrodata": "MODEL_GENERATED",
    "central_bank_forecast": "CENTRAL_BANK_FORECAST",
    "central_bank_projection": "CENTRAL_BANK_FORECAST",
    "institutional_projection": "OTHER",
    "market_implied": "OTHER",
    "imf_weo": "OTHER",
}


def epoch_seconds_to_utc(epoch: int | float) -> datetime:
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).replace(tzinfo=None)


def classify_prediction_class(prediction_class: str | None) -> str:
    if not prediction_class:
        return "UNKNOWN"
    return CLASS_MAP.get(prediction_class, "OTHER")


def is_consensus_class(prediction_class: str | None) -> bool:
    return prediction_class in CONSENSUS_CLASSES


def prediction_precedes_release(prediction_asof: datetime, release_ts: datetime) -> bool:
    return prediction_asof < release_ts


def first_print_from_revisions(revisions: list[dict], value_key: str = "val"):
    first = [r for r in revisions if r.get("is_first_release") is True]
    if not first:
        return None
    return first[0].get(value_key)


def latest_value(row: dict):
    return row.get("val")


def revisions_separated(row: dict) -> bool:
    revisions = row.get("revisions") or []
    first = first_print_from_revisions(revisions)
    latest = latest_value(row)
    if first is None or latest is None:
        return False
    return True


def clocks_match(official_utc: str, vendor_epoch: int) -> bool:
    official = datetime.fromisoformat(official_utc)
    return epoch_seconds_to_utc(vendor_epoch) == official
