"""Feature flags. Every repair is disabled unless an explicit env opt-in is set."""

from __future__ import annotations

import os


def _on(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def deterministic_select_enabled() -> bool:
    return _on("DECISION_REPAIR_DETERMINISTIC_SELECT")


def rl_persist_enabled() -> bool:
    return _on("DECISION_REPAIR_RL_PERSIST")


def rl_require_state_enabled() -> bool:
    return _on("DECISION_REPAIR_RL_REQUIRE_STATE")


def audit_enabled() -> bool:
    return _on("DECISION_REPAIR_AUDIT")


def health_enabled() -> bool:
    return _on("DECISION_REPAIR_HEALTH")


def account_risk_enabled() -> bool:
    return _on("DECISION_REPAIR_ACCOUNT_RISK")
