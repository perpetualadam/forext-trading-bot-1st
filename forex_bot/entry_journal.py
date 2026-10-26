"""Durable entry intent. A permit is not entry authority and cannot close a position."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from forex_bot.close_journal import (
    SCHEMA_VERSION,
    JournalUnavailable,
    _now,
    _units,
    active_journal,
    canonical_client_order_id,
)

ENTRY_RESERVED = "ENTRY_RESERVED"
ENTRY_SUBMITTING = "ENTRY_SUBMITTING"
ENTRY_FINALISED = "ENTRY_FINALISED"
_AMBIGUOUS_ON_RESTART = {
    ENTRY_RESERVED,
    ENTRY_SUBMITTING,
    "ENTRY_SENT",
}


class EntryGuardRefusal(RuntimeError):
    """The entry journal did not grant this submission. No order was sent."""


class EntrySubmissionPermit:
    """One-shot entry capability. Constructing it does not grant authority."""

    def __init__(
        self,
        *,
        operation_id: str,
        owner_token: str,
        account_binding: str,
        instrument: str,
        direction: str,
        requested_units: str,
        position_instance_id: str,
        position_generation: int,
        client_order_id: str,
    ) -> None:
        self.operation_id = operation_id
        self.owner_token = owner_token
        self.account_binding = account_binding
        self.instrument = instrument
        self.direction = direction
        self.requested_units = requested_units
        self.position_instance_id = position_instance_id
        self.position_generation = int(position_generation)
        self.client_order_id = client_order_id


def begin_entry_submission(
    *,
    account_binding_value: str,
    instrument: str,
    direction: str,
    requested_units: Decimal,
    position_instance_id: str,
    position_generation: int,
    client_order_id: str,
    strategy_name: str,
    stop_loss: str | None,
    take_profit: str | None,
    entry_reference: str | None,
    atr_at_entry_pips: str | None,
) -> EntrySubmissionPermit:
    """Commit reservation and submission intent. The caller may then claim once."""
    journal = active_journal()
    operation_id = uuid.uuid4().hex
    token = uuid.uuid4().hex
    units = _units(requested_units, required=True)
    stamp = _now()
    direction = direction.upper()
    client_order_id = canonical_client_order_id(client_order_id)
    with journal._lock:
        journal._begin()
        try:
            authorised = journal._conn.execute("SELECT closes_authorised FROM schema_meta WHERE id = 1").fetchone()
            if authorised is None or int(authorised[0]) != 1:
                journal._rollback()
                raise JournalUnavailable("bootstrap_does_not_authorise_closes")
            prior = journal._conn.execute(
                """
                SELECT outcome FROM entry_operations
                 WHERE account_binding = ? AND client_order_id = ?
                """,
                (account_binding_value, client_order_id),
            ).fetchone()
            tombstone = journal._conn.execute(
                """
                SELECT operation_id FROM client_order_id_registry
                 WHERE account_binding = ? AND client_order_id = ?
                """,
                (account_binding_value, client_order_id),
            ).fetchone()
            if prior is not None and str(prior["outcome"]) in {ENTRY_RESERVED, ENTRY_SUBMITTING, "ENTRY_SENT"}:
                journal._rollback()
                raise JournalUnavailable("unresolved_entry_exists")
            if prior is not None or tombstone is not None:
                journal._rollback()
                raise JournalUnavailable("client_order_id_retained")
            journal._conn.execute(
                """
                INSERT INTO entry_operations (
                    operation_id, owner_token, account_binding, instrument, direction,
                    requested_units, position_instance_id, position_generation, client_order_id,
                    strategy_name, stop_loss, take_profit, entry_reference, initial_max_profit_pips,
                    initial_protection_active, atr_at_entry_pips, submission_intent, network_permit,
                    submission_state, outcome, broker_order_id, broker_trade_id, transaction_ids,
                    recovery_status, error_classification, created_at, updated_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '0', 0, ?, 0, 0,
                          'NOT_SENT', ?, NULL, NULL, '', 'reserved', '', ?, ?, ?)
                """,
                (
                    operation_id,
                    token,
                    account_binding_value,
                    instrument,
                    direction,
                    units,
                    position_instance_id,
                    int(position_generation),
                    client_order_id,
                    strategy_name,
                    stop_loss,
                    take_profit,
                    entry_reference,
                    atr_at_entry_pips,
                    ENTRY_RESERVED,
                    stamp,
                    stamp,
                    SCHEMA_VERSION,
                ),
            )
            journal._conn.execute(
                """
                INSERT INTO client_order_id_registry (
                    account_binding, client_order_id, operation_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (account_binding_value, client_order_id, operation_id, stamp),
            )
            journal._commit()
        except JournalUnavailable:
            raise
        except Exception as exc:
            journal._rollback()
            if exc.__class__.__name__ == "IntegrityError":
                raise JournalUnavailable("client_order_id_retained") from exc
            raise JournalUnavailable("persistence_failure") from exc
    with journal._lock:
        journal._begin()
        try:
            cursor = journal._conn.execute(
                """
                UPDATE entry_operations
                   SET submission_intent = 1,
                       submission_state = 'SENDING',
                       outcome = ?,
                       updated_at = ?
                 WHERE operation_id = ?
                   AND owner_token = ?
                   AND submission_intent = 0
                   AND network_permit = 0
                   AND outcome = ?
                """,
                (ENTRY_SUBMITTING, _now(), operation_id, token, ENTRY_RESERVED),
            )
            if cursor.rowcount != 1:
                journal._rollback()
                raise JournalUnavailable("entry_intent_not_durable")
            journal._commit()
        except JournalUnavailable:
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc
    return EntrySubmissionPermit(
        operation_id=operation_id,
        owner_token=token,
        account_binding=account_binding_value,
        instrument=instrument,
        direction=direction,
        requested_units=str(units),
        position_instance_id=position_instance_id,
        position_generation=int(position_generation),
        client_order_id=client_order_id,
    )


