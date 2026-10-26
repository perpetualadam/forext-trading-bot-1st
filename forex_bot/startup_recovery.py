"""Startup recovery. Live management stays blocked until this function finishes."""

from __future__ import annotations

import os
import uuid
from typing import Any

from forex_bot.close_journal import JournalUnavailable, _now, active_journal
from forex_bot.recovery_owner_lock import (
    RecoveryOwnerLock,
    current_process_start,
    host_boot_id,
    lock_identity,
)
from forex_bot.entry_journal import capture_gaps, entry_row, recover_entry_operations, unresolved_entry_for
from forex_bot.position_recovery import (
    classify_broker_discovery,
    durable_positions,
    evaluate_durable_row,
    publish_recovered,
    quarantined_positions,
)

RECOVERY_NOT_STARTED = "RECOVERY_NOT_STARTED"
RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
RECOVERY_COMPLETED_WITH_QUARANTINE = "RECOVERY_COMPLETED_WITH_QUARANTINE"
RECOVERY_BLOCKED = "RECOVERY_BLOCKED"

_ACCEPTABLE = {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE}
_BLOCKING_SNAPSHOTS = {
    "INCOMPLETE",
    "MALFORMED",
    "REQUEST_FAILED",
    "STALE",
    "UNAVAILABLE",
    "UNKNOWN",
    "CONFLICT",
}
_state = RECOVERY_NOT_STARTED
_last_report: dict[str, Any] = {"state": RECOVERY_NOT_STARTED, "decisions": []}
_fencing_epoch: int | None = None
_owner_lock: RecoveryOwnerLock | None = None


def load_startup_broker_view() -> dict[str, Any]:
    """Read-only startup view. A missing client is not an empty book.

    One trade id on one instrument can be compared with a durable row.
    Several trade ids are not collapsed into the instrument net.
    """
    try:
        from forex_bot.oanda_client import get_api
    except Exception:
        return {"snapshot": "REQUEST_FAILED", "trades": []}
    if get_api() is None:
        return {"snapshot": "REQUEST_FAILED", "trades": []}
    try:
        from forex_bot.close_journal import account_binding
        from forex_bot.config import Config
        from forex_bot.reconciliation import (
            BrokerSnapshotError,
            _last_trade_ids,
            fetch_broker_positions_detail,
        )

        detail = fetch_broker_positions_detail()
        binding = account_binding((Config.OANDA_ACCOUNT_ID or "").strip())
    except BrokerSnapshotError as exc:
        return {"snapshot": exc.classification, "trades": [], "empty_book_is_not_flat": True}
    except Exception:
        return {"snapshot": "REQUEST_FAILED", "trades": []}
    trades: list[dict[str, Any]] = []
    for instrument, pair in detail.items():
        net = float(pair[0])
        ids = [str(item).strip() for item in (_last_trade_ids.get(instrument) or []) if str(item).strip()]
        if len(ids) != 1 or net == 0:
            for trade_id in ids:
                trades.append(
                    {
                        "trade_id": trade_id,
                        "instrument": instrument,
                        "direction": "",
                        "units": "",
                        "account_binding": binding,
                        "provenance": "broker_only",
                    }
                )
            continue
        trades.append(
            {
                "trade_id": ids[0],
                "instrument": instrument,
                "direction": "BUY" if net > 0 else "SELL",
                "units": str(abs(net)),
                "account_binding": binding,
                "provenance": "broker_snapshot_single_trade",
            }
        )
    snapshot = "COMPLETE_NONEMPTY" if detail else "COMPLETE_EMPTY"
    return {"snapshot": snapshot, "trades": trades}


def reset_startup_recovery_memory() -> None:
    global _state, _last_report, _fencing_epoch, _owner_lock
    if _owner_lock is not None:
        _owner_lock.release()
    _owner_lock = None
    _fencing_epoch = None
    _state = RECOVERY_NOT_STARTED
    _last_report = {"state": RECOVERY_NOT_STARTED, "decisions": []}


