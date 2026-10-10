"""Read-only diagnostic logs for previously silent pre-sizing exits.

Does not select strategies, vote, size, or mutate performance state.
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_SKIP_LAST_TS: dict[tuple[str, str], float] = {}


def reset_skip_log_for_tests() -> None:
    _SKIP_LAST_TS.clear()


def skip_log_interval_sec() -> float:
    raw = (os.getenv("DECISION_SKIP_LOG_INTERVAL_SEC") or "60").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 60.0


def _rate_limited(symbol: str, reason: str) -> bool:
    interval = skip_log_interval_sec()
    if interval <= 0:
        return False
    key = ((symbol or "").upper(), str(reason or ""))
    now = time.monotonic()
    last = _SKIP_LAST_TS.get(key, 0.0)
    if (now - last) < interval:
        return True
    _SKIP_LAST_TS[key] = now
    return False

NO_STRATEGY_SELECTED = "NO_STRATEGY_SELECTED"
STRATEGY_INACTIVE = "STRATEGY_INACTIVE"
STRATEGY_NOT_AUTHORISED = "STRATEGY_NOT_AUTHORISED"
QUANT_MA_INVALID = "QUANT_MA_INVALID"
NO_OHLCV = "NO_OHLCV"
DECISION_CANDLES_MISSING = "decision_candles_missing"
DECISION_CANDLES_EMPTY = "decision_candles_empty"
DECISION_CANDLES_FETCH_FAILED = "decision_candles_fetch_failed"
DECISION_CANDLES_UNVERIFIED = "decision_candles_unverified"
ENTRY_SKIPPED_NO_VALID_CANDLES = "entry_skipped_no_valid_candles"
MANAGEMENT_CONTINUED_WITHOUT_CANDLES = "management_continued_without_candles"
MANAGEMENT_QUOTE_UNAVAILABLE = "management_quote_unavailable"
MANAGEMENT_QUOTE_STALE = "management_quote_stale"
PROTECTIVE_CLOSE_FAILED = "protective_close_failed"
PROTECTIVE_CLOSE_UNCONFIRMED = "protective_close_unconfirmed"
INSTRUMENT_CYCLE_FAILED = "instrument_cycle_failed"
CANDLE_ACQUISITION_FAILED = "candle_acquisition_failed"
CANDLE_PARSING_FAILED = "candle_parsing_failed"
CANDLE_INTERNAL_ERROR = "candle_internal_error"
MANAGEMENT_UNAVAILABLE = "management_unavailable"
CYCLE_INTEGRITY_FAILED = "cycle_integrity_failed"
MARKET_SESSION_CLOSED = "MARKET_SESSION_CLOSED"
WEEKEND_FLATTEN = "WEEKEND_FLATTEN"
POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
VOLATILITY_UNSAFE = "VOLATILITY_UNSAFE"
RECONCILE_OR_PRETRADE_BLOCKED = "RECONCILE_OR_PRETRADE_BLOCKED"
LIVE_ORDER_AUTH_BLOCKED = "LIVE_ORDER_AUTH_BLOCKED"
QUANT_AI_REJECTED = "QUANT_AI_REJECTED"
RL_SKIP = "RL_SKIP"
RL_DIRECTION_MISMATCH = "RL_DIRECTION_MISMATCH"
RL_STATE_UNAVAILABLE = "RL_STATE_UNAVAILABLE"
SIZING_BELOW_MIN = "SIZING_BELOW_MIN"
STALE_OR_INVALID_DATA = "STALE_OR_INVALID_DATA"
QUANT_MA_NAN = "QUANT_MA_NAN"
QUANT_MA_NOT_CLEAR = "QUANT_MA_NOT_CLEAR"
QUANT_M5_MOVE_BELOW_THRESHOLD = "QUANT_M5_MOVE_BELOW_THRESHOLD"
QUANT_ATR_NOT_OK = "QUANT_ATR_NOT_OK"
QUANT_SIGNAL_PASS = "QUANT_SIGNAL_PASS"

_REQUIRED_MA = "fast>slow+eps -> BUY; fast<slow-eps -> SELL"


def _fmt(value: Any) -> str:
    try:
        if value is None:
            return "n/a"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float):
            if math.isnan(value):
                return "nan"
            if math.isinf(value):
                return "inf"
            return "%.10g" % value
        text = str(value)
        return text if text else "n/a"
    except Exception:
        return "n/a"


def _safe_info(message: str, *args: Any) -> None:
    try:
        logger.info(message, *args)
    except Exception:
        pass


def strategy_pool_snapshot() -> list[dict[str, Any]]:
    """Observe existing strategy objects. Does not create, reset, or evolve them."""
    from forex_bot.strategy_meta import meta, strategies

    rows: list[dict[str, Any]] = []
    for name, strat in strategies.items():
        pnl = getattr(strat, "pnl", None)
        try:
            sharpe = strat.sharpe()
        except Exception:
            sharpe = None
        try:
            meta_score = meta.score(name)
        except Exception:
            meta_score = None
        rows.append(
            {
                "name": name,
                "active": bool(getattr(strat, "active", False)),
                "pnl_n": len(pnl) if pnl is not None else 0,
                "sharpe": sharpe,
                "meta_score": meta_score,
            }
        )
    return rows


def _format_strategy_pool(rows: list[dict[str, Any]]) -> str:
    parts = []
    for row in rows:
        parts.append(
            "%s:active=%s:pnl_n=%s:sharpe=%s:meta=%s"
            % (
                _fmt(row.get("name")),
                _fmt(row.get("active")),
                _fmt(row.get("pnl_n")),
                _fmt(row.get("sharpe")),
                _fmt(row.get("meta_score")),
            )
        )
    return ",".join(parts) if parts else "none"


def log_strategy_pre_sizing_skip(
    *,
    symbol: str,
    reason: str,
    selected: str | None,
    lookback: Any = None,
    horizon: Any = None,
) -> None:
    try:
        from forex_bot.decision_repair.audit import note_current_skip

        note_current_skip(symbol=symbol, reason=reason, stage="strategy_selection")
    except Exception:
        logger.debug("decision audit skip hook failed", exc_info=True)
    if _rate_limited(symbol, reason):
        return
    rows = strategy_pool_snapshot()
    _safe_info(
        "[DECISION_SKIP] pair=%s stage=strategy_selection reason=%s selected=%s "
        "horizon=%s lookback=%s candidates=%s",
        _fmt(symbol),
        _fmt(reason),
        _fmt(selected),
        _fmt(horizon),
        _fmt(lookback),
        _format_strategy_pool(rows),
    )


def log_decision_skip(
    *,
    symbol: str,
    reason: str,
    stage: str,
    **fields: Any,
) -> None:
    """Rate-limited skip log. Never includes broker payloads or credentials."""
    try:
        from forex_bot.decision_repair.audit import note_current_skip

        note_current_skip(symbol=symbol, reason=reason, stage=stage)
    except Exception:
        logger.debug("decision audit skip hook failed", exc_info=True)
    if _rate_limited(symbol, reason):
        return
    extra = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items() if v is not None)
    from forex_bot.log_redact import redact_log_text

    msg = redact_log_text(
        "[DECISION_SKIP] pair=%s stage=%s reason=%s%s"
        % (_fmt(symbol), _fmt(stage), _fmt(reason), f" {extra}" if extra else "")
    )
    _safe_info("%s", msg)


def ma_relationship(sma_fast: float, sma_slow: float, eps: float) -> str:
    try:
        if sma_fast > sma_slow + eps:
            return "fast>slow+eps"
        if sma_fast < sma_slow - eps:
            return "fast<slow-eps"
        return "abs(fast-slow)<=eps"
    except Exception:
        return "n/a"


def log_quant_pre_sizing(
    *,
    reason: str,
    symbol: Any = None,
    timeframe: Any = None,
    bar_time: Any = None,
    sma_fast: Any = None,
    sma_slow: Any = None,
    eps: Any = None,
    relationship: Any = None,
    direction: Any = None,
    move: Any = None,
    threshold: Any = None,
    comparison: Any = None,
) -> None:
    tag = "[DECISION]" if reason == QUANT_SIGNAL_PASS else "[DECISION_SKIP]"
    _safe_info(
        "%s pair=%s stage=quant reason=%s timeframe=%s bar_time=%s "
        "ma_fast=%s ma_slow=%s eps=%s relationship=%s required=%s direction=%s "
        "m5_move=%s threshold=%s comparison=%s",
        tag,
        _fmt(symbol),
        _fmt(reason),
        _fmt(timeframe),
        _fmt(bar_time),
        _fmt(sma_fast),
        _fmt(sma_slow),
        _fmt(eps),
        _fmt(relationship),
        _REQUIRED_MA,
        _fmt(direction),
        _fmt(move),
        _fmt(threshold),
        _fmt(comparison),
    )
