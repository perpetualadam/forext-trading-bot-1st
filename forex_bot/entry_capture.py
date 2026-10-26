"""Persist a verified opened trade before it can be managed. Does not submit a close."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from forex_bot.broker_entry_evidence import ENTRY_CONFIRMED_SINGLE_TRADE, classify_entry_response
from forex_bot.close_journal import JournalUnavailable
from forex_bot.entry_journal import EntrySubmissionPermit, commit_verified_entry, entry_row, mark_entry
from forex_bot.positions import Position, _book_lock, positions

ENTRY_FINALISED = "ENTRY_FINALISED"


def _position_from_entry(row: dict[str, Any], evidence: dict[str, Any], body: dict[str, Any] | None) -> Position:
    fill = body.get("orderFillTransaction") if isinstance(body, dict) else {}
    price = Decimal(str((fill or {}).get("price")))
    atr_raw = row.get("atr_at_entry_pips")
    trade_id = str(evidence.get("broker_trade_id") or "")
    return Position(
        symbol=row["instrument"],
        direction=row["direction"],
        units=float(evidence["opened_units"]),
        entry_price=float(price),
        stop_loss=float(row["stop_loss"]),
        take_profit=float(row["take_profit"]),
        open_time=time.time(),
        strategy_name=row["strategy_name"],
        rl_state="held",
        execution_kind="live",
        client_order_id=row["client_order_id"],
        broker_order_id="",
        broker_trade_ids=trade_id,
        broker_order=True,
        position_instance_id=row["position_instance_id"],
        position_generation=int(row["position_generation"]),
        max_profit_pips=0.0,
        profit_protection_active=False,
        profit_protection_close_attempt_ts=0.0,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
        atr_at_entry_pips=None if atr_raw in (None, "") else float(atr_raw),
    )


def record_entry_response(
    permit: EntrySubmissionPermit,
    body: dict[str, Any] | None,
    *,
    account_id: str,
    retrieved_fill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the broker body and publish only after the durable transaction commits."""
    row = entry_row(permit.operation_id)
    if row is None:
        raise JournalUnavailable("operation_missing")
    evidence = classify_entry_response(
        body,
        account_id=account_id,
        instrument=row["instrument"],
        direction=row["direction"],
        requested_units=Decimal(str(row["requested_units"])),
        client_order_id=row["client_order_id"],
        retrieved_fill=retrieved_fill,
    )
    order_id = str(evidence.get("broker_order_id") or "")
    trade_id = str(evidence.get("broker_trade_id") or "")
    if order_id and trade_id and order_id == trade_id and evidence["reason"] == "missing_trade_id":
        evidence["manageable"] = False
    publishable = evidence["state"] == ENTRY_CONFIRMED_SINGLE_TRADE and bool(evidence.get("manageable"))
    if publishable and (not row.get("stop_loss") or not row.get("take_profit")):
        mark_entry(
            permit.operation_id,
            outcome="ENTRY_RECONCILIATION_REQUIRED",
            error="missing_protection_state",
            broker_order_id=order_id,
            broker_trade_id=trade_id,
            transaction_ids=tuple(evidence.get("transaction_ids") or ()),
        )
        evidence["state"] = "ENTRY_RECONCILIATION_REQUIRED"
        evidence["reason"] = "missing_protection_state"
        evidence["manageable"] = False
        evidence["published"] = False
        evidence["close_submission_count"] = 0
        return evidence
    if not publishable:
        mark_entry(
            permit.operation_id,
            outcome=str(evidence["state"]),
            error=str(evidence["reason"]),
            broker_order_id=order_id,
            broker_trade_id=trade_id,
            transaction_ids=tuple(evidence.get("transaction_ids") or ()),
            recovery_status=str(evidence["state"]),
        )
        evidence["published"] = False
        evidence["close_submission_count"] = 0
        return evidence
    already_final = str(row["outcome"]) == ENTRY_FINALISED
    pos = _position_from_entry(row, evidence, body)
    commit_verified_entry(
        permit,
        pos,
        broker_order_id=order_id,
        broker_trade_id=trade_id,
        transaction_ids=tuple(evidence.get("transaction_ids") or ()),
    )
    from forex_bot.startup_recovery import recovery_fence_allows_publication

    if not recovery_fence_allows_publication():
        evidence["published"] = False
        evidence["manageable"] = False
        evidence["publication_reason"] = "recovery_authority_absent"
        evidence["close_submission_count"] = 0
        return evidence
    if already_final:
        current = positions.get(row["instrument"])
        evidence["published"] = (
            current is not None and current.position_instance_id == row["position_instance_id"]
        )
        evidence["close_submission_count"] = 0
        return evidence
    if not recovery_fence_allows_publication():
        evidence["published"] = False
        evidence["manageable"] = False
        evidence["publication_reason"] = "recovery_authority_absent"
        evidence["close_submission_count"] = 0
        return evidence
    with _book_lock:
        current = positions.get(pos.symbol)
        if current is not None and current.position_instance_id != pos.position_instance_id:
            current.recovery_quarantine = True
            evidence["published"] = False
            evidence["reason"] = "replaced_local_position"
            evidence["manageable"] = False
            evidence["close_submission_count"] = 0
            return evidence
        positions[pos.symbol] = pos
    evidence["published"] = True
    evidence["close_submission_count"] = 0
    return evidence
