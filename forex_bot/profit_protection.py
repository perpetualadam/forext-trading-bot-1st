"""MFE profit protection — extra close layer; does not move broker/local SL or TP."""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def profit_protection_enabled() -> bool:
    return _env_bool("PROFIT_PROTECTION_ENABLED", True)


def profit_protection_trigger_percent() -> float:
    """Fraction of original TP distance that MFE must reach before protection activates."""
    return max(0.0, _env_float("PROFIT_PROTECTION_TRIGGER_PERCENT", 0.67))


def profit_giveback_atr_multiplier() -> float:
    return max(0.0, _env_float("PROFIT_GIVEBACK_ATR_MULTIPLIER", 0.5))


def profit_protection_atr_period() -> int:
    try:
        return max(2, int(_env_float("PROFIT_PROTECTION_ATR_PERIOD", 14.0)))
    except (TypeError, ValueError):
        return 14


def profit_giveback_pips() -> float:
    """Fallback only when ATR is unavailable/invalid (not the live giveback)."""
    return max(0.0, _env_float("PROFIT_GIVEBACK_PIPS", 4.0))


def profit_giveback_min_pips() -> float:
    return max(0.0, _env_float("PROFIT_GIVEBACK_MIN_PIPS", 0.5))


def profit_giveback_max_pips() -> float:
    return max(0.0, _env_float("PROFIT_GIVEBACK_MAX_PIPS", 30.0))


def profit_protection_close_retry_sec() -> float:
    return max(1.0, _env_float("PROFIT_PROTECTION_CLOSE_RETRY_SEC", 30.0))


def profit_protection_log_ratchet_pips() -> float:
    return max(0.0, _env_float("PROFIT_PROTECTION_LOG_RATCHET_PIPS", 1.0))


def pip_size(symbol: str) -> float:
    """OANDA-style pip: 0.01 for JPY quotes, 0.0001 otherwise."""
    s = (symbol or "").upper().replace("-", "_").replace("/", "_")
    return 0.01 if "JPY" in s else 0.0001


def unrealized_profit_pips(
    symbol: str,
    direction: str,
    entry_price: float,
    current_price: float,
) -> float:
    """Unrealised pips from entry to the current executable/mid price."""
    pip = pip_size(symbol)
    if pip <= 0:
        return 0.0
    entry = float(entry_price)
    px = float(current_price)
    d = (direction or "").upper().strip()
    if d == "SELL":
        raw = (entry - px) / pip
    else:
        raw = (px - entry) / pip
    return round(raw, 6)


def extreme_adverse_pips(
    symbol: str,
    direction: str,
    entry_price: float,
    bar_high: float,
    bar_low: float,
) -> float:
    """Worst intra-bar excursion as positive adverse pips (BUY uses low, SELL uses high)."""
    d = (direction or "").upper().strip()
    extreme = float(bar_high) if d == "SELL" else float(bar_low)
    return max(0.0, -unrealized_profit_pips(symbol, d, entry_price, extreme))


def update_mae(pos: Any, current_pips: float) -> None:
    """Track most adverse signed profit; ``max_adverse_pips`` is the positive MAE."""
    try:
        cur = float(current_pips)
        prev = float(getattr(pos, "min_profit_pips", 0.0) or 0.0)
        worst = min(prev, cur)
        pos.min_profit_pips = worst
        pos.max_adverse_pips = max(0.0, -worst)
    except (TypeError, ValueError):
        return


def note_protection_activation(
    pos: Any,
    *,
    mfe: float,
    giveback_pips: float,
    exit_pips: float,
    atr_pips: float | None,
) -> None:
    """Snapshot first-activation diagnostics only (never overwrites)."""
    if getattr(pos, "protect_activated_mfe_pips", None) is not None:
        return
    pos.protect_activated_mfe_pips = float(mfe)
    pos.protect_activated_giveback_pips = float(giveback_pips)
    pos.protect_activated_exit_pips = float(exit_pips)
    pos.protect_activated_atr_pips = None if atr_pips is None else float(atr_pips)


