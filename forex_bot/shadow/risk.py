"""Shadow-only risk gates. Do not apply these to the live bot."""

from __future__ import annotations

from datetime import datetime, time, timezone

from forex_bot.session_rules import volatility_ok
from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.reasons import ShadowReason


def _naive_utc(ts: datetime) -> datetime:
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def fx_week_open(ts: datetime, cfg: ShadowConfig) -> bool:
    now = _naive_utc(ts)
    close_t = time(cfg.fx_week_close_hour, 0)
    wd = now.weekday()
    t = now.time()
    if wd == 5:
        return False
    if wd == 6:
        return t >= close_t
    if wd == 4:
        return t < close_t
    return True


def weekend_flatten(ts: datetime, cfg: ShadowConfig) -> bool:
    now = _naive_utc(ts)
    if cfg.weekend_flatten_minutes <= 0 or now.weekday() != 4:
        return False
    if not fx_week_open(now, cfg):
        return False
    close_dt = datetime.combine(now.date(), time(cfg.fx_week_close_hour, 0))
    minutes_left = (close_dt - now).total_seconds() / 60.0
    return 0 < minutes_left <= cfg.weekend_flatten_minutes


def session_blocks_entry(ts: datetime, cfg: ShadowConfig) -> str | None:
    if not fx_week_open(ts, cfg):
        return ShadowReason.SESSION_REJECT
    if weekend_flatten(ts, cfg):
        return ShadowReason.SESSION_REJECT
    return None


def quant_blocks(df) -> str | None:
    if df is None or df.empty:
        return ShadowReason.INSUFFICIENT_DATA
    if not volatility_ok(df):
        return ShadowReason.QUANT_REJECT
    return None


def spread_too_wide(half_spread: float, atr: float, cfg: ShadowConfig) -> bool:
    if atr <= 1e-15:
        return True
    return (float(half_spread) / float(atr)) > cfg.max_half_spread_over_atr


def utc_day_key(ts: datetime) -> str:
    now = _naive_utc(ts)
    return now.date().isoformat()
