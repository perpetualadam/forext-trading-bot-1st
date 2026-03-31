"""Load OHLCV from CSV for backtests (no OANDA)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """
    Read a CSV with columns: **time**, **open**, **high**, **low**, **close** (headers case-insensitive).

    - **time**: ISO-8601 or any string ``pandas.to_datetime`` parses; interpreted as UTC then stored naive UTC.
    - Optional **volume** column is ignored.

    Returns a DataFrame with the same shape as :func:`forex_bot.oanda_client.fetch_ohlcv_range`
    (columns ``time``, ``open``, ``high``, ``low``, ``close``; ``time`` as datetime-like).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"OHLCV CSV not found: {p.resolve()}")

    df = pd.read_csv(p)
    df.columns = [str(c).strip().lower() for c in df.columns]
    required = {"time", "open", "high", "low", "close"}
    if not required <= set(df.columns):
        raise ValueError(f"CSV must include columns {sorted(required)}, got {sorted(df.columns)}")

    t = pd.to_datetime(df["time"], utc=True, errors="coerce")
    if t.isna().any():
        bad = int(t.isna().sum())
        raise ValueError(f"CSV has {bad} unparseable time value(s) in column 'time'")

    if t.dt.tz is not None:
        t = t.dt.tz_convert("UTC").dt.tz_localize(None)

    out = pd.DataFrame(
        {
            "time": t,
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
        }
    )
    if out.isna().any().any():
        raise ValueError("CSV has NaN in OHLC after parse (check numeric columns)")

    out = out.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    logger.info("Loaded OHLCV CSV %s: %s rows (%s → %s)", p.name, len(out), out["time"].iloc[0], out["time"].iloc[-1])
    return out


def filter_ohlcv_date_range(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Rows with ``time`` in ``[start, end]`` (naive UTC, inclusive)."""
    ts = pd.to_datetime(df["time"])
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    start_u = pd.Timestamp(start)
    end_u = pd.Timestamp(end)
    mask = (ts >= start_u) & (ts <= end_u)
    sub = df.loc[mask].copy().reset_index(drop=True)
    return sub
