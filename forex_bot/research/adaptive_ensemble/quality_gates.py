"""Stage G.2 validation gates. Does not drop bars. Does not run strategy P&L."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    RateTable,
)
from forex_bot.research.adaptive_ensemble.provenance import (
    STAGE_EG_END,
    overlap_with_stage_eg,
)
from forex_bot.research.adaptive_ensemble.quality import validate_frame
from forex_bot.research.adaptive_ensemble.simulator_v2 import WARMUP_BARS

CUTOFF = STAGE_EG_END


def complete_trading_days_after(frame: pd.DataFrame, *, cutoff: datetime = CUTOFF) -> int:
    if "time" not in frame.columns or frame.empty:
        return 0
    t = pd.to_datetime(frame["time"], utc=True, errors="coerce").dropna()
    t = t[t > pd.Timestamp(cutoff)]
    if t.empty:
        return 0
    days = t.dt.tz_convert("UTC").dt.date
    weekday = t.dt.dayofweek < 5
    return int(days[weekday].nunique())


def conversion_freshness(table: RateTable | None, when: datetime, *, max_age_hours: float = 24.0) -> str:
    if table is None:
        return GBP_CONVERSION_UNVERIFIED
    fx = table.last_at_or_before("GBP_USD", when)
    if fx is None:
        return GBP_CONVERSION_UNVERIFIED
    age_h = (when - fx.time).total_seconds() / 3600.0
    if age_h > max_age_hours:
        return "CONVERSION_STALE"
    return "ok"


def gate_dataset(frame: pd.DataFrame, *, pair: str) -> dict[str, Any]:
    q = validate_frame(frame, pair=pair)
    ov = overlap_with_stage_eg(frame["time"] if "time" in frame.columns else pd.Series(dtype="datetime64[ns, UTC]"))
    days = complete_trading_days_after(frame)
    warmup = len(frame) >= WARMUP_BARS
    status = q["status"]
    if ov["new_after_n"] == 0:
        indep = "PREVIOUSLY_EXAMINED"
    elif ov["overlap_n"]:
        indep = "INDEPENDENCE_NOT_ESTABLISHED"
        if status == "PASS":
            status = "WARN"
    else:
        indep = "POTENTIALLY_INDEPENDENT"
    if q.get("spread_invalid") or q.get("incomplete_candles"):
        status = "FAIL"
    return {
        **q,
        "status": status,
        "independence_label": indep,
        "complete_trading_days_after_cutoff": days,
        "warmup_ok_v2": warmup,
        "conversion": GBP_CONVERSION_UNVERIFIED,
        "promoted_to_validation_ready": False,
    }


def duration_status(days: int) -> str:
    if days < 40:
        return "INSUFFICIENT_INDEPENDENT_DURATION"
    return "ok"
