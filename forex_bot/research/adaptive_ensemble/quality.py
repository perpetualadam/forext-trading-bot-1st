"""Candle quality checks. Never interpolates executable bid/ask."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

FX_WEEKEND_DOW_START = 4  # Friday
FX_WEEKEND_DOW_END = 6  # Sunday


def _utc_series(frame: pd.DataFrame) -> pd.Series:
    t = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    return t


def _is_weekend_gap(a: pd.Timestamp, b: pd.Timestamp) -> bool:
    if pd.isna(a) or pd.isna(b):
        return False
    span_h = (b - a).total_seconds() / 3600.0
    if span_h < 24:
        return False
    # Typical FX close Fri 21:00–Sun 21:00 (~48h). Allow 36–60h if it covers Saturday.
    if 36 <= span_h <= 60 and a.dayofweek == FX_WEEKEND_DOW_START and b.dayofweek == FX_WEEKEND_DOW_END:
        return True
    return 36 <= span_h <= 72 and a.dayofweek >= FX_WEEKEND_DOW_START


def validate_frame(frame: pd.DataFrame, *, pair: str, bar_minutes: int = 5) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    status = "PASS"
    if "time" not in frame.columns:
        return {"pair": pair, "status": "FAIL", "issues": [{"code": "missing_time"}]}
    t = _utc_series(frame)
    if t.isna().any():
        issues.append({"code": "unparseable_timestamps", "n": int(t.isna().sum())})
        status = "FAIL"
    if not t.is_monotonic_increasing:
        issues.append({"code": "not_chronological"})
        status = "FAIL"
    dups = int(t.duplicated().sum())
    if dups:
        issues.append({"code": "duplicate_timestamps", "n": dups})
        status = "FAIL"
    expected = pd.Timedelta(minutes=bar_minutes)
    unexpected_gaps = 0
    weekend_gaps = 0
    dst_odd = 0
    deltas = t.diff()
    for i, delta in enumerate(deltas):
        if i == 0 or pd.isna(delta):
            continue
        sec = float(delta.total_seconds())
        if abs(sec - expected.total_seconds()) <= 1:
            continue
        a, b = t.iloc[i - 1], t.iloc[i]
        if _is_weekend_gap(a, b):
            weekend_gaps += 1
            continue
        unexpected_gaps += 1
        if 3 * 60 <= sec <= 7 * 60 and abs(sec - 300) > 1:
            dst_odd += 1
    if unexpected_gaps:
        issues.append({"code": "unexpected_gaps", "n": unexpected_gaps})
        if status != "FAIL":
            status = "WARN"
    incomplete = 0
    if "complete" in frame.columns:
        col = frame["complete"]
        incomplete = int((~col.fillna(True).astype(bool)).sum())
        if incomplete:
            issues.append({"code": "incomplete_candles_present", "n": incomplete})
            status = "FAIL"
    o = pd.to_numeric(frame["open"], errors="coerce") if "open" in frame.columns else pd.Series(dtype=float)
    h = pd.to_numeric(frame["high"], errors="coerce") if "high" in frame.columns else pd.Series(dtype=float)
    l = pd.to_numeric(frame["low"], errors="coerce") if "low" in frame.columns else pd.Series(dtype=float)
    c = pd.to_numeric(frame["close"], errors="coerce") if "close" in frame.columns else pd.Series(dtype=float)
    ohlc = pd.concat([o, h, l, c], axis=1)
    nonfinite = int((~np.isfinite(ohlc.to_numpy(dtype=float))).any(axis=1).sum()) if len(ohlc) else 0
    ohlc_bad = int(
        (
            (h < l)
            | (h < np.maximum(o, c))
            | (l > np.minimum(o, c))
            | (ohlc.min(axis=1) <= 0)
        ).fillna(False).sum()
    )
    bid_ask = all(col in frame.columns for col in ("bid_close", "ask_close"))
    spread_bad = 0
    if bid_ask:
        b = pd.to_numeric(frame["bid_close"], errors="coerce")
        a = pd.to_numeric(frame["ask_close"], errors="coerce")
        spread_bad = int(
            ((~np.isfinite(b)) | (~np.isfinite(a)) | (b <= 0) | (a <= 0) | (b > a)).sum()
        )
    prev = c.shift(1)
    jumps = int((prev.gt(0) & ((c / prev) - 1.0).abs().gt(0.01)).sum())
    if ohlc_bad:
        issues.append({"code": "ohlc_invalid", "n": ohlc_bad})
        status = "FAIL"
    if spread_bad:
        issues.append({"code": "spread_invalid", "n": spread_bad})
        status = "FAIL"
    if nonfinite:
        issues.append({"code": "nonfinite", "n": nonfinite})
        status = "FAIL"
    if jumps:
        issues.append({"code": "price_jump_gt_1pct", "n": jumps})
        if status == "PASS":
            status = "WARN"
    n = len(frame)
    warmup_ok = n >= 120
    if not warmup_ok:
        issues.append({"code": "insufficient_warmup_history", "n": n, "required": 120})
        if status == "PASS":
            status = "WARN"
    return {
        "pair": pair,
        "status": status,
        "rows": n,
        "bid_ask": bid_ask,
        "duplicate_timestamps": dups,
        "unexpected_gaps": unexpected_gaps,
        "weekend_or_closure_gaps": weekend_gaps,
        "dst_odd_spacing": dst_odd,
        "incomplete_candles": incomplete,
        "ohlc_invalid": ohlc_bad,
        "spread_invalid": spread_bad,
        "price_jumps_gt_1pct": jumps,
        "warmup_ok": warmup_ok,
        "interpolated_bid_ask": False,
        "issues": issues,
        "timestamp_convention": "UTC",
    }


def refuse_interpolate() -> str:
    return "never_interpolate_executable_bid_ask"
