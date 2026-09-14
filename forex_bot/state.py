"""In-memory bot state (single-process)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from forex_bot.config import Config

state: dict[str, Any] = {
    "equity_curve": [],
    "positions": {},
    "last_report_ts": None,  # time.time() when we last emitted DAILY REPORT
    "bot_status": "stopped",
    "bot_started_at": None,
    "bot_stopped_at": None,
    "last_lifecycle_message": "",
    "last_bot_cycle_utc": None,
    # FastAPI lifespan: offline | starting | running | stopping (for operational_state)
    "lifespan_phase": "offline",
    "broker_nav": None,
    "broker_currency": "",
    "last_mids": {},
}


def mark_bot_started() -> None:
    now = datetime.now(timezone.utc).isoformat()
    state["bot_status"] = "running"
    state["bot_started_at"] = now
    state["bot_stopped_at"] = None


def mark_bot_stopped() -> None:
    state["bot_status"] = "stopped"
    state["bot_stopped_at"] = datetime.now(timezone.utc).isoformat()


def set_lifecycle_message(text: str) -> None:
    state["last_lifecycle_message"] = text


def set_lifespan_phase(phase: str) -> None:
    """Lifecycle phase for :mod:`forex_bot.operational_state` (single-process)."""
    state["lifespan_phase"] = phase


def set_broker_account(nav: float, currency: str = "") -> None:
    """Broker-truth equity from OANDA AccountSummary.NAV (account currency)."""
    state["broker_nav"] = float(nav)
    state["broker_currency"] = (currency or "").strip().upper()
    curve = state["equity_curve"]
    if curve:
        curve[-1] = float(nav)
    else:
        curve.append(float(nav))


def broker_currency() -> str:
    return str(state.get("broker_currency") or "")


def record_mid(symbol: str, price: float) -> None:
    s = (symbol or "").strip().upper().replace("-", "_").replace("/", "_")
    if s and price and float(price) > 0:
        mids = state.setdefault("last_mids", {})
        mids[s] = float(price)


def last_mid(symbol: str) -> float | None:
    s = (symbol or "").strip().upper().replace("-", "_").replace("/", "_")
    mids = state.get("last_mids") or {}
    px = mids.get(s)
    return float(px) if px else None


def current_equity() -> float:
    nav = state.get("broker_nav")
    if nav is not None:
        return float(nav)
    curve = state["equity_curve"]
    return float(curve[-1]) if curve else float(Config.BASE_BALANCE)


def update_equity(pnl: float) -> None:
    last = current_equity()
    state["equity_curve"].append(last + pnl)


def last_report_ts() -> float | None:
    return state["last_report_ts"]


def set_last_report_ts(ts: float) -> None:
    state["last_report_ts"] = ts
