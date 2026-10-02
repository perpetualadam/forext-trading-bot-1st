"""Read-only diagnostic logs for previously silent pre-sizing exits.

Does not select strategies, vote, size, or mutate performance state.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

NO_STRATEGY_SELECTED = "NO_STRATEGY_SELECTED"
STRATEGY_INACTIVE = "STRATEGY_INACTIVE"
QUANT_MA_INVALID = "QUANT_MA_INVALID"
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
