"""In-memory bot state (single-process)."""

from __future__ import annotations

from datetime import date
from typing import Any

from forex_bot.config import Config

state: dict[str, Any] = {
    "equity_curve": [],
    "positions": {},
    "last_report_day": None,
}


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
