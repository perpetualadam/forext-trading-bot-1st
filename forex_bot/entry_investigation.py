"""Read-only classification of an unresolved entry. This does not resubmit or delete.

Absence of a matching transaction is not proof the order was never accepted.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from forex_bot.close_journal import JournalUnavailable, _now, active_journal

_INCOMPLETE = {"INCOMPLETE", "MALFORMED", "REQUEST_FAILED", "STALE", "UNAVAILABLE", "UNKNOWN", "CONFLICT"}


def classify_entry_investigation(entry: dict[str, Any], evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Classify synthetic or retrieved evidence. The entry row is not modified."""
    result = {
        "classification": "evidence_unavailable",
        "reason": "evidence_missing",
        "retry_permitted": False,
        "delete_permitted": False,
        "manageable": False,
        "order_submission_count": 0,
        "close_submission_count": 0,
    }
    if not isinstance(evidence, dict):
        return result
    snapshot = str(evidence.get("snapshot") or "UNAVAILABLE")
    if snapshot in _INCOMPLETE:
        result["classification"] = "snapshot_incomplete" if snapshot != "UNAVAILABLE" else "evidence_unavailable"
        result["reason"] = snapshot.lower()
        return result
    transactions = [item for item in list(evidence.get("transactions") or []) if isinstance(item, dict)]
    trades = [item for item in list(evidence.get("trades") or []) if isinstance(item, dict)]
    client_id = str(entry.get("client_order_id") or "")
    instrument = str(entry.get("instrument") or "")
    direction = str(entry.get("direction") or "").upper()
    matched_transactions = [item for item in transactions if _client_matches(item, client_id)]
    if any(_is_reject(item) for item in matched_transactions):
        if any(_identity_conflict(item, entry) for item in matched_transactions):
            result["classification"] = "conflicting_evidence"
            result["reason"] = "rejected_identity_conflict"
            return result
        result["classification"] = "rejected_order_found"
        result["reason"] = "matching_reject_transaction"
        return result
    fills = [item for item in matched_transactions if str(item.get("type") or "") == "ORDER_FILL"]
    if len(fills) > 1 or any(_multiple_opens(item) for item in fills):
        result["classification"] = "conflicting_evidence"
        result["reason"] = "multiple_or_ambiguous_fills"
        return result
    if len(fills) == 1:
        fill = fills[0]
        if _identity_conflict(fill, entry):
            result["classification"] = "conflicting_evidence"
            result["reason"] = "fill_identity_conflict"
            return result
        opened = fill.get("tradeOpened") if isinstance(fill.get("tradeOpened"), dict) else None
        trade_id = "" if opened is None else str(opened.get("tradeID") or "")
        order_id = str(fill.get("orderID") or "")
        if not trade_id or trade_id == order_id and not opened:
            result["classification"] = "conflicting_evidence"
            result["reason"] = "order_id_is_not_trade_id"
            return result
        if _reduced_or_closed(fill):
            result["classification"] = "conflicting_evidence"
            result["reason"] = "existing_trade_reduced_or_closed"
            return result
        result["classification"] = "matching_trade_found"
        result["reason"] = "fill_trade_opened"
        result["broker_trade_id"] = trade_id
        result["broker_order_id"] = order_id
        return result
    same_trade = [
        item
        for item in trades
        if str(item.get("client_order_id") or "") == client_id and str(item.get("instrument") or "") == instrument
    ]
    if len(same_trade) == 1 and str(same_trade[0].get("direction") or "").upper() == direction:
        if str(same_trade[0].get("provenance") or "") != "bot_managed":
            result["classification"] = "matching_trade_found"
            result["reason"] = "trade_without_bot_ownership"
            return result
        result["classification"] = "matching_trade_found"
        result["reason"] = "trade_id_present"
        result["broker_trade_id"] = str(same_trade[0].get("trade_id") or "")
        return result
    if len(same_trade) > 1:
        result["classification"] = "conflicting_evidence"
        result["reason"] = "multiple_trades"
        return result
    result["classification"] = "no_matching_evidence"
    result["reason"] = "absence_is_not_rejection"
    return result


def record_entry_investigation(operation_id: str, evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Append an investigation. The entry outcome stays unchanged."""
    journal = active_journal()
    row = journal._conn.execute(
        "SELECT * FROM entry_operations WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    if row is None:
        raise JournalUnavailable("operation_missing")
    before = str(row["outcome"])
    classified = classify_entry_investigation(dict(row), evidence)
    with journal._lock:
        journal._begin()
        try:
            journal._conn.execute(
                """
                INSERT INTO entry_investigations (
                    investigation_id, operation_id, classification, reason, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    operation_id,
                    classified["classification"],
                    classified["reason"],
                    _now(),
                ),
            )
            journal._commit()
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc
    after = journal._conn.execute(
        "SELECT outcome FROM entry_operations WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    classified["outcome_unchanged"] = after is not None and str(after[0]) == before
    classified["retry_permitted"] = False
    return classified


def _client_matches(transaction: dict[str, Any], client_id: str) -> bool:
    extensions = transaction.get("clientExtensions") if isinstance(transaction.get("clientExtensions"), dict) else {}
    observed = str(transaction.get("clientOrderID") or extensions.get("id") or "")
    return bool(client_id) and observed == client_id


def _is_reject(transaction: dict[str, Any]) -> bool:
    kind = str(transaction.get("type") or "")
    return kind in {"ORDER_REJECT", "MARKET_ORDER_REJECT", "ORDER_CANCEL"}


def _multiple_opens(fill: dict[str, Any]) -> bool:
    opened = fill.get("tradesOpened")
    return isinstance(opened, list) and len(opened) > 1


def _reduced_or_closed(fill: dict[str, Any]) -> bool:
    return bool(fill.get("tradeReduced") or fill.get("tradesClosed"))


def _identity_conflict(transaction: dict[str, Any], entry: dict[str, Any]) -> bool:
    account = str(transaction.get("accountID") or "")
    expected_account = str(entry.get("account_id") or "")
    if account and expected_account and account != expected_account:
        return True
    instrument = str(transaction.get("instrument") or "")
    if instrument and instrument != str(entry.get("instrument") or ""):
        return True
    units = transaction.get("units")
    if units not in (None, ""):
        try:
            signed = Decimal(str(units))
        except Exception:
            return True
        direction = "BUY" if signed > 0 else "SELL" if signed < 0 else ""
        if direction and direction != str(entry.get("direction") or "").upper():
            return True
        requested = entry.get("requested_units")
        if requested not in (None, "") and abs(signed) != Decimal(str(requested)):
            return True
    return False