def current_atr_pips(
    pos: Any,
    *,
    atr_price: float | None = None,
    ohlcv: Any = None,
) -> float | None:
    from forex_bot.indicators import latest_atr_price

    px = atr_price
    if px is None and ohlcv is not None:
        px = latest_atr_price(ohlcv, profit_protection_atr_period())
    if px is None:
        return None
    return atr_to_pips(getattr(pos, "symbol", ""), px)


def original_sl_distance_pips(pos: Any) -> float | None:
    """Favourable-risk distance from entry to original SL, in pips. None if invalid."""
    pip = pip_size(getattr(pos, "symbol", "") or "")
    if pip <= 0:
        return None
    try:
        entry = float(pos.entry_price)
        sl = float(pos.stop_loss)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(entry) or not math.isfinite(sl):
        return None
    d = (getattr(pos, "direction", "") or "").upper().strip()
    if d == "SELL":
        if sl <= entry:
            return None
        dist = (sl - entry) / pip
    else:
        if sl >= entry:
            return None
        dist = (entry - sl) / pip
    dist = round(dist, 6)
    if dist <= 0:
        return None
    return dist


def extreme_favourable_pips(
    symbol: str,
    direction: str,
    entry_price: float,
    bar_high: float,
    bar_low: float,
) -> float:
    """Best intra-bar excursion in pips (BUY uses high, SELL uses low)."""
    d = (direction or "").upper().strip()
    extreme = float(bar_low) if d == "SELL" else float(bar_high)
    return max(0.0, unrealized_profit_pips(symbol, d, entry_price, extreme))


def atr_to_pips(symbol: str, atr_price: float) -> float | None:
    pip = pip_size(symbol)
    if pip <= 0:
        return None
    try:
        px = float(atr_price)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(px) or px <= 0:
        return None
    return round(px / pip, 6)


def resolve_giveback_pips(
    pos: Any,
    *,
    atr_price: float | None = None,
    ohlcv: Any = None,
) -> tuple[float, str]:
    """
    ATR × multiplier in MFE pips. Invalid ATR → logged fallback (PROFIT_GIVEBACK_PIPS).
    Does not close; caller still ratchets the protected exit.
    """
    from forex_bot.indicators import latest_atr_price

    px = atr_price
    if px is None and ohlcv is not None:
        px = latest_atr_price(ohlcv, profit_protection_atr_period())
    atr_pips = atr_to_pips(getattr(pos, "symbol", ""), px) if px is not None else None
    if atr_pips is None:
        fb = profit_giveback_pips()
        pos.atr_fallback_used = True
        if not getattr(pos, "profit_protection_atr_fallback_logged", False):
            pos.profit_protection_atr_fallback_logged = True
            logger.warning(
                "[PROFIT PROTECTION] %s | ATR unavailable/invalid/insufficient bars — "
                "fallback giveback %.1f pips (PROFIT_GIVEBACK_PIPS)",
                _pos_label(pos),
                fb,
            )
        return fb, "fallback"

    raw = atr_pips * profit_giveback_atr_multiplier()
    lo = profit_giveback_min_pips()
    hi = profit_giveback_max_pips()
    gb = raw
    source = "atr"
    if lo > 0 and gb < lo:
        gb = lo
        source = "atr_clamped"
    if hi > 0 and gb > hi:
        gb = hi
        source = "atr_clamped"
    if source == "atr_clamped" and not getattr(pos, "profit_protection_atr_clamped_logged", False):
        pos.profit_protection_atr_clamped_logged = True
        logger.warning(
            "[PROFIT PROTECTION] %s | ATR giveback %.2f pips clamped to %.2f",
            _pos_label(pos),
            raw,
            gb,
        )
    return float(gb), source


def update_protected_exit_pips(pos: Any, max_profit_pips: float, giveback_pips: float) -> float:
    """Candidate = MFE − giveback; store max(previous, candidate) so protection never loosens."""
    candidate = float(max_profit_pips) - float(giveback_pips)
    prev = getattr(pos, "profit_protection_exit_pips", None)
    if prev is not None:
        try:
            prev_f = float(prev)
        except (TypeError, ValueError):
            prev_f = None
        else:
            if math.isfinite(prev_f):
                actual = max(prev_f, candidate)
                pos.profit_protection_exit_pips = actual
                return actual
    pos.profit_protection_exit_pips = candidate
    return candidate


