"""
Derived operational state (read-only): maps existing signals to a single enum for /system and logs.

**Invariant — do not violate:**
    :func:`derive_operational_state` and :func:`operational_state_payload` are **observational only**.
    Never use ``operational_state`` as an input to entry gating, reconcile policy, or kill/halt logic.
    Authority stays in :func:`~forex_bot.execution.pre_trade_entry_allowed` and its dependencies;
    projecting state from those signals is safe; feeding state back into them would create circular
    reasoning.

**Deterministic precedence** (first match wins; keep this order when extending):
    1. ``lifespan_phase`` → ``offline`` | ``starting`` | ``stopping`` (before trading checks).
    2. ``running`` → ``kill_switch_active`` if ``KILL_SWITCH`` env active.
    3. ``halted`` if runtime halt (POST /halt).
    4. ``trading_allowed`` if :func:`~forex_bot.execution.pre_trade_entry_allowed` is true.
    5. Else ``recovery`` (coarse: up but new entries blocked; use ``operational_state_detail`` /
       :func:`~forex_bot.execution.pre_trade_entry_blocked_reason` for the exact code).

**Semantics:** ``offline`` means this process’s FastAPI lifespan is not in the ``running`` phase
(single-process model). In multi-instance setups, “offline” here does not imply other replicas.

**Events:** bounded transition log in :mod:`forex_bot.operational_events` (append on state change only).
"""

from __future__ import annotations

from enum import Enum

from forex_bot.execution import (
    get_execution_mode,
    is_trading_halted_runtime,
    kill_switch_env_active,
    pre_trade_entry_allowed,
)
from forex_bot.state import state as bot_state


class OperationalState(str, Enum):
    """Coarse label for dashboards; fine cause is ``operational_state_detail`` / blocked-reason codes."""

    OFFLINE = "offline"
    STARTING = "starting"
    STOPPING = "stopping"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    HALTED = "halted"
    RECOVERY = "recovery"
    TRADING_ALLOWED = "trading_allowed"


def derive_operational_state() -> OperationalState:
    """
    Single derived label; see module docstring for precedence and the non-authoritative invariant.

    ``recovery`` buckets any running, non-kill, non-halt block (usually reconcile); detail carries
    specificity. No ``reconciling`` phase: periodic reconcile is unstable for UI unless gated.
    """
    phase = (bot_state.get("lifespan_phase") or "offline").strip().lower()
    if phase == "offline":
        return OperationalState.OFFLINE
    if phase == "starting":
        return OperationalState.STARTING
    if phase == "stopping":
        return OperationalState.STOPPING

    # running
    if kill_switch_env_active():
        return OperationalState.KILL_SWITCH_ACTIVE
    if is_trading_halted_runtime():
        return OperationalState.HALTED
    if pre_trade_entry_allowed():
        return OperationalState.TRADING_ALLOWED
    return OperationalState.RECOVERY


def operational_state_payload() -> dict[str, str]:
    """Minimal JSON-friendly bundle for /system."""
    s = derive_operational_state()
    if s == OperationalState.RECOVERY:
        from forex_bot.execution import pre_trade_entry_blocked_reason

        detail = pre_trade_entry_blocked_reason() or "blocked"
    elif s == OperationalState.TRADING_ALLOWED:
        detail = f"pre_trade gate open (execution_mode={get_execution_mode().value})"
    else:
        detail = {
            OperationalState.OFFLINE: "lifespan offline or bot not running",
            OperationalState.STARTING: "startup: DB connect, restore reconcile, first reconcile",
            OperationalState.STOPPING: "shutdown in progress",
            OperationalState.KILL_SWITCH_ACTIVE: "KILL_SWITCH env blocks new entries",
            OperationalState.HALTED: "POST /halt runtime stop (new entries)",
        }.get(s, s.value)
    return {
        "operational_state": s.value,
        "operational_state_detail": detail,
    }
