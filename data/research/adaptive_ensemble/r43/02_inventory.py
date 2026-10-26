"""Read-only inventory of approved local candle files. No network and no writes to source data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "historical"
G3 = ROOT / "data" / "research" / "adaptive_ensemble" / "g3" / "normalized"
SAMPLE = ROOT / "data" / "eurusd_m5_2024_sample.csv"
PAIRS = ("AUD_USD", "EUR_USD", "GBP_USD", "USD_CAD", "USD_CHF", "USD_JPY")
CANDIDATES = ("NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY", "AUD_JPY", "EUR_AUD")
KNOWN_M5 = {
    "AUD_USD": "e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0",
    "EUR_USD": "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091",
    "GBP_USD": "ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58",
    "USD_CAD": "a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60",
    "USD_CHF": "3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc",
    "USD_JPY": "e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c",
}
KNOWN_G3 = {
    "AUD_USD": "d75312decbb4c72858621a0b5a9af6103f72b01593ae26e9df4ef19a06104583",
    "EUR_USD": "c9016c8443ecc44fd0cf6ed5acb44656eae09ee3ef5b7d9fe9a334152c764b14",
    "GBP_USD": "272c7ff448ff91f587946c8b7a4335bacd04ae488c95f066e4a29cfec700c4f6",
    "USD_CAD": "e8fd5cf2acd20c481167d5ef5d0b77b7beaed9c190a8832c1291ffdee4475743",
    "USD_CHF": "7119ac28e67faaa24246c2bf9e0b8a863092328fa64b0694b4132e6835ea249f",
    "USD_JPY": "542a307964b9a365d28ca923905b5be6595c136261d52e92c154d0d29b35fd42",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def summarise(path: Path, expected_step: pd.Timedelta, provenance: str) -> dict:
    frame = pd.read_csv(path)
    columns = list(frame.columns)
    time_name = "time" if "time" in frame.columns else None
    if time_name is None:
        raise SystemExit(f"R43_TIME_COLUMN_MISSING_{path.name}")
    stamps = pd.to_datetime(frame[time_name], utc=True)
    ordered = stamps.sort_values()
    gaps = ordered.diff()
    large = gaps[gaps > expected_step]
    bid_close = next((name for name in ("bid_close", "bid_c") if name in frame.columns), None)
    ask_close = next((name for name in ("ask_close", "ask_c") if name in frame.columns), None)
    complete = frame["complete"] if "complete" in frame.columns else None
    stat = path.stat()
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": digest(path),
        "bytes": stat.st_size,
        "filesystem_mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "filesystem_mtime_is_not_market_time": True,
        "rows": int(len(frame)),
        "columns": columns,
        "bid_ask_present": bid_close is not None and ask_close is not None,
        "duplicate_timestamps": int(stamps.duplicated().sum()),
        "null_rows": int(frame.isna().any(axis=1).sum()),
        "earliest_utc": ordered.iloc[0].isoformat(),
        "latest_utc": ordered.iloc[-1].isoformat(),
        "complete_true": None if complete is None else int(complete.astype(str).str.lower().isin(["true", "1"]).sum()),
        "complete_false": None if complete is None else int((~complete.astype(str).str.lower().isin(["true", "1"])).sum()),
        "negative_close_spreads": None
        if bid_close is None
        else int((pd.to_numeric(frame[ask_close]) < pd.to_numeric(frame[bid_close])).sum()),
        "gaps_longer_than_one_bar": int(large.shape[0]),
        "largest_gap": None if large.empty else str(large.max()),
        "provenance": provenance,
    }


def main() -> None:
    rows = []
    for name in PAIRS:
        rows.append(summarise(HISTORY / f"{name}_M5.csv", pd.Timedelta(minutes=5), "approved_m5_research_year"))
        rows.append(summarise(HISTORY / "m1" / f"{name}_M1.csv", pd.Timedelta(minutes=1), "approved_m1_same_calendar_span"))
        rows.append(summarise(G3 / f"{name}_M5.csv", pd.Timedelta(minutes=5), "g3_normalized_later_extract"))
    rows.append(summarise(SAMPLE, pd.Timedelta(minutes=5), "readme_synthetic_2024_sample"))
    payload = {
        "inventory_only": True,
        "source_files_modified": False,
        "candidate_candle_files_found": {name: len(list((ROOT / "data").glob(f"**/{name}*"))) for name in CANDIDATES},
        "stored_h1_h4_candle_files": False,
        "v2_shadow_and_data_ops_left_unopened": True,
        "files": rows,
        "m5_hash_matches_prior": {
            name: next(row["sha256"] for row in rows if row["path"] == f"data/historical/{name}_M5.csv") == KNOWN_M5[name] for name in PAIRS
        },
        "g3_hash_matches_r2": {
            name: next(row["sha256"] for row in rows if row["path"] == f"data/research/adaptive_ensemble/g3/normalized/{name}_M5.csv") == KNOWN_G3[name]
            for name in PAIRS
        },
    }
    text = json.dumps(payload, indent=2)
    (OUT / "03_inventory.json").write_text(text, encoding="utf-8")
    print(json.dumps({"files": len(rows), "m5_match": payload["m5_hash_matches_prior"], "g3_match": payload["g3_hash_matches_r2"]}))


if __name__ == "__main__":
    main()
