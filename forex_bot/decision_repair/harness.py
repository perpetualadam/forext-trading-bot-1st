"""Broker-disconnected offline evaluation harness.

No credentials, no OANDA I/O, no profitability claim. Used only by isolated tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCENARIOS: tuple[str, ...] = (
    "valid_market_data",
    "missing_market_data",
    "inactive_strategy",
    "ai_rejection",
    "rl_unavailable",
    "risk_rejection",
    "authorisation_blocked",
    "broker_reconciliation_blocked",
    "order_intent_internal",
    "mock_broker_ack",
    "mock_broker_failure",
    "audit_write_failure",
    "restart_rl_state",
    "restart_risk_latch",
    "shuffled_risk_events",
    "duplicate_broker_transactions",
    "late_loss_latch",
    "pending_entry_plus_position",
    "partial_fill",
    "stale_broker_reconciliation",
    "concurrent_hypothetical_entries",
    "selector_rotation_restart",
    "audit_fail_open_blocked",
    "audit_fail_close_allowed",
    "mock_close_ack",
    "mock_close_reject",
    "close_status_unknown",
    "close_reconciled",
)


@dataclass
class ScenarioResult:
    name: str
    reason: str
    decision_id: str | None = None
    final_decision: str | None = None
    broker_called: bool = False
    strategy_activated: bool = False
    records: list[dict[str, Any]] = field(default_factory=list)


def load_jsonl(path) -> list[dict[str, Any]]:
    import json
    from pathlib import Path

    dest = Path(path)
    if not dest.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in dest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def decision_ids(records: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("decision_id") or "") for row in records]