def original_tp_distance_pips(pos: Any) -> float | None:
    """
    Favourable distance from entry to the position's original TP, in pips.

    None if TP is missing, non-finite, zero, or on the wrong side of entry
    (BUY must have TP above entry; SELL must have TP below entry).
    """
    pip = pip_size(getattr(pos, "symbol", "") or "")
    if pip <= 0:
        return None
    try:
        entry = float(pos.entry_price)
        tp = float(pos.take_profit)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(entry) or not math.isfinite(tp):
        return None
    d = (getattr(pos, "direction", "") or "").upper().strip()
    if d == "SELL":
        if tp >= entry:
            return None
        dist = (entry - tp) / pip
    else:
        if tp <= entry:
            return None
        dist = (tp - entry) / pip
    dist = round(dist, 6)
    if dist <= 0:
        return None
    return dist


def activation_trigger_pips(pos: Any) -> float | None:
    """MFE pips required to activate: ``TP_distance * PROFIT_PROTECTION_TRIGGER_PERCENT``."""
    dist = original_tp_distance_pips(pos)
    if dist is None:
        return None
    pct = profit_protection_trigger_percent()
    if pct <= 0:
        return None
    return round(dist * pct, 6)


def mfe_meets_activation(pos: Any, max_profit_pips: float) -> bool:
    trigger = activation_trigger_pips(pos)
    if trigger is None:
        return False
    return float(max_profit_pips) + 1e-12 >= trigger


def _log_invalid_tp_once(pos: Any) -> None:
    if getattr(pos, "profit_protection_invalid_tp_logged", False):
        return
    pos.profit_protection_invalid_tp_logged = True
    logger.warning(
        "[PROFIT PROTECTION] %s | no valid original TP distance "
        "(missing, zero, or wrong side of entry) — %%-of-TP protection disabled",
        _pos_label(pos),
    )


def _to_epoch(val: Any) -> float | None:
    if val is None:
        return None
    if hasattr(val, "timestamp"):
        try:
            ts = val.timestamp()
            if getattr(val, "tzinfo", None) is None and hasattr(val, "to_pydatetime"):
                dt = val.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            return float(ts)
        except (TypeError, ValueError, OSError):
            pass
    try:
        s = str(val).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def reconstruct_mfe_from_ohlcv(
    symbol: str,
    direction: str,
    entry_price: float,
    open_time: float,
    ohlcv: Any,
    *,
    bar_seconds: float = 300.0,
) -> float | None:
    """
    Best favourable excursion from complete candles that overlap or follow entry.

    Returns None if ``ohlcv`` has no usable high/low after the open (cannot reconstruct).
    """
    if ohlcv is None:
        return None
    try:
        empty = bool(ohlcv.empty)
    except AttributeError:
        empty = len(ohlcv) == 0
    if empty:
        return None
    if "high" not in ohlcv.columns or "low" not in ohlcv.columns:
        return None
    open_epoch = float(open_time)
    best = 0.0
    saw = False
    for row in ohlcv.itertuples(index=False):
        t_raw = getattr(row, "time", None)
        t_epoch = _to_epoch(t_raw)
        if t_epoch is None or (t_epoch + float(bar_seconds)) <= open_epoch:
            continue
        hi = float(getattr(row, "high"))
        lo = float(getattr(row, "low"))
        if not math.isfinite(hi) or not math.isfinite(lo):
            continue
        saw = True
        best = max(best, extreme_favourable_pips(symbol, direction, entry_price, hi, lo))
    if not saw:
        return None
    return best


