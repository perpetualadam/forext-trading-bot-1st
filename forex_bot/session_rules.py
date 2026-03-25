"""Session windows, pre-close sizing, and volatility filter."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

SESSION_WINDOWS: dict[str, list[tuple[str, str]]] = {
    "EUR_USD": [("08:00", "22:00")],
    "GBP_USD": [("08:00", "22:00")],
    "USD_JPY": [("00:00", "09:00"), ("13:00", "22:00")],
}


def in_active_session(symbol: str) -> bool:
    now_utc = datetime.utcnow()
    sessions = SESSION_WINDOWS.get(symbol, [("00:00", "23:59")])
    for start, end in sessions:
        s = datetime.strptime(start, "%H:%M").replace(
            year=now_utc.year, month=now_utc.month, day=now_utc.day
        )
        e = datetime.strptime(end, "%H:%M").replace(
            year=now_utc.year, month=now_utc.month, day=now_utc.day
        )
        if s <= now_utc <= e:
            return True
    return False


def pre_close_adjustment(symbol: str) -> bool:
    now_utc = datetime.utcnow()
    sessions = SESSION_WINDOWS.get(symbol, [])
    for start, end in sessions:
        _ = start
        e = datetime.strptime(end, "%H:%M").replace(
            year=now_utc.year, month=now_utc.month, day=now_utc.day
        )
        delta_min = (e - now_utc).total_seconds() / 60.0
        if 0 < delta_min < 15:
            return True
    return False


def volatility_ok(df: pd.DataFrame) -> bool:
    atr = df["atr"]
    if len(atr) < 20 or atr.iloc[-1] != atr.iloc[-1]:  # NaN check
        return True
    atr_latest = float(atr.iloc[-1])
    valid = atr.dropna()
    if len(valid) < 20:
        return True
    p90 = float(np.percentile(valid, 90))
    p10 = float(np.percentile(valid, 10))
    if atr_latest > p90 * 2 or atr_latest < p10 * 0.5:
        return False
    return True
