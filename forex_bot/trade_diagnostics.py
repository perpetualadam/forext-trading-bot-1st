"""Measurement-only trade result snapshot. Never raises to callers."""

from __future__ import annotations

import logging
import math
from typing import Any

from forex_bot.profit_protection import (
    original_sl_distance_pips,
    original_tp_distance_pips,
    profit_giveback_atr_multiplier,
    profit_giveback_max_pips,
    profit_giveback_min_pips,
    profit_protection_atr_period,
    profit_protection_trigger_percent,
    unrealized_profit_pips,
)

logger = logging.getLogger(__name__)


def _f(val: Any) -> float | None:
    if val is None:
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def _div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return round(num / den, 6)


def snapshot_from_position(
    pos: Any,
    *,
    exit_reason: str,
    exit_price: float | None,
) -> dict[str, Any]:
    """Build a JSON-safe diagnostics dict from an open position at close time."""
    try:
        return _snapshot_from_position(pos, exit_reason=exit_reason, exit_price=exit_price)
    except Exception:
        logger.exception("trade diagnostics snapshot failed (ignored)")
        return {}


def _snapshot_from_position(
    pos: Any,
    *,
    exit_reason: str,
    exit_price: float | None,
) -> dict[str, Any]:
    sl_pips = original_sl_distance_pips(pos)
    tp_pips = original_tp_distance_pips(pos)
    mfe = _f(getattr(pos, "max_profit_pips", 0.0)) or 0.0
    mae = _f(getattr(pos, "max_adverse_pips", 0.0)) or 0.0
    realised = None
    if exit_price is not None:
        realised = unrealized_profit_pips(pos.symbol, pos.direction, pos.entry_price, exit_price)
    tp_progress = _div(mfe, tp_pips)
    activated = bool(getattr(pos, "profit_protection_active", False))
    reason = (exit_reason or "close").strip().lower()
    protect_exit = reason == "profit_protection"
    giveback = None
    if realised is not None:
        giveback = round(mfe - realised, 6)
    atr_entry = _f(getattr(pos, "atr_at_entry_pips", None))
    return {
        "symbol": getattr(pos, "symbol", None),
        "direction": getattr(pos, "direction", None),
        "entry_price": _f(getattr(pos, "entry_price", None)),
        "original_sl": _f(getattr(pos, "stop_loss", None)),
        "original_tp": _f(getattr(pos, "take_profit", None)),
        "original_sl_pips": sl_pips,
        "original_tp_pips": tp_pips,
        "exit_price": _f(exit_price),
        "exit_reason": reason,
        "realised_pips": realised,
        "mfe_pips": mfe,
        "mae_pips": mae,
        "max_tp_progress": tp_progress,
        "profit_protection_activated": activated,
        "mfe_at_activation_pips": _f(getattr(pos, "protect_activated_mfe_pips", None)),
        "atr_at_activation_pips": _f(getattr(pos, "protect_activated_atr_pips", None)),
        "atr_giveback_at_activation_pips": _f(getattr(pos, "protect_activated_giveback_pips", None)),
        "protected_exit_at_activation_pips": _f(getattr(pos, "protect_activated_exit_pips", None)),
        "final_protected_exit_pips": _f(getattr(pos, "profit_protection_exit_pips", None)),
        "atr_fallback_used": bool(getattr(pos, "atr_fallback_used", False)),
        "exited_on_profit_protection": protect_exit,
        "mfe_giveback_pips": giveback,
        "atr_at_entry_pips": atr_entry,
        "mfe_r": _div(mfe, sl_pips),
        "realised_r": _div(realised, sl_pips),
        "mfe_atr": _div(mfe, atr_entry),
        "settings": {
            "trigger_percent": profit_protection_trigger_percent(),
            "atr_multiplier": profit_giveback_atr_multiplier(),
            "atr_period": profit_protection_atr_period(),
            "giveback_min_pips": profit_giveback_min_pips(),
            "giveback_max_pips": profit_giveback_max_pips(),
        },
    }


def finalize_diagnostics(
    diagnostics: dict[str, Any] | None,
    *,
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
) -> dict[str, Any] | None:
    """Fill realised pips from the actual close price. Never raises."""
    if not diagnostics:
        return diagnostics
    try:
        realised = unrealized_profit_pips(symbol, direction, entry_price, exit_price)
        diagnostics["exit_price"] = _f(exit_price)
        diagnostics["realised_pips"] = realised
        mfe = _f(diagnostics.get("mfe_pips")) or 0.0
        diagnostics["mfe_giveback_pips"] = round(mfe - realised, 6)
        sl = _f(diagnostics.get("original_sl_pips"))
        diagnostics["realised_r"] = _div(realised, sl)
    except Exception:
        logger.exception("trade diagnostics finalize failed (ignored)")
    return diagnostics


def format_trade_result_line(diagnostics: dict[str, Any] | None) -> str | None:
    if not diagnostics:
        return None
    try:
        reason = str(diagnostics.get("exit_reason") or "close").upper()
        if diagnostics.get("exited_on_profit_protection"):
            reason = "PROFIT_PROTECTION"
        elif reason == "SL_TP":
            reason = "SL_TP"
        res = diagnostics.get("realised_pips")
        mfe = diagnostics.get("mfe_pips")
        gb = diagnostics.get("mfe_giveback_pips")
        prog = diagnostics.get("max_tp_progress")
        atr_p = diagnostics.get("atr_at_activation_pips")
        atr_gb = diagnostics.get("atr_giveback_at_activation_pips")
        activated = bool(diagnostics.get("profit_protection_activated"))

        def _p(val: Any, plus: bool = True) -> str:
            if val is None:
                return "n/a"
            x = float(val)
            if plus:
                return f"{x:+.1f}p"
            return f"{x:.1f}p"

        prog_s = "n/a" if prog is None else f"{float(prog) * 100:.1f}%"
        return (
            f"[TRADE RESULT] {diagnostics.get('symbol')} {diagnostics.get('direction')} | "
            f"Exit={reason} | Result={_p(res)} | MFE={_p(mfe)} | Giveback={_p(gb, plus=False)} | "
            f"TPProgressMax={prog_s} | ATR@Protect={_p(atr_p, plus=False)} | "
            f"ATRGiveback={_p(atr_gb, plus=False)} | Protected={activated}"
        )
    except Exception:
        logger.exception("trade result line failed (ignored)")
        return None


def emit_trade_result(diagnostics: dict[str, Any] | None) -> None:
    line = format_trade_result_line(diagnostics)
    if line:
        logger.info("%s", line)