def claim_entry_permit(permit: EntrySubmissionPermit) -> None:
    """Consume one entry submission. A second claim commits nothing and sends nothing."""
    if not isinstance(permit, EntrySubmissionPermit) or not permit.owner_token:
        raise JournalUnavailable("entry_authority_refused")
    requested = _units(permit.requested_units, required=True)
    journal = active_journal()
    with journal._lock:
        journal._begin()
        try:
            cursor = journal._conn.execute(
                """
                UPDATE entry_operations
                   SET network_permit = 1,
                       submission_state = 'SENT',
                       updated_at = ?
                 WHERE operation_id = ?
                   AND owner_token = ?
                   AND account_binding = ?
                   AND instrument = ?
                   AND direction = ?
                   AND requested_units = ?
                   AND position_instance_id = ?
                   AND position_generation = ?
                   AND client_order_id = ?
                   AND submission_intent = 1
                   AND network_permit = 0
                   AND outcome = ?
                """,
                (
                    _now(),
                    permit.operation_id,
                    permit.owner_token,
                    permit.account_binding,
                    permit.instrument,
                    permit.direction,
                    requested,
                    permit.position_instance_id,
                    int(permit.position_generation),
                    permit.client_order_id,
                    ENTRY_SUBMITTING,
                ),
            )
            if cursor.rowcount != 1:
                journal._rollback()
                raise JournalUnavailable("entry_authority_refused")
            journal._commit()
        except JournalUnavailable:
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("journal_lock_or_disk") from exc


