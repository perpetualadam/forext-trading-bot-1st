"""R.42 level, trendline, and range lifecycle. Research only; no trading signals."""

from __future__ import annotations

import pandas as pd

from forex_bot.research.learning.structure import EXACT_ABS_TOL, _utc, line_price

PARENT_DEFINITION = "r41.structure.v1"
IMPLEMENTATION_VERSION = "r42.structure.v1"
RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
RANGE_STATES = ("UNCERTAIN", "CANDIDATE", "CONFIRMED", "INVALIDATED")
LEVEL_STATES = ("ACTIVE", "INVALIDATED", "SUPERSEDED", "UNCERTAIN")
LINE_STATES = ("ACTIVE", "BROKEN", "SUPERSEDED", "UNCERTAIN")


def _beyond_level(kind: str, close: float, price: float) -> bool:
    if kind == "SUPPORT":
        return close < price - EXACT_ABS_TOL
    return close > price + EXACT_ABS_TOL


def _reach_level(kind: str, high: float, low: float, close: float, price: float) -> bool:
    if abs(close - price) <= EXACT_ABS_TOL:
        return False
    if kind == "SUPPORT":
        return low <= price + EXACT_ABS_TOL and close > price
    return high >= price - EXACT_ABS_TOL and close < price


def _beyond_line(kind: str, close: float, projected: float) -> bool:
    if kind == "SUPPORT":
        return close < projected - EXACT_ABS_TOL
    return close > projected + EXACT_ABS_TOL


def _reach_line(kind: str, high: float, low: float, close: float, projected: float) -> bool:
    if abs(close - projected) <= EXACT_ABS_TOL:
        return False
    if kind == "SUPPORT":
        return low <= projected + EXACT_ABS_TOL and close > projected
    return high >= projected - EXACT_ABS_TOL and close < projected


def _transition(obj: dict, status: str, when: pd.Timestamp, reason: str, related_id: str | None) -> None:
    obj["status"] = status
    obj["transitions"].append(
        {
            "status": status,
            "available_at": when,
            "reason": reason,
            "related_id": related_id,
            "definition_version": IMPLEMENTATION_VERSION,
        }
    )


def _event(kind: str, when: pd.Timestamp, related_id: str, detail: dict | None = None) -> dict:
    row = {
        "event_type": kind,
        "available_at": when,
        "related_id": related_id,
        "definition_version": IMPLEMENTATION_VERSION,
    }
    if detail:
        row.update(detail)
    return row


