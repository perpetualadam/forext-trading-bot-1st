"""
A/B-style experiment flags (quant vs API vs hybrid ensemble, nn_pred mode).

Set via environment; read by :func:`experiment_snapshot` for `/health`, `/status`, and backtest banners.
"""

from __future__ import annotations

import os
from typing import Any, Literal

EnsembleMode = Literal["quant", "api", "hybrid"]


def normalize_ensemble_mode() -> EnsembleMode:
    """
    ``ENSEMBLE_MODE``:

    - ``quant`` — LocalLLM quant stub only (ignore API keys; baseline).
    - ``api`` — registered API voters only (no quant stub), if keys exist.
    - ``hybrid`` — quant stub + API voters (default).
    """
    raw = (os.getenv("ENSEMBLE_MODE") or "hybrid").strip().lower()
    if raw in ("quant", "quant_only", "stub", "baseline"):
        return "quant"
    if raw in ("api", "api_only", "llm"):
        return "api"
    return "hybrid"


def nn_pred_mode_display() -> str:
    m = (os.getenv("NN_PRED_MODE") or "").strip()
    return m if m else "default(backtest=seq, live=noise)"


def experiment_snapshot() -> dict[str, Any]:
    from forex_bot.execution import (
        execution_mode_explicit,
        get_execution_mode,
        is_trading_halted_runtime,
        kill_switch_env_active,
        trading_allowed,
    )

    return {
        "ensemble_mode": normalize_ensemble_mode(),
        "nn_pred_mode": nn_pred_mode_display(),
        "forex_backtest": (os.getenv("FOREX_BACKTEST") or "").strip(),
        "ai_disable_stub": (os.getenv("AI_DISABLE_STUB") or "").strip(),
        "execution_mode": get_execution_mode().value,
        "execution_mode_explicit": execution_mode_explicit(),
        "trading_allowed": trading_allowed(),
        "kill_switch_env": kill_switch_env_active(),
        "halted_runtime": is_trading_halted_runtime(),
    }


def experiment_snapshot_with_voters(ai_ensemble: Any) -> dict[str, Any]:
    """Same as :func:`experiment_snapshot` plus resolved voter counts from the live ``AIEnsemble``."""
    out = experiment_snapshot()
    out["local_voters"] = len(ai_ensemble.local_llms)
    out["external_voters"] = len(ai_ensemble.external_llms)
    return out
