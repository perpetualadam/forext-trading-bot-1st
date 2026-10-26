"""Read-only exposure report.

This module does not write a journal, mutate the position book, submit a
broker request, or release quarantine. OpenPositions in this repository is one
response with no page token, so a parsed body is not COMPLETE_VERIFIED.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

COMPLETE_VERIFIED = "COMPLETE_VERIFIED"
INCOMPLETE = "INCOMPLETE"
UNKNOWN_COMPLETENESS = "UNKNOWN_COMPLETENESS"
FAILED = "FAILED"
STALE = "STALE"

PAGINATION_NOT_REPRESENTED = "NOT_REPRESENTED"
PAGINATION_INCOMPLETE = "INCOMPLETE"
PAGINATION_FAILED = "FAILED"

ACTIVE_MANAGEABLE_EXPOSURE = "ACTIVE_MANAGEABLE_EXPOSURE"
QUARANTINED_JOURNAL_REMAINDER = "QUARANTINED_JOURNAL_REMAINDER"
BROKER_OBSERVED_EXPOSURE = "BROKER_OBSERVED_EXPOSURE"
UNRESOLVED_EXPOSURE = "UNRESOLVED_EXPOSURE"
UNKNOWN_EXPOSURE = "UNKNOWN_EXPOSURE"

_OPEN_POSITIONS = "OpenPositions"


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _text(value: Any) -> str:
    return str(value or "").strip()


def classify_open_positions_body(
    body: Any,
    *,
    expected_account: str,
    origin: str,
    recovery_epoch: int | None,
    observed_at_utc: str | None,
    request_start_monotonic: int | None,
    response_complete_monotonic: int | None,
    chronology: str,
    cached: bool = False,
    process_id: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Classify one OpenPositions-shaped body without claiming pagination proof.

    The operational adapter performs one request and stores no page cursor.
    Completeness therefore stays unknown, incomplete, failed, or stale.
    """
    observation: dict[str, Any] = {
        "observation_id": "",
        "source_operation": _OPEN_POSITIONS,
        "origin": origin,
        "expected_account": expected_account,
        "observed_account": None,
        "request_start_monotonic": request_start_monotonic,
        "response_complete_monotonic": response_complete_monotonic,
        "observed_at_utc": observed_at_utc,
        "process_id": process_id,
        "recovery_epoch": recovery_epoch,
        "endpoint": _OPEN_POSITIONS,
        "validation": "unclassified",
        "completeness": UNKNOWN_COMPLETENESS,
        "pagination_state": PAGINATION_NOT_REPRESENTED,
        "pages_observed": 1 if body is not None else 0,
        "trade_count": None,
        "transaction_watermark": None,
        "error": error,
        "suitable_for_reporting": False,
        "suitable_for_recovery": False,
        "flat_verified": False,
        "chronology": chronology,
        "cached": bool(cached),
        "trades": [],
        "broker_order_known": False,
    }
    if error or body is None:
        observation["completeness"] = FAILED
        observation["validation"] = "retrieval_failed"
        observation["pagination_state"] = PAGINATION_FAILED
        return _seal(observation)
    if not isinstance(body, dict):
        observation["completeness"] = INCOMPLETE
        observation["validation"] = "malformed"
        return _seal(observation)
    if "positions" not in body:
        observation["completeness"] = INCOMPLETE
        observation["validation"] = "missing_positions"
        return _seal(observation)
    rows = body.get("positions")
    if not isinstance(rows, list):
        observation["completeness"] = INCOMPLETE
        observation["validation"] = "malformed_positions"
        return _seal(observation)
    account = _text(body.get("accountID") or body.get("account_id"))
    observation["observed_account"] = account or None
    if account and expected_account and account != expected_account:
        observation["completeness"] = FAILED
        observation["validation"] = "account_mismatch"
        return _seal(observation)
    trades: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            observation["completeness"] = INCOMPLETE
            observation["validation"] = "malformed_row"
            observation["trades"] = []
            return _seal(observation)
        instrument = _text(row.get("instrument")).replace("-", "_").replace("/", "_")
        if not instrument:
            observation["completeness"] = INCOMPLETE
            observation["validation"] = "missing_instrument"
            observation["trades"] = []
            return _seal(observation)
        for side_name, direction in (("long", "BUY"), ("short", "SELL")):
            side = row.get(side_name)
            if side is None:
                continue
            if not isinstance(side, dict) or "units" not in side:
                observation["completeness"] = INCOMPLETE
                observation["validation"] = "malformed_side"
                observation["trades"] = []
                return _seal(observation)
            units = _decimal(side.get("units"))
            if units is None:
                observation["completeness"] = INCOMPLETE
                observation["validation"] = "malformed_units"
                observation["trades"] = []
                return _seal(observation)
            if units == 0:
                continue
            raw_ids = side.get("tradeIDs", [])
            if raw_ids is None:
                raw_ids = []
            if not isinstance(raw_ids, list) or not raw_ids:
                observation["completeness"] = INCOMPLETE
                observation["validation"] = "missing_trade_id"
                observation["trades"] = []
                return _seal(observation)
            for raw_id in raw_ids:
                trade_id = _text(raw_id)
                if not trade_id:
                    observation["completeness"] = INCOMPLETE
                    observation["validation"] = "missing_trade_id"
                    observation["trades"] = []
                    return _seal(observation)
                key = (instrument, trade_id)
                if key in seen:
                    observation["completeness"] = INCOMPLETE
                    observation["validation"] = "duplicate_trade"
                    observation["trades"] = []
                    return _seal(observation)
                seen.add(key)
                trades.append(
                    {
                        "trade_id": trade_id,
                        "instrument": instrument,
                        "direction": direction,
                        "units": abs(units),
                        "account": account or expected_account,
                    }
                )
        _ = index
    if cached or chronology in {"LOCAL_BEFORE_CLOSE", "BEFORE_EPOCH_CHANGE", "STALE_CACHE"}:
        observation["completeness"] = STALE
        observation["validation"] = "stale"
        observation["trades"] = trades
        observation["trade_count"] = len(trades)
        return _seal(observation)
    observation["validation"] = "parsed_single_response"
    observation["completeness"] = UNKNOWN_COMPLETENESS
    observation["trades"] = trades
    observation["trade_count"] = len(trades)
    observation["suitable_for_reporting"] = True
    observation["suitable_for_recovery"] = False
    return _seal(observation)


