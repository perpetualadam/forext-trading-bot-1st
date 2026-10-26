"""Parse injected OANDA-shaped account documents. This module makes no network call.

Field names come from the local oandapyV20 response fixtures and from this
repository's order-fill parser. Values in tests are synthetic. Financial
treatment that those sources do not define fails closed.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

_NON_PNL_TYPES = {
    "LIMIT_ORDER",
    "ORDER_CANCEL",
    "ORDER_CLIENT_EXTENSIONS_MODIFY",
    "CLIENT_CONFIGURE",
    "HEARTBEAT",
}
_PENDING = "PENDING"


def account_core(document: Any, *, expected_account_id: str | None) -> dict[str, Any] | str:
    """Read NAV, balance, identity and currency. Missing NAV is not taken from balance."""
    account = _account_dict(document)
    if isinstance(account, str):
        return account
    actual_id = str(account.get("id") or "").strip()
    expected = str(expected_account_id or "").strip()
    if not actual_id or (expected and actual_id != expected):
        return "broker_account_mismatch"
    currency = str(account.get("currency") or "").strip().upper()
    if not currency:
        return "broker_currency_missing"
    if "NAV" not in account:
        return "broker_equity_missing"
    nav = _number(account.get("NAV"))
    if nav is None:
        return "broker_value_nonfinite"
    if nav <= 0:
        return "broker_equity_invalid"
    if "balance" not in account:
        return "broker_balance_missing"
    balance = _number(account.get("balance"))
    if balance is None:
        return "broker_value_nonfinite"
    if balance <= 0:
        return "broker_balance_invalid"
    if "unrealizedPL" not in account:
        return "broker_unrealised_missing"
    unrealised = _number(account.get("unrealizedPL"))
    if unrealised is None:
        return "broker_value_nonfinite"
    margin = account.get("marginAvailable")
    margin_value = None if margin is None else _number(margin)
    if margin is not None and margin_value is None:
        return "broker_value_nonfinite"
    return {
        "id": actual_id,
        "currency": currency,
        "NAV": nav,
        "balance": balance,
        "unrealised": unrealised,
        "marginAvailable": margin_value,
        "alias": str(account.get("alias") or ""),
        "last_transaction_id": str(account.get("lastTransactionID") or document.get("lastTransactionID") or "").strip(),
        "account": account,
    }


def normalize_oanda_risk_inputs(
    summary: Any,
    transactions: Any,
    *,
    expected_account_id: str | None,
    expected_currency: str | None,
    now: datetime | None,
) -> tuple[str | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """Build an R.26 snapshot from an injected account document and transaction page."""
    core = account_core(summary, expected_account_id=expected_account_id)
    if isinstance(core, str):
        return core, None, []
    expected_ccy = str(expected_currency or "").strip().upper()
    if expected_ccy and core["currency"] != expected_ccy:
        return "broker_currency_mismatch", None, []
    if now is None or now.tzinfo is None:
        return "broker_timestamp_malformed", None, []
    observed = _observed_at(summary, now)
    if isinstance(observed, str):
        return observed, None, []
    account = core["account"]
    if "positions" not in account:
        return "position_book_missing", None, []
    if "orders" not in account:
        return "order_book_missing", None, []
    positions = _positions(account.get("positions"), core["currency"])
    if isinstance(positions, str):
        return positions, None, []
    orders = _orders(account.get("orders"), core["currency"])
    if isinstance(orders, str):
        return orders, None, []
    events = _transactions(transactions, core["last_transaction_id"])
    if isinstance(events, str):
        return events, None, []
    snapshot = {
        "provenance": "oanda_account_summary",
        "id": core["id"],
        "currency": core["currency"],
        "snapshot_id": f"summary-{core['last_transaction_id'] or 'none'}-{core['NAV']:.6f}",
        "as_of": observed,
        "NAV": core["NAV"],
        "balance": core["balance"],
        "unrealised": core["unrealised"],
        "positions": positions,
        "orders": orders,
    }
    return None, snapshot, events


def _account_dict(document: Any) -> dict[str, Any] | str:
    if not isinstance(document, dict):
        return "broker_response_invalid"
    if "errorMessage" in document or "errorCode" in document:
        return "broker_response_invalid"
    account = document.get("account", document)
    if not isinstance(account, dict) or "NAV" not in account and "id" not in account and "balance" not in account:
        return "broker_response_invalid"
    return account


def _positions(raw: Any, currency: str) -> list[dict[str, Any]] | str:
    if not isinstance(raw, list):
        return "position_book_missing"
    positions: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            return "exposure_unreadable"
        instrument = str(item.get("instrument") or "").upper()
        long_side = item.get("long") if isinstance(item.get("long"), dict) else {}
        short_side = item.get("short") if isinstance(item.get("short"), dict) else {}
        long_units = _number(long_side.get("units")) if "units" in long_side else 0.0
        short_units = _number(short_side.get("units")) if "units" in short_side else 0.0
        if long_units is None or short_units is None:
            return "exposure_unreadable"
        if long_units < 0 or short_units > 0 or (long_units != 0 and short_units != 0):
            return "position_book_unresolved"
        units = long_units + short_units
        if units == 0:
            continue
        side = long_side if long_units != 0 else short_side
        price = _number(side.get("averagePrice"))
        if "_" not in instrument or price is None or price <= 0:
            return "exposure_unreadable"
        if instrument.split("_")[-1] != currency:
            return "exposure_conversion_missing"
        positions.append({"symbol": instrument, "units": units, "price": price})
    return positions


def _orders(raw: Any, currency: str) -> list[dict[str, Any]] | str:
    if not isinstance(raw, list):
        return "order_book_missing"
    orders: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            return "exposure_unreadable"
        state = str(item.get("state") or "").upper()
        if state != _PENDING:
            return "order_state_unverified"
        instrument = str(item.get("instrument") or "").upper()
        units = _number(item.get("units"))
        price = _number(item.get("price"))
        order_id = str(item.get("id") or "").strip()
        if "_" not in instrument or units is None or units == 0 or price is None or price <= 0 or not order_id:
            return "exposure_unreadable"
        if instrument.split("_")[-1] != currency:
            return "exposure_conversion_missing"
        orders.append(
            {
                "id": order_id,
                "symbol": instrument,
                "status": "PENDING",
                "units": abs(units),
                "price": price,
            }
        )
    return orders


def _transactions(document: Any, summary_last_id: str) -> list[dict[str, Any]] | str:
    if document is None:
        return _continuity([], summary_last_id)
    if not isinstance(document, dict):
        return "broker_response_invalid"
    if "pages" in document and "transactions" not in document:
        return "transaction_pages_incomplete"
    rows = document.get("transactions", [])
    if not isinstance(rows, list):
        return "broker_response_invalid"
    events: list[dict[str, Any]] = []
    ids: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            return "pnl_classification_unresolved"
        kind = str(row.get("type") or "").upper()
        if "orderFillTransaction" in row:
            fill = row.get("orderFillTransaction")
            event = _fill_event(fill)
            if isinstance(event, str):
                return event
            events.append(event)
            if event["sequence"] is not None:
                ids.append(int(event["sequence"]))
            continue
        if kind in _NON_PNL_TYPES or kind:
            return "pnl_classification_unresolved"
        return "pnl_classification_unresolved"
    last_id = str(document.get("lastTransactionID") or summary_last_id or "").strip()
    return _continuity(events, last_id, ids)


def _fill_event(fill: Any) -> dict[str, Any] | str:
    if not isinstance(fill, dict):
        return "pnl_unreconciled"
    event_id = str(fill.get("id") or "").strip()
    amount = _number(fill.get("pl"))
    when = fill.get("time")
    if not event_id or amount is None or not isinstance(when, str) or not when.strip():
        return "pnl_unreconciled"
    sequence = int(event_id) if event_id.isdigit() else None
    if sequence is None:
        return "event_sequence_incomplete"
    return {
        "id": event_id,
        "kind": "trade_pl",
        "amount": amount,
        "time": when,
        "sequence": sequence,
    }


def _continuity(events: list[dict[str, Any]], last_id: str, ids: list[int] | None = None) -> list[dict[str, Any]] | str:
    numbers = list(ids if ids is not None else [])
    if last_id and not last_id.isdigit():
        return "event_sequence_incomplete"
    if numbers:
        ordered = sorted(numbers)
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            return "event_gap"
        if last_id and int(last_id) != ordered[-1]:
            return "event_gap"
    elif last_id and int(last_id) != 0:
        return "event_gap"
    return events


def _observed_at(document: Any, now: datetime) -> datetime | str:
    raw = document.get("observed_at") if isinstance(document, dict) else None
    if raw is None and isinstance(document, dict) and isinstance(document.get("account"), dict):
        raw = document["account"].get("observed_at")
    if raw is None:
        return now.astimezone(timezone.utc)
    if isinstance(raw, datetime):
        parsed = raw
    elif isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return "broker_timestamp_malformed"
    else:
        return "broker_timestamp_malformed"
    if parsed.tzinfo is None:
        return "broker_timestamp_malformed"
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed
