"""Fail-closed live close confirmation.

The durable journal commits the reservation and the submission intent before
the broker close helper is called. Process memory is not that record. A durable
reservation is not broker-enforced exactly-once execution. A helper return, a
timeout, and a flat broker book are not filled-unit proof.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

CLOSE_NOT_REQUESTED = "CLOSE_NOT_REQUESTED"
CLOSE_PREPARED = "CLOSE_PREPARED"
CLOSE_SUBMITTING = "CLOSE_SUBMITTING"
CLOSE_SUBMITTED = "CLOSE_SUBMITTED"
CLOSE_RESPONSE_RECEIVED = "CLOSE_RESPONSE_RECEIVED"
CLOSE_CONFIRMATION_PENDING = "CLOSE_CONFIRMATION_PENDING"
CLOSE_PARTIALLY_CONFIRMED = "CLOSE_PARTIALLY_CONFIRMED"
CLOSE_FULLY_CONFIRMED = "CLOSE_FULLY_CONFIRMED"
CLOSE_REJECTED_CONFIRMED = "CLOSE_REJECTED_CONFIRMED"
CLOSE_OUTCOME_AMBIGUOUS = "CLOSE_OUTCOME_AMBIGUOUS"
CLOSE_RECONCILIATION_REQUIRED = "CLOSE_RECONCILIATION_REQUIRED"

_BLOCKING = frozenset(
    {
        CLOSE_PREPARED,
        CLOSE_SUBMITTING,
        CLOSE_SUBMITTED,
        CLOSE_RESPONSE_RECEIVED,
        CLOSE_CONFIRMATION_PENDING,
        CLOSE_PARTIALLY_CONFIRMED,
        CLOSE_OUTCOME_AMBIGUOUS,
        CLOSE_RECONCILIATION_REQUIRED,
        CLOSE_FULLY_CONFIRMED,
    }
)

_lock = threading.Lock()
_operations: dict[str, "CloseOperation"] = {}
_recovered: dict[str, "CloseOperation"] = {}
_flat_notes: dict[str, str] = {}


class CloseReadError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class CloseOperation:
    operation_id: str
    account_scope: str
    instrument: str
    direction: str
    trade_ids: tuple[str, ...]
    local_position_identity: str
    original_units: Decimal | None
    requested_units: Decimal | None
    confirmed_units: Decimal | None
    remaining_units: Decimal | None
    broker_request_identity: str
    transaction_ids: tuple[str, ...]
    submission_state: str
    confirmation_state: str
    error_classification: str
    attempt_count: int
    created_at: str
    updated_at: str
    evidence_source: str
    reason: str = ""
    submission_count: int = 0
    realized_pnl: Decimal | None = None
    transaction_body_retrieved: bool = False
    position_instance_id: str = ""
    position_generation: int = 0

    @property
    def blocks_resubmission(self) -> bool:
        return self.confirmation_state in _BLOCKING


def reset_close_evidence_state() -> None:
    with _lock:
        _operations.clear()
        _recovered.clear()
        _flat_notes.clear()


def close_operation_for(symbol: str) -> CloseOperation | None:
    from forex_bot.symbols import normalize_oanda_symbol

    key = normalize_oanda_symbol(symbol)
    with _lock:
        return _operations.get(key) or _recovered.get(key)


def broker_flat_note(symbol: str) -> str:
    from forex_bot.symbols import normalize_oanda_symbol

    with _lock:
        return _flat_notes.get(normalize_oanda_symbol(symbol), "")


def operation_from_journal_row(row: dict) -> CloseOperation:
    def _dec(value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        return Decimal(str(value))

    return CloseOperation(
        operation_id=row["operation_id"],
        account_scope=row["account_binding"],
        instrument=row["instrument"],
        direction=row["direction"],
        trade_ids=(row["trade_id"],),
        local_position_identity=row["position_instance_id"],
        original_units=_dec(row["original_units"]),
        requested_units=_dec(row["requested_units"]),
        confirmed_units=_dec(row["confirmed_units"]),
        remaining_units=_dec(row["remaining_units"]),
        broker_request_identity="",
        transaction_ids=tuple(part for part in (row["transaction_ids"] or "").split(",") if part),
        submission_state=row["submission_state"],
        confirmation_state=row["confirmation_state"],
        error_classification=row["error_classification"],
        attempt_count=int(row["attempt_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        evidence_source="close_journal",
        position_instance_id=row["position_instance_id"],
        position_generation=int(row["position_generation"]),
        submission_count=int(row["attempt_count"]),
    )


def operation_from_confirmed_journal(symbol: str) -> CloseOperation | None:
    """Return the single fully confirmed journal row for this instrument, if one exists."""
    from forex_bot.close_journal import JournalUnavailable, active_journal
    from forex_bot.symbols import normalize_oanda_symbol

    try:
        rows = active_journal().fully_confirmed(normalize_oanda_symbol(symbol))
    except JournalUnavailable:
        return None
    if len(rows) != 1:
        return None
    return operation_from_journal_row(rows[0])


def note_recovery_observation(operation_id: str, observation: str) -> str:
    """Record read-only evidence without clearing a blocker or submitting a close."""
    from forex_bot.close_journal import active_journal

    journal = active_journal()
    row = journal.get(operation_id)
    if row is None:
        return "missing_operation"
    journal.mark(
        operation_id,
        confirmation_state=row["confirmation_state"],
        submission_state=row["submission_state"],
        error_classification=row["error_classification"],
        confirmed_units=row["confirmed_units"],
        remaining_units=row["remaining_units"],
        transaction_ids=tuple(part for part in (row["transaction_ids"] or "").split(",") if part),
        recovery_status=observation,
    )
    return row["confirmation_state"]


def resolve_from_retrieved_transaction(operation_id: str, body: dict | None, *, account_id: str) -> str:
    """Apply one already retrieved transaction. This does not submit a close."""
    from forex_bot.close_journal import active_journal

    journal = active_journal()
    row = journal.get(operation_id)
    if row is None:
        return "missing_operation"
    if row["confirmation_state"] in {CLOSE_REJECTED_CONFIRMED, "CLOSE_FINALISED"}:
        return row["confirmation_state"]
    if row["requested_units"] is None:
        note_recovery_observation(operation_id, "incomplete_identity")
        return row["confirmation_state"]
    if not body:
        note_recovery_observation(operation_id, "no_attributable_transaction")
        return row["confirmation_state"]
    payload = body.get("transaction") if isinstance(body.get("transaction"), dict) else body
    tx_id = str(payload.get("id") or "")
    existing_ids = [
        part.strip() for part in str(row.get("transaction_ids") or "").split(",") if part.strip()
    ]
    if existing_ids and tx_id and tx_id not in existing_ids:
        note_recovery_observation(operation_id, "conflicting_transaction_id")
        return row["confirmation_state"]
    try:
        verified = apply_transaction_body(
            payload,
            instrument=row["instrument"],
            trade_id=row["trade_id"],
            direction=row["direction"],
            requested_units=Decimal(row["requested_units"]),
            transaction_id=tx_id,
            account_id=account_id,
        )
    except CloseReadError as exc:
        note_recovery_observation(operation_id, exc.reason)
        return row["confirmation_state"]
    journal.mark(
        operation_id,
        confirmation_state=str(verified["state"]),
        submission_state="SENT",
        error_classification=str(verified.get("error") or ""),
        confirmed_units=verified.get("confirmed_units"),
        remaining_units=verified.get("remaining_units"),
        transaction_ids=(tx_id,) if tx_id else (),
        recovery_status="retrieved_transaction",
    )
    return str(verified["state"])


def live_local_delete_permitted(symbol: str) -> bool:
    """Symbol-only permission is withdrawn. Deletion uses close_confirmed_live_position."""
    del symbol
    return False


def note_unattributed_broker_flat(symbol: str) -> None:
    """Record a flat book without confirming a bot close or erasing an operation."""
    from forex_bot.symbols import normalize_oanda_symbol

    key = normalize_oanda_symbol(symbol)
    with _lock:
        _flat_notes[key] = "broker_flat_not_close_confirmation"


def declare_process_restart() -> None:
    """Keep unresolved operations as in-memory blockers. This does not touch disk."""
    with _lock:
        for key, op in list(_operations.items()):
            if op.confirmation_state in _BLOCKING and op.confirmation_state != CLOSE_FULLY_CONFIRMED:
                op.confirmation_state = CLOSE_RECONCILIATION_REQUIRED
                op.error_classification = "restart_unresolved"
                op.updated_at = _now()
                _recovered[key] = op
            elif op.confirmation_state == CLOSE_FULLY_CONFIRMED:
                _recovered[key] = op
        _operations.clear()


def clear_confirmed_operation(symbol: str) -> None:
    from forex_bot.symbols import normalize_oanda_symbol

    key = normalize_oanda_symbol(symbol)
    with _lock:
        op = _operations.get(key)
        if op is not None and op.confirmation_state == CLOSE_FULLY_CONFIRMED:
            _operations.pop(key, None)
        recovered = _recovered.get(key)
        if recovered is not None and recovered.confirmation_state == CLOSE_FULLY_CONFIRMED:
            _recovered.pop(key, None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(raw: Any, *, label: str) -> Decimal:
    if raw is None:
        raise CloseReadError(f"missing_{label}")
    text = str(raw).replace(",", "").strip()
    if text == "":
        raise CloseReadError(f"missing_{label}")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise CloseReadError(f"malformed_{label}") from exc
    if not value.is_finite():
        raise CloseReadError(f"nonfinite_{label}")
    return value


def _identity(symbol: str, trade_ids: tuple[str, ...], direction: str, units: Decimal) -> str:
    return f"{symbol}|{','.join(trade_ids)}|{direction}|{units}"


def _blank(
    *,
    instrument: str = "",
    state: str = CLOSE_NOT_REQUESTED,
    reason: str = "",
) -> CloseOperation:
    stamp = _now()
    return CloseOperation(
        operation_id="",
        account_scope="missing",
        instrument=instrument,
        direction="",
        trade_ids=(),
        local_position_identity="",
        original_units=None,
        requested_units=None,
        confirmed_units=None,
        remaining_units=None,
        broker_request_identity="",
        transaction_ids=(),
        submission_state="NOT_SENT",
        confirmation_state=state,
        error_classification=reason,
        attempt_count=0,
        created_at=stamp,
        updated_at=stamp,
        evidence_source="none",
        reason=reason,
    )


def _position_still(op: CloseOperation) -> bool:
    from forex_bot.broker_exit import local_broker_trade_ids
    from forex_bot.positions import positions
    from forex_bot.symbols import normalize_oanda_symbol

    row = positions.get(op.instrument)
    if row is None:
        return False
    if normalize_oanda_symbol(getattr(row, "symbol", "") or "") != op.instrument:
        return False
    if (getattr(row, "direction", "") or "").upper() != op.direction:
        return False
    if op.position_instance_id and getattr(row, "position_instance_id", "") != op.position_instance_id:
        return False
    if op.position_generation and int(getattr(row, "position_generation", 0) or 0) != int(op.position_generation):
        return False
    if op.requested_units is not None:
        try:
            if Decimal(str(getattr(row, "units", ""))) != op.requested_units:
                return False
        except Exception:
            return False
    return tuple(local_broker_trade_ids(row)) == op.trade_ids


def _reserve(pos: Any, trade_ids: tuple[str, ...], units: Decimal, reason: str) -> tuple[CloseOperation, bool]:
    from forex_bot.symbols import normalize_oanda_symbol

    symbol = normalize_oanda_symbol(getattr(pos, "symbol", "") or "")
    direction = (getattr(pos, "direction", "") or "").upper()
    with _lock:
        recovered = _recovered.get(symbol)
        if recovered is not None and recovered.blocks_resubmission:
            return recovered, False
        current = _operations.get(symbol)
        if current is not None and current.blocks_resubmission:
            return current, False
        stamp = _now()
        op = CloseOperation(
            operation_id=uuid.uuid4().hex,
            account_scope="scoped",
            instrument=symbol,
            direction=direction,
            trade_ids=trade_ids,
            local_position_identity=_identity(symbol, trade_ids, direction, units),
            original_units=units,
            requested_units=units,
            confirmed_units=None,
            remaining_units=None,
            broker_request_identity="",
            transaction_ids=(),
            submission_state="NOT_SENT",
            confirmation_state=CLOSE_PREPARED,
            error_classification="",
            attempt_count=0,
            created_at=stamp,
            updated_at=stamp,
            evidence_source="position_close",
            reason=reason,
        )
        _operations[symbol] = op
        return op, True


def _mark(op: CloseOperation, *, state: str, error: str = "", submission: str | None = None) -> None:
    op.confirmation_state = state
    op.updated_at = _now()
    if error:
        op.error_classification = error
    if submission is not None:
        op.submission_state = submission


def _release_unsent(op: CloseOperation) -> None:
    with _lock:
        current = _operations.get(op.instrument)
        if current is op and op.submission_count == 0 and op.confirmation_state == CLOSE_PREPARED:
            _operations.pop(op.instrument, None)


def _begin_submit(op: CloseOperation) -> bool:
    with _lock:
        current = _operations.get(op.instrument)
        if current is not op or op.confirmation_state != CLOSE_PREPARED:
            return False
        if not _position_still(op):
            _mark(op, state=CLOSE_RECONCILIATION_REQUIRED, error="identity_changed", submission="NOT_SENT")
            return False
        op.attempt_count += 1
        op.submission_count += 1
        _mark(op, state=CLOSE_SUBMITTING, submission="SENDING")
        return True


def _fill_sections(body: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for key in ("longOrderFillTransaction", "shortOrderFillTransaction", "orderFillTransaction"):
        value = body.get(key)
        if isinstance(value, dict) and value:
            found.append(value)
    return found


def _reject_section(body: dict[str, Any]) -> dict[str, Any] | None:
    for key in (
        "longOrderCancelTransaction",
        "shortOrderCancelTransaction",
        "orderCancelTransaction",
        "longOrderRejectTransaction",
        "shortOrderRejectTransaction",
        "orderRejectTransaction",
    ):
        value = body.get(key)
        if isinstance(value, dict) and value:
            return value
    return None


def interpret_close_response(
    body: Any,
    *,
    instrument: str,
    trade_id: str,
    direction: str,
    requested_units: Decimal,
) -> dict[str, Any]:
    """Classify a PositionClose body. Does not confirm units until a transaction is retrieved."""
    if not isinstance(body, dict):
        raise CloseReadError("malformed_response")
    fills = _fill_sections(body)
    if len(fills) > 1:
        raise CloseReadError("duplicate_fill_transaction")
    reject = _reject_section(body)
    if not fills and reject is not None:
        return {
            "state": CLOSE_REJECTED_CONFIRMED,
            "confirmed_units": Decimal("0"),
            "remaining_units": requested_units,
            "transaction_ids": (str(reject.get("id") or ""),),
            "error": "broker_reject_or_cancel",
            "needs_transaction": False,
        }
    if not fills:
        raise CloseReadError("missing_fill_transaction")
    fill = fills[0]
    tx_id = str(fill.get("id") or "").strip()
    if not tx_id:
        raise CloseReadError("missing_transaction_id")
    fill_instrument = str(fill.get("instrument") or "").upper().replace("-", "_")
    if fill_instrument and fill_instrument != instrument:
        raise CloseReadError("instrument_mismatch")
    return {
        "state": CLOSE_RESPONSE_RECEIVED,
        "confirmed_units": None,
        "remaining_units": None,
        "transaction_ids": (tx_id,),
        "error": "",
        "needs_transaction": True,
        "direction": direction,
        "trade_id": trade_id,
    }


def _signed_reduction_magnitude(raw: Decimal, fill_units: Decimal) -> Decimal:
    """Convert one TradeReduce quantity into a non-negative magnitude.

    The two official close examples store the same signed quantity on the fill
    and on the TradeReduce. The schema text also calls TradeReduce.units the
    number of units the trade was reduced by, which is a positive magnitude
    beside a fill whose sign already matches the position direction. A negative
    TradeReduce beside a positive fill matches neither source and is rejected.
    """
    if raw == 0:
        return Decimal("0")
    if fill_units < 0:
        if raw < 0:
            return -raw
        return raw
    if raw < 0:
        raise CloseReadError("negative_closed_units")
    return raw


def _result(
    *,
    state: str,
    confirmed: Decimal | None,
    remaining: Decimal | None,
    error: str,
    signed: Decimal | None,
) -> dict[str, Any]:
    return {
        "state": state,
        "confirmed_units": confirmed,
        "remaining_units": remaining,
        "error": error,
        "account_scope": "matched",
        "signed_reduction_units": None if signed is None else str(signed),
    }


def apply_transaction_body(
    tx: Any,
    *,
    instrument: str,
    trade_id: str,
    direction: str,
    requested_units: Decimal,
    transaction_id: str,
    account_id: str,
) -> dict[str, Any]:
    """Confirm closed units from a retrieved transaction body."""
    if not isinstance(tx, dict):
        raise CloseReadError("malformed_transaction")
    if str(tx.get("type") or "").upper() != "ORDER_FILL":
        raise CloseReadError("unexpected_transaction_type")
    tx_body_id = str(tx.get("id") or "").strip()
    expected_id = transaction_id.strip()
    if not tx_body_id or not expected_id:
        raise CloseReadError("missing_transaction_id")
    if tx_body_id != expected_id:
        raise CloseReadError("transaction_id_mismatch")
    got_account = str(tx.get("accountID") or "").strip()
    if not account_id or not got_account or got_account != account_id:
        raise CloseReadError("account_mismatch")
    got_instrument = str(tx.get("instrument") or "").upper().replace("-", "_")
    if got_instrument != instrument:
        raise CloseReadError("instrument_mismatch")
    side_units = _decimal(tx.get("units"), label="units")
    if direction == "BUY" and side_units >= 0:
        raise CloseReadError("direction_mismatch")
    if direction == "SELL" and side_units <= 0:
        raise CloseReadError("direction_mismatch")
    closed_rows = tx.get("tradesClosed")
    reduced = tx.get("tradeReduced")
    if closed_rows is None and reduced is None:
        raise CloseReadError("missing_closed_trade_details")
    if closed_rows is None:
        closed_rows = []
    if not isinstance(closed_rows, list):
        raise CloseReadError("malformed_transaction")
    entries: list[tuple[str, str, Decimal]] = []
    for row in closed_rows:
        if not isinstance(row, dict):
            raise CloseReadError("malformed_transaction")
        entries.append(
            (
                "tradesClosed",
                str(row.get("tradeID") or "").strip(),
                _decimal(row.get("units"), label="units"),
            )
        )
    if reduced is not None:
        if not isinstance(reduced, dict):
            raise CloseReadError("malformed_transaction")
        entries.append(
            (
                "tradeReduced",
                str(reduced.get("tradeID") or "").strip(),
                _decimal(reduced.get("units"), label="units"),
            )
        )
    if not entries:
        raise CloseReadError("missing_closed_trade_details")
    signed_by_trade: dict[str, Decimal] = {}
    source_by_trade: dict[str, str] = {}
    closed_ids: set[str] = set()
    for source, row_trade, raw in entries:
        if not row_trade:
            raise CloseReadError("duplicate_transaction_id")
        previous = signed_by_trade.get(row_trade)
        if previous is not None:
            if source_by_trade[row_trade] == source:
                raise CloseReadError("duplicate_transaction_id")
            if previous != raw:
                return _result(
                    state=CLOSE_RECONCILIATION_REQUIRED,
                    confirmed=None,
                    remaining=None,
                    error="contradictory_reduction",
                    signed=previous,
                )
            if source == "tradesClosed":
                closed_ids.add(row_trade)
            continue
        signed_by_trade[row_trade] = raw
        source_by_trade[row_trade] = source
        if source == "tradesClosed":
            closed_ids.add(row_trade)
    matched = Decimal("0")
    other = Decimal("0")
    matched_signed: Decimal | None = None
    for row_trade, raw in signed_by_trade.items():
        magnitude = _signed_reduction_magnitude(raw, side_units)
        if row_trade == trade_id:
            matched = magnitude
            matched_signed = raw
        else:
            other += magnitude
    if matched == 0 and trade_id not in signed_by_trade:
        raise CloseReadError("trade_id_mismatch")
    if matched == 0:
        return _result(
            state=CLOSE_RECONCILIATION_REQUIRED,
            confirmed=Decimal("0"),
            remaining=requested_units,
            error="zero_confirmed_units",
            signed=matched_signed,
        )
    fill_magnitude = -side_units if side_units < 0 else side_units
    opened = tx.get("tradeOpened")
    mixed_open = isinstance(opened, dict) and bool(opened)
    if matched + other != fill_magnitude or mixed_open:
        return _result(
            state=CLOSE_RECONCILIATION_REQUIRED,
            confirmed=matched,
            remaining=None,
            error="mixed_open_and_reduce" if mixed_open else "fill_reduction_mismatch",
            signed=matched_signed,
        )
    if other > 0 or matched > requested_units:
        return _result(
            state=CLOSE_RECONCILIATION_REQUIRED,
            confirmed=matched,
            remaining=None,
            error="unit_mismatch",
            signed=matched_signed,
        )
    if matched < requested_units:
        return _result(
            state=CLOSE_PARTIALLY_CONFIRMED,
            confirmed=matched,
            remaining=requested_units - matched,
            error="partial_fill",
            signed=matched_signed,
        )
    if trade_id not in closed_ids:
        return _result(
            state=CLOSE_RECONCILIATION_REQUIRED,
            confirmed=matched,
            remaining=None,
            error="trade_reduced_is_not_full_close",
            signed=matched_signed,
        )
    return _result(
        state=CLOSE_FULLY_CONFIRMED,
        confirmed=matched,
        remaining=Decimal("0"),
        error="",
        signed=matched_signed,
    )


def _fetch_transaction(transaction_id: str) -> dict[str, Any]:
    from forex_bot.config import Config
    from forex_bot.oanda_client import get_api

    api = get_api()
    account = (Config.OANDA_ACCOUNT_ID or "").strip()
    if api is None:
        raise CloseReadError("missing_client")
    if not account:
        raise CloseReadError("missing_account")
    try:
        import oandapyV20.endpoints.transactions as tx_ep

        from forex_bot.oanda_client import _oanda_request
    except ModuleNotFoundError as exc:
        raise CloseReadError("reader_unavailable") from exc
    request = tx_ep.TransactionDetails(accountID=account, transactionID=transaction_id)
    try:
        body = _oanda_request(api, request, context="close transaction details")
    except TimeoutError as exc:
        raise CloseReadError("timeout") from exc
    except CloseReadError:
        raise
    except Exception as exc:
        raise CloseReadError("request_exception") from exc
    if not isinstance(body, dict):
        raise CloseReadError("malformed_transaction")
    tx = body.get("transaction")
    if not isinstance(tx, dict):
        raise CloseReadError("missing_transaction_body")
    return tx


def _other_operation_has_transaction(journal: Any, transaction_id: str, operation_id: str) -> bool:
    """True when a different close row already recorded this transaction id."""
    needle = transaction_id.strip()
    if not needle:
        return False
    with journal._lock:
        rows = journal._conn.execute(
            "SELECT operation_id, transaction_ids FROM close_operations"
        ).fetchall()
    for row in rows:
        if str(row["operation_id"]) == operation_id:
            continue
        parts = [part.strip() for part in str(row["transaction_ids"] or "").split(",") if part.strip()]
        if needle in parts:
            return True
    return False


def _apply_verified(op: CloseOperation, result: dict[str, Any]) -> None:
    op.confirmation_state = str(result["state"])
    op.confirmed_units = result.get("confirmed_units")
    op.remaining_units = result.get("remaining_units")
    op.error_classification = str(result.get("error") or "")
    op.transaction_body_retrieved = op.confirmation_state in {
        CLOSE_FULLY_CONFIRMED,
        CLOSE_PARTIALLY_CONFIRMED,
        CLOSE_RECONCILIATION_REQUIRED,
    }
    op.evidence_source = "transaction_details"
    op.updated_at = _now()


async def run_guarded_live_close(pos: Any, *, reason: str) -> CloseOperation:
    """Reserve, submit through the existing position-close helper, then verify units."""
    from forex_bot.broker_exit import local_broker_trade_ids
    from forex_bot.positions import ensure_position_identity, position_management_permitted
    from forex_bot.symbols import normalize_oanda_symbol

    symbol = normalize_oanda_symbol(getattr(pos, "symbol", "") or "")
    if not position_management_permitted(pos):
        return _blank(instrument=symbol, reason="management_not_permitted")
    if (getattr(pos, "execution_kind", "") or "").strip().lower() != "live":
        return _blank(instrument=symbol, reason="not_live_close")
    trade_ids = tuple(local_broker_trade_ids(pos))
    if len(trade_ids) != 1:
        error = "missing_trade_id" if not trade_ids else "multiple_trade_ids"
        op = _reserve_blocked(pos, trade_ids, error)
        return op
    try:
        units = _decimal(getattr(pos, "units", None), label="units")
    except CloseReadError as exc:
        return _reserve_blocked(pos, trade_ids, exc.reason)
    if units != units.to_integral_value():
        return _reserve_blocked(pos, trade_ids, "fractional_units")
    ensure_position_identity(pos)
    from forex_bot.close_journal import JournalUnavailable, account_binding, active_journal
    from forex_bot.config import Config

    try:
        binding = account_binding((Config.OANDA_ACCOUNT_ID or "").strip())
        journal = active_journal()
    except JournalUnavailable as exc:
        return _blank(instrument=symbol, reason=exc.reason)
    try:
        from forex_bot.position_recovery import persist_bot_position

        persist_bot_position(pos, binding)
    except JournalUnavailable as exc:
        return _blank(instrument=symbol, reason=exc.reason)
    blocker = journal.blocking_trade(binding, symbol, trade_ids[0])
    if blocker is not None:
        return operation_from_journal_row(blocker)
    op, created = _reserve(pos, trade_ids, units, reason)
    if not created or op.confirmation_state != CLOSE_PREPARED:
        return op
    try:
        from forex_bot.oanda_exec import assert_broker_order_allowed

        assert_broker_order_allowed(execution_kind="live", action="close")
    except Exception:
        _release_unsent(op)
        return _blank(instrument=symbol, reason="broker_orders_disabled")
    try:
        record = journal.reserve(
            account_binding_value=binding,
            position_instance_id=pos.position_instance_id,
            position_generation=int(pos.position_generation),
            instrument=symbol,
            trade_id=trade_ids[0],
            direction=op.direction,
            original_units=units,
            requested_units=units,
        )
        token = journal.commit_submission_intent(record["operation_id"])
        permit = journal.issue_submission_permit(record["operation_id"], token)
    except JournalUnavailable as exc:
        _mark(op, state=CLOSE_RECONCILIATION_REQUIRED, error=exc.reason, submission="NOT_SENT")
        return op
    op.operation_id = record["operation_id"]
    op.account_scope = binding
    op.position_instance_id = pos.position_instance_id
    op.position_generation = int(pos.position_generation)

    def _persist(state: str, error: str, submission: str) -> None:
        _mark(op, state=state, error=error, submission=submission)
        try:
            journal.mark(
                op.operation_id,
                confirmation_state=state,
                submission_state=submission,
                error_classification=error,
                confirmed_units=op.confirmed_units,
                remaining_units=op.remaining_units,
                transaction_ids=op.transaction_ids,
            )
        except JournalUnavailable:
            op.error_classification = error or "journal_update_failed"

    if not journal.submission_authorized(op.operation_id, token):
        _persist(CLOSE_RECONCILIATION_REQUIRED, "stale_submission_fence", "NOT_SENT")
        return op
    if not _position_still(op):
        _persist(CLOSE_RECONCILIATION_REQUIRED, "identity_changed", "SENT")
        return op
    if not _begin_submit(op):
        _persist(CLOSE_RECONCILIATION_REQUIRED, "submit_not_granted", "SENT")
        return op
    try:
        from forex_bot.oanda_exec import CloseGuardRefusal, _submit_position_close_body

        body = await asyncio.to_thread(
            _submit_position_close_body, symbol, float(units), op.direction, permit
        )
    except CloseGuardRefusal as exc:
        _persist(CLOSE_RECONCILIATION_REQUIRED, "submission_authority_refused", "NOT_SENT")
        op.reason = str(exc)
        return op
    except TimeoutError:
        _persist(CLOSE_OUTCOME_AMBIGUOUS, "timeout", "SENT")
        return op
    except Exception:
        _persist(CLOSE_OUTCOME_AMBIGUOUS, "request_exception", "SENT")
        return op
    _persist(CLOSE_RESPONSE_RECEIVED, "", "SENT")
    try:
        parsed = interpret_close_response(
            body,
            instrument=symbol,
            trade_id=trade_ids[0],
            direction=op.direction,
            requested_units=units,
        )
    except CloseReadError as exc:
        state = CLOSE_RECONCILIATION_REQUIRED if exc.reason.endswith("mismatch") or exc.reason.startswith("duplicate") else CLOSE_OUTCOME_AMBIGUOUS
        _persist(state, exc.reason, "SENT")
        return op
    op.transaction_ids = tuple(item for item in parsed["transaction_ids"] if item)
    if parsed["state"] == CLOSE_REJECTED_CONFIRMED:
        op.confirmed_units = Decimal("0")
        op.remaining_units = units
        _persist(CLOSE_REJECTED_CONFIRMED, "broker_reject_or_cancel", "SENT")
        with _lock:
            if _operations.get(symbol) is op:
                _operations.pop(symbol, None)
        return op
    if not _position_still(op):
        _persist(CLOSE_RECONCILIATION_REQUIRED, "identity_changed", "SENT")
        return op
    tx_id = op.transaction_ids[0] if op.transaction_ids else ""
    if not tx_id:
        _persist(CLOSE_OUTCOME_AMBIGUOUS, "missing_transaction_id", "SENT")
        return op
    try:
        from forex_bot.config import Config

        tx = _fetch_transaction(tx_id)
        if not _position_still(op):
            _persist(CLOSE_RECONCILIATION_REQUIRED, "identity_changed", "SENT")
            return op
        verified = apply_transaction_body(
            tx,
            instrument=symbol,
            trade_id=trade_ids[0],
            direction=op.direction,
            requested_units=units,
            transaction_id=tx_id,
            account_id=(Config.OANDA_ACCOUNT_ID or "").strip(),
        )
        if _other_operation_has_transaction(journal, tx_id, op.operation_id):
            _persist(CLOSE_RECONCILIATION_REQUIRED, "replayed_transaction_id", "SENT")
            return op
    except CloseReadError as exc:
        pending = exc.reason in {"timeout", "request_exception", "missing_client", "missing_transaction_body", "reader_unavailable"}
        _persist(
            CLOSE_CONFIRMATION_PENDING if pending else CLOSE_RECONCILIATION_REQUIRED,
            exc.reason,
            "SENT",
        )
        op.evidence_source = "transaction_details"
        return op
    _apply_verified(op, verified)
    _persist(op.confirmation_state, op.error_classification, "SENT")
    logger.info(
        "[CLOSE EVIDENCE] instrument=%s state=%s confirmed=%s remaining=%s reason=%s",
        op.instrument,
        op.confirmation_state,
        op.confirmed_units,
        op.remaining_units,
        op.error_classification,
    )
    return op


def _reserve_blocked(pos: Any, trade_ids: tuple[str, ...], error: str) -> CloseOperation:
    from forex_bot.symbols import normalize_oanda_symbol

    symbol = normalize_oanda_symbol(getattr(pos, "symbol", "") or "")
    with _lock:
        current = _operations.get(symbol) or _recovered.get(symbol)
        if current is not None and current.blocks_resubmission:
            return current
        stamp = _now()
        op = CloseOperation(
            operation_id=uuid.uuid4().hex,
            account_scope="scoped",
            instrument=symbol,
            direction=(getattr(pos, "direction", "") or "").upper(),
            trade_ids=trade_ids,
            local_position_identity=symbol,
            original_units=None,
            requested_units=None,
            confirmed_units=None,
            remaining_units=None,
            broker_request_identity="",
            transaction_ids=(),
            submission_state="NOT_SENT",
            confirmation_state=CLOSE_RECONCILIATION_REQUIRED,
            error_classification=error,
            attempt_count=0,
            created_at=stamp,
            updated_at=stamp,
            evidence_source="none",
            reason=error,
        )
        _operations[symbol] = op
        return op
