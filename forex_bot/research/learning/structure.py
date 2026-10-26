"""Causal swing and trendline observations. Research only; no trading signals."""

from __future__ import annotations

import pandas as pd

PARENT_DEFINITION = "r40.structure.v1"
IMPLEMENTATION_VERSION = "r41.structure.v1"
RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
K = 2
PRICE_SERIES = "bid"
# Float equality for exact contact. It is not a pip or spread tolerance.
EXACT_ABS_TOL = 1e-8
LINE_PAIRING = "consecutive_same_type_swings"
LINE_SAMPLE = "candle_available_at"
RANGE_STATE = "UNCERTAIN"
RANGE_REASON = "BOUNDARY_SELECTION_UNSPECIFIED"
SLOPE_UNIT = "price_per_elapsed_utc_second"

SWING_FIELDS = (
    "swing_id",
    "instrument",
    "timeframe",
    "swing_type",
    "pivot_time",
    "pivot_price",
    "confirmation_time",
    "available_at",
    "source_sha256",
    "definition_version",
    "relation",
    "relation_reason",
    "compared_with",
)
LINE_FIELDS = (
    "line_id",
    "instrument",
    "timeframe",
    "line_type",
    "version",
    "first_pivot_time",
    "first_pivot_price",
    "first_confirmation_time",
    "second_pivot_time",
    "second_pivot_price",
    "second_confirmation_time",
    "available_at",
    "slope_per_second",
    "source_swing_ids",
    "definition_version",
)
EVENT_TYPES = ("TOUCH_EXACT", "TOUCH_REACH", "BREAK", "CLOSE_ON_LINE", "BEYOND_CONTINUATION")


def _utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _relation(swing_type: str, newer: float, prior: float) -> tuple[str, str]:
    if newer > prior:
        return ("HIGHER_HIGH" if swing_type == "HIGH" else "HIGHER_LOW", "compared_with_prior_confirmed_swing")
    if newer < prior:
        return ("LOWER_HIGH" if swing_type == "HIGH" else "LOWER_LOW", "compared_with_prior_confirmed_swing")
    return ("UNCERTAIN", "equal_confirmed_swing_prices")


def _state_from_relations(high_relation: str | None, low_relation: str | None) -> tuple[str, str]:
    if high_relation is None:
        return ("UNCERTAIN", "no_confirmed_high")
    if low_relation is None:
        return ("UNCERTAIN", "no_confirmed_low")
    if high_relation == "UNCERTAIN":
        return ("UNCERTAIN", "high_relation_uncertain")
    if low_relation == "UNCERTAIN":
        return ("UNCERTAIN", "low_relation_uncertain")
    if high_relation == "HIGHER_HIGH" and low_relation == "HIGHER_LOW":
        return ("UPTREND", "higher_high_and_higher_low")
    if high_relation == "LOWER_HIGH" and low_relation == "LOWER_LOW":
        return ("DOWNTREND", "lower_high_and_lower_low")
    return ("TRANSITION", "mixed_confirmed_structure")


def confirmed_swings(
    candles: pd.DataFrame,
    *,
    period: pd.Timedelta,
    instrument: str,
    timeframe: str,
    source_sha256: str,
) -> tuple[list[dict], dict]:
    """Confirm k=2 swings only when four neighbouring candles sit on the period grid."""
    if K != 2:
        raise RuntimeError("swing_width_is_frozen_at_2")
    work = candles.sort_values("time").reset_index(drop=True)
    count = len(work)
    period_ns = int(pd.Timedelta(period).value)
    times = work["time"].map(_utc)
    available = work["available_at"].map(_utc)
    time_ns = times.astype("int64").to_numpy()
    highs = work["bid_high"].to_numpy(dtype=float)
    lows = work["bid_low"].to_numpy(dtype=float)
    swings: list[dict] = []
    gap_windows = 0
    tie_highs = 0
    tie_lows = 0
    for center in range(K, count - K):
        steps = time_ns[center - K + 1 : center + K + 1] - time_ns[center - K : center + K]
        if steps.size != 2 * K or not (steps == period_ns).all():
            gap_windows += 1
            continue
        neighbour_high = [highs[center - 2], highs[center - 1], highs[center + 1], highs[center + 2]]
        neighbour_low = [lows[center - 2], lows[center - 1], lows[center + 1], lows[center + 2]]
        confirmation = available.iloc[center + K]
        pivot = times.iloc[center]
        if highs[center] > max(neighbour_high):
            swings.append(_swing("HIGH", instrument, timeframe, pivot, float(highs[center]), confirmation, source_sha256))
        elif highs[center] == max(neighbour_high):
            tie_highs += 1
        if lows[center] < min(neighbour_low):
            swings.append(_swing("LOW", instrument, timeframe, pivot, float(lows[center]), confirmation, source_sha256))
        elif lows[center] == min(neighbour_low):
            tie_lows += 1
    labelled = assign_relations(swings)
    report = {
        "complete_candles": int(count),
        "edge_windows_not_evaluated": int(min(count, 2 * K)),
        "gap_rejected_windows": int(gap_windows),
        "tied_high_candidates": int(tie_highs),
        "tied_low_candidates": int(tie_lows),
        "confirmed_swing_highs": int(sum(item["swing_type"] == "HIGH" for item in labelled)),
        "confirmed_swing_lows": int(sum(item["swing_type"] == "LOW" for item in labelled)),
    }
    return labelled, report


