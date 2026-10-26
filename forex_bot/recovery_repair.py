"""Offline repair for an abandoned startup-recovery claim.

Startup does not call this module. A repair cannot submit, close, delete, or
publish a position, and it does not decide an ambiguous broker outcome.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from forex_bot.close_journal import JournalUnavailable, _now, active_journal
from forex_bot.recovery_owner_lock import (
    RecoveryOwnerLock,
    host_boot_id,
    lock_identity,
    owner_process_status,
)

APPROVED_LIVENESS_METHOD = "owner_token_and_exit_observation"
_WEAK_METHODS = {"pid", "pid_only", "timestamp", "timestamp_only", "unknown"}
_RELEASED = "RECOVERY_REPAIR_RELEASED"


@dataclass(frozen=True)
class ProcessLivenessEvidence:
    """Operator evidence that a recovery owner is inactive. A PID is not enough."""

    status: str
    method: str
    observed_owner_token: str


@dataclass(frozen=True)
class RepairAuthorisation:
    """One explicit repair request. This is not a trading permit."""

    operator_acknowledged: bool
    acknowledgement: str
    account_binding: str
    journal_path: str
    target_run_id: str
    liveness: ProcessLivenessEvidence


def _journal_identity(path: str) -> str:
    return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()


def _result(result: str, reason: str, **extra) -> dict:
    payload = {
        "result": result,
        "reason": reason,
        "published": False,
        "close_submission_count": 0,
        "order_submission_count": 0,
        "positions_deleted": 0,
        "entries_resolved": 0,
        "closes_resolved": 0,
        "trading_enabled": False,
    }
    payload.update(extra)
    return payload


def repair_abandoned_recovery(authorisation: RepairAuthorisation) -> dict:
    """Release one abandoned recovery claim after a committed audit row."""
    if not authorisation.operator_acknowledged or not str(authorisation.acknowledgement or "").strip():
        return _result("REPAIR_REFUSED", "operator_acknowledgement_required")
    configured = os.environ.get("CLOSE_JOURNAL_PATH", "").strip()
    path_matches = bool(configured) and Path(authorisation.journal_path).resolve() == Path(configured).resolve()
    try:
        journal = active_journal()
    except JournalUnavailable as exc:
        return _result("REPAIR_REFUSED", exc.reason if path_matches else "wrong_journal")
    if not path_matches:
        return _record(journal, authorisation, _journal_identity(configured), "REPAIR_REFUSED", "wrong_journal", release=False)
    identity = _journal_identity(configured)
    evidence = authorisation.liveness
    method = str(evidence.method or "").strip().lower()
    status = str(evidence.status or "").strip().lower()
    if method in _WEAK_METHODS or "pid" in method:
        reason = "pid_reuse_ambiguous" if "pid" in method or status == "pid_reused" else "process_not_proven_inactive"
        if "timestamp" in method:
            reason = "timestamp_not_sufficient"
        return _record(journal, authorisation, identity, "REPAIR_REFUSED", reason, release=False)
    if status == "active":
        return _record(journal, authorisation, identity, "REPAIR_REFUSED", "recovery_owner_active", release=False)
    if status in {"unknown", ""}:
        return _record(journal, authorisation, identity, "REPAIR_REFUSED", "process_status_unknown", release=False)
    if status == "pid_reused":
        return _record(journal, authorisation, identity, "REPAIR_REFUSED", "pid_reuse_ambiguous", release=False)
    if status != "inactive" or method != APPROVED_LIVENESS_METHOD:
        return _record(journal, authorisation, identity, "REPAIR_REFUSED", "process_not_proven_inactive", release=False)
    lock = RecoveryOwnerLock(configured)
    if not lock.try_acquire():
        refused = _record(
            journal,
            authorisation,
            identity,
            "REPAIR_REFUSED",
            "recovery_owner_active",
            release=False,
        )
        refused["independent_liveness"] = "lock_held"
        return refused
    try:
        return _record(
            journal,
            authorisation,
            identity,
            "REPAIR_COMMITTED",
            "abandoned_claim_released",
            release=True,
            owner_lock=lock,
        )
    finally:
        lock.release()


def _record(
    journal,
    authorisation: RepairAuthorisation,
    identity: str,
    result: str,
    reason: str,
    *,
    release: bool,
    owner_lock: RecoveryOwnerLock | None = None,
) -> dict:
    _ = owner_lock
    observation = "not_required"
    with journal._lock:
        journal._begin()
        try:
            foreign = journal._conn.execute(
                """
                SELECT 1 FROM entry_operations WHERE account_binding != ?
                UNION ALL
                SELECT 1 FROM close_operations WHERE account_binding != ?
                UNION ALL
                SELECT 1 FROM managed_positions WHERE account_binding != ?
                """,
                (authorisation.account_binding, authorisation.account_binding, authorisation.account_binding),
            ).fetchone()
            if foreign is not None:
                result, reason, release = "REPAIR_REFUSED", "wrong_account_binding", False
            run = journal._conn.execute(
                """
                SELECT state, owner_token, owner_pid, process_start, boot_id, lock_identity
                  FROM recovery_runs WHERE run_id = ?
                """,
                (authorisation.target_run_id,),
            ).fetchone()
            if run is None or str(run["state"]) != "RECOVERY_IN_PROGRESS":
                result, reason, release = "REPAIR_REFUSED", "recovery_claim_missing", False
            elif release and str(run["owner_token"]) != authorisation.liveness.observed_owner_token:
                result, reason, release = "REPAIR_REFUSED", "process_not_proven_inactive", False
            elif release and run["boot_id"] and str(run["boot_id"]) != host_boot_id():
                result, reason, release = "REPAIR_REFUSED", "host_boot_identity_changed", False
            elif release and run["lock_identity"] and str(run["lock_identity"]) != lock_identity(
                authorisation.journal_path
            ):
                result, reason, release = "REPAIR_REFUSED", "journal_lock_path_changed", False
            elif release:
                observation = owner_process_status(run["owner_pid"], run["process_start"])
                if observation == "alive":
                    result, reason, release = "REPAIR_REFUSED", "recovery_owner_active", False
                elif observation == "unknown":
                    result, reason, release = "REPAIR_REFUSED", "process_status_unknown", False
            entry_count = journal._conn.execute(
                "SELECT COUNT(*) FROM entry_operations WHERE outcome != 'ENTRY_FINALISED'"
            ).fetchone()[0]
            close_count = journal._conn.execute(
                """
                SELECT COUNT(*) FROM close_operations
                 WHERE confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED')
                """
            ).fetchone()[0]
            previous = "" if run is None else str(run["state"])
            new_state = previous
            if release:
                cursor = journal._conn.execute(
                    """
                    UPDATE recovery_runs
                       SET state = ?, updated_at = ?
                     WHERE run_id = ? AND state = 'RECOVERY_IN_PROGRESS'
                    """,
                    (_RELEASED, _now(), authorisation.target_run_id),
                )
                if cursor.rowcount != 1:
                    raise JournalUnavailable("recovery_claim_missing")
                advanced = journal._conn.execute(
                    """
                    UPDATE recovery_authority
                       SET fencing_epoch = fencing_epoch + 1, updated_at = ?
                     WHERE id = 1
                    """,
                    (_now(),),
                )
                if advanced.rowcount != 1:
                    raise JournalUnavailable("fencing_authority_missing")
                new_state = _RELEASED
            journal._conn.execute(
                """
                INSERT INTO recovery_repairs (
                    repair_id, journal_identity, account_binding, target_run_id, previous_state,
                    new_state, operator_acknowledgement, liveness_method, liveness_status,
                    integrity_result, unresolved_entry_count, unresolved_close_count,
                    result, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    identity,
                    authorisation.account_binding,
                    authorisation.target_run_id,
                    previous,
                    new_state,
                    authorisation.acknowledgement,
                    authorisation.liveness.method,
                    authorisation.liveness.status,
                    int(entry_count),
                    int(close_count),
                    result,
                    reason,
                    _now(),
                ),
            )
            journal._commit()
        except JournalUnavailable:
            journal._rollback()
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc
    return _result(
        result,
        reason,
        unresolved_entry_count=int(entry_count),
        unresolved_close_count=int(close_count),
        process_observation=observation,
        independent_liveness="os_lock_acquired" if result == "REPAIR_COMMITTED" else "os_lock_checked",
    )