def apply_lifecycle(
    candles: pd.DataFrame,
    swings: list[dict],
    lines: list[dict],
    *,
    instrument: str,
    timeframe: str,
    pip_size: float,
) -> dict:
    """Walk completed candles once. Only the active level and active line are evaluated."""
    work = candles.sort_values("available_at").reset_index(drop=True)
    avail = [_utc(value) for value in work["available_at"]]
    opens = [_utc(value) for value in work["time"]]
    high = work["bid_high"].to_numpy(dtype=float)
    low = work["bid_low"].to_numpy(dtype=float)
    close = work["bid_close"].to_numpy(dtype=float)
    swing_queue = sorted(swings, key=lambda item: (item["available_at"], item["pivot_time"], item["swing_type"]))
    line_queue = sorted(lines, key=lambda item: (item["available_at"], item["line_type"], item["line_id"]))
    swing_at = 0
    line_at = 0
    levels: list[dict] = []
    live_lines: list[dict] = []
    ranges: list[dict] = []
    events: list[dict] = []
    states: list[dict] = []
    active = {"SUPPORT": None, "RESISTANCE": None}
    active_line = {"SUPPORT": None, "RESISTANCE": None}
    episode_open = {"SUPPORT": False, "RESISTANCE": False}
    line_episode_open = {"SUPPORT": False, "RESISTANCE": False}
    current = None
    contradictory = 0
    crossed_key = None
    counts = {name: 0 for name in (
        "levels_created",
        "level_invalidations",
        "level_supersessions",
        "trendlines_created",
        "trendline_breaks",
        "trendline_supersessions",
        "line_touch_episodes",
        "support_touch_episodes",
        "resistance_touch_episodes",
        "range_pairs",
        "range_reaction_episodes",
        "confirmed_ranges",
        "range_invalidations",
        "range_replacements",
        "contradictory_pairs",
        "invalidated_before_confirmation",
        "replaced_before_confirmation",
        "confirmed_then_invalidated",
        "confirmed_then_replaced",
    )}

    def add_event(kind: str, when: pd.Timestamp, related_id: str, detail: dict | None = None) -> None:
        events.append(_event(kind, when, related_id, detail))

    def close_range(reason: str, when: pd.Timestamp, new_state: str | None) -> None:
        nonlocal current
        if current is None or current["pairing_status"] != "ACTIVE_PAIR":
            return
        if new_state == "INVALIDATED":
            current["state"] = "INVALIDATED"
            current["invalidated_at"] = when
            current["invalidation_reason"] = reason
            current["pairing_status"] = "CLOSED"
            counts["range_invalidations"] += 1
            if current["confirmed_at"] is None:
                counts["invalidated_before_confirmation"] += 1
            else:
                counts["confirmed_then_invalidated"] += 1
            add_event("RANGE_INVALIDATION", when, current["range_id"], {"reason": reason})
        else:
            current["pairing_status"] = "REPLACED"
            current["replaced_at"] = when
            current["replace_reason"] = reason
            counts["range_replacements"] += 1
            if current["confirmed_at"] is None:
                counts["replaced_before_confirmation"] += 1
            else:
                counts["confirmed_then_replaced"] += 1
            add_event("RANGE_REPLACED", when, current["range_id"], {"reason": reason})
        current = None

    def open_pair(when: pd.Timestamp) -> None:
        nonlocal current, contradictory, crossed_key
        support = active["SUPPORT"]
        resistance = active["RESISTANCE"]
        same = (
            current is not None
            and support is not None
            and resistance is not None
            and current["support_level_id"] == support["level_id"]
            and current["resistance_level_id"] == resistance["level_id"]
        )
        if same:
            return
        if current is not None:
            close_range("latest_levels_changed", when, None)
        if support is None or resistance is None:
            return
        if not support["price"] < resistance["price"]:
            key = (support["level_id"], resistance["level_id"])
            if key != crossed_key:
                contradictory += 1
                counts["contradictory_pairs"] += 1
                add_event("CROSSED_PAIR", when, f"{support['level_id']}|{resistance['level_id']}", {"reason": "support_not_below_resistance"})
                crossed_key = key
            return
        crossed_key = None
        born = max(support["available_at"], resistance["available_at"])
        current = {
            "range_id": f"{support['level_id']}|{resistance['level_id']}",
            "instrument": instrument,
            "timeframe": timeframe,
            "state": "CANDIDATE",
            "pairing_status": "ACTIVE_PAIR",
            "support_level_id": support["level_id"],
            "resistance_level_id": resistance["level_id"],
            "support_swing_id": support["source_swing_id"],
            "resistance_swing_id": resistance["source_swing_id"],
            "support_price": support["price"],
            "resistance_price": resistance["price"],
            "pair_available_at": born,
            "support_reactions": [],
            "resistance_reactions": [],
            "confirmed_at": None,
            "invalidated_at": None,
            "invalidation_reason": None,
            "replaced_at": None,
            "replace_reason": None,
            "width_price": resistance["price"] - support["price"],
            "width_pips": (resistance["price"] - support["price"]) / pip_size,
            "definition_version": IMPLEMENTATION_VERSION,
        }
        ranges.append(current)
        counts["range_pairs"] += 1
        add_event("RANGE_PAIR", born, current["range_id"])

    for index, when in enumerate(avail):
        candle_open = opens[index]
        bar_high = float(high[index])
        bar_low = float(low[index])
        bar_close = float(close[index])
        range_state = "UNCERTAIN"
        range_reason = "no_eligible_pair"
        if current is not None and current["pair_available_at"] < when and current["state"] in {"CANDIDATE", "CONFIRMED"}:
            outside = _beyond_level("SUPPORT", bar_close, current["support_price"]) or _beyond_level(
                "RESISTANCE", bar_close, current["resistance_price"]
            )
            if outside:
                close_range("close_outside", when, "INVALIDATED")
                range_state = "INVALIDATED"
                range_reason = "close_outside"
            else:
                for side, price_key, store_key in (
                    ("SUPPORT", "support_price", "support_reactions"),
                    ("RESISTANCE", "resistance_price", "resistance_reactions"),
                ):
                    if _reach_level(side, bar_high, bar_low, bar_close, current[price_key]) and not episode_open[side]:
                        reaction = {"available_at": when, "candle_time": candle_open, "level_id": current[f"{side.lower()}_level_id"]}
                        current[store_key].append(reaction)
                        counts["range_reaction_episodes"] += 1
                        add_event("RANGE_REACTION", when, current["range_id"], {"side": side})
                if current["state"] == "CANDIDATE" and len(current["support_reactions"]) >= 2 and len(current["resistance_reactions"]) >= 2:
                    current["state"] = "CONFIRMED"
                    current["confirmed_at"] = when
                    counts["confirmed_ranges"] += 1
                    add_event("RANGE_CONFIRMED", when, current["range_id"])
                range_state = current["state"]
                range_reason = "active_pair"
        for side in ("SUPPORT", "RESISTANCE"):
            level = active[side]
            if level is None or level["status"] != "ACTIVE" or not level["available_at"] < when:
                continue
            if _beyond_level(side, bar_close, level["price"]):
                _transition(level, "INVALIDATED", when, "close_through", None)
                counts["level_invalidations"] += 1
                add_event("LEVEL_INVALIDATION", when, level["level_id"])
                active[side] = None
                episode_open[side] = False
                continue
            if _reach_level(side, bar_high, bar_low, bar_close, level["price"]):
                if not episode_open[side]:
                    key = "support_touch_episodes" if side == "SUPPORT" else "resistance_touch_episodes"
                    counts[key] += 1
                    add_event("LEVEL_TOUCH_EPISODE", when, level["level_id"], {"side": side})
                    episode_open[side] = True
            else:
                episode_open[side] = False
        for side in ("SUPPORT", "RESISTANCE"):
            line = active_line[side]
            if line is None or line["status"] != "ACTIVE" or not line["available_at"] < when:
                continue
            projected = line_price(line, when)
            if _beyond_line(side, bar_close, projected):
                _transition(line, "BROKEN", when, "close_beyond", None)
                line["break_event"] = {"available_at": when, "candle_time": candle_open, "line_price": projected, "bid_close": bar_close}
                counts["trendline_breaks"] += 1
                add_event("LINE_BREAK", when, line["line_id"])
                active_line[side] = None
                line_episode_open[side] = False
            elif _reach_line(side, bar_high, bar_low, bar_close, projected):
                if not line_episode_open[side]:
                    counts["line_touch_episodes"] += 1
                    add_event("LINE_TOUCH_EPISODE", when, line["line_id"], {"side": side})
                    line_episode_open[side] = True
            else:
                line_episode_open[side] = False
        while swing_at < len(swing_queue) and swing_queue[swing_at]["available_at"] <= when:
            swing = swing_queue[swing_at]
            swing_at += 1
            side = "RESISTANCE" if swing["swing_type"] == "HIGH" else "SUPPORT"
            level = {
                "level_id": f"{side}|{swing['swing_id']}",
                "instrument": instrument,
                "timeframe": timeframe,
                "kind": side,
                "price": float(swing["pivot_price"]),
                "source_swing_id": swing["swing_id"],
                "pivot_time": swing["pivot_time"],
                "available_at": swing["available_at"],
                "status": "ACTIVE",
                "transitions": [],
                "definition_version": IMPLEMENTATION_VERSION,
            }
            _transition(level, "ACTIVE", swing["available_at"], "confirmed_swing", swing["swing_id"])
            levels.append(level)
            counts["levels_created"] += 1
            add_event("LEVEL_CREATED", swing["available_at"], level["level_id"])
            previous = active[side]
            if previous is not None and previous["status"] == "ACTIVE":
                _transition(previous, "SUPERSEDED", when, "newer_confirmed_level", level["level_id"])
                counts["level_supersessions"] += 1
                add_event("LEVEL_SUPERSEDED", when, previous["level_id"], {"replacement_id": level["level_id"]})
            active[side] = level
            episode_open[side] = False
        while line_at < len(line_queue) and line_queue[line_at]["available_at"] <= when:
            source = line_queue[line_at]
            line_at += 1
            side = source["line_type"]
            line = dict(source)
            line["status"] = "ACTIVE"
            line["transitions"] = []
            line["break_event"] = None
            line["definition_version"] = IMPLEMENTATION_VERSION
            _transition(line, "ACTIVE", line["available_at"], "second_swing_confirmed", line["line_id"])
            live_lines.append(line)
            counts["trendlines_created"] += 1
            add_event("LINE_CREATED", line["available_at"], line["line_id"])
            previous = active_line[side]
            if previous is not None and previous["status"] == "ACTIVE":
                _transition(previous, "SUPERSEDED", when, "newer_confirmed_line", line["line_id"])
                counts["trendline_supersessions"] += 1
                add_event("LINE_SUPERSEDED", when, previous["line_id"], {"replacement_id": line["line_id"]})
            active_line[side] = line
            line_episode_open[side] = False
        open_pair(when)
        if current is not None:
            range_state = current["state"]
            range_reason = "active_pair"
        elif range_state != "INVALIDATED":
            range_state = "UNCERTAIN"
            range_reason = "crossed_or_missing_level" if crossed_key is not None else "no_eligible_pair"
        states.append(
            {
                "time": candle_open,
                "available_at": when,
                "range_state": range_state,
                "range_reason": range_reason,
                "range_id": None if current is None else current["range_id"],
                "support_level_id": None if active["SUPPORT"] is None else active["SUPPORT"]["level_id"],
                "resistance_level_id": None if active["RESISTANCE"] is None else active["RESISTANCE"]["level_id"],
                "support_line_id": None if active_line["SUPPORT"] is None else active_line["SUPPORT"]["line_id"],
                "resistance_line_id": None if active_line["RESISTANCE"] is None else active_line["RESISTANCE"]["line_id"],
                "definition_version": IMPLEMENTATION_VERSION,
            }
        )
    counts["uncertain_candles"] = int(sum(row["range_state"] == "UNCERTAIN" for row in states))
    counts["candidate_candles"] = int(sum(row["range_state"] == "CANDIDATE" for row in states))
    counts["confirmed_candles"] = int(sum(row["range_state"] == "CONFIRMED" for row in states))
    counts["invalidated_candles"] = int(sum(row["range_state"] == "INVALIDATED" for row in states))
    counts["active_levels_at_end"] = int(sum(level["status"] == "ACTIVE" for level in levels))
    counts["active_lines_at_end"] = int(sum(line["status"] == "ACTIVE" for line in live_lines))
    counts["legacy_raw_continuation_comparisons"] = 0
    return {
        "implementation_version": IMPLEMENTATION_VERSION,
        "parent_definition": PARENT_DEFINITION,
        "levels": levels,
        "lines": live_lines,
        "ranges": ranges,
        "events": events,
        "states": states,
        "counts": counts,
        "trading_signal": None,
    }


def events_known_by(result: dict, when) -> list[dict]:
    limit = _utc(when)
    return [row for row in result["events"] if row["available_at"] <= limit]


def observation_row(state: dict, instrument: str, timeframe: str, source_sha256: str, protocol_sha256: str) -> dict:
    """A lifecycle observation. It is not a trading decision."""
    return {
        "record_type": "market_structure_lifecycle_observation",
        "instrument": instrument,
        "timeframe": timeframe,
        "candle_time": state["time"],
        "available_at": state["available_at"],
        "range_state": state["range_state"],
        "range_reason": state["range_reason"],
        "range_id": state["range_id"],
        "support_level_id": state["support_level_id"],
        "resistance_level_id": state["resistance_level_id"],
        "support_line_id": state["support_line_id"],
        "resistance_line_id": state["resistance_line_id"],
        "source_sha256": source_sha256,
        "definition_version": IMPLEMENTATION_VERSION,
        "parent_definition": PARENT_DEFINITION,
        "protocol_sha256": protocol_sha256,
        "trading_decision": None,
        "outcome": None,
        "confidence": None,
    }