def _swing(swing_type, instrument, timeframe, pivot, price, confirmation, source_sha256) -> dict:
    pivot = _utc(pivot)
    confirmation = _utc(confirmation)
    return {
        "swing_id": f"{swing_type}|{instrument}|{timeframe}|{pivot.isoformat()}",
        "instrument": instrument,
        "timeframe": timeframe,
        "swing_type": swing_type,
        "pivot_time": pivot,
        "pivot_price": price,
        "confirmation_time": confirmation,
        "available_at": confirmation,
        "source_sha256": source_sha256,
        "definition_version": IMPLEMENTATION_VERSION,
        "relation": "UNCERTAIN",
        "relation_reason": "unlabelled",
        "compared_with": None,
    }


def assign_relations(swings: list[dict]) -> list[dict]:
    """Label a swing only against the previous swing of the same type."""
    ordered = sorted(swings, key=lambda item: (item["available_at"], item["pivot_time"], item["swing_type"]))
    latest: dict[str, dict] = {}
    labelled = []
    for swing in ordered:
        previous = latest.get(swing["swing_type"])
        row = dict(swing)
        if previous is None:
            row["relation"] = "UNCERTAIN"
            row["relation_reason"] = "insufficient_prior_confirmed_swing"
            row["compared_with"] = None
        else:
            relation, reason = _relation(swing["swing_type"], swing["pivot_price"], previous["pivot_price"])
            row["relation"] = relation
            row["relation_reason"] = reason
            row["compared_with"] = previous["swing_id"]
        labelled.append(row)
        latest[swing["swing_type"]] = row
    return labelled


def trend_states(candles: pd.DataFrame, swings: list[dict]) -> list[dict]:
    """Assign a state at each completed candle from swings already available."""
    ordered = sorted(swings, key=lambda item: item["available_at"])
    work = candles.sort_values("available_at").reset_index(drop=True)
    cursor = 0
    high_relation = None
    low_relation = None
    rows = []
    previous = None
    for _, candle in work.iterrows():
        when = _utc(candle["available_at"])
        supporting = []
        while cursor < len(ordered) and ordered[cursor]["available_at"] <= when:
            swing = ordered[cursor]
            supporting.append(swing["swing_id"])
            if swing["swing_type"] == "HIGH":
                high_relation = swing["relation"]
            else:
                low_relation = swing["relation"]
            cursor += 1
        state, reason = _state_from_relations(high_relation, low_relation)
        changed = previous is not None and state != previous
        rows.append(
            {
                "time": _utc(candle["time"]),
                "available_at": when,
                "state": state,
                "reason": reason,
                "changed": changed,
                "supporting_swing_ids": supporting if changed or previous is None else [],
                "definition_version": IMPLEMENTATION_VERSION,
            }
        )
        previous = state
    return rows


def build_trendlines(swings: list[dict]) -> list[dict]:
    """Pair each swing with the immediately previous swing of the same type."""
    ordered = sorted(swings, key=lambda item: (item["available_at"], item["pivot_time"], item["swing_type"]))
    previous: dict[str, dict] = {}
    versions = {"HIGH": 0, "LOW": 0}
    lines = []
    for swing in ordered:
        prior = previous.get(swing["swing_type"])
        previous[swing["swing_type"]] = swing
        if prior is None:
            continue
        elapsed = (swing["pivot_time"] - prior["pivot_time"]).total_seconds()
        if elapsed <= 0:
            continue
        versions[swing["swing_type"]] += 1
        kind = "RESISTANCE" if swing["swing_type"] == "HIGH" else "SUPPORT"
        lines.append(
            {
                "line_id": f"{kind}|{swing['instrument']}|{swing['timeframe']}|{prior['pivot_time'].isoformat()}|{swing['pivot_time'].isoformat()}",
                "instrument": swing["instrument"],
                "timeframe": swing["timeframe"],
                "line_type": kind,
                "version": versions[swing["swing_type"]],
                "first_pivot_time": prior["pivot_time"],
                "first_pivot_price": prior["pivot_price"],
                "first_confirmation_time": prior["confirmation_time"],
                "second_pivot_time": swing["pivot_time"],
                "second_pivot_price": swing["pivot_price"],
                "second_confirmation_time": swing["confirmation_time"],
                "available_at": swing["available_at"],
                "slope_per_second": (swing["pivot_price"] - prior["pivot_price"]) / elapsed,
                "source_swing_ids": [prior["swing_id"], swing["swing_id"]],
                "definition_version": IMPLEMENTATION_VERSION,
            }
        )
    return lines