def recovery_state() -> str:
    return _state


def current_fencing_epoch() -> int | None:
    return _fencing_epoch


def recovery_fence_allows_publication() -> bool:
    """Operational publication requires a current epoch and an active recovery session.

    A missing epoch fails closed. Offline reconstruction does not use this function.
    """
    if _fencing_epoch is None or _state not in {RECOVERY_IN_PROGRESS, *_ACCEPTABLE}:
        return False
    return _authority_matches()


def live_management_permitted() -> bool:
    """True only after a completed recovery whose fencing epoch is still current."""
    if _state not in _ACCEPTABLE or _fencing_epoch is None:
        return False
    return _authority_matches()


def _authority_matches() -> bool:
    try:
        journal = active_journal()
        row = journal._conn.execute(
            "SELECT fencing_epoch FROM recovery_authority WHERE id = 1"
        ).fetchone()
    except JournalUnavailable:
        return False
    return row is not None and int(row[0]) == int(_fencing_epoch)


def last_recovery_report() -> dict[str, Any]:
    return dict(_last_report)


def _claim_run(journal) -> str | None:
    global _fencing_epoch, _owner_lock
    journal_path = os.environ.get("CLOSE_JOURNAL_PATH", "").strip()
    lock = RecoveryOwnerLock(journal_path)
    if not lock.try_acquire():
        return None
    run_id = uuid.uuid4().hex
    token = uuid.uuid4().hex
    stamp = _now()
    with journal._lock:
        journal._begin()
        try:
            current = journal._conn.execute(
                "SELECT fencing_epoch FROM recovery_authority WHERE id = 1"
            ).fetchone()
            if current is None:
                raise JournalUnavailable("fencing_authority_missing")
            epoch = int(current[0]) + 1
            journal._conn.execute(
                "UPDATE recovery_authority SET fencing_epoch = ?, updated_at = ? WHERE id = 1",
                (epoch, stamp),
            )
            journal._conn.execute(
                """
                INSERT INTO recovery_runs (
                    run_id, state, owner_token, created_at, updated_at, fencing_epoch,
                    owner_pid, process_start, boot_id, lock_identity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    RECOVERY_IN_PROGRESS,
                    token,
                    stamp,
                    stamp,
                    epoch,
                    os.getpid(),
                    current_process_start(),
                    host_boot_id(),
                    lock_identity(journal_path),
                ),
            )
            journal._commit()
        except JournalUnavailable:
            journal._rollback()
            lock.release()
            raise
        except Exception as exc:
            journal._rollback()
            lock.release()
            if exc.__class__.__name__ == "IntegrityError":
                return None
            raise JournalUnavailable("persistence_failure") from exc
    _fencing_epoch = epoch
    _owner_lock = lock
    return run_id


def _release_owner_lock() -> None:
    global _owner_lock
    if _owner_lock is not None:
        _owner_lock.release()
        _owner_lock = None


def _finish_run(journal, run_id: str, state: str) -> None:
    with journal._lock:
        journal._begin()
        journal._conn.execute(
            "UPDATE recovery_runs SET state = ?, updated_at = ? WHERE run_id = ? AND state = ?",
            (state, _now(), run_id, RECOVERY_IN_PROGRESS),
        )
        journal._commit()
    _release_owner_lock()


def execute_startup_sequence(broker_view: dict[str, Any] | None) -> dict[str, Any]:
    """Recover closes, entries, and positions before any live management decision."""
    global _state, _last_report
    _state = RECOVERY_IN_PROGRESS
    decisions: list[dict[str, Any]] = []
    try:
        journal = active_journal()
    except JournalUnavailable as exc:
        _state = RECOVERY_BLOCKED
        _last_report = {"state": _state, "reason": exc.reason, "decisions": [], "close_submission_count": 0}
        return _last_report
    run_id = _claim_run(journal)
    if run_id is None:
        _state = RECOVERY_BLOCKED
        _last_report = {
            "state": _state,
            "reason": "recovery_already_in_progress",
            "decisions": [],
            "close_submission_count": 0,
        }
        return _last_report
    try:
        recover_entry_operations()
        from forex_bot.positions import _book_lock, positions

        with _book_lock:
            positions.clear()
        quarantined_positions.clear()
        snapshot = str((broker_view or {}).get("snapshot") or "UNAVAILABLE")
        if snapshot in _BLOCKING_SNAPSHOTS or broker_view is None:
            _state = RECOVERY_BLOCKED
            _last_report = {
                "state": _state,
                "reason": "broker_snapshot_not_authoritative",
                "snapshot": snapshot,
                "decisions": [],
                "close_submission_count": 0,
                "empty_book_is_not_flat": True,
            }
            return _last_report
        for trade in list((broker_view or {}).get("trades") or []):
            if not any(row["trade_id"] == trade.get("trade_id") for row in durable_positions()):
                decisions.append(classify_broker_discovery(str(trade.get("provenance") or "broker_only")))
        if not recovery_fence_allows_publication():
            _state = RECOVERY_BLOCKED
            _last_report = {
                "state": _state,
                "reason": "recovery_fence_lost",
                "snapshot": snapshot,
                "decisions": decisions,
                "close_submission_count": 0,
                "empty_book_is_not_flat": True,
            }
            return _last_report
        for row in durable_positions():
            pending = unresolved_entry_for(row["account_binding"], row["instrument"])
            pending_outcome = "" if pending is None else str(pending.get("outcome") or "")
            linked = entry_row(row["entry_operation_id"]) if row.get("entry_operation_id") else None
            conflict = ""
            if row.get("entry_operation_id") and linked is None:
                conflict = "position_without_entry_history"
            elif linked is not None and str(linked["outcome"]) == "ENTRY_FINALISED":
                if (
                    str(linked.get("broker_trade_id") or "") != row["trade_id"]
                    or linked["position_instance_id"] != row["position_instance_id"]
                    or int(linked["position_generation"]) != int(row["position_generation"])
                ):
                    conflict = "entry_position_identity_conflict"
            elif pending_outcome == "ENTRY_CONFIRMED_SINGLE_TRADE":
                conflict = "unfinalised_capture"
            elif pending_outcome in {
                "ENTRY_RESERVED",
                "ENTRY_SUBMITTING",
                "ENTRY_SENT",
                "ENTRY_OUTCOME_AMBIGUOUS",
                "ENTRY_RECONCILIATION_REQUIRED",
                "ENTRY_EVIDENCE_CONFLICT",
                "ENTRY_PARTIAL_OR_MIXED_EFFECT",
                "ENTRY_CONFIRMED_MULTIPLE_TRADES",
            }:
                conflict = "ambiguous_entry"
            if conflict:
                decision = {
                    "state": "quarantined",
                    "reason": conflict,
                    "manageable": False,
                    "close_submission_count": 0,
                    "delete_permitted": False,
                    "operator_required": True,
                }
            else:
                decision = evaluate_durable_row(row, broker_view or {})
            decisions.append(publish_recovered(row, decision))
        decisions.extend(capture_gaps())
        quarantined = any(not item.get("manageable") for item in decisions) or bool(quarantined_positions)
        _state = RECOVERY_COMPLETED_WITH_QUARANTINE if quarantined and decisions else RECOVERY_COMPLETED
        if not decisions:
            _state = RECOVERY_COMPLETED
        _last_report = {
            "state": _state,
            "reason": "recovery_finished",
            "snapshot": snapshot,
            "decisions": decisions,
            "close_submission_count": 0,
            "delete_permitted": False,
        }
        return _last_report
    finally:
        if _state == RECOVERY_IN_PROGRESS:
            _state = RECOVERY_BLOCKED
        _finish_run(journal, run_id, _state)