def entry_row(operation_id: str) -> dict[str, Any] | None:
    journal = active_journal()
    row = journal._conn.execute(
        "SELECT * FROM entry_operations WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def mark_entry(
    operation_id: str,
    *,
    outcome: str,
    error: str,
    broker_order_id: str = "",
    broker_trade_id: str = "",
    transaction_ids: tuple[str, ...] = (),
    recovery_status: str = "",
) -> None:
    journal = active_journal()
    with journal._lock:
        journal._begin()
        try:
            existing = journal._conn.execute(
                "SELECT outcome FROM entry_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if existing is None:
                journal._rollback()
                raise JournalUnavailable("operation_missing")
            if str(existing["outcome"]) == ENTRY_FINALISED:
                journal._rollback()
                return
            cursor = journal._conn.execute(
                """
                UPDATE entry_operations
                   SET outcome = ?,
                       error_classification = ?,
                       broker_order_id = ?,
                       broker_trade_id = ?,
                       transaction_ids = ?,
                       recovery_status = CASE WHEN ? = '' THEN recovery_status ELSE ? END,
                       updated_at = ?
                 WHERE operation_id = ?
                   AND outcome != ?
                """,
                (
                    outcome,
                    error,
                    broker_order_id or None,
                    broker_trade_id or None,
                    ",".join(transaction_ids),
                    recovery_status,
                    recovery_status,
                    _now(),
                    operation_id,
                    ENTRY_FINALISED,
                ),
            )
            if cursor.rowcount != 1:
                journal._rollback()
                raise JournalUnavailable("operation_missing")
            journal._commit()
        except JournalUnavailable:
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc


def recover_entry_operations() -> list[dict[str, Any]]:
    """Ambiguous submitted entries stay blocked. This does not send another order."""
    journal = active_journal()
    with journal._lock:
        rows = [
            dict(row)
            for row in journal._conn.execute(
                "SELECT * FROM entry_operations WHERE outcome != ?",
                (ENTRY_FINALISED,),
            ).fetchall()
        ]
        recovered: list[dict[str, Any]] = []
        for row in rows:
            intent = int(row["submission_intent"])
            if intent == 0 and row["outcome"] == ENTRY_RESERVED:
                outcome = "ENTRY_RECONCILIATION_REQUIRED"
                error = "reserved_without_submission_intent"
            elif intent == 1 and row["outcome"] in _AMBIGUOUS_ON_RESTART:
                outcome = "ENTRY_OUTCOME_AMBIGUOUS"
                error = "crash_after_entry_submission_intent"
            else:
                continue
            journal._begin()
            journal._conn.execute(
                """
                UPDATE entry_operations
                   SET outcome = ?, error_classification = ?, recovery_status = ?, updated_at = ?
                 WHERE operation_id = ?
                """,
                (outcome, error, error, _now(), row["operation_id"]),
            )
            journal._commit()
            recovered.append(entry_row(row["operation_id"]) or row)
        return recovered


def unresolved_entry_for(account_binding_value: str, instrument: str) -> dict[str, Any] | None:
    journal = active_journal()
    row = journal._conn.execute(
        """
        SELECT * FROM entry_operations
         WHERE account_binding = ? AND instrument = ? AND outcome != ?
        """,
        (account_binding_value, instrument, ENTRY_FINALISED),
    ).fetchone()
    return dict(row) if row is not None else None


def commit_verified_entry(
    permit: EntrySubmissionPermit,
    pos: Any,
    *,
    broker_order_id: str,
    broker_trade_id: str,
    transaction_ids: tuple[str, ...],
) -> None:
    """Commit the managed position and ENTRY_FINALISED in one transaction."""
    from forex_bot.position_recovery import _write_managed_position

    if not isinstance(permit, EntrySubmissionPermit):
        raise JournalUnavailable("entry_authority_refused")
    if not broker_trade_id:
        raise JournalUnavailable("missing_trade_id")
    journal = active_journal()
    with journal._lock:
        journal._begin()
        try:
            row = journal._conn.execute(
                "SELECT * FROM entry_operations WHERE operation_id = ?",
                (permit.operation_id,),
            ).fetchone()
            if row is None:
                raise JournalUnavailable("operation_missing")
            if (
                row["owner_token"] != permit.owner_token
                or row["account_binding"] != permit.account_binding
                or row["client_order_id"] != permit.client_order_id
                or row["instrument"] != permit.instrument
                or row["direction"] != permit.direction
                or row["position_instance_id"] != permit.position_instance_id
                or int(row["position_generation"]) != int(permit.position_generation)
                or str(row["requested_units"]) != str(permit.requested_units)
            ):
                raise JournalUnavailable("entry_position_identity_conflict")
            if not row["stop_loss"] or not row["take_profit"]:
                raise JournalUnavailable("missing_protection_state")
            if str(row["outcome"]) == ENTRY_FINALISED:
                existing = journal._conn.execute(
                    """
                    SELECT trade_id, position_instance_id, position_generation
                      FROM managed_positions WHERE entry_operation_id = ?
                    """,
                    (permit.operation_id,),
                ).fetchone()
                if (
                    existing is None
                    or existing["trade_id"] != broker_trade_id
                    or existing["position_instance_id"] != permit.position_instance_id
                    or int(existing["position_generation"]) != int(permit.position_generation)
                ):
                    raise JournalUnavailable("finalised_without_matching_position")
                journal._rollback()
                return
            if str(row["outcome"]) not in {ENTRY_SUBMITTING, "ENTRY_CONFIRMED_SINGLE_TRADE"}:
                raise JournalUnavailable("entry_not_finalisable")
            _write_managed_position(journal, pos, permit.account_binding, permit.operation_id)
            cursor = journal._conn.execute(
                """
                UPDATE entry_operations
                   SET outcome = ?,
                       error_classification = '',
                       broker_order_id = ?,
                       broker_trade_id = ?,
                       transaction_ids = ?,
                       recovery_status = 'position_persisted',
                       updated_at = ?
                 WHERE operation_id = ?
                   AND owner_token = ?
                   AND outcome IN ('ENTRY_SUBMITTING', 'ENTRY_CONFIRMED_SINGLE_TRADE')
                """,
                (
                    ENTRY_FINALISED,
                    broker_order_id or None,
                    broker_trade_id,
                    ",".join(transaction_ids),
                    _now(),
                    permit.operation_id,
                    permit.owner_token,
                ),
            )
            if cursor.rowcount != 1:
                raise JournalUnavailable("entry_finalisation_refused")
            journal._commit()
        except JournalUnavailable:
            journal._rollback()
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc


def archive_finalised_client_id(operation_id: str) -> None:
    """Remove a finalised operation row. The client-id registry stays."""
    journal = active_journal()
    with journal._lock:
        journal._begin()
        try:
            row = journal._conn.execute(
                "SELECT account_binding, client_order_id, outcome FROM entry_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if row is None or str(row["outcome"]) != ENTRY_FINALISED:
                raise JournalUnavailable("archive_refused")
            kept = journal._conn.execute(
                """
                SELECT operation_id FROM client_order_id_registry
                 WHERE account_binding = ? AND client_order_id = ?
                """,
                (row["account_binding"], row["client_order_id"]),
            ).fetchone()
            if kept is None:
                raise JournalUnavailable("archive_refused")
            journal._conn.execute("DELETE FROM entry_operations WHERE operation_id = ?", (operation_id,))
            journal._commit()
        except JournalUnavailable:
            journal._rollback()
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc


def capture_gaps() -> list[dict[str, Any]]:
    """Finalised or confirmed entries that have no matching durable position."""
    journal = active_journal()
    rows = journal._conn.execute(
        """
        SELECT outcome, operation_id FROM entry_operations
         WHERE outcome IN ('ENTRY_FINALISED', 'ENTRY_CONFIRMED_SINGLE_TRADE')
           AND operation_id NOT IN (
                SELECT entry_operation_id FROM managed_positions
                 WHERE entry_operation_id IS NOT NULL
           )
        """
    ).fetchall()
    gaps = []
    for row in rows:
        reason = (
            "finalised_without_position"
            if row["outcome"] == ENTRY_FINALISED
            else "confirmed_without_position"
        )
        gaps.append(
            {
                "state": "quarantined",
                "reason": reason,
                "manageable": False,
                "close_submission_count": 0,
                "delete_permitted": False,
                "operator_required": True,
                "operation_id": row["operation_id"],
            }
        )
    return gaps
