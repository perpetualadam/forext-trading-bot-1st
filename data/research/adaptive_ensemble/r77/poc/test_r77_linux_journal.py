"""Journal, migration, and repair checks that do not import the OANDA SDK."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot.close_journal import (  # noqa: E402
    JournalUnavailable,
    account_binding,
    bootstrap_journal,
    create_legacy_schema_3_database,
    migrate_journal_3_to_4,
    open_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import begin_entry_submission  # noqa: E402
from forex_bot.positions import positions  # noqa: E402
from forex_bot.recovery_repair import (  # noqa: E402
    ProcessLivenessEvidence,
    RepairAuthorisation,
    repair_abandoned_recovery,
)
from forex_bot.startup_recovery import execute_startup_sequence, reset_startup_recovery_memory  # noqa: E402

ACCOUNT = "001-002-0000001-003"
BINDING = account_binding(ACCOUNT)


class LinuxJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "journal.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()

    def tearDown(self) -> None:
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()
        self.tmp.cleanup()

    def test_atomic_finalisation_and_retained_client_id(self) -> None:
        permit = begin_entry_submission(
            account_binding_value=BINDING,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-1",
            position_generation=1,
            client_order_id="CID-LINUX",
            strategy_name="r77",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-1",
            atr_at_entry_pips="8",
        )
        body = {
            "orderCreateTransaction": {"id": "O-ORDER", "accountID": ACCOUNT},
            "orderFillTransaction": {
                "id": "F-1",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.10000",
                "orderID": "O-ORDER",
                "clientExtensions": {"id": "CID-LINUX"},
                "tradeOpened": {"tradeID": "T-LINUX", "units": "1000", "price": "1.10000"},
            },
        }
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertTrue(evidence["published"])
        self.assertIn("EUR_USD", positions)
        with self.assertRaises(JournalUnavailable) as caught:
            begin_entry_submission(
                account_binding_value=BINDING,
                instrument="EUR_USD",
                direction="BUY",
                requested_units=Decimal("1000"),
                position_instance_id="INST-2",
                position_generation=1,
                client_order_id="CID-LINUX",
                strategy_name="r77",
                stop_loss="1.09000",
                take_profit="1.12000",
                entry_reference="decision-1",
                atr_at_entry_pips="8",
            )
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_migration_and_repair_do_not_enable_trading(self) -> None:
        legacy = str(Path(self.tmp.name) / "legacy.sqlite")
        create_legacy_schema_3_database(legacy)
        connection = sqlite3.connect(legacy)
        connection.execute(
            "INSERT INTO entry_operations VALUES ('op-1', ?, 'CID-1', 'ENTRY_FINALISED', 't')",
            (BINDING,),
        )
        connection.commit()
        connection.close()
        migrate_journal_3_to_4(legacy)
        journal = open_journal(legacy)
        version = journal._conn.execute("SELECT schema_version FROM schema_meta").fetchone()[0]
        journal.close()
        self.assertEqual(version, 4)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            INSERT INTO recovery_runs (run_id, state, owner_token, created_at, updated_at)
            VALUES ('RUN-1', 'RECOVERY_IN_PROGRESS', 'OWNER-1', 't', 't')
            """
        )
        connection.commit()
        connection.close()
        result = repair_abandoned_recovery(
            RepairAuthorisation(
                operator_acknowledged=True,
                acknowledgement="operator confirms the recovery owner has exited",
                account_binding=BINDING,
                journal_path=self.path,
                target_run_id="RUN-1",
                liveness=ProcessLivenessEvidence("inactive", "owner_token_and_exit_observation", "OWNER-1"),
            )
        )
        self.assertEqual(result["result"], "REPAIR_COMMITTED")
        self.assertFalse(result["trading_enabled"])
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertNotEqual(report["reason"], "recovery_already_in_progress")
        self.assertEqual(report["close_submission_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