def reconstruct_mae_from_ohlcv(
    symbol: str,
    direction: str,
    entry_price: float,
    open_time: float,
    ohlcv: Any,
    *,
    bar_seconds: float = 300.0,
) -> float | None:
    """Worst adverse excursion (positive pips) from candles overlapping or after entry."""
    if ohlcv is None:
        return None
    try:
        empty = bool(ohlcv.empty)
    except AttributeError:
        empty = len(ohlcv) == 0
    if empty:
        return None
    if "high" not in ohlcv.columns or "low" not in ohlcv.columns:
        return None
    open_epoch = float(open_time)
    worst = 0.0
    saw = False
    for row in ohlcv.itertuples(index=False):
        t_raw = getattr(row, "time", None)
        t_epoch = _to_epoch(t_raw)
        if t_epoch is None or (t_epoch + float(bar_seconds)) <= open_epoch:
            continue
        hi = float(getattr(row, "high"))
        lo = float(getattr(row, "low"))
        if not math.isfinite(hi) or not math.isfinite(lo):
            continue
        saw = True
        worst = max(worst, extreme_adverse_pips(symbol, direction, entry_price, hi, lo))
    if not saw:
        return None
    return worst


@dataclass
class ProtectionDecision:
    enabled: bool
    current_pips: float
    max_profit_pips: float
    active: bool
    exit_threshold_pips: float | None
    should_close: bool
    just_activated: bool
    just_ratcheted: bool


def _pos_label(pos: Any) -> str:
    return getattr(pos, "symbol", None) or "position"


def seed_position_mfe(
    pos: Any,
    current_price: float,
    ohlcv: Any = None,
    *,
    atr_price: float | None = None,
) -> str:
    """
    Restart-safe MFE seed. Never assume 0 when current profit is positive.

    Prefer candle high/low since entry; otherwise seed from current unrealised pips.
    """
    if getattr(pos, "profit_protection_seeded", False):
        return "already"
    current = unrealized_profit_pips(pos.symbol, pos.direction, pos.entry_price, current_price)
    reconstructed = reconstruct_mfe_from_ohlcv(
        pos.symbol,
        pos.direction,
        pos.entry_price,
        float(pos.open_time),
        ohlcv,
    )
    prior = float(getattr(pos, "max_profit_pips", 0.0) or 0.0)
    if reconstructed is None:
        seeded = max(0.0, current, prior)
        source = "current"
        if current > 1e-9:
            logger.warning(
                "[PROFIT PROTECTION] %s | cannot reconstruct MFE from candles; "
                "seeding from current %.1f pips (peak since entry may be understated)",
                _pos_label(pos),
                current,
            )
    else:
        seeded = max(0.0, reconstructed, current, prior)
        source = "ohlcv"
    pos.max_profit_pips = seeded
    pos.profit_protection_seeded = True
    try:
        mae = reconstruct_mae_from_ohlcv(
            pos.symbol,
            pos.direction,
            pos.entry_price,
            float(pos.open_time),
            ohlcv,
        )
        if mae is not None:
            pos.max_adverse_pips = max(float(getattr(pos, "max_adverse_pips", 0.0) or 0.0), mae)
            pos.min_profit_pips = min(float(getattr(pos, "min_profit_pips", 0.0) or 0.0), -mae)
        update_mae(pos, current)
    except Exception:
        logger.exception("[PROFIT PROTECTION] %s | MAE seed failed (ignored)", _pos_label(pos))
    if activation_trigger_pips(pos) is None:
        _log_invalid_tp_once(pos)
    if mfe_meets_activation(pos, seeded):
        pos.profit_protection_active = True
        gb, _src = resolve_giveback_pips(pos, atr_price=atr_price, ohlcv=ohlcv)
        thresh = update_protected_exit_pips(pos, seeded, gb)
        try:
            note_protection_activation(
                pos,
                mfe=seeded,
                giveback_pips=gb,
                exit_pips=thresh,
                atr_pips=current_atr_pips(pos, atr_price=atr_price, ohlcv=ohlcv),
            )
        except Exception:
            logger.exception("[PROFIT PROTECTION] %s | activation snapshot failed (ignored)", _pos_label(pos))
        logger.info(
            "[PROFIT PROTECTION] %s | Current: %.1f pips | MFE: %.1f | "
            "Protection activated | Exit threshold: %.1f | seed=%s",
            _pos_label(pos),
            current,
            seeded,
            thresh,
            source,
        )
        pos.profit_protection_last_logged_mfe = seeded
    return source


