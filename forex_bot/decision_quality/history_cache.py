"""Local historical M5 cache: validate, merge, resume ranges. No broker I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from forex_bot.session_rules import fx_market_open_at
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS, normalize_oanda_symbol

RESEARCH_SYMBOLS: tuple[str, ...] = tuple(DEFAULT_FOREX_SYMBOLS)
GRANULARITY = "M5"
BAR_MINUTES = 5
ALLOWED_GRANULARITIES = ("M5", "M1")
GRANULARITY_MINUTES = {"M5": 5, "M1": 1}
CANONICAL_MID = ("time", "open", "high", "low", "close")
OPTIONAL_FIELDS = (
    "volume",
    "complete",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)
CSV_COLUMNS = CANONICAL_MID + OPTIONAL_FIELDS


def default_historical_dir(root: Path | None = None) -> Path:
    if root is None:
        root = Path(__file__).resolve().parents[2]
    return root / "data" / "historical"


def cache_filename(symbol: str, granularity: str = GRANULARITY) -> str:
    return f"{normalize_oanda_symbol(symbol)}_{granularity}.csv"


def cache_path(symbol: str, data_dir: Path | None = None, granularity: str = GRANULARITY) -> Path:
    return (data_dir or default_historical_dir()) / cache_filename(symbol, granularity)


def to_naive_utc(dt: datetime | pd.Timestamp) -> datetime:
    ts = pd.Timestamp(dt)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def last_completed_bar_start(now_utc: datetime | None = None, bar_minutes: int = BAR_MINUTES) -> datetime:
    """Latest bar *start* whose period is already finished. Never the forming candle."""
    now = to_naive_utc(now_utc or datetime.now(timezone.utc))
    width = max(1, int(bar_minutes))
    complete_end = now - timedelta(minutes=width)
    minute = (complete_end.minute // width) * width
    return complete_end.replace(minute=minute, second=0, microsecond=0)


def last_completed_m5_start(now_utc: datetime | None = None) -> datetime:
    """Latest M5 *start* whose 5-minute bar is already finished. Never the forming candle."""
    return last_completed_bar_start(now_utc, BAR_MINUTES)


def default_m1_historical_dir(root: Path | None = None) -> Path:
    return default_historical_dir(root) / "m1"


def twelve_complete_months_utc(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Most recent 12 *complete calendar months* in UTC, clipped so the end is a completed M5.

    Example: on 2026-09-16 → 2025-09-01 00:00:00 through last completed M5 of 2026-08-31.
    """
    now = to_naive_utc(now_utc or datetime.now(timezone.utc))
    first_this_month = datetime(now.year, now.month, 1)
    start = datetime(first_this_month.year - 1, first_this_month.month, 1)
    last_month_end = first_this_month - timedelta(minutes=BAR_MINUTES)
    end = min(last_month_end, last_completed_m5_start(now))
    if end < start:
        end = start
    return start, end


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CSV_COLUMNS))


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_frame()
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    if "time" not in out.columns:
        raise ValueError("frame missing time column")
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    if out["time"].isna().any():
        raise ValueError("unparseable timestamps")
    out["time"] = out["time"].dt.tz_convert("UTC").dt.tz_localize(None)
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            raise ValueError(f"frame missing {col}")
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in OPTIONAL_FIELDS:
        if col not in out.columns:
            out[col] = pd.NA
        elif col != "complete":
            if col == "volume":
                out[col] = pd.to_numeric(out[col], errors="coerce")
            elif col.startswith("bid_") or col.startswith("ask_"):
                out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    return out.loc[:, [c for c in CSV_COLUMNS if c in out.columns]]


def exclude_incomplete(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "complete" not in df.columns:
        return df
    flag = df["complete"]
    keep = flag.isna() | flag.astype(str).str.lower().isin(("1", "true", "yes", "t"))
    # Explicit False / 0 / incomplete dropped.
    drop = flag.astype(str).str.lower().isin(("0", "false", "no", "f", "incomplete"))
    return df.loc[keep & ~drop].reset_index(drop=True)


@dataclass
class ValidationReport:
    ok: bool
    symbol: str
    granularity: str
    bars: int
    earliest: datetime | None = None
    latest: datetime | None = None
    errors: list[str] = field(default_factory=list)
    expected_weekend_gaps: int = 0
    unexpected_gaps: int = 0
    unexpected_gap_examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "symbol": self.symbol,
            "granularity": self.granularity,
            "bars": self.bars,
            "earliest": self.earliest.isoformat() if self.earliest else None,
            "latest": self.latest.isoformat() if self.latest else None,
            "errors": list(self.errors),
            "expected_weekend_gaps": self.expected_weekend_gaps,
            "unexpected_gaps": self.unexpected_gaps,
            "unexpected_gap_examples": list(self.unexpected_gap_examples),
        }


