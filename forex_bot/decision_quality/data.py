"""Local historical OHLCV inventory and leak-safe slicing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from forex_bot.csv_ohlcv import load_ohlcv_csv
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

REQUIRED_SYMBOLS = tuple(DEFAULT_FOREX_SYMBOLS)
OHLCV_COLUMNS = ("time", "open", "high", "low", "close")


@dataclass(frozen=True)
class SeriesCoverage:
    symbol: str
    timeframe: str
    path: str | None
    earliest: datetime | None
    latest: datetime | None
    bars: int
    missing_reason: str = ""


def default_data_dir(root: Path | None = None) -> Path:
    if root is None:
        root = Path(__file__).resolve().parents[2]
    return root / "data"


def _infer_symbol(path: Path) -> str | None:
    name = path.stem.upper()
    for sym in REQUIRED_SYMBOLS:
        compact = sym.replace("_", "")
        if sym in name or compact in name:
            return sym
    return None


def _infer_timeframe(path: Path) -> str:
    name = path.stem.upper()
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1"):
        if tf in name:
            return tf
    return "M5"


def inventory_local_ohlcv(data_dir: Path | None = None) -> list[SeriesCoverage]:
    """Describe every local CSV and report missing required pairs. Does not call OANDA."""
    ddir = default_data_dir() if data_dir is None else Path(data_dir)
    found: dict[tuple[str, str], SeriesCoverage] = {}
    if ddir.is_dir():
        for path in sorted(ddir.rglob("*.csv")):
            try:
                df = load_ohlcv_csv(path)
            except (OSError, ValueError):
                continue
            if df.empty:
                continue
            symbol = _infer_symbol(path) or "UNKNOWN"
            tf = _infer_timeframe(path)
            ts = pd.to_datetime(df["time"])
            found[(symbol, tf)] = SeriesCoverage(
                symbol=symbol,
                timeframe=tf,
                path=str(path.resolve()),
                earliest=ts.iloc[0].to_pydatetime(),
                latest=ts.iloc[-1].to_pydatetime(),
                bars=int(len(df)),
            )
    out = list(found.values())
    have = {c.symbol for c in out}
    for symbol in REQUIRED_SYMBOLS:
        if symbol not in have:
            out.append(
                SeriesCoverage(
                    symbol=symbol,
                    timeframe="M5",
                    path=None,
                    earliest=None,
                    latest=None,
                    bars=0,
                    missing_reason="no local CSV under data/",
                )
            )
    return out


def load_symbol_frame(path: str | Path) -> pd.DataFrame:
    df = load_ohlcv_csv(path)
    return ensure_chronological(df)


def ensure_chronological(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.reset_index(drop=True)
    out = df.loc[:, list(OHLCV_COLUMNS)].copy()
    out["time"] = pd.to_datetime(out["time"])
    if out["time"].dt.tz is not None:
        out["time"] = out["time"].dt.tz_convert("UTC").dt.tz_localize(None)
    out = out.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    if not out["time"].is_monotonic_increasing:
        raise ValueError("OHLCV times are not strictly chronological after sort")
    return out


def history_at(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """Inclusive slice ``[:index+1]`` — no future bars."""
    if index < 0:
        raise IndexError("index must be >= 0")
    if index >= len(df):
        raise IndexError("index past end of frame")
    return df.iloc[: index + 1].copy().reset_index(drop=True)


def assert_no_future(window: pd.DataFrame, asof: datetime) -> None:
    if window.empty:
        return
    last = pd.Timestamp(window["time"].iloc[-1]).to_pydatetime()
    if last > asof:
        raise AssertionError(f"future bar leaked: last={last} asof={asof}")
