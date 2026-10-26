"""R.41 descriptive structure counts. No entries, exits, or profit."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import statistics
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["DOTENV_PATH"] = str(OUT / "missing.env")
import dotenv

dotenv.load_dotenv = lambda *a, **k: False


class _Blocked(socket.socket):
    def connect(self, *_args, **_kwargs):
        raise OSError("R41_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.regimes import DATASET_SHA256
from forex_bot.research.learning.structure import (
    IMPLEMENTATION_VERSION,
    asof_view,
    build_trendlines,
    confirmed_swings,
    known_before,
    level_interactions,
    observation_row,
    range_decision,
    support_resistance,
    trend_states,
    trendline_events,
)
from forex_bot.research.learning.timeframes import H1_MINUTES, H4_MINUTES, aggregate_bid_ask, visible_close

PROTOCOL_SHA = "8880d210ca38e783c1a2615c50a90688ed75825adf1652e525a5bfe55b60e1d0"
STRUCTURE_SHA = "b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc"
PREFIX_AT = pd.Timestamp("2026-03-01T00:00:00Z")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _runs(states: list[dict]) -> dict:
    grouped: dict[str, list[tuple[int, float]]] = {}
    start = 0
    for index in range(1, len(states) + 1):
        if index == len(states) or states[index]["state"] != states[start]["state"]:
            chunk = states[start:index]
            elapsed = (chunk[-1]["available_at"] - chunk[0]["available_at"]).total_seconds() / 3600.0
            grouped.setdefault(chunk[0]["state"], []).append((len(chunk), elapsed))
            start = index
    summary = {}
    for name, rows in grouped.items():
        lengths = [item[0] for item in rows]
        hours = [item[1] for item in rows]
        summary[name] = {
            "runs": len(rows),
            "candles": int(sum(lengths)),
            "median_candles": float(statistics.median(lengths)),
            "median_elapsed_hours": float(statistics.median(hours)),
        }
    return summary


def _assert_causal(swings, states, period) -> None:
    delay = 3 * pd.Timedelta(period)
    for swing in swings:
        if swing["available_at"] != swing["pivot_time"] + delay:
            raise SystemExit("R41_CONFIRMATION_DELAY")
        if swing["confirmation_time"] != swing["available_at"]:
            raise SystemExit("R41_AVAILABILITY_MISMATCH")
        if swing["relation"] not in {"UNCERTAIN", "HIGHER_HIGH", "LOWER_HIGH", "HIGHER_LOW", "LOWER_LOW"}:
            raise SystemExit("R41_BAD_RELATION")
    for row in states:
        if row["changed"] and not row["supporting_swing_ids"]:
            raise SystemExit("R41_STATE_CHANGED_WITHOUT_SWING")


def _clock(h1: pd.DataFrame, h4: pd.DataFrame, h1_swings, h4_swings) -> dict:
    checks = {
        "no_swing_after_dataset_end": all(swing["available_at"] <= h1["available_at"].iloc[-1] for swing in h1_swings)
        and all(swing["available_at"] <= h4["available_at"].iloc[-1] for swing in h4_swings)
    }
    if len(h1):
        row = h1.iloc[min(10, len(h1) - 1)]
        midpoint = row["time"] + pd.Timedelta(minutes=30)
        known = h1.loc[h1["available_at"] <= midpoint, "time"]
        checks["unfinished_h1_hidden_from_m5_midpoint"] = row["time"] not in set(known)
        checks["h1_visible_at_its_close"] = bool((h1["available_at"] == row["available_at"]).any()) and visible_close(h1, row["available_at"]) == float(
            h1.loc[h1["available_at"] <= row["available_at"], "bid_close"].iloc[-1]
        )
    if len(h4):
        row = h4.iloc[min(3, len(h4) - 1)]
        inside = row["time"] + pd.Timedelta(minutes=5)
        known = h4.loc[h4["available_at"] <= inside, "time"]
        checks["unfinished_h4_hidden_from_m5_inside_bucket"] = row["time"] not in set(known)
        just_before = row["available_at"] - pd.Timedelta(seconds=1)
        checks["h4_hidden_one_second_before_close"] = row["time"] not in set(h4.loc[h4["available_at"] <= just_before, "time"])
        checks["h4_visible_at_boundary"] = row["time"] in set(h4.loc[h4["available_at"] <= row["available_at"], "time"])
    if h1_swings:
        swing = h1_swings[0]
        before = asof_view(h1_swings, [], [], swing["available_at"] - pd.Timedelta(seconds=1))
        at = asof_view(h1_swings, [], [], swing["available_at"])
        checks["h1_swing_hidden_before_confirmation"] = swing["swing_id"] not in {item["swing_id"] for item in before["swings"]}
        checks["h1_swing_visible_at_confirmation"] = swing["swing_id"] in {item["swing_id"] for item in at["swings"]}
    if h4_swings:
        swing = h4_swings[0]
        before = asof_view(h4_swings, [], [], swing["available_at"] - pd.Timedelta(seconds=1))
        at = asof_view(h4_swings, [], [], swing["available_at"])
        checks["h4_swing_hidden_before_confirmation"] = swing["swing_id"] not in {item["swing_id"] for item in before["swings"]}
        checks["h4_swing_visible_at_confirmation"] = swing["swing_id"] in {item["swing_id"] for item in at["swings"]}
    return checks


def _analyse(candles: pd.DataFrame, period, instrument: str, timeframe: str, source_sha256: str) -> dict:
    swings, swing_report = confirmed_swings(
        candles, period=period, instrument=instrument, timeframe=timeframe, source_sha256=source_sha256
    )
    states = trend_states(candles, swings)
    lines = build_trendlines(swings)
    levels = support_resistance(swings)
    _assert_causal(swings, states, period)
    early = candles.loc[candles["available_at"] <= PREFIX_AT].copy()
    early_swings, _early_report = confirmed_swings(
        early, period=period, instrument=instrument, timeframe=timeframe, source_sha256=source_sha256
    )
    early_states = trend_states(early, early_swings)
    early_lines = build_trendlines(early_swings)
    full_lines_known = known_before(lines, PREFIX_AT)
    if [item["swing_id"] for item in early_swings] != [item["swing_id"] for item in known_before(swings, PREFIX_AT)]:
        raise SystemExit("R41_PREFIX_SWING")
    if [item["line_id"] for item in early_lines] != [item["line_id"] for item in full_lines_known]:
        raise SystemExit("R41_PREFIX_LINE")
    if [row["state"] for row in early_states] != [row["state"] for row in states if row["available_at"] <= PREFIX_AT]:
        raise SystemExit("R41_PREFIX_STATE")
    early_events = trendline_events(early, early_lines)
    full_events_cut = trendline_events(early, lines)
    if early_events["counts"] != full_events_cut["counts"]:
        raise SystemExit("R41_PREFIX_EVENT")
    early_levels = support_resistance(early_swings)
    early_level_events = level_interactions(early, early_levels)
    full_level_cut = level_interactions(early, levels)
    if early_level_events["counts"] != full_level_cut["counts"]:
        raise SystemExit("R41_PREFIX_LEVEL")
    events = trendline_events(candles, lines)
    interactions = level_interactions(candles, levels)
    ranges = range_decision()
    if ranges["confirmed_ranges"] != 0 or ranges["available_ranges"]:
        raise SystemExit("R41_RANGE_NOT_FAIL_CLOSED")
    relations = {}
    for swing in swings:
        relations[swing["relation"]] = relations.get(swing["relation"], 0) + 1
    state_counts = {}
    for row in states:
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
    examples = {
        "first_swing": None if not swings else _jsonable(swings[0]),
        "first_line": None if not lines else _jsonable(lines[0]),
        "first_transition": _jsonable(next((row for row in states if row["changed"]), None)),
        "touch": _jsonable(events["examples"]["TOUCH_REACH"]),
        "break": _jsonable(events["examples"]["BREAK"]),
        "level": _jsonable(levels[0]) if levels else None,
        "observation": _jsonable(observation_row(instrument, timeframe, states[0], source_sha256, PROTOCOL_SHA)),
    }
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "complete_candles": swing_report["complete_candles"],
        "edge_windows_not_evaluated": swing_report["edge_windows_not_evaluated"],
        "gap_rejected_windows": swing_report["gap_rejected_windows"],
        "tied_high_candidates": swing_report["tied_high_candidates"],
        "tied_low_candidates": swing_report["tied_low_candidates"],
        "confirmed_swing_highs": swing_report["confirmed_swing_highs"],
        "confirmed_swing_lows": swing_report["confirmed_swing_lows"],
        "relations": relations,
        "state_counts": state_counts,
        "state_runs": _runs(states),
        "transitions": int(sum(row["changed"] for row in states)),
        "trendlines": len(lines),
        "trendline_versions": {kind: max((line["version"] for line in lines if line["line_type"] == kind), default=0) for kind in ("SUPPORT", "RESISTANCE")},
        "events": events["counts"],
        "levels": len(levels),
        "level_events": interactions["counts"],
        "ranges": ranges,
        "prefix_invariant": True,
        "examples": examples,
    }


def main() -> None:
    protocol = OUT / "03_protocol.json"
    if _digest(protocol) != PROTOCOL_SHA:
        raise SystemExit("R41_PROTOCOL_HASH")
    if _digest(ROOT / "forex_bot" / "research" / "learning" / "structure.py") != STRUCTURE_SHA:
        raise SystemExit("R41_STRUCTURE_HASH")
    history = ROOT / "data" / "historical"
    hashes = {}
    frames = {}
    for name, expected in sorted(DATASET_SHA256.items()):
        path = history / f"{name}_M5.csv"
        digest = file_sha256(path)
        if digest != expected:
            raise SystemExit(f"R41_HASH_MISMATCH_{name}")
        hashes[name] = digest
        raw = pd.read_csv(path)
        frames[name], _quality = validate_frame(raw)
    rows = []
    rejected = {}
    clock = {}
    for name in sorted(frames):
        h1, h1_report = aggregate_bid_ask(frames[name], H1_MINUTES)
        h4, h4_report = aggregate_bid_ask(frames[name], H4_MINUTES)
        rejected[name] = {"h1_incomplete_buckets": h1_report["incomplete_buckets"], "h4_incomplete_buckets": h4_report["incomplete_buckets"]}
        h1_row = _analyse(h1, pd.Timedelta(minutes=H1_MINUTES), name, "H1", hashes[name])
        h4_row = _analyse(h4, pd.Timedelta(minutes=H4_MINUTES), name, "H4", hashes[name])
        h1_swings, _report = confirmed_swings(h1, period=pd.Timedelta(minutes=H1_MINUTES), instrument=name, timeframe="H1", source_sha256=hashes[name])
        h4_swings, _h4_report = confirmed_swings(h4, period=pd.Timedelta(minutes=H4_MINUTES), instrument=name, timeframe="H4", source_sha256=hashes[name])
        clock[name] = _clock(h1, h4, h1_swings, h4_swings)
        if not all(clock[name].values()):
            raise SystemExit(f"R41_CLOCK_{name}")
        rows.extend([h1_row, h4_row])
    payload = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "protocol_sha256": PROTOCOL_SHA,
        "structure_py_sha256": STRUCTURE_SHA,
        "source_sha256": hashes,
        "rejected_buckets": rejected,
        "clock": clock,
        "series": rows,
        "trading_backtest_run": False,
    }
    text = json.dumps(_jsonable(payload), indent=2)
    if '"BUY"' in text or '"SELL"' in text:
        raise SystemExit("R41_SIGNAL_LEAKED")
    (OUT / "13_descriptive_statistics.json").write_text(text, encoding="utf-8")
    print(json.dumps({row["instrument"] + "_" + row["timeframe"]: {"swings": row["confirmed_swing_highs"] + row["confirmed_swing_lows"], "states": row["state_counts"]} for row in rows}))


if __name__ == "__main__":
    main()
