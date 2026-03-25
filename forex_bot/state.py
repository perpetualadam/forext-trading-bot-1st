"""In-memory bot state (single-process)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from forex_bot.config import Config

state: dict[str, Any] = {
    "equity_curve": [],
    "positions": {},
    "last_report_day": None,
    "bot_status": "stopped",
    "bot_started_at": None,
    "bot_stopped_at": None,
    "last_lifecycle_message": "",
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


def current_equity() -> float:
    curve = state["equity_curve"]
    return float(curve[-1]) if curve else float(Config.BASE_BALANCE)


def update_equity(pnl: float) -> None:
    last = current_equity()
    state["equity_curve"].append(last + pnl)


def last_report_day() -> date | None:
    return state["last_report_day"]


def set_last_report_day(d: date) -> None:
    state["last_report_day"] = d
