"""Session windows, pre-close sizing, volatility filter, and live execution windows (UTC)."""

from __future__ import annotations

import os
from datetime import datetime, time, timezone

import numpy as np
import pandas as pd

SESSION_WINDOWS: dict[str, list[tuple[str, str]]] = {
    "EUR_USD": [("08:00", "22:00")],
    "GBP_USD": [("08:00", "22:00")],
    "USD_JPY": [("00:00", "09:00"), ("13:00", "22:00")],
}


def _as_naive_utc(dt: datetime) -> datetime:
    """Normalize to naive UTC for comparisons with session windows."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def in_active_session_at(symbol: str, at_utc: datetime) -> bool:
    """Like :func:`in_active_session` but for a historical UTC timestamp (backtests)."""
    now_utc = _as_naive_utc(at_utc)
    if not fx_market_open_at(now_utc):
        return False
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


def fx_market_open_at(at_utc: datetime) -> bool:
    """
    Approximate FX week: closed from Friday 21:00 UTC through Sunday 21:00 UTC.

    Tunable via ``FX_WEEK_CLOSE_UTC`` / ``FX_WEEK_OPEN_UTC`` (``%H:%M``, defaults 21:00).
    """
    now_utc = _as_naive_utc(at_utc)
    close_t = _parse_hhmm_utc(os.getenv("FX_WEEK_CLOSE_UTC", "21:00"), "21:00")
    open_t = _parse_hhmm_utc(os.getenv("FX_WEEK_OPEN_UTC", "21:00"), "21:00")
    wd = now_utc.weekday()  # Mon=0 ... Sun=6
    t = now_utc.time()
    if wd == 5:  # Saturday
        return False
    if wd == 6:  # Sunday
        return t >= open_t
    if wd == 4:  # Friday
        return t < close_t
    return True


def fx_market_open() -> bool:
    return fx_market_open_at(datetime.utcnow())


def in_active_session(symbol: str) -> bool:
    return in_active_session_at(symbol, datetime.utcnow())


def pre_close_adjustment_at(symbol: str, at_utc: datetime) -> bool:
    """Like :func:`pre_close_adjustment` for a historical UTC timestamp."""
    now_utc = _as_naive_utc(at_utc)
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


def pre_close_adjustment(symbol: str) -> bool:
    return pre_close_adjustment_at(symbol, datetime.utcnow())


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


def _parse_hhmm_utc(value: str, fallback: str) -> time:
    raw = (value or "").strip() or fallback
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        return datetime.strptime(fallback, "%H:%M").time()


def _in_utc_hhmm_window(start: time, end: time, now: time) -> bool:
    """Inclusive bounds; if ``start > end``, the window crosses UTC midnight."""
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _scalp_bounds_from_env(symbol: str) -> tuple[time, time] | None:
    """Return scalp (start, end) only if both ``SCALP_<SYM>_START`` and ``_END`` are set and valid."""
    sym = symbol.upper().strip()
    start_raw = (os.getenv(f"SCALP_{sym}_START") or "").strip()
    end_raw = (os.getenv(f"SCALP_{sym}_END") or "").strip()
    if not start_raw or not end_raw:
        return None
    try:
        return (
            datetime.strptime(start_raw, "%H:%M").time(),
            datetime.strptime(end_raw, "%H:%M").time(),
        )
    except ValueError:
        return None


def read_scalp_windows() -> dict[str, tuple[time, time]]:
    """Snapshot of optional scalp windows from env (UTC). Re-read after process restart if .env changes."""
    out: dict[str, tuple[time, time]] = {}
    for sym in ("EUR_USD", "GBP_USD", "USD_JPY"):
        b = _scalp_bounds_from_env(sym)
        if b:
            out[sym] = b
    return out


# Optional intraday sub-window for live fills; see ``read_scalp_windows()`` for live env values.
SCALP_WINDOWS: dict[str, tuple[time, time]] = read_scalp_windows()


def is_live_trading(symbol: str, use_scalp_window: bool = False) -> bool:
    """
    True if current UTC time is inside the configured live *order* window for ``symbol``.

    Env: ``LIVE_<SYMBOL>_START`` / ``LIVE_<SYMBOL>_END`` (``%H:%M``, UTC), e.g. ``LIVE_EUR_USD_START``.
    If ``start <= end``, the window is same calendar day; if ``start > end``, it spans midnight.
    Missing or invalid LIVE times fall back to ``13:00``–``17:00`` UTC for that symbol.

    When ``use_scalp_window`` is True and both ``SCALP_<SYMBOL>_START`` / ``_END`` are set, the caller
    must also be inside that scalp sub-window (intersection with LIVE). If SCALP vars are unset,
    behaviour matches the full LIVE window only.
    """
    sym = symbol.upper().strip()
    live_start = _parse_hhmm_utc(os.getenv(f"LIVE_{sym}_START", "13:00"), "13:00")
    live_end = _parse_hhmm_utc(os.getenv(f"LIVE_{sym}_END", "17:00"), "17:00")
    now = datetime.utcnow().time()
    if not _in_utc_hhmm_window(live_start, live_end, now):
        return False
    if not use_scalp_window:
        return True
    scalp = _scalp_bounds_from_env(sym)
    if scalp is None:
        return True
    s_start, s_end = scalp
    return _in_utc_hhmm_window(s_start, s_end, now)


def execution_simulations_enabled(symbol: str, paper_trading: bool) -> bool:
    """
    Returns ``False`` **only** when ``not paper_trading`` and ``is_live_trading(symbol)`` (broker-live path).
    Otherwise ``True`` so latency / impact / spread / slippage run for paper or off-window learning.

    Summary: ``PAPER_TRADING=true`` → simulations on; ``PAPER_TRADING=false`` and inside ``LIVE_*`` → off;
    ``PAPER_TRADING=false`` and outside window → on (``window_paper`` learning path).
    """
    if paper_trading:
        return True
    return not is_live_trading(symbol)


def simulation_layers_enabled(symbol: str, paper_trading: bool) -> bool:
    """
    Same as :func:`execution_simulations_enabled` unless ``SIMULATION_<SYMBOL>=false`` (or 0/off),
    which forces **off** even for paper / off-window (raw mid only).
    ``SIMULATION_<SYMBOL>=true`` leaves the default behaviour (explicit opt-in, same as unset).
    """
    sym = symbol.upper().strip()
    raw = (os.getenv(f"SIMULATION_{sym}") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return execution_simulations_enabled(symbol, paper_trading)
