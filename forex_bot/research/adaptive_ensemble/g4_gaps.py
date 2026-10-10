"""Classify Stage G.3 M5 gaps from local raw and normalised files."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.g4_integrity import G3

PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
BAR = timedelta(minutes=5)
MAX_SOURCE_OMISSION = timedelta(minutes=60)
EXPECTED_MARKET_CLOSURE = "EXPECTED_MARKET_CLOSURE"
SOURCE_NO_CANDLE_RETURNED = "SOURCE_NO_CANDLE_RETURNED"
ACQUISITION_OR_PAGINATION_DEFECT = "ACQUISITION_OR_PAGINATION_DEFECT"
NORMALISATION_DEFECT = "NORMALISATION_DEFECT"
PROVIDER_DATA_ANOMALY = "PROVIDER_DATA_ANOMALY"
UNRESOLVED = "UNRESOLVED"
BLOCKING = {
    ACQUISITION_OR_PAGINATION_DEFECT,
    NORMALISATION_DEFECT,
    PROVIDER_DATA_ANOMALY,
    UNRESOLVED,
}


def _utc(value: datetime | pd.Timestamp | str) -> datetime:
    if isinstance(value, str):
        ts = pd.Timestamp(value)
    else:
        ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    out = ts.to_pydatetime()
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    else:
        out = out.astimezone(timezone.utc)
    return out.replace(microsecond=0)


def load_windows() -> list[tuple[datetime, datetime]]:
    plan = json.loads((G3 / "request_plan.json").read_text(encoding="utf-8"))
    return [(_utc(a), _utc(b)) for a, b in plan["windows"]]


def _covered(prev: datetime, nxt: datetime, windows: list[tuple[datetime, datetime]]) -> bool:
    cursor = prev + BAR
    while cursor < nxt:
        if not any(start <= cursor < stop for start, stop in windows):
            return False
        cursor += BAR
    return True


def _page_boundary_inside(prev: datetime, nxt: datetime, windows: list[tuple[datetime, datetime]]) -> bool:
    bounds = [start for start, _stop in windows[1:]]
    return any(prev < bound < nxt for bound in bounds)


def is_expected_weekend(prev: datetime, nxt: datetime) -> bool:
    span_h = (nxt - prev).total_seconds() / 3600.0
    return prev.weekday() == 4 and nxt.weekday() == 6 and 36.0 <= span_h <= 72.0


def classify_one(
    *,
    prev: datetime,
    nxt: datetime,
    raw_contains_interior: bool,
    norm_contains_interior: bool,
    windows: list[tuple[datetime, datetime]],
    adjacent_complete: bool,
) -> str:
    if raw_contains_interior != norm_contains_interior:
        return NORMALISATION_DEFECT
    if is_expected_weekend(prev, nxt):
        return EXPECTED_MARKET_CLOSURE
    if not _covered(prev, nxt, windows):
        return ACQUISITION_OR_PAGINATION_DEFECT
    if not adjacent_complete:
        return PROVIDER_DATA_ANOMALY
    if (nxt - prev) <= MAX_SOURCE_OMISSION + BAR:
        return SOURCE_NO_CANDLE_RETURNED
    return UNRESOLVED


def _session_context(prev: datetime, nxt: datetime, classification: str) -> str:
    if classification == EXPECTED_MARKET_CLOSURE:
        return "fx_weekend_close_friday_to_sunday"
    if prev.date().isoformat() == "2026-09-07" or nxt.date().isoformat() == "2026-09-07":
        return "us_labor_day_fx_still_open"
    if nxt.weekday() == 6 and 21 <= nxt.hour <= 22:
        return "sunday_reopen_thin_print"
    if prev.hour == 21 or nxt.hour == 21:
        return "near_new_york_1700_rollover"
    return "intraday"


def _raw_rows(pair: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((G3 / "raw" / pair).glob("page_*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        for candle in body.get("candles") or []:
            rows.append(
                {
                    "time": _utc(str(candle["time"])),
                    "complete": bool(candle.get("complete")),
                    "volume": int(candle.get("volume") or 0),
                    "page": path.name,
                }
            )
    rows.sort(key=lambda item: item["time"])
    return rows


def _norm_times(pair: str) -> list[datetime]:
    frame = pd.read_csv(G3 / "normalized" / f"{pair}_M5.csv")
    return [_utc(value) for value in pd.to_datetime(frame["time"], utc=True)]


def _interior(prev: datetime, nxt: datetime, present: set[datetime]) -> bool:
    cursor = prev + BAR
    while cursor < nxt:
        if cursor in present:
            return True
        cursor += BAR
    return False


def missing_opens(prev: datetime, nxt: datetime) -> list[datetime]:
    out: list[datetime] = []
    cursor = prev + BAR
    while cursor < nxt:
        out.append(cursor)
        cursor += BAR
    return out


def build_gap_inventory() -> dict[str, Any]:
    windows = load_windows()
    per_pair: dict[str, list[dict[str, Any]]] = {}
    opens_by_pair: dict[str, set[datetime]] = {}
    summaries: list[dict[str, Any]] = []
    for pair in PAIRS:
        raw = _raw_rows(pair)
        norm = _norm_times(pair)
        raw_set = {row["time"] for row in raw}
        raw_by_time = {row["time"]: row for row in raw}
        norm_set = set(norm)
        zero_volume = sum(1 for row in raw if row["volume"] <= 0)
        gaps: list[dict[str, Any]] = []
        pair_opens: set[datetime] = set()
        for idx in range(1, len(norm)):
            prev, nxt = norm[idx - 1], norm[idx]
            if nxt - prev <= BAR:
                continue
            raw_hit = _interior(prev, nxt, raw_set)
            norm_hit = _interior(prev, nxt, norm_set)
            left = raw_by_time.get(prev)
            right = raw_by_time.get(nxt)
            adjacent = bool(left and right and left["complete"] and right["complete"])
            kind = classify_one(
                prev=prev,
                nxt=nxt,
                raw_contains_interior=raw_hit,
                norm_contains_interior=norm_hit,
                windows=windows,
                adjacent_complete=adjacent,
            )
            opens = missing_opens(prev, nxt)
            if kind != EXPECTED_MARKET_CLOSURE:
                pair_opens.update(opens)
            gaps.append(
                {
                    "instrument": pair,
                    "previous": prev.isoformat(),
                    "next": nxt.isoformat(),
                    "missing_m5": len(opens),
                    "duration_minutes": (nxt - prev).total_seconds() / 60.0,
                    "previous_weekday": prev.strftime("%A"),
                    "next_weekday": nxt.strftime("%A"),
                    "previous_hour_utc": prev.hour,
                    "next_hour_utc": nxt.hour,
                    "adjacent_complete": adjacent,
                    "adjacent_volume": [None if left is None else left["volume"], None if right is None else right["volume"]],
                    "present_in_raw_interior": raw_hit,
                    "introduced_by_normalisation": raw_set != norm_set or raw_hit != norm_hit,
                    "page_boundary_inside": _page_boundary_inside(prev, nxt, windows),
                    "request_window_covers_gap": _covered(prev, nxt, windows),
                    "classification": kind,
                    "unresolved": kind in BLOCKING,
                    "session_context": _session_context(prev, nxt, kind),
                }
            )
        opens_by_pair[pair] = pair_opens
        per_pair[pair] = gaps
        counts: dict[str, int] = {}
        for gap in gaps:
            counts[gap["classification"]] = counts.get(gap["classification"], 0) + 1
        summaries.append(
            {
                "instrument": pair,
                "raw_rows": len(raw_set),
                "normalised_rows": len(norm_set),
                "raw_equals_normalised": raw_set == norm_set,
                "zero_volume_candles": zero_volume,
                "gap_counts": counts,
                "unresolved": sum(1 for gap in gaps if gap["unresolved"]),
            }
        )
    for pair, gaps in per_pair.items():
        for gap in gaps:
            if gap["classification"] == EXPECTED_MARKET_CLOSURE:
                gap["other_pairs_with_same_omission"] = []
                continue
            open_set = set(missing_opens(_utc(gap["previous"]), _utc(gap["next"])))
            shared = [other for other, have in opens_by_pair.items() if other != pair and open_set & have]
            gap["other_pairs_with_same_omission"] = shared
    unresolved = [
        {"instrument": gap["instrument"], "previous": gap["previous"], "next": gap["next"], "classification": gap["classification"]}
        for gaps in per_pair.values()
        for gap in gaps
        if gap["unresolved"]
    ]
    chf = [gap for gap in per_pair["USD_CHF"] if gap["classification"] != EXPECTED_MARKET_CLOSURE]
    hours: dict[str, int] = {}
    for gap in chf:
        key = f"{gap['previous_hour_utc']:02d}"
        hours[key] = hours.get(key, 0) + 1
    chf_summary = next(item for item in summaries if item["instrument"] == "USD_CHF")
    chf_classes = sorted({str(gap["classification"]) for gap in chf})
    return {
        "source": "local_stage_g3_files",
        "broker_requests": 0,
        "max_source_omission_minutes": MAX_SOURCE_OMISSION.total_seconds() / 60.0,
        "source_semantics": (
            "Returned candles include a positive volume field and no zero-volume placeholders. "
            "Intervals absent from the raw payload were inside the requested windows. "
            "That matches candle responses that omit an interval when it contains no prices."
        ),
        "pairs": summaries,
        "gaps": [gap for gaps in per_pair.values() for gap in gaps],
        "unresolved": unresolved,
        "redownload_recommended": bool(unresolved),
        "proposed_requests": [],
        "usd_chf": {
            "unexpected_in_stage_g3_quality": 17,
            "non_weekend_gaps": len(chf),
            "classifications": chf_classes,
            "hour_histogram_utc": hours,
            "page_boundary_hits": sum(1 for gap in chf if gap["page_boundary_inside"]),
            "raw_normalised_mismatch": not bool(chf_summary["raw_equals_normalised"]),
            "gaps": chf,
            "conversion_note": (
                "Missing intervals are not themselves quotes. Neighbouring quotes remain usable. "
                "No fill may be invented inside the hole."
            ),
        },
    }
