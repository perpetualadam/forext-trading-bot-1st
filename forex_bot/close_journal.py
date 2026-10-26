"""Durable close-operation journal.

Local SQLite is the source of truth for close reservations. Process memory is not.
A reservation row is committed before submission intent, and submission intent is
committed before any broker-close helper may be called.

Durability choices, verified by the open sequence rather than assumed:
- journal_mode=WAL so a commit is a single WAL frame append.
- synchronous=FULL so SQLite waits for the WAL frame to be flushed before COMMIT returns.
- isolation_level=None and an explicit BEGIN IMMEDIATE / COMMIT around each transition.
- busy_timeout so a second process waits briefly, then the caller fails closed.
- a partial unique index so one account/instrument/trade can have only one unresolved row.

This is single-machine file locking. It is not cross-machine coordination, and it is
not broker-enforced exactly-once execution. There is no lease expiry and no takeover:
an intent row stays ambiguous until authoritative evidence is recorded.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 5
CLIENT_ORDER_ID_LIMIT = 128
_RELEASED = ("CLOSE_REJECTED_CONFIRMED", "CLOSE_FINALISED")

SCHEMA_SQL = """
CREATE TABLE schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    bootstrapped_at TEXT NOT NULL,
    closes_authorised INTEGER NOT NULL
);
CREATE TABLE close_operations (
    operation_id TEXT PRIMARY KEY,
    position_instance_id TEXT NOT NULL,
    position_generation INTEGER NOT NULL,
    account_binding TEXT NOT NULL,
    instrument TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    original_units TEXT,
    requested_units TEXT,
    confirmed_units TEXT,
    remaining_units TEXT,
    submission_state TEXT NOT NULL,
    confirmation_state TEXT NOT NULL,
    submission_intent INTEGER NOT NULL,
    network_permit INTEGER NOT NULL,
    owner_token TEXT NOT NULL,
    transaction_ids TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_classification TEXT NOT NULL,
    recovery_status TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);
CREATE UNIQUE INDEX one_unresolved_close
    ON close_operations(account_binding, instrument, trade_id)
    WHERE confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED');
