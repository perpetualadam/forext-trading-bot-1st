"""Validate local historical candles. This module does not download or rewrite them."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pandas as pd

from forex_bot.research.learning.protocol import BAR_SECONDS

PRICE_COLUMNS = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.notna() & numeric.map(math.isfinite)


def validate_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return a sorted research copy and a quality report. The input is not modified."""
    missing = [name for name in ("time", *PRICE_COLUMNS) if name not in frame.columns]
    if missing:
        raise ValueError("missing_columns:" + ",".join(missing))
    work = frame.copy()
    work["time"] = pd.to_datetime(work["time"], utc=True, errors="coerce")
    ordered = work["time"].dropna()
    out_of_order = int((ordered.diff() < pd.Timedelta(0)).sum()) if len(ordered) else 0
    duplicate_timestamps = int(work["time"].duplicated().sum())
    missing_timestamps = int(work["time"].isna().sum())
    price_ok = pd.Series(True, index=work.index)
    non_finite = {}
    for name in PRICE_COLUMNS:
        ok = _finite(work[name])
        non_finite[name] = int((~ok).sum())
        price_ok = price_ok & ok
        work[name] = pd.to_numeric(work[name], errors="coerce")
    spread = work["ask_close"] - work["bid_close"]
    negative_spread = int((spread < 0).fillna(False).sum())
    if "complete" in work.columns:
        incomplete = int(work["complete"].astype(str).str.lower().isin(["false", "0"]).sum())
    else:
        incomplete = 0
    volume_available = "volume" in work.columns
    if volume_available:
        work["volume"] = pd.to_numeric(work["volume"], errors="coerce")
    clean = work.loc[work["time"].notna() & price_ok & (spread >= 0)].copy()
    if "complete" in clean.columns:
        clean = clean.loc[~clean["complete"].astype(str).str.lower().isin(["false", "0"])].copy()
    clean = clean.sort_values("time").drop_duplicates("time", keep="first")
    gaps = clean["time"].diff().dt.total_seconds()
    gap_count = int((gaps > BAR_SECONDS).sum()) if len(clean) else 0
    report = {
        "rows_read": int(len(frame)),
        "rows_kept": int(len(clean)),
        "missing_timestamps": missing_timestamps,
        "duplicate_timestamps": duplicate_timestamps,
        "out_of_order_steps": out_of_order,
        "non_finite_prices": non_finite,
        "negative_spread_rows": negative_spread,
        "incomplete_rows": incomplete,
        "gaps_longer_than_one_bar": gap_count,
        "volume_available": volume_available,
        "spread_unit": "price",
        "timestamp_convention": "UTC",
        "first_timestamp": None if clean.empty else clean["time"].iloc[0].isoformat(),
        "last_timestamp": None if clean.empty else clean["time"].iloc[-1].isoformat(),
    }
    return clean.reset_index(drop=True), report