def _ohlc_row_valid(open_: float, high: float, low: float, close: float) -> bool:
    if any(v != v for v in (open_, high, low, close)):  # NaN
        return False
    if high < low:
        return False
    if high < max(open_, close):
        return False
    if low > min(open_, close):
        return False
    return True


def classify_gap(prev_start: datetime, next_start: datetime, bar_minutes: int = BAR_MINUTES) -> str:
    """``none``, ``expected_weekend``, or ``unexpected`` between two candle starts."""
    prev_start = to_naive_utc(prev_start)
    next_start = to_naive_utc(next_start)
    step = timedelta(minutes=max(1, int(bar_minutes)))
    expected = prev_start + step
    if next_start <= prev_start:
        return "unexpected"
    if next_start == expected:
        return "none"
    saw_open = False
    saw_closed = False
    cursor = expected
    safety = 0
    while cursor < next_start and safety < 20_000:
        safety += 1
        if fx_market_open_at(cursor):
            saw_open = True
        else:
            saw_closed = True
        cursor += step
    if saw_open:
        return "unexpected"
    if saw_closed:
        return "expected_weekend"
    return "unexpected"


def validate_frame(
    df: pd.DataFrame,
    *,
    symbol: str,
    granularity: str = GRANULARITY,
    now_utc: datetime | None = None,
    require_complete_only: bool = True,
) -> ValidationReport:
    now = to_naive_utc(now_utc or datetime.now(timezone.utc))
    gran = str(granularity or GRANULARITY).upper()
    report = ValidationReport(ok=True, symbol=normalize_oanda_symbol(symbol), granularity=gran, bars=0)
    if gran not in ALLOWED_GRANULARITIES:
        report.ok = False
        report.errors.append(f"timeframe {gran} is not one of {ALLOWED_GRANULARITIES}")
    bar_minutes = GRANULARITY_MINUTES.get(gran, BAR_MINUTES)
    try:
        frame = normalize_frame(df)
    except ValueError as exc:
        report.ok = False
        report.errors.append(str(exc))
        return report
    if require_complete_only:
        frame = exclude_incomplete(frame)
    report.bars = int(len(frame))
    if frame.empty:
        report.errors.append("no bars")
        report.ok = False
        return report
    times = frame["time"]
    if times.duplicated().any():
        report.ok = False
        report.errors.append("duplicate timestamps")
    if not times.is_monotonic_increasing:
        report.ok = False
        report.errors.append("timestamps not strictly increasing")
    if times.nunique() != len(times):
        report.ok = False
        report.errors.append("duplicate timestamps after unique check")
    last_complete = last_completed_bar_start(now, bar_minutes)
    if to_naive_utc(times.iloc[-1]) > last_complete:
        report.ok = False
        report.errors.append("future or still-forming candle present")
    for i, row in frame.iterrows():
        if not _ohlc_row_valid(float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])):
            report.ok = False
            report.errors.append(f"invalid OHLC at {row['time']}")
            break
        _ = i
    report.earliest = to_naive_utc(times.iloc[0])
    report.latest = to_naive_utc(times.iloc[-1])
    for a, b in zip(times.iloc[:-1], times.iloc[1:]):
        kind = classify_gap(to_naive_utc(a), to_naive_utc(b), bar_minutes=bar_minutes)
        if kind == "expected_weekend":
            report.expected_weekend_gaps += 1
        elif kind == "unexpected":
            report.unexpected_gaps += 1
            if len(report.unexpected_gap_examples) < 8:
                report.unexpected_gap_examples.append(f"{to_naive_utc(a).isoformat()} → {to_naive_utc(b).isoformat()}")
    # Unexpected gaps are reported, not treated as file corruption.
    report.ok = report.ok and not report.errors
    return report


def write_canonical_csv(df: pd.DataFrame, path: Path) -> Path:
    import os
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = normalize_frame(df)
    frame = exclude_incomplete(frame)
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    price_cols = [c for c in cols_except_time_volume_complete(out) if c in out.columns]
    for col in price_cols:
        out[col] = out[col].map(_fmt_price)
    if "volume" in out.columns:
        out["volume"] = out["volume"].map(_fmt_volume)
    cols = [c for c in CSV_COLUMNS if c in out.columns]
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    out.to_csv(tmp, index=False, columns=cols, lineterminator="\n")
    last_exc: Exception | None = None
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            last_exc = None
            break
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.4 * (attempt + 1))
    if last_exc is not None:
        out.to_csv(path, index=False, columns=cols, lineterminator="\n")
        try:
            tmp.unlink()
        except OSError:
            pass
    return path


