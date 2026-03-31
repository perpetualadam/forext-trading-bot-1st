"""Single source of truth for execution profile (paper vs broker) and safety gates."""

from __future__ import annotations

import os
from enum import Enum


class ExecutionMode(str, Enum):
    """How fills and broker orders are handled."""

    PAPER = "paper"
    PAPER_BROKER = "paper_broker"
    LIVE_BROKER = "live_broker"


_trading_halted: bool = False


def halt_trading() -> None:
    """In-process emergency stop (also use KILL_SWITCH env for startup)."""
    global _trading_halted
    _trading_halted = True


def resume_trading() -> None:
    global _trading_halted
    _trading_halted = False


def is_trading_halted_runtime() -> bool:
    return _trading_halted


def kill_switch_env_active() -> bool:
    return (os.getenv("KILL_SWITCH") or "").strip().lower() in ("1", "true", "yes", "on")


def trading_allowed() -> bool:
    """False blocks **new** risk only; closes may still run."""
    if _trading_halted:
        return False
    if kill_switch_env_active():
        return False
    return True


def strict_execution() -> bool:
    """When true, broker modes must not use random or missing-PnL fallbacks."""
    raw = (os.getenv("STRICT_EXECUTION") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def execution_mode_env_explicitly_set() -> bool:
    """True when ``EXECUTION_MODE`` is set to a known value (``PAPER_TRADING`` is ignored then)."""
    raw = (os.getenv("EXECUTION_MODE") or "").strip().lower()
    return raw in ("paper", "paper_broker", "live_broker")


def get_execution_mode() -> ExecutionMode:
    """
    Authoritative execution profile.

    **Precedence:** If ``EXECUTION_MODE`` is set to ``paper`` / ``paper_broker`` / ``live_broker``,
    it **fully overrides** legacy ``PAPER_TRADING`` for execution semantics. If unset, derive from
    ``PAPER_TRADING`` + ``TRADING_MODE`` (see below).

    - ``EXECUTION_MODE`` env wins when set to paper | paper_broker | live_broker.
    - Otherwise derive from legacy ``PAPER_TRADING`` + ``TRADING_MODE`` (OANDA host).
    """
    raw = (os.getenv("EXECUTION_MODE") or "").strip().lower()
    if raw == "paper":
        return ExecutionMode.PAPER
    if raw == "paper_broker":
        return ExecutionMode.PAPER_BROKER
    if raw == "live_broker":
        return ExecutionMode.LIVE_BROKER

    from forex_bot.config import Config

    paper = bool(getattr(Config, "PAPER_TRADING", True))
    if paper:
        return ExecutionMode.PAPER
    tm = (getattr(Config, "TRADING_MODE", None) or os.getenv("TRADING_MODE") or "practice").strip().lower()
    return ExecutionMode.LIVE_BROKER if tm == "live" else ExecutionMode.PAPER_BROKER


def effective_paper_trading() -> bool:
    """True when fully simulated (no broker order path). Replaces bare ``PAPER_TRADING`` checks."""
    return get_execution_mode() == ExecutionMode.PAPER


def is_broker_execution() -> bool:
    return get_execution_mode() in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER)


def is_live_broker() -> bool:
    return get_execution_mode() == ExecutionMode.LIVE_BROKER


def execution_mode_explicit() -> bool:
    """True if ``EXECUTION_MODE`` is set (dashboard-friendly name; same as ``execution_mode_env_explicitly_set``)."""
    return execution_mode_env_explicitly_set()


def pre_trade_entry_allowed() -> bool:
    """Single combined gate for **new** risk: kill switch / halt + reconcile policy.

    :mod:`forex_bot.operational_state` derives labels from this path; do not gate on those labels.
    """
    if not trading_allowed():
        return False
    from forex_bot.reconciliation import new_entries_allowed_by_reconcile

    return new_entries_allowed_by_reconcile()


def pre_trade_entry_blocked_reason() -> str | None:
    if is_trading_halted_runtime():
        return "halt_runtime"
    if kill_switch_env_active():
        return "kill_switch_env"
    from forex_bot.reconciliation import reconcile_entry_blocked_reason

    return reconcile_entry_blocked_reason()
