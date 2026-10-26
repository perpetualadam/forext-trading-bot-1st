"""R.42 descriptive lifecycle counts. No entries, exits, or profit."""

from __future__ import annotations

import hashlib
import json
import os
import socket
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
        raise OSError("R42_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.lifecycle import apply_lifecycle, events_known_by, observation_row
from forex_bot.research.learning.regimes import DATASET_SHA256
from forex_bot.research.learning.structure import build_trendlines, confirmed_swings
from forex_bot.research.learning.timeframes import H1_MINUTES, H4_MINUTES, aggregate_bid_ask, research_pip_size, visible_close

PROTOCOL_SHA = "da8f53c0f8b89037ab00721f4c0a3b8d7c322d6da692e37a2b3f142a643c6b27"
LIFECYCLE_SHA = "4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5"
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


def _ids(events: list[dict]) -> list[tuple]:
    return [(row["event_type"], row["related_id"], row["available_at"].isoformat()) for row in events]


def _clock(frame: pd.DataFrame, result: dict) -> dict:
    checks = {"active_levels_at_most_one_per_side": True, "active_lines_at_most_one_per_side": True}
    for kind in ("SUPPORT", "RESISTANCE"):
        if sum(level["status"] == "ACTIVE" and level["kind"] == kind for level in result["levels"]) > 1:
            checks["active_levels_at_most_one_per_side"] = False
        if sum(line["status"] == "ACTIVE" and line["line_type"] == kind for line in result["lines"]) > 1:
            checks["active_lines_at_most_one_per_side"] = False
    for item in result["ranges"]:
        if item["confirmed_at"] is not None and (len(item["support_reactions"]) < 2 or len(item["resistance_reactions"]) < 2):
            checks["confirmed_range_has_two_reactions"] = False
    checks.setdefault("confirmed_range_has_two_reactions", True)
    if len(frame):
        row = frame.iloc[min(10, len(frame) - 1)]
        midpoint = row["time"] + pd.Timedelta(minutes=30)
        checks["unfinished_candle_hidden"] = row["time"] not in set(frame.loc[frame["available_at"] <= midpoint, "time"])
        checks["visible_at_close"] = visible_close(frame, row["available_at"]) == float(frame.loc[frame["available_at"] <= row["available_at"], "bid_close"].iloc[-1])
    if result["levels"]:
        born = result["levels"][0]["available_at"]
        before = {row["related_id"] for row in events_known_by(result, born - pd.Timedelta(seconds=1))}
        at = {row["related_id"] for row in events_known_by(result, born)}
        checks["level_hidden_before_birth"] = result["levels"][0]["level_id"] not in before
        checks["level_visible_at_birth"] = result["levels"][0]["level_id"] in at
    return checks


def _analyse(frame: pd.DataFrame, period: pd.Timedelta, instrument: str, timeframe: str, source_sha256: str) -> dict:
    swings, swing_report = confirmed_swings(frame, period=period, instrument=instrument, timeframe=timeframe, source_sha256=source_sha256)
    lines = build_trendlines(swings)
    result = apply_lifecycle(frame, swings, lines, instrument=instrument, timeframe=timeframe, pip_size=research_pip_size(instrument))
    early = frame.loc[frame["available_at"] <= PREFIX_AT].copy()
    early_swings, _early_report = confirmed_swings(early, period=period, instrument=instrument, timeframe=timeframe, source_sha256=source_sha256)
    early_lines = build_trendlines(early_swings)
    early_result = apply_lifecycle(early, early_swings, early_lines, instrument=instrument, timeframe=timeframe, pip_size=research_pip_size(instrument))
    if _ids(early_result["events"]) != _ids(events_known_by(result, PREFIX_AT)):
        raise SystemExit(f"R42_PREFIX_{instrument}_{timeframe}")
    checks = _clock(frame, result)
    if not all(checks.values()):
        raise SystemExit(f"R42_CLOCK_{instrument}_{timeframe}")
    confirmed = [item for item in result["ranges"] if item["confirmed_at"] is not None]
    example_state = next((row for row in result["states"] if row["range_state"] == "CONFIRMED"), result["states"][0])
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "complete_candles": swing_report["complete_candles"],
        "gap_rejected_windows": swing_report["gap_rejected_windows"],
        "confirmed_swing_highs": swing_report["confirmed_swing_highs"],
        "confirmed_swing_lows": swing_report["confirmed_swing_lows"],
        "tied_high_candidates": swing_report["tied_high_candidates"],
        "tied_low_candidates": swing_report["tied_low_candidates"],
        "counts": result["counts"],
        "prefix_invariant": True,
        "clock": checks,
        "example": _jsonable(
            {
                "observation": observation_row(example_state, instrument, timeframe, source_sha256, PROTOCOL_SHA),
                "first_level": None if not result["levels"] else {"level_id": result["levels"][0]["level_id"], "status": result["levels"][0]["status"], "transitions": result["levels"][0]["transitions"][:2]},
                "first_confirmed_range": None if not confirmed else {key: confirmed[0][key] for key in ("range_id", "pair_available_at", "confirmed_at", "invalidated_at", "width_price", "width_pips", "state")},
            }
        ),
    }


def main() -> None:
    if _digest(OUT / "03_protocol.json") != PROTOCOL_SHA:
        raise SystemExit("R42_PROTOCOL_HASH")
    if _digest(ROOT / "forex_bot" / "research" / "learning" / "lifecycle.py") != LIFECYCLE_SHA:
        raise SystemExit("R42_LIFECYCLE_HASH")
    history = ROOT / "data" / "historical"
    frames = {}
    hashes = {}
    for name, expected in sorted(DATASET_SHA256.items()):
        path = history / f"{name}_M5.csv"
        digest = file_sha256(path)
        if digest != expected:
            raise SystemExit(f"R42_HASH_MISMATCH_{name}")
        hashes[name] = digest
        raw = pd.read_csv(path)
        frames[name], _quality = validate_frame(raw)
    rows = []
    rejected = {}
    for name in sorted(frames):
        h1, h1_report = aggregate_bid_ask(frames[name], H1_MINUTES)
        h4, h4_report = aggregate_bid_ask(frames[name], H4_MINUTES)
        rejected[name] = {"h1_incomplete_buckets": h1_report["incomplete_buckets"], "h4_incomplete_buckets": h4_report["incomplete_buckets"]}
        rows.append(_analyse(h1, pd.Timedelta(minutes=H1_MINUTES), name, "H1", hashes[name]))
        rows.append(_analyse(h4, pd.Timedelta(minutes=H4_MINUTES), name, "H4", hashes[name]))
    payload = {
        "implementation_version": "r42.structure.v1",
        "protocol_sha256": PROTOCOL_SHA,
        "lifecycle_py_sha256": LIFECYCLE_SHA,
        "source_sha256": hashes,
        "rejected_buckets": rejected,
        "series": rows,
        "trading_backtest_run": False,
    }
    text = json.dumps(_jsonable(payload), indent=2)
    if '"BUY"' in text or '"SELL"' in text:
        raise SystemExit("R42_SIGNAL_LEAKED")
    (OUT / "13_descriptive_statistics.json").write_text(text, encoding="utf-8")
    print(json.dumps({row["instrument"] + "_" + row["timeframe"]: row["counts"] for row in rows}))


if __name__ == "__main__":
    main()