def assess_supplied_pages(pages: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Assess caller-supplied page records.

    OpenPositions does not produce these records. The result is never
    COMPLETE_VERIFIED.
    """
    if not pages:
        return {"completeness": UNKNOWN_COMPLETENESS, "pagination_state": PAGINATION_NOT_REPRESENTED, "flat_verified": False}
    tokens: list[str] = []
    accounts: set[str] = set()
    trade_keys: set[tuple[str, str]] = set()
    for page in pages:
        if not isinstance(page, dict):
            return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "malformed_page", "flat_verified": False}
        if page.get("error"):
            return {"completeness": FAILED, "pagination_state": PAGINATION_FAILED, "reason": "page_retrieval_failed", "flat_verified": False}
        token = _text(page.get("page_token") or page.get("index"))
        if token and token in tokens:
            return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "repeated_page", "flat_verified": False}
        if token:
            tokens.append(token)
        if page.get("unexpected_token"):
            return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "unexpected_token", "flat_verified": False}
        if page.get("loop"):
            return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "pagination_loop", "flat_verified": False}
        account = _text(page.get("account"))
        if account:
            accounts.add(account)
        if len(accounts) > 1:
            return {"completeness": FAILED, "pagination_state": PAGINATION_INCOMPLETE, "reason": "mixed_account", "flat_verified": False}
        for trade in list(page.get("trades") or []):
            key = (_text(trade.get("instrument")), _text(trade.get("trade_id")))
            if not key[1]:
                return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "missing_trade_id", "flat_verified": False}
            if key in trade_keys:
                return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "duplicate_trade", "flat_verified": False}
            trade_keys.add(key)
        if page.get("missing"):
            return {"completeness": INCOMPLETE, "pagination_state": PAGINATION_INCOMPLETE, "reason": "missing_page", "flat_verified": False}
    return {
        "completeness": UNKNOWN_COMPLETENESS,
        "pagination_state": PAGINATION_NOT_REPRESENTED,
        "reason": "position_endpoint_has_no_completion_proof",
        "flat_verified": False,
        "pages_observed": len(pages),
    }


def exposure_report(
    *,
    managed: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None,
    quarantined: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None,
    close_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None,
    observation: dict[str, Any] | None,
    current_epoch: int | None = None,
    reference_now_utc: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic report. Inputs are copied. Nothing is written."""
    try:
        managed_rows = tuple(dict(row) for row in (managed or ()))
        quarantined_rows = tuple(dict(row) for row in (quarantined or ()))
        closes = tuple(dict(row) for row in (close_rows or ()))
    except (TypeError, ValueError):
        return _unavailable("malformed_input")
    if observation is not None and not isinstance(observation, dict):
        return _unavailable("malformed_observation")
    lines: list[dict[str, Any]] = []
    seen_trades: set[tuple[str, str, str]] = set()
    for row in managed_rows:
        line = _position_line(row, ACTIVE_MANAGEABLE_EXPOSURE, manageable=True, quality="in_memory_book")
        if line is None:
            return _unavailable("malformed_managed_row")
        lines.append(line)
    for row in quarantined_rows:
        line = _quarantine_line(row, closes)
        if line is None:
            return _unavailable("malformed_quarantine_row")
        lines.append(line)
    observed_lines, unknown, authoritative = _broker_lines(
        observation,
        current_epoch=current_epoch,
        reference_now_utc=reference_now_utc,
    )
    if observed_lines is None:
        return _unavailable("malformed_observation")
    for line in observed_lines:
        key = (line["category"], line["instrument"], line.get("trade_id") or "")
        if key in seen_trades:
            continue
        seen_trades.add(key)
        lines.append(line)
    if unknown:
        lines.append(
            {
                "category": UNKNOWN_EXPOSURE,
                "instrument": None,
                "direction": None,
                "trade_id": None,
                "units": None,
                "confirmed": False,
                "manageable": False,
                "suitable_for_aggregation": False,
                "evidence_quality": "unknown",
            }
        )
    by_instrument: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        instrument = line.get("instrument") or "UNKNOWN"
        by_instrument.setdefault(instrument, []).append(line)
    return {
        "status": "reported",
        "flat": False,
        "flat_verified": False,
        "authoritative_current": authoritative,
        "managed_units_by_instrument": _units_by_instrument(lines, ACTIVE_MANAGEABLE_EXPOSURE),
        "quarantined_journal_units_by_instrument": _units_by_instrument(lines, QUARANTINED_JOURNAL_REMAINDER),
        "broker_observed_units_by_instrument": _units_by_instrument(lines, BROKER_OBSERVED_EXPOSURE),
        "unknown_exposure_count": sum(1 for line in lines if line["category"] == UNKNOWN_EXPOSURE),
        "exposure_completeness": None if observation is None else observation.get("completeness"),
        "cross_instrument_raw_unit_total": None,
        "lines": lines,
        "by_instrument": by_instrument,
        "journal_mutated": False,
        "position_book_mutated": False,
        "quarantine_released": False,
        "broker_requests": 0,
    }


def _seal(observation: dict[str, Any]) -> dict[str, Any]:
    observation["flat_verified"] = False
    if observation["completeness"] != UNKNOWN_COMPLETENESS or observation["validation"] != "parsed_single_response":
        observation["suitable_for_reporting"] = observation["completeness"] == UNKNOWN_COMPLETENESS and observation["validation"] == "parsed_single_response"
        observation["suitable_for_recovery"] = False
    observation["observation_id"] = "|".join(
        [
            _text(observation.get("endpoint")),
            _text(observation.get("expected_account")),
            _text(observation.get("recovery_epoch")),
            _text(observation.get("observed_at_utc")),
            _text(observation.get("completeness")),
            str(observation.get("trade_count")),
        ]
    )
    return observation


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "flat": False,
        "flat_verified": False,
        "authoritative_current": False,
        "managed_units_by_instrument": {},
        "quarantined_journal_units_by_instrument": {},
        "broker_observed_units_by_instrument": {},
        "unknown_exposure_count": 1,
        "exposure_completeness": UNKNOWN_COMPLETENESS,
        "cross_instrument_raw_unit_total": None,
        "lines": [
            {
                "category": UNKNOWN_EXPOSURE,
                "instrument": None,
                "direction": None,
                "trade_id": None,
                "units": None,
                "confirmed": False,
                "manageable": False,
                "suitable_for_aggregation": False,
                "evidence_quality": reason,
            }
        ],
        "journal_mutated": False,
        "position_book_mutated": False,
        "quarantine_released": False,
        "broker_requests": 0,
    }


