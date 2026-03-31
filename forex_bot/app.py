"""FastAPI dashboard and process lifespan (bot task)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.utils import get_openapi

from forex_bot.alerts import alert
from forex_bot.ai_ensemble import ai as ai_ensemble
from forex_bot.analytics import analytics
from forex_bot.bot_loop import run_bot
from forex_bot.config import Config
from forex_bot.experiment import experiment_snapshot_with_voters
from forex_bot.trading import configured_max_portfolio_risk_pct, portfolio_risk_fraction
from forex_bot.database import fetch_all_trades_ordered, fetch_strategy_analysis, get_connection
from forex_bot.oanda_client import build_api
from forex_bot.state import (
    current_equity,
    mark_bot_started,
    mark_bot_stopped,
    set_lifecycle_message,
    state as bot_state,
)

logger = logging.getLogger(__name__)


def _profit_factor_json(pf: float | None) -> float | str | None:
    if pf is None:
        return None
    if pf == float("inf"):
        return "inf"
    return round(float(pf), 4)


def _trading_metrics_payload() -> dict[str, Any]:
    wr = analytics.winrate()
    pf = analytics.profit_factor()
    eq = current_equity()
    cap = configured_max_portfolio_risk_pct()
    return {
        "equity": eq,
        "sharpe": analytics.sharpe(),
        # winrate: fraction 0..1 (0.54 == 54% wins). Do not append "%" without ×100.
        "winrate": wr,
        "win_rate_pct": round(analytics.win_rate_pct(), 2),
        "drawdown": analytics.drawdown(),
        "avg_win": round(analytics.avg_win(), 4),
        "avg_loss": round(analytics.avg_loss(), 4),
        "profit_factor": _profit_factor_json(pf),
        "portfolio_risk_pct": round(portfolio_risk_fraction(eq) * 100.0, 2),
        "max_portfolio_risk_pct_cap": round(cap * 100.0, 2) if cap > 0 else 0.0,
        "trading_mode": Config.TRADING_MODE,
        "paper_trading": Config.PAPER_TRADING,
        "sizing_note": (
            "Per-trade: POSITION_RISK_PCT (capped by POSITION_RISK_PCT_MAX); portfolio: "
            "sum of stop risks vs MAX_PORTFOLIO_RISK_PCT; optional USE_ATR_STOPS + SL_ATR_MULT; "
            "MAX_POSITION_UNITS hard cap. TRADING_MODE does not change sizing."
        ),
    }


def _health_snapshot() -> dict[str, Any]:
    return {**_trading_metrics_payload(), "symbols": list(Config.SYMBOLS)}


def _health_alert_text(prefix: str) -> str:
    h = _health_snapshot()
    return (
        f"{prefix} | mode={h['trading_mode']} paper={h['paper_trading']} | "
        f"equity={h['equity']:.2f} sharpe={h['sharpe']:.2f} "
        f"winrate={h['winrate']:.2%} drawdown={h['drawdown']:.2f} | "
        f"symbols={h['symbols']}"
    )


def _serialize_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        t = d.get("time")
        if hasattr(t, "isoformat"):
            d["time"] = t.isoformat()
        out.append(d)
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    get_connection()
    build_api()
    mark_bot_started()
    started_msg = _health_alert_text("BOT STARTED")
    set_lifecycle_message(started_msg)
    alert(started_msg)
    logger.info("Bot started; trading_mode=%s", Config.TRADING_MODE)
    task = asyncio.create_task(run_bot())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        mark_bot_stopped()
        stopped_msg = _health_alert_text("BOT STOPPED")
        set_lifecycle_message(stopped_msg)
        alert(stopped_msg)
        logger.info("Bot stopped (lifespan shutdown)")


app = FastAPI(
    title="Final Boss Forex Bot",
    description="Live/Paper OANDA workflow, indicators, AI ensemble stub, PostgreSQL logging.",
    lifespan=lifespan,
)


@app.get(
    "/health",
    tags=["Status"],
    operation_id="get_health",
    summary="Liveness and bot flags",
)
async def health() -> dict[str, Any]:
    """Liveness probe; includes bot run state for dashboards (OANDA/DB not verified)."""
    return {
        "status": "ok",
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "paper_trading": Config.PAPER_TRADING,
        "trading_mode": Config.TRADING_MODE,
        "experiment": experiment_snapshot_with_voters(ai_ensemble),
    }


@app.get(
    "/status",
    tags=["Status"],
    operation_id="get_status",
    summary="Full status snapshot",
)
async def status() -> dict[str, Any]:
    """Full system status for dashboard / monitoring."""
    snap = _health_snapshot()
    return {
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "stopped_at": bot_state.get("bot_stopped_at"),
        "last_lifecycle_message": bot_state.get("last_lifecycle_message", ""),
        "health": snap,
        "experiment": experiment_snapshot_with_voters(ai_ensemble),
    }


@app.get(
    "/experiment",
    tags=["Status"],
    operation_id="get_experiment",
    summary="A/B flags: ensemble mode (quant vs API vs hybrid) and nn_pred mode",
)
async def experiment_endpoint() -> dict[str, Any]:
    """Quant vs LLM vs hybrid configuration for comparing runs (same env as backtest when aligned)."""
    return experiment_snapshot_with_voters(ai_ensemble)


@app.get(
    "/metrics",
    tags=["Status"],
    operation_id="get_metrics",
    summary="Equity and risk metrics",
)
async def metrics() -> dict[str, Any]:
    return _trading_metrics_payload()


@app.get(
    "/replay",
    tags=["Trades & analytics"],
    operation_id="get_trade_replay",
    summary="All logged trades (newest first)",
)
async def replay() -> list[dict[str, Any]]:
    return _serialize_trades(fetch_all_trades_ordered())


@app.get(
    "/strategy-analysis",
    tags=["Trades & analytics"],
    operation_id="get_strategy_analysis",
    summary="Per-strategy stats from the database",
    response_description="List of strategy aggregate rows (Sharpe, PnL, etc.).",
)
async def strategy_analysis() -> list[dict[str, Any]]:
    """Returns analytics grouped by strategy name (not related to OANDA mode or `/set_mode`)."""
    return fetch_strategy_analysis()


class OandaEnvMode(str, Enum):
    """OANDA REST environment (market data / API host), not paper PnL."""

    live = "live"
    practice = "practice"


def _apply_trading_mode(mode: str) -> dict[str, str]:
    try:
        Config.set_trading_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    build_api()
    alert(f" Trading mode changed to {Config.TRADING_MODE.upper()}")
    return {"status": "success", "mode": Config.TRADING_MODE}


@app.get(
    "/set_mode",
    tags=["Configuration"],
    operation_id="get_set_trading_mode",
    summary="Switch OANDA mode (GET — recommended in ReDoc)",
    description=(
        "No request body. Set **mode** to `live` or `practice` in the query dropdown. "
        "Example: `/set_mode?mode=practice`"
    ),
)
async def set_mode_get(
    mode: OandaEnvMode = Query(..., description="OANDA API environment"),
) -> dict[str, str]:
    return _apply_trading_mode(mode.value)


@app.post(
    "/set_mode",
    tags=["Configuration"],
    operation_id="post_set_trading_mode",
    summary="Switch OANDA mode (POST — query only, no JSON body)",
    description=(
        "ReDoc often sends an empty JSON body on POST, which breaks optional-body handlers. "
        "This route uses **only** the query parameter `mode` — leave the body empty / do not send JSON."
    ),
)
async def set_mode_post(
    mode: OandaEnvMode = Query(..., description="OANDA API environment"),
) -> dict[str, str]:
    return _apply_trading_mode(mode.value)


def custom_openapi() -> dict[str, Any]:
    """Drop 422 from the published schema so ReDoc/Swagger do not show the ValidationError block."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    for path_item in openapi_schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            op_item = path_item.get(method)
            if not isinstance(op_item, dict):
                continue
            responses = op_item.get("responses")
            if isinstance(responses, dict):
                responses.pop("422", None)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
