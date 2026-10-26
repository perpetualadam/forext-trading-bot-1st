"""R.40 data inventory. No signals and no trading results."""

from __future__ import annotations

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
        raise OSError("R40_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.regimes import DATASET_SHA256
from forex_bot.research.learning.timeframes import H1_MINUTES, H4_MINUTES, aggregate_bid_ask, research_pip_size


def _gaps(times: pd.Series) -> dict:
    delta = times.diff().dt.total_seconds()
    return {
        "steps_over_5_minutes": int((delta > 300).sum()),
        "steps_over_1_hour_to_48_hours": int(((delta > 3600) & (delta <= 48 * 3600)).sum()),
        "steps_over_48_hours": int((delta > 48 * 3600).sum()),
        "largest_gap_hours": None if delta.empty else float(delta.max() / 3600.0),
    }


def main() -> None:
    history = ROOT / "data" / "historical"
    rows = []
    for name, expected in DATASET_SHA256.items():
        path = history / f"{name}_M5.csv"
        digest = file_sha256(path)
        if digest != expected:
            raise SystemExit(f"R40_HASH_MISMATCH_{name}")
        raw = pd.read_csv(path)
        clean, quality = validate_frame(raw)
        h1, h1_report = aggregate_bid_ask(clean, H1_MINUTES)
        h4, h4_report = aggregate_bid_ask(clean, H4_MINUTES)
        spread = clean["ask_close"] - clean["bid_close"]
        rows.append(
            {
                "instrument": name,
                "sha256": digest,
                "source_timeframe": "M5",
                "rows_read": quality["rows_read"],
                "rows_kept": quality["rows_kept"],
                "first": quality["first_timestamp"],
                "last": quality["last_timestamp"],
                "duplicate_timestamps": quality["duplicate_timestamps"],
                "negative_spread_rows": quality["negative_spread_rows"],
                "incomplete_source_rows": quality["incomplete_rows"],
                "pip_size_local_rule": research_pip_size(name),
                "median_close_spread_price": float(spread.median()),
                "gaps": _gaps(clean["time"]),
                "h1": h1_report,
                "h4": h4_report,
                "first_complete_h1": None if h1.empty else str(h1["time"].iloc[0]),
                "last_complete_h1": None if h1.empty else str(h1["time"].iloc[-1]),
                "first_complete_h4": None if h4.empty else str(h4["time"].iloc[0]),
                "last_complete_h4": None if h4.empty else str(h4["time"].iloc[-1]),
                "trading_backtest_run": False,
            }
        )
    payload = {
        "files_on_disk": sorted(path.name for path in history.glob("*.csv")),
        "candidate_pairs_with_local_candles": [],
        "instruments": rows,
    }
    (OUT / "02_data_inventory.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({row["instrument"]: {"h1": row["h1"]["complete_candles"], "h4": row["h4"]["complete_candles"], "incomplete_h1": row["h1"]["incomplete_buckets"]} for row in rows}))


if __name__ == "__main__":
    main()