def apply_profit_protection(
    pos: Any,
    current_price: float,
    *,
    atr_price: float | None = None,
    ohlcv: Any = None,
) -> ProtectionDecision:
    """Update MFE (never decreases) and decide whether to protect-close."""
    current = unrealized_profit_pips(pos.symbol, pos.direction, pos.entry_price, current_price)
    try:
        update_mae(pos, current)
    except Exception:
        logger.exception("[PROFIT PROTECTION] %s | MAE update failed (ignored)", _pos_label(pos))
    if not profit_protection_enabled():
        return ProtectionDecision(
            enabled=False,
            current_pips=current,
            max_profit_pips=float(getattr(pos, "max_profit_pips", 0.0) or 0.0),
            active=False,
            exit_threshold_pips=None,
            should_close=False,
            just_activated=False,
            just_ratcheted=False,
        )

    mfe = float(getattr(pos, "max_profit_pips", 0.0) or 0.0)
    just_ratcheted = False
    if current > mfe + 1e-15:
        mfe = current
        just_ratcheted = True
    pos.max_profit_pips = mfe

    if activation_trigger_pips(pos) is None:
        _log_invalid_tp_once(pos)
    was_active = bool(getattr(pos, "profit_protection_active", False))
    just_activated = False
    active = was_active
    if mfe_meets_activation(pos, mfe):
        active = True
        pos.profit_protection_active = True
        just_activated = not was_active

    thresh = None
    gb = 0.0
    if active:
        gb, _src = resolve_giveback_pips(pos, atr_price=atr_price, ohlcv=ohlcv)
        thresh = update_protected_exit_pips(pos, mfe, gb)
        if just_activated:
            try:
                note_protection_activation(
                    pos,
                    mfe=mfe,
                    giveback_pips=gb,
                    exit_pips=thresh,
                    atr_pips=current_atr_pips(pos, atr_price=atr_price, ohlcv=ohlcv),
                )
            except Exception:
                logger.exception(
                    "[PROFIT PROTECTION] %s | activation snapshot failed (ignored)",
                    _pos_label(pos),
                )
    should_close = bool(active and thresh is not None and current <= thresh + 1e-12)

    label = _pos_label(pos)
    if just_activated:
        logger.info(
            "[PROFIT PROTECTION] %s | Current: %.1f pips | MFE: %.1f | "
            "Protection activated | Exit threshold: %.1f",
            label,
            current,
            mfe,
            thresh if thresh is not None else 0.0,
        )
        pos.profit_protection_last_logged_mfe = mfe
    elif active and just_ratcheted:
        last = float(getattr(pos, "profit_protection_last_logged_mfe", -1.0) or -1.0)
        step = profit_protection_log_ratchet_pips()
        if last < 0 or (mfe - last) + 1e-12 >= step:
            logger.info(
                "[PROFIT PROTECTION] %s | Current: %.1f pips | MFE: %.1f | "
                "Exit threshold: %.1f",
                label,
                current,
                mfe,
                thresh if thresh is not None else 0.0,
            )
            pos.profit_protection_last_logged_mfe = mfe

    if should_close:
        logger.info(
            "[PROFIT PROTECTION] %s | Current: %.1f pips | MFE: %.1f | Threshold: %.1f | Closing position",
            label,
            current,
            mfe,
            thresh if thresh is not None else 0.0,
        )

    return ProtectionDecision(
        enabled=True,
        current_pips=current,
        max_profit_pips=mfe,
        active=active,
        exit_threshold_pips=thresh,
        should_close=should_close,
        just_activated=just_activated,
        just_ratcheted=just_ratcheted and active,
    )


def protection_close_allowed(pos: Any, now: float | None = None) -> bool:
    """True if we may send a protect-close (cooldown after a failed/rejected close)."""
    import time

    t = float(now if now is not None else time.time())
    last = float(getattr(pos, "profit_protection_close_attempt_ts", 0.0) or 0.0)
    if last <= 0:
        return True
    return (t - last) >= profit_protection_close_retry_sec()


def mark_protection_close_attempt(pos: Any, now: float | None = None) -> None:
    import time

    pos.profit_protection_close_attempt_ts = float(now if now is not None else time.time())
