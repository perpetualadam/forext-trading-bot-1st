"""R.74 journal, identity deletion, and process-restart tests. No broker client."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from forex_bot.broker_close_evidence import (  # noqa: E402
    operation_from_journal_row,
    resolve_from_retrieved_transaction,
)
from forex_bot.close_journal import (  # noqa: E402
    JournalUnavailable,
    account_binding,
    active_journal,
    arm_active_journal_fault,
    bootstrap_journal,
    open_journal,
    reset_journal_process_state,
)
from forex_bot.positions import (  # noqa: E402
    Position,
    close_confirmed_live_position,
    close_position,
    open_position,
    positions,
)

BINDING = account_binding("001-002-0000001-003")
WORKER = Path(__file__).with_name("journal_worker.py")


def _position(**kwargs) -> Position:
    data = dict(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        broker_order=True,
        position_instance_id="instance-a",
        position_generation=1,
    )
    data.update(kwargs)
    return Position(**data)


class JournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "closes.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        positions.clear()
        reset_journal_process_state()

    def tearDown(self) -> None:
        reset_journal_process_state()
        positions.clear()
        self.tmp.cleanup()

    def _ready(self):
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        return active_journal()

    def _reserve(self, journal, trade="T1", instrument="EUR_USD", instance="instance-a"):
        return journal.reserve(
            account_binding_value=BINDING,
            position_instance_id=instance,
            position_generation=1,
            instrument=instrument,
            trade_id=trade,
            direction="BUY",
            original_units="1000",
            requested_units="1000",
        )

    def test_two_threads_one_reservation(self) -> None:
        journal = self._ready()
        barrier = threading.Barrier(2)
        results = []

        def worker() -> None:
            barrier.wait(2)
            try:
                results.append(self._reserve(journal)["operation_id"])
            except JournalUnavailable as exc:
                results.append(exc.reason)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(item != "unresolved_operation_exists" for item in results), 1)

    def test_two_processes_one_reservation(self) -> None:
        self._ready()
        reset_journal_process_state()
        args = [sys.executable, str(WORKER), "reserve", self.path, BINDING, "EUR_USD", "T1", "instance-a", "BUY", "1000"]
        first = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
        second = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
        out1, _ = first.communicate(timeout=20)
        out2, _ = second.communicate(timeout=20)
        rows = [json.loads(out1), json.loads(out2)]
        self.assertEqual(sum(row["ok"] for row in rows), 1)
        self.assertEqual(sum(row.get("reason") == "unresolved_operation_exists" for row in rows), 1)

    def test_two_symbols_reserve_independently(self) -> None:
        journal = self._ready()
        self._reserve(journal, trade="T1", instrument="EUR_USD")
        self._reserve(journal, trade="T2", instrument="GBP_USD", instance="instance-b")
        self.assertIsNotNone(journal.blocking_trade(BINDING, "EUR_USD", "T1"))
        self.assertIsNotNone(journal.blocking_trade(BINDING, "GBP_USD", "T2"))

    def test_crash_before_reserve_commit_writes_nothing(self) -> None:
        journal = self._ready()
        arm_active_journal_fault("before_reserve_commit")
        with self.assertRaises(JournalUnavailable):
            self._reserve(journal)
        self.assertIsNone(journal.blocking_trade(BINDING, "EUR_USD", "T1"))

    def test_restart_after_reserve_blocks_without_submission(self) -> None:
        journal = self._ready()
        self._reserve(journal)
        journal.close()
        reset_journal_process_state()
        recovered = active_journal()
        row = recovered.blocking_trade(BINDING, "EUR_USD", "T1")
        self.assertEqual(row["error_classification"], "reserved_without_submission_intent")
        self.assertEqual(int(row["submission_intent"]), 0)
        with self.assertRaises(JournalUnavailable):
            self._reserve(recovered)

    def test_restart_after_intent_is_ambiguous_and_not_retried(self) -> None:
        journal = self._ready()
        row = self._reserve(journal)
        journal.commit_submission_intent(row["operation_id"])
        journal.close()
        reset_journal_process_state()
        recovered = active_journal()
        stored = recovered.get(row["operation_id"])
        self.assertEqual(stored["confirmation_state"], "CLOSE_OUTCOME_AMBIGUOUS")
        self.assertEqual(stored["error_classification"], "crash_after_submission_intent")
        with self.assertRaises(JournalUnavailable):
            self._reserve(recovered)

    def test_subprocess_restart_keeps_intent(self) -> None:
        self._ready()
        reset_journal_process_state()
        args = [sys.executable, str(WORKER), "intent", self.path, BINDING, "EUR_USD", "T1", "instance-a", "BUY", "1000"]
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=20)
        self.assertTrue(json.loads(completed.stdout)["ok"])
        recovered = active_journal()
        stored = recovered.blocking_trade(BINDING, "EUR_USD", "T1")
        self.assertEqual(stored["confirmation_state"], "CLOSE_OUTCOME_AMBIGUOUS")

    def test_missing_corrupt_and_schema_fail_closed(self) -> None:
        with self.assertRaises(JournalUnavailable) as missing:
            open_journal(str(Path(self.tmp.name) / "absent.sqlite"))
        self.assertEqual(missing.exception.reason, "missing_journal")
        corrupt_path = str(Path(self.tmp.name) / "corrupt.sqlite")
        Path(corrupt_path).write_bytes(b"this is not a database")
        with self.assertRaises(JournalUnavailable) as corrupt:
            open_journal(corrupt_path)
        self.assertEqual(corrupt.exception.reason, "corrupt_journal")
        self._ready()
        reset_journal_process_state()
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE schema_meta SET schema_version = 99")
        connection.commit()
        connection.close()
        with self.assertRaises(JournalUnavailable) as schema:
            open_journal(self.path)
        self.assertEqual(schema.exception.reason, "unsupported_schema")

    def test_lock_and_disk_failure(self) -> None:
        holder = self._ready()
        holder._conn.execute("BEGIN IMMEDIATE")
        other = open_journal(self.path)
        with self.assertRaises(JournalUnavailable) as locked:
            self._reserve(other)
        self.assertEqual(locked.exception.reason, "journal_lock_or_disk")
        holder._conn.execute("ROLLBACK")
        other.close()
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable) as disk:
            self._reserve(holder)
        self.assertEqual(disk.exception.reason, "persistence_failure")
        self.assertIsNone(holder.blocking_trade(BINDING, "EUR_USD", "T1"))

    def test_bootstrap_without_acknowledgement_refuses_reserves(self) -> None:
        bootstrap_journal(self.path).close()
        journal = open_journal(self.path)
        try:
            with self.assertRaises(JournalUnavailable) as refused:
                self._reserve(journal)
            self.assertEqual(refused.exception.reason, "bootstrap_does_not_authorise_closes")
        finally:
            journal.close()

    def test_preexisting_trade_blocks_close(self) -> None:
        bootstrap_journal(self.path, preexisting=((BINDING, "EUR_USD", "T1"),)).close()
        journal = open_journal(self.path)
        try:
            with self.assertRaises(JournalUnavailable):
                self._reserve(journal)
        finally:
            journal.close()

    def test_invalid_units_are_not_coerced(self) -> None:
        journal = self._ready()
        with self.assertRaises(JournalUnavailable):
            journal.reserve(
                account_binding_value=BINDING,
                position_instance_id="instance-a",
                position_generation=1,
                instrument="EUR_USD",
                trade_id="T1",
                direction="BUY",
                original_units="not-a-number",
                requested_units="1000",
            )

    def test_partial_recovery_keeps_units_and_blocks(self) -> None:
        journal = self._ready()
        row = self._reserve(journal)
        token = journal.commit_submission_intent(row["operation_id"])
        journal.mark(
            row["operation_id"],
            confirmation_state="CLOSE_PARTIALLY_CONFIRMED",
            submission_state="SENT",
            error_classification="partial_fill",
            confirmed_units="400",
            remaining_units="600",
            transaction_ids=("TX1",),
        )
        journal.close()
        reset_journal_process_state()
        recovered = active_journal()
        stored = recovered.get(row["operation_id"])
        self.assertEqual(stored["confirmation_state"], "CLOSE_PARTIALLY_CONFIRMED")
        self.assertEqual(stored["confirmed_units"], "400")
        self.assertEqual(stored["remaining_units"], "600")
        self.assertFalse(recovered.submission_authorized(row["operation_id"], token))
        with self.assertRaises(JournalUnavailable):
            self._reserve(recovered)

    def test_stale_token_is_not_authorised(self) -> None:
        journal = self._ready()
        row = self._reserve(journal)
        token = journal.commit_submission_intent(row["operation_id"])
        journal._conn.execute(
            "UPDATE close_operations SET owner_token = ? WHERE operation_id = ?",
            ("replacement-token", row["operation_id"]),
        )
        self.assertFalse(journal.submission_authorized(row["operation_id"], token))
        self.assertTrue(journal.submission_authorized(row["operation_id"], "replacement-token"))

    def _confirm(self, journal, instance="instance-a", generation=1, trade="T1", units="1000"):
        row = journal.reserve(
            account_binding_value=BINDING,
            position_instance_id=instance,
            position_generation=generation,
            instrument="EUR_USD",
            trade_id=trade,
            direction="BUY",
            original_units=units,
            requested_units=units,
        )
        journal.commit_submission_intent(row["operation_id"])
        journal.mark(
            row["operation_id"],
            confirmation_state="CLOSE_FULLY_CONFIRMED",
            submission_state="SENT",
            error_classification="",
            confirmed_units=units,
            remaining_units="0",
            transaction_ids=("TX1",),
        )
        return operation_from_journal_row(journal.get(row["operation_id"]))

    def test_identity_delete_refuses_a_different_row(self) -> None:
        journal = self._ready()
        original = _position()
        open_position(original)
        operation = self._confirm(journal)
        replacement = _position(position_instance_id="instance-b", broker_trade_ids="T9")
        open_position(replacement)
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertEqual(positions["EUR_USD"].position_instance_id, "instance-b")
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIn("EUR_USD", positions)

    def test_identity_delete_removes_only_the_matching_row(self) -> None:
        journal = self._ready()
        open_position(_position())
        operation = self._confirm(journal)
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertEqual(removed.position_instance_id, "instance-a")
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(journal.get(operation.operation_id)["confirmation_state"], "CLOSE_FINALISED")

    def test_changed_units_generation_direction_and_account_refuse(self) -> None:
        journal = self._ready()
        row = _position()
        open_position(row)
        operation = self._confirm(journal)
        row.units = 500.0
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        row.units = 1000.0
        row.position_generation = 2
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        row.position_generation = 1
        row.direction = "SELL"
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        row.direction = "BUY"
        operation.account_scope = "different-binding"
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertIn("EUR_USD", positions)

    def test_observation_and_partial_rows_are_not_deleted(self) -> None:
        journal = self._ready()
        open_position(_position(observation_only=True, execution_kind="reconcile_import"))
        operation = self._confirm(journal)
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        positions.clear()
        open_position(_position())
        partial = self._reserve(journal, trade="T2", instance="instance-p")
        journal.mark(
            partial["operation_id"],
            confirmation_state="CLOSE_PARTIALLY_CONFIRMED",
            submission_state="SENT",
            error_classification="partial_fill",
            confirmed_units="400",
            remaining_units="600",
            transaction_ids=("TX2",),
        )
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation_from_journal_row(journal.get(partial["operation_id"]))))
        self.assertEqual(positions["EUR_USD"].units, 1000.0)

    def test_delete_then_failed_finalise_does_not_match_a_new_row(self) -> None:
        journal = self._ready()
        open_position(_position())
        operation = self._confirm(journal)
        arm_active_journal_fault("before_commit")
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNotNone(removed)
        self.assertEqual(journal.get(operation.operation_id)["confirmation_state"], "CLOSE_FULLY_CONFIRMED")
        open_position(_position(position_instance_id="instance-new", broker_trade_ids="T2"))
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T2")

    def test_ambiguous_observation_does_not_authorise_retry(self) -> None:
        journal = self._ready()
        row = self._reserve(journal)
        journal.commit_submission_intent(row["operation_id"])
        journal.mark(
            row["operation_id"],
            confirmation_state="CLOSE_OUTCOME_AMBIGUOUS",
            submission_state="SENT",
            error_classification="timeout",
        )
        for observation in ("trade_still_open", "no_attributable_transaction", "broker_flat_without_attribution"):
            state = resolve_from_retrieved_transaction(row["operation_id"], None, account_id="001-002-0000001-003")
            journal.mark(
                row["operation_id"],
                confirmation_state=state,
                submission_state="SENT",
                error_classification="timeout",
                recovery_status=observation,
            )
        stored = journal.get(row["operation_id"])
        self.assertEqual(stored["confirmation_state"], "CLOSE_OUTCOME_AMBIGUOUS")
        with self.assertRaises(JournalUnavailable):
            self._reserve(journal)


if __name__ == "__main__":
    unittest.main()
