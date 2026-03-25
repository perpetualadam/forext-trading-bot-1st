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
from forex_bot.state import current_equity

logger = logging.getLogger(__name__)


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
    mode = Config.TRADING_MODE.upper()
    alert(f" TRADING MODE: {'LIVE' if Config.TRADING_MODE == 'live' else 'PRACTICE (PAPER TRADING)'}")
    logger.info("Starting bot task; API mode label: %s", mode)
    task = asyncio.create_task(run_bot())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Final Boss Forex Bot",
    description="Live/Paper OANDA workflow, indicators, AI ensemble stub, PostgreSQL logging.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for Docker/Kubernetes (does not verify OANDA or DB)."""
    return {"status": "ok"}


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
