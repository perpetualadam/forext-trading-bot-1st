"""Injected broker-account reconciliation for the shared evaluate path.

This module does not call OANDA and does not read credentials. A snapshot is
accepted only when its provenance is ``injected_synthetic``.

OANDA contracts that this repository does not define, and which are therefore
not guessed:

- ``AccountSummary`` NAV is described by the existing client as broker equity.
  The live fetch substitutes ``balance`` when NAV is absent. This boundary
  does not. It also does not assume ``NAV == balance + unrealisedPL``.
- Transaction names such as ORDER_FILL, DAILY_FINANCING and TRANSFER_FUNDS
  are not parsed. Financing, fees, transfers and unclassified amounts fail
  closed. Only an explicit ``trade_pl`` event, or a reversal of one, changes
  realised P&L.
- A sequence gap is enforced only when a snapshot or event carries sequence
  information. Absent sequence evidence is recorded and is not treated as
  proof that the ledger is complete.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from forex_bot.execution_risk import (
    _attested,
    _finite,
    _load,
    _save,
    _state_path,
    exclusive_state,
)
from forex_bot.execution_risk import _LOCK

SNAPSHOT_MAX_AGE_SEC = 300
_PROVENANCE = {"injected_synthetic", "oanda_account_summary"}
_TRADE = "trade_pl"
_REVERSAL = {"reversal", "correction"}
_UNRESOLVED_KINDS = {"financing", "fee", "transfer", "unknown"}
_OUTSTANDING = {"PENDING", "PARTIAL", "UNRESOLVED"}


def reconcile_for_entry(
    *,
    now: datetime | None,
    snapshot: dict[str, Any] | None,
    events: list[Any] | None,
    expected_account_id: str | None,
    expected_currency: str | None,
) -> tuple[str | None, dict[str, Any]]:
    """Validate an injected snapshot into durable state, or require an existing attestation."""
    if snapshot is None and not events:
        return _require_attestation()
    if not isinstance(snapshot, dict):
        return "broker_snapshot_missing", {}
    reason, dest = _state_path()
    if reason or dest is None:
        return reason or "risk_state_unconfigured", {}
    with _LOCK:
        with exclusive_state(dest) as held:
            if held:
                return held, {}
            loaded, doc = _load(dest)
            if loaded or doc is None:
                return loaded or "risk_state_missing", {}
            if not _attested(doc):
                return "account_unreconciled", {}
            reason, view = _reconcile(doc, snapshot, list(events or []), now, expected_account_id, expected_currency)
            if reason:
                return reason, {}
            saved = _save(dest, view["document"])
            if saved:
                return "durable_state_failed", {}
            return None, view["result"]


def _require_attestation() -> tuple[str | None, dict[str, Any]]:
    reason, dest = _state_path()
    if reason or dest is None:
        return reason or "risk_state_unconfigured", {}
    with _LOCK:
        with exclusive_state(dest) as held:
            if held:
                return held, {}
            loaded, doc = _load(dest)
            if loaded or doc is None:
                return loaded or "risk_state_missing", {}
            if not _attested(doc):
                return "account_unreconciled", {}
    return None, {"used_broker_nav": False}


def _reconcile(
    doc: dict[str, Any],
    snapshot: dict[str, Any],
    events: list[Any],
    now: datetime | None,
    expected_account_id: str | None,
    expected_currency: str | None,
) -> tuple[str | None, dict[str, Any]]:
    if now is None or now.tzinfo is None:
        return "broker_timestamp_malformed", {}
    identity = _identity(snapshot, doc, expected_account_id, expected_currency)
    if identity:
        return identity, {}
    parsed = _snapshot_values(snapshot, now)
    if isinstance(parsed, str):
        return parsed, {}
    reason = _snapshot_order(doc, parsed)
    if reason:
        return reason, {}
    planned = _plan_events(doc, events, parsed)
    if isinstance(planned, str):
        return planned, {}
    exposure = _exposure_book(snapshot, str(doc.get("currency") or ""), now)
    if isinstance(exposure, str):
        return exposure, {}
    updated = _apply(doc, parsed, planned, exposure)
    if isinstance(updated, str):
        return updated, {}
    result = {
        "used_broker_nav": True,
        "nav": parsed["nav"],
        "balance": parsed["balance"],
        "unrealised": parsed["unrealised"],
        "as_of": parsed["as_of"],
        "changed": updated["changed"],
    }
    return None, {"document": updated["document"], "result": result}


def _identity(
    snapshot: dict[str, Any],
    doc: dict[str, Any],
    expected_account_id: str | None,
    expected_currency: str | None,
) -> str | None:
    if str(snapshot.get("provenance") or "") not in _PROVENANCE:
        return "broker_provenance_rejected"
    expected_id = (expected_account_id or os.getenv("RISK_ACCOUNT_ID") or "").strip()
    expected_ccy = (expected_currency or os.getenv("RISK_ACCOUNT_CURRENCY") or "").strip().upper()
    actual_id = str(snapshot.get("id") or "").strip()
    actual_ccy = str(snapshot.get("currency") or "").strip().upper()
    if not expected_id:
        return "broker_account_unconfigured"
    if not expected_ccy:
        return "broker_currency_unconfigured"
    if not actual_id or actual_id != expected_id or actual_id != str(doc.get("account_id") or ""):
        return "broker_account_mismatch"
    if not actual_ccy or actual_ccy != expected_ccy or actual_ccy != str(doc.get("currency") or ""):
        return "broker_currency_mismatch"
    return None


def _snapshot_values(snapshot: dict[str, Any], now: datetime) -> dict[str, Any] | str:
    as_of = _time(snapshot.get("as_of"))
    if as_of is None:
        return "broker_timestamp_malformed"
    if as_of > now:
        return "account_timestamp_future"
    if (now - as_of).total_seconds() > SNAPSHOT_MAX_AGE_SEC:
        return "account_snapshot_stale"
    if "NAV" not in snapshot and "nav" not in snapshot:
        return "broker_equity_missing"
    nav = _finite(snapshot.get("NAV", snapshot.get("nav")))
    if nav is None:
        return "broker_value_nonfinite"
    if nav <= 0:
        return "broker_equity_invalid"
    if "balance" not in snapshot:
        return "broker_balance_missing"
    balance = _finite(snapshot.get("balance"))
    if balance is None:
        return "broker_value_nonfinite"
    if balance <= 0:
        return "broker_balance_invalid"
    if "unrealised" not in snapshot and "unrealizedPL" not in snapshot:
        return "broker_unrealised_missing"
    unrealised = _finite(snapshot.get("unrealised", snapshot.get("unrealizedPL")))
    if unrealised is None:
        return "broker_value_nonfinite"
    if "equity" in snapshot:
        other = _finite(snapshot.get("equity"))
        if other is None or abs(other - nav) > 1e-6:
            return "account_values_inconsistent"
    if "unrealised" in snapshot and "unrealizedPL" in snapshot:
        other_pl = _finite(snapshot.get("unrealizedPL"))
        if other_pl is None or abs(other_pl - unrealised) > 1e-6:
            return "account_values_inconsistent"
    day_start = None
    if "day_start_nav" in snapshot:
        day_start = _finite(snapshot.get("day_start_nav"))
        if day_start is None or day_start <= 0:
            return "broker_value_nonfinite"
    realised_today = None
    if "realised_today" in snapshot:
        realised_today = _finite(snapshot.get("realised_today"))
        if realised_today is None:
            return "broker_value_nonfinite"
    sequence_end = snapshot.get("expected_sequence_end")
    if sequence_end is not None and (isinstance(sequence_end, bool) or not isinstance(sequence_end, int)):
        return "event_sequence_incomplete"
    return {
        "snapshot_id": str(snapshot.get("snapshot_id") or "").strip(),
        "as_of": as_of,
        "nav": nav,
        "balance": balance,
        "unrealised": unrealised,
        "day_start_nav": day_start,
        "realised_today": realised_today,
        "sequence_end": sequence_end,
        "body": (
            str(snapshot.get("snapshot_id") or ""),
            as_of.isoformat(),
            nav,
            balance,
            unrealised,
        ),
    }


def _snapshot_order(doc: dict[str, Any], parsed: dict[str, Any]) -> str | None:
    if not parsed["snapshot_id"]:
        return "broker_snapshot_missing"
    recon = doc.get("reconciliation")
    if not isinstance(recon, dict):
        return "account_unreconciled"
    if recon.get("status") != "verified":
        return None
    stored_as_of = _time(recon.get("as_of"))
    stored_body = (
        str(recon.get("snapshot_id") or ""),
        stored_as_of.isoformat() if stored_as_of else "",
        _finite(recon.get("nav")),
        _finite(recon.get("balance")),
        _finite(recon.get("unrealised")),
    )
    if stored_as_of is not None and parsed["as_of"] < stored_as_of:
        return "snapshot_out_of_order"
    if stored_as_of is not None and parsed["as_of"] == stored_as_of and stored_body != parsed["body"]:
        return "snapshot_conflict"
    if str(recon.get("snapshot_id") or "") == parsed["snapshot_id"] and stored_body != parsed["body"]:
        return "snapshot_conflict"
    return None


def _plan_events(doc: dict[str, Any], events: list[Any], parsed: dict[str, Any]) -> dict[str, Any] | str:
    stored = doc.get("events", {})
    if not isinstance(stored, dict):
        return "risk_state_malformed"
    recon = doc.get("reconciliation") if isinstance(doc.get("reconciliation"), dict) else {}
    last_sequence = recon.get("last_sequence")
    if last_sequence is not None and (isinstance(last_sequence, bool) or not isinstance(last_sequence, int)):
        return "risk_state_malformed"
    if parsed["sequence_end"] is not None and not events and last_sequence != parsed["sequence_end"]:
        return "event_gap"
    sequenced = [event for event in events if isinstance(event, dict) and event.get("sequence") is not None]
    if sequenced and len(sequenced) != len(events):
        return "event_sequence_incomplete"
    if parsed["sequence_end"] is not None and not sequenced and events:
        return "event_gap"
    if sequenced:
        events = sorted(events, key=lambda item: int(item["sequence"]))
    prepared: list[dict[str, Any]] = []
    seen = dict(stored)
    for raw in events:
        if not isinstance(raw, dict):
            return "pnl_classification_unresolved"
        item = _one_event(raw, seen)
        if isinstance(item, str):
            return item
        if item is not None:
            seen[item["id"]] = item
            prepared.append(item)
    if prepared and sequenced:
        reason = _sequence(prepared, last_sequence, parsed["sequence_end"])
        if reason:
            return reason
    if parsed["sequence_end"] is not None:
        resulting = last_sequence
        numbers = [int(item["sequence"]) for item in prepared if item.get("sequence") is not None]
        if numbers:
            resulting = max(numbers)
        if resulting != parsed["sequence_end"]:
            return "event_gap"
    deltas: dict[str, float] = {}
    new_events: dict[str, dict[str, Any]] = {}
    for item in prepared:
        if item["id"] in stored:
            continue
        new_events[item["id"]] = item
        if item["effect"] == "realised":
            deltas[item["day"]] = deltas.get(item["day"], 0.0) + float(item["amount"])
    return {"new_events": new_events, "deltas": deltas, "sequenced": bool(sequenced)}


def _one_event(raw: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any] | str | None:
    event_id = str(raw.get("id") or "").strip()
    kind = str(raw.get("kind") or "").strip().lower()
    when = _time(raw.get("time"))
    amount = _finite(raw.get("amount"))
    if not event_id or when is None or amount is None:
        return "pnl_unreconciled"
    sequence = raw.get("sequence")
    if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int)):
        return "event_sequence_incomplete"
    previous = stored.get(event_id)
    if isinstance(previous, dict):
        if _finite(previous.get("amount")) != amount or str(previous.get("kind") or "") != kind:
            return "event_conflict"
        return None
    if kind in _UNRESOLVED_KINDS or kind not in {_TRADE, *_REVERSAL}:
        return "pnl_classification_unresolved"
    day = when.astimezone(timezone.utc).date().isoformat()
    if kind in _REVERSAL:
        target_id = str(raw.get("reverses") or "").strip()
        target = stored.get(target_id)
        if not target_id or not isinstance(target, dict):
            return "correction_target_missing"
        target_amount = _finite(target.get("amount"))
        if target_amount is None or abs(amount + target_amount) > 1e-6:
            return "event_conflict"
        if str(target.get("effect") or "") != "realised":
            return "pnl_classification_unresolved"
    elif kind != _TRADE:
        return "pnl_classification_unresolved"
    return {
        "id": event_id,
        "kind": kind,
        "amount": amount,
        "time": when.isoformat(),
        "sequence": sequence,
        "day": day,
        "effect": "realised",
        "reverses": str(raw.get("reverses") or "") or None,
    }


def _sequence(events: list[dict[str, Any]], last_sequence: int | None, sequence_end: int | None) -> str | None:
    numbers = [int(event["sequence"]) for event in events]
    if len(numbers) != len(set(numbers)):
        return "event_conflict"
    ordered = sorted(numbers)
    if any(ordered[index] + 1 != ordered[index + 1] for index in range(len(ordered) - 1)):
        return "event_gap"
    if last_sequence is None:
        if ordered[0] != 1:
            return "event_gap"
    elif ordered[0] <= last_sequence:
        return "event_out_of_order"
    elif ordered[0] != last_sequence + 1:
        return "event_gap"
    if sequence_end is not None and ordered[-1] != sequence_end:
        return "event_gap"
    return None


def _exposure_book(snapshot: dict[str, Any], currency: str, now: datetime) -> dict[str, list[dict[str, Any]]] | str:
    positions_raw = snapshot.get("positions", [])
    orders_raw = snapshot.get("orders", [])
    if not isinstance(positions_raw, list) or not isinstance(orders_raw, list):
        return "exposure_unreadable"
    positions: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for raw in positions_raw:
        item = _notional_item(raw, currency, now, require_id=False)
        if isinstance(item, str):
            return item
        symbols.add(item["symbol"])
        positions.append(item)
    orders: list[dict[str, Any]] = []
    for raw in orders_raw:
        item = _notional_item(raw, currency, now, require_id=True)
        if isinstance(item, str):
            return item
        status = str(raw.get("status") or "").upper()
        if status == "FILLED" and item["symbol"] in symbols:
            continue
        if status not in _OUTSTANDING and status != "FILLED":
            continue
        item["status"] = status
        orders.append(item)
    return {"exposure_positions": positions, "exposure_orders": orders}


def _notional_item(raw: Any, currency: str, now: datetime, *, require_id: bool) -> dict[str, Any] | str:
    if not isinstance(raw, dict):
        return "exposure_unreadable"
    symbol = str(raw.get("symbol") or "").upper()
    units = _finite(raw.get("units"))
    price = _finite(raw.get("price"))
    if "_" not in symbol or units is None or price is None or units == 0 or price <= 0:
        return "exposure_unreadable"
    quote = symbol.split("_")[-1]
    conversion = raw.get("conversion_price")
    if quote == currency:
        notional = abs(units) * price
    else:
        rate = _finite(conversion)
        if conversion is None or rate is None or rate <= 0:
            return "exposure_conversion_missing"
        priced_at = _time(raw.get("conversion_as_of"))
        if priced_at is None or priced_at > now or (now - priced_at).total_seconds() > SNAPSHOT_MAX_AGE_SEC:
            return "conversion_price_stale"
        notional = abs(units) * price * rate
    item = {"symbol": symbol, "notional_account_ccy": notional}
    if require_id:
        item["id"] = str(raw.get("id") or "").strip()
        if not item["id"]:
            return "exposure_unreadable"
    return item


def _apply(
    doc: dict[str, Any],
    parsed: dict[str, Any],
    planned: dict[str, Any],
    exposure: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | str:
    day = parsed["as_of"].astimezone(timezone.utc).date().isoformat()
    baselines = dict(doc.get("day_baselines") or {})
    realised_book = dict(doc.get("realised_by_day") or {})
    if parsed["day_start_nav"] is not None:
        current = _finite(baselines.get(day))
        if current is None:
            baselines[day] = parsed["day_start_nav"]
        elif abs(current - parsed["day_start_nav"]) > 1e-6:
            return "daily_baseline_conflict"
    for event_day, delta in planned["deltas"].items():
        if _finite(baselines.get(event_day)) is None or _finite(realised_book.get(event_day)) is None:
            return "daily_loss_baseline_missing"
        realised_book[event_day] = float(realised_book[event_day]) + float(delta)
    if parsed["realised_today"] is not None:
        current = _finite(realised_book.get(day))
        if current is None or abs(current - parsed["realised_today"]) > 1e-6:
            return "pnl_unreconciled"
    peak = _finite(doc.get("peak_equity"))
    if peak is None or peak <= 0:
        return "drawdown_reference_missing"
    if parsed["nav"] > peak:
        peak = parsed["nav"]
    events = dict(doc.get("events") or {})
    events.update(planned["new_events"])
    sequences = [int(item["sequence"]) for item in planned["new_events"].values() if item.get("sequence") is not None]
    recon = dict(doc.get("reconciliation") or {})
    last_sequence = recon.get("last_sequence")
    if sequences:
        last_sequence = max(sequences)
    same_book = exposure["exposure_positions"] == doc.get("exposure_positions", []) and exposure["exposure_orders"] == doc.get(
        "exposure_orders", []
    )
    same_snapshot = (
        str(recon.get("snapshot_id") or "") == parsed["snapshot_id"]
        and _finite(recon.get("nav")) == parsed["nav"]
        and _finite(recon.get("balance")) == parsed["balance"]
        and _finite(recon.get("unrealised")) == parsed["unrealised"]
        and str(recon.get("as_of") or "") == parsed["as_of"].isoformat()
    )
    changed = bool(planned["new_events"]) or parsed["nav"] > float(doc.get("peak_equity") or 0.0) or not same_book or not same_snapshot
    recon.update(
        {
            "status": "verified",
            "account_id": doc.get("account_id"),
            "currency": doc.get("currency"),
            "snapshot_id": parsed["snapshot_id"],
            "as_of": parsed["as_of"].isoformat(),
            "nav": parsed["nav"],
            "balance": parsed["balance"],
            "unrealised": parsed["unrealised"],
            "equity_source": "broker_nav",
            "sequence_evidence": "contiguous" if planned["sequenced"] or last_sequence is not None else "absent",
            "last_sequence": last_sequence,
        }
    )
    revision = doc.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        revision = 0
    if changed:
        revision += 1
    updated = dict(doc)
    updated.update(
        {
            "peak_equity": peak,
            "day_baselines": baselines,
            "realised_by_day": realised_book,
            "revision": revision,
            "reconciliation": recon,
            "events": events,
            "exposure_positions": exposure["exposure_positions"],
            "exposure_orders": exposure["exposure_orders"],
        }
    )
    return {"document": updated, "changed": changed}


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)