def line_price(line: dict, when) -> float:
    seconds = (_utc(when) - line["first_pivot_time"]).total_seconds()
    return float(line["first_pivot_price"] + line["slope_per_second"] * seconds)


def trendline_events(candles: pd.DataFrame, lines: list[dict]) -> dict:
    """Count causal touches and breaks. A wick alone is not a break."""
    totals = {name: 0 for name in EVENT_TYPES}
    examples = {name: None for name in EVENT_TYPES}
    if candles.empty or not lines:
        return {"counts": totals, "examples": examples}
    work = candles.sort_values("available_at").reset_index(drop=True)
    when_ns = work["available_at"].map(_utc).astype("int64").to_numpy()
    high = work["bid_high"].to_numpy(dtype=float)
    low = work["bid_low"].to_numpy(dtype=float)
    close = work["bid_close"].to_numpy(dtype=float)
    opens = work["time"].map(_utc)
    available = work["available_at"].map(_utc)
    for line in lines:
        start = int(when_ns.searchsorted(int(line["available_at"].value), side="right"))
        if start >= len(work):
            continue
        sample_ns = when_ns[start:]
        first_ns = int(line["first_pivot_time"].value)
        projected = line["first_pivot_price"] + line["slope_per_second"] * ((sample_ns - first_ns) / 1_000_000_000.0)
        window_close = close[start:]
        window_low = low[start:]
        window_high = high[start:]
        if line["line_type"] == "SUPPORT":
            on_line = abs(window_close - projected) <= EXACT_ABS_TOL
            beyond = window_close < projected - EXACT_ABS_TOL
            reach = (~beyond) & (~on_line) & (window_low <= projected + EXACT_ABS_TOL) & (window_close > projected)
            exact = reach & (abs(window_low - projected) <= EXACT_ABS_TOL)
        else:
            on_line = abs(window_close - projected) <= EXACT_ABS_TOL
            beyond = window_close > projected + EXACT_ABS_TOL
            reach = (~beyond) & (~on_line) & (window_high >= projected - EXACT_ABS_TOL) & (window_close < projected)
            exact = reach & (abs(window_high - projected) <= EXACT_ABS_TOL)
        started = beyond.copy()
        started[1:] = beyond[1:] & ~beyond[:-1]
        continuation = beyond & ~started
        _accumulate(totals, examples, "BREAK", started, line, projected, opens, available, high, low, close, start)
        _accumulate(totals, examples, "BEYOND_CONTINUATION", continuation, line, projected, opens, available, high, low, close, start)
        _accumulate(totals, examples, "TOUCH_REACH", reach, line, projected, opens, available, high, low, close, start)
        _accumulate(totals, examples, "TOUCH_EXACT", exact, line, projected, opens, available, high, low, close, start)
        _accumulate(totals, examples, "CLOSE_ON_LINE", on_line, line, projected, opens, available, high, low, close, start)
    return {"counts": totals, "examples": examples}


def _accumulate(totals, examples, name, mask, line, projected, opens, available, high, low, close, start) -> None:
    hits = int(mask.sum())
    totals[name] += hits
    if hits and examples[name] is None:
        position = int(mask.argmax())
        index = start + position
        examples[name] = {
            "event_type": name,
            "event_time": opens.iloc[index],
            "available_at": available.iloc[index],
            "line_id": line["line_id"],
            "line_version": line["version"],
            "line_price": float(projected[position]),
            "bid_high": float(high[index]),
            "bid_low": float(low[index]),
            "bid_close": float(close[index]),
            "definition_version": IMPLEMENTATION_VERSION,
        }


def support_resistance(swings: list[dict]) -> list[dict]:
    """Each confirmed swing is a level from its confirmation time onward."""
    levels = []
    for swing in swings:
        kind = "RESISTANCE" if swing["swing_type"] == "HIGH" else "SUPPORT"
        levels.append(
            {
                "level_id": f"{kind}|{swing['swing_id']}",
                "source_swing_id": swing["swing_id"],
                "kind": kind,
                "price": swing["pivot_price"],
                "available_at": swing["available_at"],
                "pivot_time": swing["pivot_time"],
                "invalidation_time": None,
                "invalidation_reason": "level_retirement_not_defined_in_r40",
                "definition_version": IMPLEMENTATION_VERSION,
            }
        )
    return levels


def level_interactions(candles: pd.DataFrame, levels: list[dict]) -> dict:
    """Count later closes and reaches. Levels stay in the record."""
    counts = {"REACH": 0, "CLOSE_BEYOND": 0, "CLOSE_ON_LEVEL": 0, "BEYOND_CONTINUATION": 0}
    examples = {name: None for name in counts}
    if candles.empty or not levels:
        return {"counts": counts, "examples": examples}
    work = candles.sort_values("available_at").reset_index(drop=True)
    when = work["available_at"].map(_utc)
    when_ns = when.astype("int64").to_numpy()
    high = work["bid_high"].to_numpy(dtype=float)
    low = work["bid_low"].to_numpy(dtype=float)
    close = work["bid_close"].to_numpy(dtype=float)
    for level in levels:
        start = int(when_ns.searchsorted(int(level["available_at"].value), side="right"))
        if start >= len(work):
            continue
        price = float(level["price"])
        window_close = close[start:]
        if level["kind"] == "SUPPORT":
            on_level = abs(window_close - price) <= EXACT_ABS_TOL
            beyond = window_close < price - EXACT_ABS_TOL
            reach = (~beyond) & (~on_level) & (low[start:] <= price + EXACT_ABS_TOL) & (window_close > price)
        else:
            on_level = abs(window_close - price) <= EXACT_ABS_TOL
            beyond = window_close > price + EXACT_ABS_TOL
            reach = (~beyond) & (~on_level) & (high[start:] >= price - EXACT_ABS_TOL) & (window_close < price)
        started = beyond.copy()
        started[1:] = beyond[1:] & ~beyond[:-1]
        _count_level(counts, examples, "CLOSE_BEYOND", started, level, when, work, close, start)
        _count_level(counts, examples, "BEYOND_CONTINUATION", beyond & ~started, level, when, work, close, start)
        _count_level(counts, examples, "REACH", reach, level, when, work, close, start)
        _count_level(counts, examples, "CLOSE_ON_LEVEL", on_level, level, when, work, close, start)
    return {"counts": counts, "examples": examples}


def _count_level(counts, examples, name, mask, level, when, work, close, start) -> None:
    hits = int(mask.sum())
    counts[name] += hits
    if hits and examples[name] is None:
        position = int(mask.argmax())
        index = start + position
        examples[name] = {
            "event_type": name,
            "level_id": level["level_id"],
            "available_at": when.iloc[index],
            "candle_time": _utc(work["time"].iloc[index]),
            "level_price": level["price"],
            "bid_close": float(close[index]),
            "definition_version": IMPLEMENTATION_VERSION,
        }


def range_decision() -> dict:
    """R.40 requires two sides and two reactions, but not which levels pair."""
    return {
        "range_state": RANGE_STATE,
        "confirmed_ranges": 0,
        "reason": RANGE_REASON,
        "available_ranges": [],
        "reaction_rule_status": "described_for_individual_levels_only",
        "definition_version": IMPLEMENTATION_VERSION,
    }


def asof_view(swings: list[dict], lines: list[dict], states: list[dict], decision_time) -> dict:
    """Return structure whose availability time is at or before the decision."""
    when = _utc(decision_time)
    known_states = [row for row in states if row["available_at"] <= when]
    state = known_states[-1] if known_states else None
    return {
        "decision_time": when,
        "swings": [swing for swing in swings if swing["available_at"] <= when],
        "lines": [line for line in lines if line["available_at"] <= when],
        "state": None if state is None else state["state"],
        "state_reason": None if state is None else state["reason"],
        "trading_signal": None,
    }


def observation_row(instrument: str, timeframe: str, state_row: dict, source_sha256: str, protocol_sha256: str) -> dict:
    """A structure observation. It is not a trading-journal decision."""
    return {
        "record_type": "market_structure_observation",
        "instrument": instrument,
        "timeframe": timeframe,
        "candle_time": state_row["time"],
        "available_at": state_row["available_at"],
        "structural_state": state_row["state"],
        "uncertainty_reason": state_row["reason"],
        "supporting_swing_ids": list(state_row["supporting_swing_ids"]),
        "source_sha256": source_sha256,
        "definition_version": IMPLEMENTATION_VERSION,
        "parent_definition": PARENT_DEFINITION,
        "protocol_sha256": protocol_sha256,
        "trading_decision": None,
        "outcome": None,
        "confidence": None,
    }


def known_before(records: list[dict], when, key: str = "available_at") -> list[dict]:
    limit = _utc(when)
    return [row for row in records if row[key] <= limit]