CREATE TABLE managed_positions (
    position_instance_id TEXT PRIMARY KEY,
    position_generation INTEGER NOT NULL,
    account_binding TEXT NOT NULL,
    instrument TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    units TEXT NOT NULL,
    execution_kind TEXT NOT NULL,
    provenance TEXT NOT NULL,
    entry_price TEXT,
    stop_loss TEXT,
    take_profit TEXT,
    open_time TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    rl_state TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    broker_order_id TEXT NOT NULL,
    broker_order INTEGER NOT NULL,
    management_status TEXT NOT NULL,
    close_operation_id TEXT,
    max_profit_pips TEXT,
    profit_protection_active INTEGER,
    profit_protection_seeded INTEGER,
    profit_protection_exit_pips TEXT,
    profit_protection_close_attempt_ts TEXT,
    atr_at_entry_pips TEXT,
    protect_activated_mfe_pips TEXT,
    protect_activated_atr_pips TEXT,
    protect_activated_giveback_pips TEXT,
    protect_activated_exit_pips TEXT,
    atr_fallback_used INTEGER,
    min_profit_pips TEXT,
    max_adverse_pips TEXT,
    entry_operation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX one_managed_trade
    ON managed_positions(account_binding, trade_id);
CREATE TABLE entry_operations (
    operation_id TEXT PRIMARY KEY,
    owner_token TEXT NOT NULL,
    account_binding TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    requested_units TEXT NOT NULL,
    position_instance_id TEXT NOT NULL,
    position_generation INTEGER NOT NULL,
    client_order_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    stop_loss TEXT,
    take_profit TEXT,
    entry_reference TEXT,
    initial_max_profit_pips TEXT,
    initial_protection_active INTEGER NOT NULL,
    atr_at_entry_pips TEXT,
    submission_intent INTEGER NOT NULL,
    network_permit INTEGER NOT NULL,
    submission_state TEXT NOT NULL,
    outcome TEXT NOT NULL,
    broker_order_id TEXT,
    broker_trade_id TEXT,
    transaction_ids TEXT NOT NULL,
    recovery_status TEXT NOT NULL,
    error_classification TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);
CREATE UNIQUE INDEX one_client_order_id
    ON entry_operations(account_binding, client_order_id);
CREATE TABLE client_order_id_registry (
    account_binding TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (account_binding, client_order_id)
);
CREATE TABLE recovery_runs (
    run_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    owner_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    fencing_epoch INTEGER NOT NULL DEFAULT 0,
    owner_pid INTEGER,
    process_start TEXT,
    boot_id TEXT,
    lock_identity TEXT
);
CREATE UNIQUE INDEX one_recovery_in_progress
    ON recovery_runs(state)
    WHERE state = 'RECOVERY_IN_PROGRESS';
CREATE TABLE recovery_authority (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    fencing_epoch INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE entry_investigations (
    investigation_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    classification TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE recovery_repairs (
    repair_id TEXT PRIMARY KEY,
    journal_identity TEXT NOT NULL,
    account_binding TEXT NOT NULL,
    target_run_id TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    operator_acknowledgement TEXT NOT NULL,
    liveness_method TEXT NOT NULL,
    liveness_status TEXT NOT NULL,
    integrity_result TEXT NOT NULL,
    unresolved_entry_count INTEGER NOT NULL,
    unresolved_close_count INTEGER NOT NULL,
    result TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class JournalUnavailable(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class CloseSubmissionPermit:
    """One-shot capability. Constructing it does not grant authority.

    ``claim_network_permit`` is the only check that allows a broker close,
    and it accepts the permit only when the journal row still matches.
    """

    def __init__(
        self,
        *,
        operation_id: str,
        owner_token: str,
        account_binding: str,
        instrument: str,
        trade_id: str,
        direction: str,
        requested_units: str,
        position_instance_id: str,
        position_generation: int,
    ) -> None:
        self.operation_id = operation_id
        self.owner_token = owner_token
        self.account_binding = account_binding
        self.instrument = instrument
        self.trade_id = trade_id
        self.direction = direction
        self.requested_units = requested_units
        self.position_instance_id = position_instance_id
        self.position_generation = int(position_generation)


def account_binding(account_id: str) -> str:
    """Non-secret scope. The raw account id is not stored."""
    text = str(account_id or "").strip()
    if not text:
        raise JournalUnavailable("missing_account")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _units(value: Any, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise JournalUnavailable("invalid_units")
        return None
    if isinstance(value, bool):
        raise JournalUnavailable("invalid_units")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise JournalUnavailable("invalid_units") from None
    if not dec.is_finite():
        raise JournalUnavailable("invalid_units")
    return format(dec, "f")


def _busy_ms() -> int:
    raw = os.environ.get("CLOSE_JOURNAL_BUSY_MS", "5000").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 5000


class CloseJournal:
    def __init__(self, connection: sqlite3.Connection, *, fail_after: str = "") -> None:
        self._conn = connection
        self._fail_after = fail_after
        self._lock = threading.RLock()

    def close(self) -> None:
        self._conn.close()

    def _fault(self, point: str) -> None:
        if self._fail_after == point:
            self._fail_after = ""
            raise JournalUnavailable(f"injected_{point}")

    def _begin(self) -> None:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise JournalUnavailable("journal_lock_or_disk") from exc

    def _commit(self) -> None:
        if self._fail_after == "before_commit":
            self._fail_after = ""
            self._rollback()
            raise JournalUnavailable("persistence_failure")
        try:
            self._conn.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            self._rollback()
            raise JournalUnavailable("persistence_failure") from exc

    def _rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            return

    def reserve(
        self,
        *,
        account_binding_value: str,
        position_instance_id: str,
        position_generation: int,
        instrument: str,
        trade_id: str,
        direction: str,
        original_units: Any,
        requested_units: Any,
    ) -> dict[str, Any]:
        with self._lock:
            return self._reserve_locked(
                account_binding_value=account_binding_value,
                position_instance_id=position_instance_id,
                position_generation=position_generation,
                instrument=instrument,
                trade_id=trade_id,
                direction=direction,
                original_units=original_units,
                requested_units=requested_units,
            )

    def _reserve_locked(
        self,
        *,
        account_binding_value: str,
        position_instance_id: str,
        position_generation: int,
        instrument: str,
        trade_id: str,
        direction: str,
        original_units: Any,
        requested_units: Any,
    ) -> dict[str, Any]:
        flag = self._conn.execute("SELECT closes_authorised FROM schema_meta WHERE id = 1").fetchone()
        if flag is None or flag[0] is None or int(flag[0]) != 1:
            raise JournalUnavailable("bootstrap_does_not_authorise_closes")
        if not account_binding_value or not position_instance_id or not instrument or not trade_id:
            raise JournalUnavailable("incomplete_identity")
        if int(position_generation) < 1:
            raise JournalUnavailable("incomplete_identity")
        original = _units(original_units, required=True)
        requested = _units(requested_units, required=True)
        self._fault("before_reserve_commit")
        operation_id = uuid.uuid4().hex
        stamp = _now()
        self._begin()
        try:
            self._conn.execute(
                """
                INSERT INTO close_operations (
                    operation_id, position_instance_id, position_generation, account_binding,
                    instrument, trade_id, direction, original_units, requested_units,
                    confirmed_units, remaining_units, submission_state, confirmation_state,
                    submission_intent, network_permit, owner_token, transaction_ids, attempt_count,
                    created_at, updated_at, error_classification, recovery_status, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'NOT_SENT', 'CLOSE_PREPARED',
                          0, 0, '', '', 0, ?, ?, '', 'active', ?)
                """,
                (
                    operation_id,
                    position_instance_id,
                    int(position_generation),
                    account_binding_value,
                    instrument,
                    trade_id,
                    direction,
                    original,
                    requested,
                    stamp,
                    stamp,
                    SCHEMA_VERSION,
                ),
            )
            self._commit()
        except JournalUnavailable:
            raise
        except sqlite3.IntegrityError as exc:
            self._rollback()
            raise JournalUnavailable("unresolved_operation_exists") from exc
        except sqlite3.OperationalError as exc:
            self._rollback()
            raise JournalUnavailable("journal_lock_or_disk") from exc
        self._fault("after_reserve_commit")
        stored = self.get(operation_id)
        if stored is None:
            raise JournalUnavailable("reservation_not_durable")
        return stored

    def commit_submission_intent(self, operation_id: str) -> str:
        with self._lock:
            return self._intent_locked(operation_id)

    def _intent_locked(self, operation_id: str) -> str:
        self._fault("before_intent_commit")
        token = uuid.uuid4().hex
        stamp = _now()
        self._begin()
        try:
            cursor = self._conn.execute(
                """
                UPDATE close_operations
                   SET submission_intent = 1,
                       owner_token = ?,
                       confirmation_state = 'CLOSE_SUBMITTING',
                       submission_state = 'SENDING',
                       attempt_count = attempt_count + 1,
                       updated_at = ?
                 WHERE operation_id = ?
                   AND submission_intent = 0
                   AND confirmation_state = 'CLOSE_PREPARED'
                """,
                (token, stamp, operation_id),
            )
            if cursor.rowcount != 1:
                self._rollback()
                raise JournalUnavailable("intent_not_granted")
            self._commit()
        except JournalUnavailable:
            raise
        except sqlite3.OperationalError as exc:
            self._rollback()
            raise JournalUnavailable("persistence_failure") from exc
        self._fault("after_intent_commit")
        if not self.submission_authorized(operation_id, token):
            raise JournalUnavailable("intent_not_durable")
        return token

    def issue_submission_permit(self, operation_id: str, owner_token: str) -> CloseSubmissionPermit:
        """Copy the committed intent into a permit. This does not allow a second claim."""
        if not self.submission_authorized(operation_id, owner_token):
            raise JournalUnavailable("submission_authority_refused")
        row = self.get(operation_id)
        if row is None or int(row["network_permit"]) != 0:
            raise JournalUnavailable("submission_authority_refused")
        return CloseSubmissionPermit(
            operation_id=row["operation_id"],
            owner_token=owner_token,
            account_binding=row["account_binding"],
            instrument=row["instrument"],
            trade_id=row["trade_id"],
            direction=row["direction"],
            requested_units=str(row["requested_units"]),
            position_instance_id=row["position_instance_id"],
            position_generation=int(row["position_generation"]),
        )

    def claim_network_permit(self, permit: CloseSubmissionPermit) -> None:
        """Atomically consume one submission. A second claim, or a stale token, commits nothing."""
        if not isinstance(permit, CloseSubmissionPermit) or not permit.owner_token:
            raise JournalUnavailable("submission_authority_refused")
        requested = _units(permit.requested_units, required=True)
        stamp = _now()
        with self._lock:
            self._begin()
            try:
                cursor = self._conn.execute(
                    """
                    UPDATE close_operations
                       SET network_permit = 1,
                           submission_state = 'SENT',
                           updated_at = ?
                     WHERE operation_id = ?
                       AND owner_token = ?
                       AND account_binding = ?
                       AND instrument = ?
                       AND trade_id = ?
                       AND direction = ?
                       AND requested_units = ?
                       AND position_instance_id = ?
                       AND position_generation = ?
                       AND submission_intent = 1
                       AND network_permit = 0
                       AND confirmation_state = 'CLOSE_SUBMITTING'
                    """,
                    (
                        stamp,
                        permit.operation_id,
                        permit.owner_token,
                        permit.account_binding,
                        permit.instrument,
                        permit.trade_id,
                        permit.direction,
                        requested,
                        permit.position_instance_id,
                        int(permit.position_generation),
                    ),
                )
                if cursor.rowcount != 1:
                    self._rollback()
                    raise JournalUnavailable("submission_authority_refused")
                self._commit()
            except JournalUnavailable:
                raise
            except sqlite3.OperationalError as exc:
                self._rollback()
                raise JournalUnavailable("journal_lock_or_disk") from exc

    def submission_authorized(self, operation_id: str, owner_token: str) -> bool:
        with self._lock:
            return self._authorized_locked(operation_id, owner_token)

    def _authorized_locked(self, operation_id: str, owner_token: str) -> bool:
        if not owner_token:
            return False
        row = self.get(operation_id)
        if row is None:
            return False
        return (
            int(row["submission_intent"]) == 1
            and int(row["network_permit"]) == 0
            and row["owner_token"] == owner_token
            and row["confirmation_state"] == "CLOSE_SUBMITTING"
            and row["submission_state"] == "SENDING"
        )

    def mark(
        self,
        operation_id: str,
        *,
        confirmation_state: str,
        submission_state: str,
        error_classification: str,
        confirmed_units: Any = None,
        remaining_units: Any = None,
        transaction_ids: tuple[str, ...] = (),
        recovery_status: str = "",
    ) -> None:
        with self._lock:
            self._mark_locked(
                operation_id,
                confirmation_state=confirmation_state,
                submission_state=submission_state,
                error_classification=error_classification,
                confirmed_units=confirmed_units,
                remaining_units=remaining_units,
                transaction_ids=transaction_ids,
                recovery_status=recovery_status,
            )

    def _mark_locked(
        self,
        operation_id: str,
        *,
        confirmation_state: str,
        submission_state: str,
        error_classification: str,
        confirmed_units: Any = None,
        remaining_units: Any = None,
        transaction_ids: tuple[str, ...] = (),
        recovery_status: str = "",
    ) -> None:
        confirmed = _units(confirmed_units, required=False)
        remaining = _units(remaining_units, required=False)
        stamp = _now()
        self._begin()
        try:
            cursor = self._conn.execute(
                """
                UPDATE close_operations
                   SET confirmation_state = ?,
                       submission_state = ?,
                       error_classification = ?,
                       confirmed_units = ?,
                       remaining_units = ?,
                       transaction_ids = ?,
                       recovery_status = CASE WHEN ? = '' THEN recovery_status ELSE ? END,
                       updated_at = ?
                 WHERE operation_id = ?
                """,
                (
                    confirmation_state,
                    submission_state,
                    error_classification,
                    confirmed,
                    remaining,
                    ",".join(transaction_ids),
                    recovery_status,
                    recovery_status,
                    stamp,
                    operation_id,
                ),
            )
            if cursor.rowcount != 1:
                self._rollback()
                raise JournalUnavailable("operation_missing")
            self._commit()
        except JournalUnavailable:
            raise
        except sqlite3.OperationalError as exc:
            self._rollback()
            raise JournalUnavailable("persistence_failure") from exc

    def finalise(self, operation_id: str, *, expected_epoch: int | None = None) -> None:
        """Record local deletion only after the identity-bound pop has succeeded.

        When ``expected_epoch`` is set, the epoch comparison and the state
        change share one immediate transaction. A newer recovery epoch refuses
        the finalisation.
        """
        with self._lock:
            self._finalise_locked(operation_id, expected_epoch=expected_epoch)

    def _finalise_locked(self, operation_id: str, *, expected_epoch: int | None = None) -> None:
        stamp = _now()
        self._begin()
        try:
            if expected_epoch is not None:
                authority = self._conn.execute(
                    "SELECT fencing_epoch FROM recovery_authority WHERE id = 1"
                ).fetchone()
                if authority is None or int(authority[0]) != int(expected_epoch):
                    self._rollback()
                    raise JournalUnavailable("finalise_refused")
            cursor = self._conn.execute(
                """
                UPDATE close_operations
                   SET confirmation_state = 'CLOSE_FINALISED',
                       recovery_status = 'local_delete_recorded',
                       updated_at = ?
                 WHERE operation_id = ?
                   AND confirmation_state = 'CLOSE_FULLY_CONFIRMED'
                """,
                (stamp, operation_id),
            )
            if cursor.rowcount != 1:
                self._rollback()
                raise JournalUnavailable("finalise_refused")
            self._commit()
        except JournalUnavailable:
            raise
        except sqlite3.OperationalError as exc:
            self._rollback()
            raise JournalUnavailable("persistence_failure") from exc

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._get_locked(operation_id)

    def _get_locked(self, operation_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT * FROM close_operations WHERE operation_id = ?",
            (operation_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    def blocking_trade(self, account_binding_value: str, instrument: str, trade_id: str) -> dict[str, Any] | None:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM close_operations
                 WHERE account_binding = ? AND instrument = ? AND trade_id = ?
                   AND confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED')
                """,
                (account_binding_value, instrument, trade_id),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    def blocking_instrument(self, instrument: str) -> dict[str, Any] | None:
        """Any unresolved close on this instrument, regardless of trade id."""
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM close_operations
                 WHERE instrument = ?
                   AND confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED')
                 LIMIT 1
                """,
                (instrument,),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    def fully_confirmed(self, instrument: str) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM close_operations
                 WHERE instrument = ? AND confirmation_state = 'CLOSE_FULLY_CONFIRMED'
                """,
                (instrument,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def recover(self) -> list[dict[str, Any]]:
        """Reconstruct conservative states. This never grants a new submission."""
        with self._lock:
            return self._recover_locked()

    def _recover_locked(self) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            """
            SELECT * FROM close_operations
             WHERE confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED')
            """
        )
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            intent = int(row["submission_intent"])
            state = row["confirmation_state"]
            if intent == 0 and state == "CLOSE_PREPARED":
                self.mark(
                    row["operation_id"],
                    confirmation_state="CLOSE_RECONCILIATION_REQUIRED",
                    submission_state="NOT_SENT",
                    error_classification="reserved_without_submission_intent",
                    recovery_status="recovered_not_submitted",
                )
            elif intent == 1 and state in {
                "CLOSE_SUBMITTING",
                "CLOSE_RESPONSE_RECEIVED",
                "CLOSE_CONFIRMATION_PENDING",
                "CLOSE_PREPARED",
            }:
                self.mark(
                    row["operation_id"],
                    confirmation_state="CLOSE_OUTCOME_AMBIGUOUS",
                    submission_state="SENT",
                    error_classification="crash_after_submission_intent",
                    confirmed_units=row["confirmed_units"],
                    remaining_units=row["remaining_units"],
                    transaction_ids=tuple(part for part in (row["transaction_ids"] or "").split(",") if part),
                    recovery_status="recovered_ambiguous",
                )
            elif state == "CLOSE_PARTIALLY_CONFIRMED":
                self.mark(
                    row["operation_id"],
                    confirmation_state="CLOSE_PARTIALLY_CONFIRMED",
                    submission_state=row["submission_state"],
                    error_classification=row["error_classification"] or "partial_fill",
                    confirmed_units=row["confirmed_units"],
                    remaining_units=row["remaining_units"],
                    transaction_ids=tuple(part for part in row["transaction_ids"].split(",") if part),
                    recovery_status="recovered_partial",
                )
            elif state == "CLOSE_FULLY_CONFIRMED":
                self.mark(
                    row["operation_id"],
                    confirmation_state="CLOSE_FULLY_CONFIRMED",
                    submission_state=row["submission_state"],
                    error_classification=row["error_classification"],
                    confirmed_units=row["confirmed_units"],
                    remaining_units=row["remaining_units"],
                    transaction_ids=tuple(part for part in row["transaction_ids"].split(",") if part),
                    recovery_status="recovered_confirmed_delete_not_assumed",
                )
        return [self.get(row["operation_id"]) or row for row in rows]


def _configure(connection: sqlite3.Connection) -> None:
    connection.row_factory = sqlite3.Row
    mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if str(mode).lower() != "wal":
        raise JournalUnavailable("journal_mode_refused")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(f"PRAGMA busy_timeout={_busy_ms()}")
    sync = connection.execute("PRAGMA synchronous").fetchone()[0]
    if int(sync) < 2:
        raise JournalUnavailable("synchronous_not_full")


def bootstrap_journal(
    path: str | Path,
    *,
    acknowledge_empty: bool = False,
    preexisting: tuple[tuple[str, str, str], ...] = (),
) -> CloseJournal:
    """Create a new journal.

    acknowledge_empty is an explicit operator statement that no broker position
    already exists. It does not query the broker. Passing preexisting trade
    bindings inserts durable blockers and does not authorise those closes.
    Calling this with neither argument creates a journal that refuses reservations.
    """
    if acknowledge_empty and preexisting:
        raise JournalUnavailable("contradictory_bootstrap")
    target = Path(path)
    if target.exists():
        raise JournalUnavailable("journal_already_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=_busy_ms() / 1000, isolation_level=None, check_same_thread=False)
    try:
        _configure(connection)
        connection.executescript(SCHEMA_SQL)
        stamp = _now()
        connection.execute(
            "INSERT INTO schema_meta (id, schema_version, bootstrapped_at, closes_authorised) VALUES (1, ?, ?, ?)",
            (SCHEMA_VERSION, stamp, 1 if acknowledge_empty else 0),
        )
        connection.execute(
            "INSERT INTO recovery_authority (id, fencing_epoch, updated_at) VALUES (1, 0, ?)",
            (stamp,),
        )
        journal = CloseJournal(connection)
        for binding, instrument, trade_id in preexisting:
            _insert_preexisting_blocker(connection, binding, instrument, trade_id)
        if preexisting:
            connection.execute("UPDATE schema_meta SET closes_authorised = 1 WHERE id = 1")
        return journal
    except Exception:
        connection.close()
        raise


def _insert_preexisting_blocker(
    connection: sqlite3.Connection, binding: str, instrument: str, trade_id: str
) -> None:
    if not binding or not instrument or not trade_id:
        raise JournalUnavailable("incomplete_identity")
    stamp = _now()
    connection.execute(
        """
        INSERT INTO close_operations (
            operation_id, position_instance_id, position_generation, account_binding,
            instrument, trade_id, direction, original_units, requested_units,
            confirmed_units, remaining_units, submission_state, confirmation_state,
            submission_intent, network_permit, owner_token, transaction_ids, attempt_count,
            created_at, updated_at, error_classification, recovery_status, schema_version
        ) VALUES (?, 'preexisting', 1, ?, ?, ?, 'UNKNOWN', NULL, NULL, NULL, NULL,
                  'NOT_SENT', 'CLOSE_RECONCILIATION_REQUIRED', 0, 0, '', '', 0, ?, ?,
                  'preexisting_broker_position', 'bootstrap_blocked', ?)
        """,
        (uuid.uuid4().hex, binding, instrument, trade_id, stamp, stamp, SCHEMA_VERSION),
    )


def open_journal(path: str | Path, *, fail_after: str = "") -> CloseJournal:
    """Open an existing journal. A missing file is not treated as an empty history."""
    target = Path(path)
    if not target.exists():
        raise JournalUnavailable("missing_journal")
    if target.stat().st_size == 0:
        raise JournalUnavailable("corrupt_journal")
    connection = sqlite3.connect(target, timeout=_busy_ms() / 1000, isolation_level=None, check_same_thread=False)
    try:
        _configure(connection)
        check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise JournalUnavailable("corrupt_journal")
        meta = connection.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
        if meta is None or int(meta[0]) != SCHEMA_VERSION:
            raise JournalUnavailable("unsupported_schema")
    except JournalUnavailable:
        connection.close()
        raise
    except sqlite3.DatabaseError as exc:
        connection.close()
        raise JournalUnavailable("corrupt_journal") from exc
    return CloseJournal(connection, fail_after=fail_after)


_process_journal: CloseJournal | None = None
_process_journal_path: str = ""
_process_lock = threading.Lock()


def reset_journal_process_state() -> None:
    global _process_journal, _process_journal_path
    with _process_lock:
        if _process_journal is not None:
            _process_journal.close()
        _process_journal = None
        _process_journal_path = ""


def arm_active_journal_fault(point: str) -> None:
    active_journal()._fail_after = point


def canonical_client_order_id(value: str) -> str:
    """Strip a client id. Ids longer than the broker extension limit are refused."""
    text = str(value or "").strip()
    if not text:
        raise JournalUnavailable("client_order_id_missing")
    if len(text) > CLIENT_ORDER_ID_LIMIT:
        raise JournalUnavailable("client_order_id_exceeds_broker_limit")
    return text


def client_order_truncation_key(value: str) -> str:
    """The 128-character broker label. This does not authorise truncation."""
    return str(value or "").strip()[:CLIENT_ORDER_ID_LIMIT]


def create_legacy_schema_3_database(path: str | Path) -> None:
    """Write a synthetic schema-3 file for the offline migrator. Refuses an existing path."""
    target = Path(path)
    if target.exists():
        raise JournalUnavailable("legacy_database_exists")
    connection = sqlite3.connect(target, isolation_level=None)
    connection.executescript(
        """
        CREATE TABLE schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version INTEGER NOT NULL,
            bootstrapped_at TEXT NOT NULL,
            closes_authorised INTEGER NOT NULL
        );
        CREATE TABLE entry_operations (
            operation_id TEXT PRIMARY KEY,
            account_binding TEXT NOT NULL,
            client_order_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX one_unresolved_entry
            ON entry_operations(account_binding, client_order_id)
            WHERE outcome != 'ENTRY_FINALISED';
        """
    )
    connection.execute(
        "INSERT INTO schema_meta (id, schema_version, bootstrapped_at, closes_authorised) VALUES (1, 3, ?, 1)",
        (_now(),),
    )
    connection.close()


def migrate_journal_3_to_4(path: str | Path, *, fail_before_commit: bool = False) -> None:
    """Upgrade a schema-3 copy. Startup does not call this. Duplicates fail closed."""
    target = Path(path)
    if not target.exists():
        raise JournalUnavailable("missing_journal")
    if target.stat().st_size == 0:
        raise JournalUnavailable("corrupt_journal")
    connection = sqlite3.connect(target, timeout=_busy_ms() / 1000, isolation_level=None)
    try:
        check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise JournalUnavailable("corrupt_journal")
        meta = connection.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
        if meta is None or int(meta[0]) != 3:
            raise JournalUnavailable("schema_migration_refused")
        duplicate = connection.execute(
            """
            SELECT 1 FROM entry_operations
            GROUP BY account_binding, client_order_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        ).fetchone()
        if duplicate is not None:
            raise JournalUnavailable("historical_client_id_conflict")
        _configure(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("DROP INDEX IF EXISTS one_unresolved_entry")
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS one_client_order_id
                ON entry_operations(account_binding, client_order_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS client_order_id_registry (
                    account_binding TEXT NOT NULL,
                    client_order_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (account_binding, client_order_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_repairs (
                    repair_id TEXT PRIMARY KEY,
                    journal_identity TEXT NOT NULL,
                    account_binding TEXT NOT NULL,
                    target_run_id TEXT NOT NULL,
                    previous_state TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    operator_acknowledgement TEXT NOT NULL,
                    liveness_method TEXT NOT NULL,
                    liveness_status TEXT NOT NULL,
                    integrity_result TEXT NOT NULL,
                    unresolved_entry_count INTEGER NOT NULL,
                    unresolved_close_count INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO client_order_id_registry (
                    account_binding, client_order_id, operation_id, created_at
                )
                SELECT account_binding, client_order_id, operation_id, created_at
                FROM entry_operations
                """
            )
            updated = connection.execute(
                "UPDATE schema_meta SET schema_version = 4 WHERE id = 1 AND schema_version = 3"
            )
            if updated.rowcount != 1:
                raise JournalUnavailable("schema_migration_refused")
            if fail_before_commit:
                connection.execute("ROLLBACK")
                raise JournalUnavailable("migration_interrupted")
            connection.execute("COMMIT")
        except JournalUnavailable:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        except Exception as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise JournalUnavailable("persistence_failure") from exc
    finally:
        connection.close()


def migrate_journal_4_to_5(path: str | Path, *, fail_before_commit: bool = False) -> None:
    """Upgrade a schema-4 copy. Startup does not call this."""
    target = Path(path)
    if not target.exists() or target.stat().st_size == 0:
        raise JournalUnavailable("missing_journal" if not target.exists() else "corrupt_journal")
    connection = sqlite3.connect(target, timeout=_busy_ms() / 1000, isolation_level=None)
    try:
        check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise JournalUnavailable("corrupt_journal")
        meta = connection.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
        if meta is None or int(meta[0]) != 4:
            raise JournalUnavailable("schema_migration_refused")
        _configure(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = {row[1] for row in connection.execute("PRAGMA table_info(recovery_runs)")}
            for name, declaration in (
                ("fencing_epoch", "INTEGER NOT NULL DEFAULT 0"),
                ("owner_pid", "INTEGER"),
                ("process_start", "TEXT"),
                ("boot_id", "TEXT"),
                ("lock_identity", "TEXT"),
            ):
                if name not in existing:
                    connection.execute(f"ALTER TABLE recovery_runs ADD COLUMN {name} {declaration}")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_authority (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    fencing_epoch INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entry_investigations (
                    investigation_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO recovery_authority (id, fencing_epoch, updated_at) VALUES (1, 0, ?)",
                (_now(),),
            )
            updated = connection.execute(
                "UPDATE schema_meta SET schema_version = 5 WHERE id = 1 AND schema_version = 4"
            )
            if updated.rowcount != 1:
                raise JournalUnavailable("schema_migration_refused")
            if fail_before_commit:
                connection.execute("ROLLBACK")
                raise JournalUnavailable("migration_interrupted")
            connection.execute("COMMIT")
        except JournalUnavailable:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        except Exception as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise JournalUnavailable("persistence_failure") from exc
    finally:
        connection.close()


def active_journal() -> CloseJournal:
    """Open the configured journal and recover once. Never creates a missing file."""
    global _process_journal, _process_journal_path
    path = os.environ.get("CLOSE_JOURNAL_PATH", "").strip()
    if not path:
        raise JournalUnavailable("missing_journal")
    with _process_lock:
        global _process_journal, _process_journal_path
        if _process_journal is not None and _process_journal_path == path:
            return _process_journal
        if _process_journal is not None:
            _process_journal.close()
        journal = open_journal(path)
        journal.recover()
        _process_journal = journal
        _process_journal_path = path
        return journal
