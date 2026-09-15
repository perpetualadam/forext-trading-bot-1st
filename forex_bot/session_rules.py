"""Session windows, pre-close sizing, volatility filter, and live execution windows.

``LIVE_*_START`` / ``LIVE_*_END`` are wall-clock times in ``LIVE_TIMEZONE`` (not raw UTC).
``Europe/London`` (and UK aliases) switch BST vs GMT on their own. ``auto`` uses the host
or ``TZ`` env zone so you do not retune hours when the clocks change.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TZ_ALIASES = {
    "bst": "Europe/London",
    "gmt": "Europe/London",
    "uk": "Europe/London",
    "gb": "Europe/London",
    "london": "Europe/London",
    "britain": "Europe/London",
    "england": "Europe/London",
}

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


def _parse_hhmm(value: str, fallback: str) -> time:
    raw = (value or "").strip() or fallback
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        return datetime.strptime(fallback, "%H:%M").time()


def _parse_hhmm_utc(value: str, fallback: str) -> time:
    """Backward-compatible alias for :func:`_parse_hhmm`."""
    return _parse_hhmm(value, fallback)


def _in_hhmm_window(start: time, end: time, now: time) -> bool:
    """Inclusive bounds; if ``start > end``, the window crosses midnight in that clock."""
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _in_utc_hhmm_window(start: time, end: time, now: time) -> bool:
    """Backward-compatible alias for :func:`_in_hhmm_window`."""
    return _in_hhmm_window(start, end, now)


def _zone_from_name(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def resolve_live_timezone() -> tuple[Any, str, str]:
    """
    Timezone used to interpret ``LIVE_*`` / ``SCALP_*`` clock times.

    - ``LIVE_TIMEZONE=auto`` / ``local`` / ``system`` / empty: ``TZ`` env, then OS local zone.
    - Named IANA zone (``Europe/London``) or aliases (``BST``, ``UK``, ``GMT``): that zone.
      ``Europe/London`` applies BST vs GMT from the calendar date — no seasonal .env edits.
    """
    raw = (os.getenv("LIVE_TIMEZONE") or "auto").strip()
    auto = raw.lower() in ("", "auto", "local", "system")

    if auto:
        tz_env = (os.getenv("TZ") or "").strip()
        if tz_env:
            mapped = _TZ_ALIASES.get(tz_env.lower(), tz_env)
            z = _zone_from_name(mapped)
            if z is not None:
                return z, getattr(z, "key", mapped), "TZ"
        local = datetime.now().astimezone()
        key = getattr(local.tzinfo, "key", None)
        if key:
            z = _zone_from_name(key)
            if z is not None:
                return z, key, "system"
        if local.tzinfo is not None:
            return local.tzinfo, key or str(local.tzinfo), "system"
        fallback = _zone_from_name("Europe/London")
        if fallback is not None:
            return fallback, "Europe/London", "fallback"
        return timezone.utc, "UTC", "fallback"

    mapped = _TZ_ALIASES.get(raw.lower(), raw)
    z = _zone_from_name(mapped)
    if z is not None:
        return z, getattr(z, "key", mapped), "LIVE_TIMEZONE"
    logger.warning("LIVE_TIMEZONE=%r is not a known zone; using UTC", raw)
    return timezone.utc, "UTC", "invalid_LIVE_TIMEZONE"


def _aware_utc(at_utc: datetime | None) -> datetime:
    if at_utc is None:
        return datetime.now(timezone.utc)
    if at_utc.tzinfo is None:
        return at_utc.replace(tzinfo=timezone.utc)
    return at_utc.astimezone(timezone.utc)


def _local_clock(at_utc: datetime | None = None) -> tuple[datetime, datetime, Any, str, str]:
    tz, tz_name, source = resolve_live_timezone()
    now_utc = _aware_utc(at_utc)
    now_local = now_utc.astimezone(tz)
    return now_utc, now_local, tz, tz_name, source


def _hhmm_as_utc_label(local_day: datetime, hhmm: time, tz) -> str:
    local_dt = datetime.combine(local_day.date(), hhmm, tzinfo=tz)
    return local_dt.astimezone(timezone.utc).strftime("%H:%M")


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
    """Snapshot of optional scalp windows from env (same zone as LIVE_*). Re-read after restart."""
    out: dict[str, tuple[time, time]] = {}
    for sym in ("EUR_USD", "GBP_USD", "USD_JPY"):
        b = _scalp_bounds_from_env(sym)
        if b:
            out[sym] = b
    return out


# Optional intraday sub-window for live fills; see ``read_scalp_windows()`` for live env values.
SCALP_WINDOWS: dict[str, tuple[time, time]] = read_scalp_windows()


def symbol_live_window_status(
    symbol: str,
    *,
    use_scalp_window: bool = False,
    at_utc: datetime | None = None,
) -> dict[str, Any]:
    """One-symbol live-window snapshot (local clock, UTC equivalent, in/out)."""
    now_utc, now_local, tz, tz_name, source = _local_clock(at_utc)
    sym = symbol.upper().strip()
    live_start = _parse_hhmm(os.getenv(f"LIVE_{sym}_START", "13:00"), "13:00")
    live_end = _parse_hhmm(os.getenv(f"LIVE_{sym}_END", "17:00"), "17:00")
    inside_live = _in_hhmm_window(live_start, live_end, now_local.time())
    scalp = _scalp_bounds_from_env(sym) if use_scalp_window else None
    inside_scalp = True
    scalp_local = None
    scalp_utc = None
    if scalp is not None:
        s_start, s_end = scalp
        inside_scalp = _in_hhmm_window(s_start, s_end, now_local.time())
        scalp_local = f"{s_start.strftime('%H:%M')}-{s_end.strftime('%H:%M')}"
        scalp_utc = f"{_hhmm_as_utc_label(now_local, s_start, tz)}-{_hhmm_as_utc_label(now_local, s_end, tz)}"
    inside = inside_live and inside_scalp
    dst_label = now_local.tzname() or tz_name
    return {
        "symbol": sym,
        "timezone": tz_name,
        "timezone_source": source,
        "dst_label": dst_label,
        "utc_offset": now_local.strftime("%z"),
        "now_local": now_local.strftime("%Y-%m-%d %H:%M"),
        "now_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "local_window": f"{live_start.strftime('%H:%M')}-{live_end.strftime('%H:%M')}",
        "utc_window": (
            f"{_hhmm_as_utc_label(now_local, live_start, tz)}-"
            f"{_hhmm_as_utc_label(now_local, live_end, tz)}"
        ),
        "inside_live": inside_live,
        "inside_scalp": inside_scalp if scalp is not None else None,
        "scalp_local": scalp_local,
        "scalp_utc": scalp_utc,
        "inside": inside,
    }


def live_windows_status(
    symbols: list[str] | None = None,
    *,
    use_scalp_window: bool = False,
    at_utc: datetime | None = None,
) -> dict[str, Any]:
    """Full live-window status for logs and ``/health`` / ``/system``."""
    from forex_bot.config import Config
    from forex_bot.execution import (
        broker_orders_enabled,
        effective_paper_trading,
        get_execution_mode,
    )

    now_utc, now_local, _tz, tz_name, source = _local_clock(at_utc)
    syms = list(symbols or getattr(Config, "SYMBOLS", ["EUR_USD", "GBP_USD", "USD_JPY"]))
    per = [symbol_live_window_status(s, use_scalp_window=use_scalp_window, at_utc=at_utc) for s in syms]

    paper = effective_paper_trading()
    any_inside = any(p["inside"] for p in per)
    broker_on = broker_orders_enabled()
    if paper:
        fills = "paper (EXECUTION_MODE=paper / PAPER_TRADING) — never sends broker orders"
    elif any_inside and broker_on:
        fills = "live broker — symbols inside the window send OANDA market orders"
    elif any_inside and not broker_on:
        fills = "blocked — inside live window but broker orders disabled (fail closed, no local live fill)"
    else:
        fills = "window_paper — outside local live hours; simulated fills until the window opens"
    return {
        "timezone": tz_name,
        "timezone_source": source,
        "dst_label": now_local.tzname() or tz_name,
        "utc_offset": now_local.strftime("%z"),
        "now_local": now_local.strftime("%Y-%m-%d %H:%M"),
        "now_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "execution_mode": get_execution_mode().value,
        "paper_trading": paper,
        "broker_orders_enabled": broker_on,
        "any_symbol_inside": any_inside,
        "fills": fills,
        "symbols": per,
    }


def format_live_window_log(status: dict[str, Any] | None = None) -> str:
    """Single-line [LIVE WINDOW] summary for logs, Telegram, and BOT STARTED."""
    snap = status if status is not None else live_windows_status()
    parts = [
        f"tz={snap['timezone']} ({snap['timezone_source']})",
        f"dst={snap['dst_label']}",
        f"offset={snap['utc_offset']}",
        f"now_local={snap['now_local']}",
        f"now_utc={snap['now_utc']}",
        f"exec={snap['execution_mode']}",
    ]
    for p in snap["symbols"]:
        flag = "IN" if p["inside"] else "OUT"
        parts.append(f"{p['symbol']} {flag} local={p['local_window']} utc={p['utc_window']}")
    parts.append(f"fills={snap['fills']}")
    return "[LIVE WINDOW] " + " | ".join(parts)


def live_window_log_enabled() -> bool:
    return (os.getenv("LIVE_WINDOW_LOG") or "1").strip().lower() not in ("0", "false", "no", "off")


def log_live_windows(*, reason: str = "status") -> str:
    """Log and return the [LIVE WINDOW] line so dashboards and alerts can reuse it."""
    line = format_live_window_log()
    logger.info("%s %s", line, f"({reason})" if reason else "")
    return line


def is_live_trading(
    symbol: str,
    use_scalp_window: bool = False,
    at_utc: datetime | None = None,
) -> bool:
    """
    True if *local* clock (see :func:`resolve_live_timezone`) is inside the live *order* window.

    Env: ``LIVE_<SYMBOL>_START`` / ``LIVE_<SYMBOL>_END`` (``%H:%M`` in ``LIVE_TIMEZONE``).
    Missing or invalid times fall back to ``13:00``–``17:00`` local.
    ``Europe/London`` in September (BST, UTC+1) makes that ``12:00``–``16:00`` UTC; in winter GMT
    it is ``13:00``–``17:00`` UTC — no manual edit.

    When ``use_scalp_window`` is True and both ``SCALP_<SYMBOL>_START`` / ``_END`` are set, the caller
    must also be inside that scalp sub-window (same timezone). If SCALP vars are unset,
    behaviour matches the full LIVE window only.
    """
    return bool(
        symbol_live_window_status(symbol, use_scalp_window=use_scalp_window, at_utc=at_utc)["inside"]
    )


def execution_simulations_enabled(
    symbol: str, paper_trading: bool, at_utc: datetime | None = None
) -> bool:
    """
    Returns ``False`` **only** when ``not paper_trading`` and ``is_live_trading(symbol)`` (broker-live path).
    Otherwise ``True`` so latency / impact / spread / slippage run for paper or off-window learning.

    Summary: ``PAPER_TRADING=true`` → simulations on; ``PAPER_TRADING=false`` and inside ``LIVE_*`` → off;
    ``PAPER_TRADING=false`` and outside window → on (``window_paper`` learning path).
    """
    if paper_trading:
        return True
    return not is_live_trading(symbol, at_utc=at_utc)


def simulation_layers_enabled(
    symbol: str, paper_trading: bool, at_utc: datetime | None = None
) -> bool:
    """
    Same as :func:`execution_simulations_enabled` unless ``SIMULATION_<SYMBOL>=false`` (or 0/off),
    which forces **off** even for paper / off-window (raw mid only).
    ``SIMULATION_<SYMBOL>=true`` leaves the default behaviour (explicit opt-in, same as unset).
    """
    sym = symbol.upper().strip()
    raw = (os.getenv(f"SIMULATION_{sym}") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return execution_simulations_enabled(symbol, paper_trading, at_utc=at_utc)
