"""FastAPI dashboard and process lifespan (bot task)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.bot_loop import run_bot
from forex_bot.config import Config
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


def _health_snapshot() -> dict[str, Any]:
    return {
        "equity": current_equity(),
        "sharpe": analytics.sharpe(),
        "winrate": analytics.winrate(),
        "drawdown": analytics.drawdown(),
        "trading_mode": Config.TRADING_MODE,
        "paper_trading": Config.PAPER_TRADING,
        "symbols": list(Config.SYMBOLS),
    }


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


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe; includes bot run state for dashboards (OANDA/DB not verified)."""
    return {
        "status": "ok",
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "paper_trading": Config.PAPER_TRADING,
        "trading_mode": Config.TRADING_MODE,
    }


@app.get("/status")
async def status() -> dict[str, Any]:
    """Full system status for dashboard / monitoring."""
    snap = _health_snapshot()
    return {
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "stopped_at": bot_state.get("bot_stopped_at"),
        "last_lifecycle_message": bot_state.get("last_lifecycle_message", ""),
        "health": snap,
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "equity": current_equity(),
        "sharpe": analytics.sharpe(),
        "winrate": analytics.winrate(),
        "drawdown": analytics.drawdown(),
        "trading_mode": Config.TRADING_MODE,
    }


@app.get("/replay")
async def replay() -> list[dict[str, Any]]:
    return _serialize_trades(fetch_all_trades_ordered())


@app.get("/strategy-analysis")
async def strategy_analysis() -> list[dict[str, Any]]:
    return fetch_strategy_analysis()


class SetModeBody(BaseModel):
    mode: str | None = Field(default=None, description="live or practice")


def _resolve_trading_mode(
    mode_query: str | None,
    body: SetModeBody | None,
) -> str:
    """Body wins if it includes a non-empty mode; else query ?mode= (legacy)."""
    if body is not None and body.mode and str(body.mode).strip():
        return str(body.mode).strip()
    if mode_query is not None and str(mode_query).strip():
        return str(mode_query).strip()
    raise HTTPException(
        status_code=400,
        detail="Provide mode via query (?mode=practice) or JSON body {\"mode\":\"practice\"}",
    )


@app.post("/set_mode")
async def set_mode(
    mode: str | None = Query(
        default=None,
        description="live or practice (legacy; same as original Query-only POST)",
    ),
    body: SetModeBody | None = Body(default=None),
) -> dict[str, str]:
    raw = _resolve_trading_mode(mode, body)
    try:
        Config.set_trading_mode(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    build_api()
    alert(f" Trading mode changed to {Config.TRADING_MODE.upper()}")
    return {"status": "success", "mode": Config.TRADING_MODE}