def _position_line(row: dict[str, Any], category: str, *, manageable: bool, quality: str) -> dict[str, Any] | None:
    units = _decimal(row.get("units"))
    instrument = _text(row.get("instrument") or row.get("symbol"))
    direction = _text(row.get("direction")).upper()
    if units is None or not instrument or direction not in {"BUY", "SELL"}:
        return None
    return {
        "category": category,
        "instrument": instrument,
        "direction": direction,
        "trade_id": _text(row.get("trade_id")) or None,
        "account": _text(row.get("account") or row.get("account_binding")) or None,
        "units": units,
        "original_units": _decimal(row.get("original_units")),
        "confirmed": False,
        "manageable": manageable,
        "suitable_for_aggregation": False,
        "evidence_quality": quality,
    }


def _quarantine_line(row: dict[str, Any], closes: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    instrument = _text(row.get("instrument") or row.get("symbol"))
    trade_id = _text(row.get("trade_id"))
    direction = _text(row.get("direction")).upper()
    if not instrument or direction not in {"BUY", "SELL"}:
        return None
    match = None
    for close in closes:
        if _text(close.get("instrument")) == instrument and _text(close.get("trade_id") or trade_id) == trade_id:
            match = close
            break
        if _text(close.get("instrument")) == instrument and not trade_id:
            match = close
            break
    state = _text(match.get("confirmation_state")) if match else ""
    if state and state not in {"CLOSE_FULLY_CONFIRMED", "CLOSE_PARTIALLY_CONFIRMED", "CLOSE_FINALISED"}:
        category = UNRESOLVED_EXPOSURE
        units = None
        quality = "unresolved_close"
    elif match is not None and _decimal(match.get("remaining_units")) is not None:
        category = QUARANTINED_JOURNAL_REMAINDER
        units = _decimal(match.get("remaining_units"))
        quality = "journal_remainder_not_broker_proof"
    else:
        category = QUARANTINED_JOURNAL_REMAINDER
        units = _decimal(row.get("remaining_units"))
        quality = "journal_remainder_not_broker_proof"
        if units is None:
            category = UNKNOWN_EXPOSURE
            quality = "quarantine_without_remainder"
    if units is not None and units < 0:
        return None
    return {
        "category": category,
        "instrument": instrument,
        "direction": direction,
        "trade_id": trade_id or None,
        "account": _text(row.get("account") or row.get("account_binding")) or None,
        "units": units,
        "original_units": _decimal(row.get("original_units") if row.get("original_units") is not None else row.get("units")),
        "confirmed_closed_units": None if match is None else _decimal(match.get("confirmed_units")),
        "confirmed": False,
        "manageable": False,
        "suitable_for_aggregation": False,
        "evidence_quality": quality,
    }


def _broker_lines(
    observation: dict[str, Any] | None,
    *,
    current_epoch: int | None,
    reference_now_utc: str | None,
) -> tuple[list[dict[str, Any]] | None, bool, bool]:
    if observation is None:
        return [], True, False
    completeness = _text(observation.get("completeness")) or UNKNOWN_COMPLETENESS
    if completeness == COMPLETE_VERIFIED:
        completeness = UNKNOWN_COMPLETENESS
    observed_at = _text(observation.get("observed_at_utc"))
    epoch = observation.get("recovery_epoch")
    stale = completeness == STALE or bool(observation.get("cached"))
    if reference_now_utc and observed_at and observed_at > reference_now_utc:
        stale = True
    if not observed_at:
        stale = stale or False
    if current_epoch is not None and epoch is not None and int(epoch) != int(current_epoch):
        stale = True
    if completeness == FAILED or observation.get("error"):
        return [], True, False
    if completeness == INCOMPLETE and not observation.get("trades"):
        return [], True, False
    if completeness == UNKNOWN_COMPLETENESS and not observation.get("suitable_for_reporting") and not observation.get("trades"):
        return [], True, False
    quality = "stale_not_current" if stale or completeness == STALE else "unverified_single_response"
    if completeness == INCOMPLETE:
        quality = "incomplete_not_current"
    lines: list[dict[str, Any]] = []
    expected = _text(observation.get("expected_account"))
    seen: set[tuple[str, str]] = set()
    for trade in list(observation.get("trades") or []):
        if not isinstance(trade, dict):
            return None, True, False
        account = _text(trade.get("account"))
        if expected and account and account != expected:
            continue
        units = _decimal(trade.get("units"))
        instrument = _text(trade.get("instrument"))
        direction = _text(trade.get("direction")).upper()
        trade_id = _text(trade.get("trade_id"))
        if not instrument or not trade_id or direction not in {"BUY", "SELL"} or units is None:
            return [], True, False
        identity = (instrument, trade_id)
        if identity in seen:
            continue
        seen.add(identity)
        lines.append(
            {
                "category": BROKER_OBSERVED_EXPOSURE,
                "instrument": instrument,
                "direction": direction,
                "trade_id": trade_id,
                "account": account or None,
                "units": units,
                "confirmed": False,
                "manageable": False,
                "suitable_for_aggregation": False,
                "evidence_quality": quality,
            }
        )
    unknown = not lines
    return lines, unknown, False


def _units_by_instrument(lines: list[dict[str, Any]], category: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for line in lines:
        if line["category"] != category or line.get("units") is None or not line.get("instrument"):
            continue
        instrument = str(line["instrument"])
        direction = str(line.get("direction") or "")
        bucket = out.setdefault(instrument, {})
        current = Decimal(bucket.get(direction, "0"))
        bucket[direction] = str(current + Decimal(line["units"]))
    return out