def cols_except_time_volume_complete(df: pd.DataFrame) -> list[str]:
    skip = {"time", "volume", "complete"}
    return [c for c in df.columns if c not in skip]


def _fmt_price(val: object) -> str:
    if val is None or (isinstance(val, float) and val != val) or pd.isna(val):
        return ""
    return f"{float(val):.8f}"


def _fmt_volume(val: object) -> str:
    if val is None or (isinstance(val, float) and val != val) or pd.isna(val):
        return ""
    return str(int(round(float(val))))


def read_canonical_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return empty_frame()
    raw = pd.read_csv(path)
    return exclude_incomplete(normalize_frame(raw))


def merge_frames(*frames: pd.DataFrame) -> pd.DataFrame:
    nonempty = [normalize_frame(f) for f in frames if f is not None and not f.empty]
    if not nonempty:
        return empty_frame()
    return normalize_frame(pd.concat(nonempty, ignore_index=True))


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime


def missing_windows(
    existing: pd.DataFrame,
    start: datetime,
    end: datetime,
    bar_minutes: int = BAR_MINUTES,
    fill_internal_gaps: bool = True,
) -> list[TimeWindow]:
    """Inclusive UTC windows still needed inside ``[start, end]`` (candle start times)."""
    start_u = to_naive_utc(start)
    end_u = to_naive_utc(end)
    step = timedelta(minutes=max(1, int(bar_minutes)))
    if start_u > end_u:
        return []
    frame = normalize_frame(existing)
    if not frame.empty:
        ts = pd.to_datetime(frame["time"])
        mask = (ts >= pd.Timestamp(start_u)) & (ts <= pd.Timestamp(end_u))
        frame = frame.loc[mask].reset_index(drop=True)
    if frame.empty:
        return [TimeWindow(start_u, end_u)]

    windows: list[TimeWindow] = []
    first = to_naive_utc(frame["time"].iloc[0])
    last = to_naive_utc(frame["time"].iloc[-1])
    if first > start_u:
        windows.append(TimeWindow(start_u, first - step))
    if fill_internal_gaps:
        prev = first
        for raw in frame["time"].iloc[1:]:
            cur = to_naive_utc(raw)
            if cur > prev + step:
                windows.append(TimeWindow(prev + step, cur - step))
            prev = cur
    if last < end_u:
        windows.append(TimeWindow(last + step, end_u))
    return [w for w in windows if w.start <= w.end]


def resume_and_fetch(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    existing: pd.DataFrame,
    fetch_page,
    max_candles: int = 2000,
    bar_minutes: int = BAR_MINUTES,
    on_page=None,
    checkpoint_every: int = 0,
    fill_internal_gaps: bool = True,
) -> tuple[pd.DataFrame, list[TimeWindow]]:
    """
    Fetch only missing pages via ``fetch_page(symbol, page_start, page_end) -> DataFrame``.
    ``fetch_page`` is injected so unit tests never touch the network.
    Optional ``on_page(merged_df, page_index, page)`` every ``checkpoint_every`` pages.
    """
    needed = missing_windows(
        existing, start, end, bar_minutes=bar_minutes, fill_internal_gaps=fill_internal_gaps
    )
    pages: list[TimeWindow] = []
    frames: list[pd.DataFrame] = [existing]
    for window in needed:
        for page in iter_page_windows(
            window.start, window.end, max_candles=max_candles, bar_minutes=bar_minutes
        ):
            pages.append(page)
            chunk = fetch_page(symbol, page.start, page.end)
            if chunk is not None and not getattr(chunk, "empty", True):
                frames.append(chunk)
            if on_page is not None and checkpoint_every and len(pages) % int(checkpoint_every) == 0:
                on_page(merge_frames(*frames), len(pages), page)
    merged = merge_frames(*frames)
    return merged, pages


def iter_page_windows(
    start: datetime,
    end: datetime,
    *,
    max_candles: int = 2000,
    bar_minutes: int = BAR_MINUTES,
) -> list[TimeWindow]:
    """Deterministic OANDA-sized pages. ``max_candles`` inclusive capacity per request."""
    start_u = to_naive_utc(start)
    end_u = to_naive_utc(end)
    if start_u > end_u:
        return []
    cap = max(2, int(max_candles))
    span = timedelta(minutes=bar_minutes * (cap - 1))
    out: list[TimeWindow] = []
    cur = start_u
    safety = 0
    while cur <= end_u and safety < 20_000:
        safety += 1
        page_end = min(cur + span, end_u)
        out.append(TimeWindow(cur, page_end))
        cur = page_end + timedelta(minutes=bar_minutes)
    return out
