"""Classify an OANDA v20 market-order response. This does not submit or close."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

ENTRY_CONFIRMED_SINGLE_TRADE = "ENTRY_CONFIRMED_SINGLE_TRADE"
ENTRY_CONFIRMED_MULTIPLE_TRADES = "ENTRY_CONFIRMED_MULTIPLE_TRADES"
ENTRY_REJECTED_CONFIRMED = "ENTRY_REJECTED_CONFIRMED"
ENTRY_PARTIAL_OR_MIXED_EFFECT = "ENTRY_PARTIAL_OR_MIXED_EFFECT"
ENTRY_OUTCOME_AMBIGUOUS = "ENTRY_OUTCOME_AMBIGUOUS"
ENTRY_EVIDENCE_CONFLICT = "ENTRY_EVIDENCE_CONFLICT"
ENTRY_RECONCILIATION_REQUIRED = "ENTRY_RECONCILIATION_REQUIRED"

_CONFIRMED = {
    ENTRY_CONFIRMED_SINGLE_TRADE,
    ENTRY_CONFIRMED_MULTIPLE_TRADES,
    ENTRY_REJECTED_CONFIRMED,
    ENTRY_PARTIAL_OR_MIXED_EFFECT,
    ENTRY_OUTCOME_AMBIGUOUS,
    ENTRY_EVIDENCE_CONFLICT,
    ENTRY_RECONCILIATION_REQUIRED,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _opened_trades(fill: dict[str, Any]) -> list[dict[str, Any]]:
    raw = fill.get("tradeOpened")
    if raw is None:
        raw = fill.get("tradesOpened")
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _affected(fill: dict[str, Any], name: str) -> list[dict[str, Any]]:
    raw = fill.get(name)
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def classify_entry_response(
    body: dict[str, Any] | None,
    *,
    account_id: str,
    instrument: str,
    direction: str,
    requested_units: Decimal,
    client_order_id: str,
    retrieved_fill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one entry evidence state. An order id is not a trade id."""
    result = {
        "state": ENTRY_RECONCILIATION_REQUIRED,
        "reason": "unclassified",
        "broker_order_id": "",
        "broker_trade_id": "",
        "transaction_ids": (),
        "opened_units": None,
        "manageable": False,
    }
    if not isinstance(body, dict):
        result["state"] = ENTRY_OUTCOME_AMBIGUOUS
        result["reason"] = "malformed_response"
        return result
    create_tx = body.get("orderCreateTransaction") if isinstance(body.get("orderCreateTransaction"), dict) else {}
    cancel_tx = body.get("orderCancelTransaction") if isinstance(body.get("orderCancelTransaction"), dict) else {}
    reject_tx = body.get("orderRejectTransaction") if isinstance(body.get("orderRejectTransaction"), dict) else {}
    fill = body.get("orderFillTransaction") if isinstance(body.get("orderFillTransaction"), dict) else None
    order_id = _text(create_tx.get("id") or (fill or {}).get("orderID") or cancel_tx.get("orderID"))
    result["broker_order_id"] = order_id
    if fill is None and (reject_tx or cancel_tx):
        result["state"] = ENTRY_REJECTED_CONFIRMED
        result["reason"] = "broker_reject_or_cancel"
        result["transaction_ids"] = tuple(
            item for item in (_text(reject_tx.get("id")), _text(cancel_tx.get("id")), _text(create_tx.get("id"))) if item
        )
        return result
    if fill is None:
        result["state"] = ENTRY_OUTCOME_AMBIGUOUS
        result["reason"] = "missing_fill_transaction"
        return result
    if retrieved_fill is not None:
        if _text(retrieved_fill.get("id")) != _text(fill.get("id")) or _text(retrieved_fill.get("instrument")) != _text(fill.get("instrument")):
            result["state"] = ENTRY_EVIDENCE_CONFLICT
            result["reason"] = "retrieved_fill_conflict"
            return result
        fill = retrieved_fill
    fill_account = _text(fill.get("accountID"))
    if fill_account and fill_account != account_id:
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "account_mismatch"
        return result
    if _text(fill.get("instrument")) != instrument:
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "instrument_mismatch"
        return result
    client = fill.get("clientExtensions") if isinstance(fill.get("clientExtensions"), dict) else {}
    extension_id = _text(client.get("id"))
    order_client_id = _text(fill.get("clientOrderID"))
    if extension_id and order_client_id and extension_id != order_client_id:
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "conflicting_client_id"
        return result
    observed_client_id = extension_id or order_client_id
    if not client_order_id or observed_client_id != client_order_id:
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "missing_client_order_id" if not observed_client_id else "client_order_mismatch"
        return result
    units = _decimal(fill.get("units"))
    if units is None:
        result["state"] = ENTRY_RECONCILIATION_REQUIRED
        result["reason"] = "missing_units"
        return result
    signed_direction = "BUY" if units > 0 else "SELL" if units < 0 else ""
    if signed_direction != direction:
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "direction_mismatch"
        return result
    opened = _opened_trades(fill)
    closed = _affected(fill, "tradesClosed")
    reduced = _affected(fill, "tradeReduced")
    result["transaction_ids"] = tuple(item for item in (_text(fill.get("id")), _text(create_tx.get("id"))) if item)
    if closed or reduced:
        result["state"] = ENTRY_PARTIAL_OR_MIXED_EFFECT
        result["reason"] = "existing_trade_reduced_or_closed"
        return result
    if len(opened) > 1:
        result["state"] = ENTRY_CONFIRMED_MULTIPLE_TRADES
        result["reason"] = "multiple_opened_trades"
        return result
    if len(opened) == 0:
        result["state"] = ENTRY_RECONCILIATION_REQUIRED
        result["reason"] = "missing_trade_id"
        return result
    trade_id = _text(opened[0].get("tradeID"))
    opened_units = _decimal(opened[0].get("units"))
    if not trade_id or opened_units is None:
        result["state"] = ENTRY_RECONCILIATION_REQUIRED
        result["reason"] = "missing_trade_id"
        return result
    if trade_id == order_id:
        result["state"] = ENTRY_RECONCILIATION_REQUIRED
        result["reason"] = "order_id_is_not_trade_id"
        return result
    if abs(opened_units) != abs(units):
        result["state"] = ENTRY_EVIDENCE_CONFLICT
        result["reason"] = "units_mismatch"
        return result
    if abs(units) != requested_units:
        result["state"] = ENTRY_PARTIAL_OR_MIXED_EFFECT
        result["reason"] = "partial_fill"
        result["broker_trade_id"] = trade_id
        result["opened_units"] = abs(opened_units)
        return result
    result["state"] = ENTRY_CONFIRMED_SINGLE_TRADE
    result["reason"] = "trade_opened"
    result["broker_trade_id"] = trade_id
    result["opened_units"] = abs(opened_units)
    result["manageable"] = True
    return result
