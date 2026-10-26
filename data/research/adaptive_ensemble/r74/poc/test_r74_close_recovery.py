"""R.74 operational close recovery with a synthetic broker. No network."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_OUTCOME_AMBIGUOUS,
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_REJECTED_CONFIRMED,
    note_recovery_observation,
    reset_close_evidence_state,
    resolve_from_retrieved_transaction,
    run_guarded_live_close,
)
from forex_bot.broker_exit import account_disappeared_broker_position  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    account_binding,
    active_journal,
    arm_active_journal_fault,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    close_confirmed_live_position,
    import_position_from_broker,
    positions,
)
from forex_bot.reconciliation import BrokerSnapshotError, _interpret_open_positions  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.close_body: dict | None = None
        self.transaction: dict | None = None
        self.fail_close: BaseException | None = None
        self.lock = threading.Lock()

    def request(self, request_obj):
        name = type(request_obj).__name__
        with self.lock:
            self.calls.append(name)
        if name not in {"PositionClose", "TransactionDetails", "OpenPositions", "TradeDetails", "OrdersPending"}:
            raise isolation.IsolationBreach(name)
        if name == "PositionClose":
            if self.fail_close is not None:
                raise self.fail_close
            return self.close_body
        if name == "TransactionDetails":
            return {"transaction": self.transaction}
        if name == "OpenPositions":
            return {"positions": []}
        if name == "OrdersPending":
            return {"orders": []}
        return {"trade": {"id": "T1", "instrument": "EUR_USD", "state": "OPEN", "currentUnits": "1000"}}


def _row(**kwargs) -> Position:
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
    )
    data.update(kwargs)
    return Position(**data)


def _fill(units: str = "-1000") -> dict:
    return {"longOrderFillTransaction": {"id": "TX1", "type": "ORDER_FILL", "instrument": "EUR_USD", "units": units}}


def _tx(units: str = "-1000", closed: str = "1000") -> dict:
    return {
        "id": "TX1",
        "type": "ORDER_FILL",
        "accountID": ACCOUNT,
        "instrument": "EUR_USD",
        "units": units,
        "tradesClosed": [{"tradeID": "T1", "units": closed}],
    }


class OperationalRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "closes.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        reset_oanda_rate_limiter_for_tests()
        reset_close_evidence_state()
        positions.clear()
        broker_observations.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.api = FakeAPI()
        oanda_client._api = self.api

    def tearDown(self) -> None:
        oanda_client._api = None
        reset_journal_process_state()
        positions.clear()
        broker_observations.clear()
        self.tmp.cleanup()

    def test_full_fill_deletes_matching_row_only(self) -> None:
        self.api.close_body = _fill()
        self.api.transaction = _tx()
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        replacement = _row(broker_trade_ids="T9", position_instance_id="other", position_generation=1)
        positions["EUR_USD"] = replacement
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T9")

    def test_partial_fill_keeps_row_and_blocks_resubmit(self) -> None:
        self.api.close_body = _fill(units="-400")
        self.api.transaction = _tx(units="-400", closed="400")
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(row.units, 1000.0)
        again = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(again.operation_id, operation.operation_id)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))

    def test_timeout_blocks_resubmit_across_process_reopen(self) -> None:
        self.api.fail_close = TimeoutError("synthetic")
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(operation.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        reset_close_evidence_state()
        reset_journal_process_state()
        again = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(again.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)

    def test_missing_and_unauthorised_journal_do_not_submit(self) -> None:
        os.environ["CLOSE_JOURNAL_PATH"] = str(Path(self.tmp.name) / "missing.sqlite")
        reset_journal_process_state()
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(operation.error_classification, "missing_journal")
        self.assertEqual(self.api.calls, [])
        plain = str(Path(self.tmp.name) / "plain.sqlite")
        bootstrap_journal(plain).close()
        os.environ["CLOSE_JOURNAL_PATH"] = plain
        reset_journal_process_state()
        refused = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(refused.error_classification, "bootstrap_does_not_authorise_closes")
        self.assertEqual(self.api.calls, [])

    def test_rejection_can_reserve_a_new_operation(self) -> None:
        self.api.close_body = {"longOrderRejectTransaction": {"id": "RJ", "type": "ORDER_REJECT"}}
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(operation.confirmation_state, CLOSE_REJECTED_CONFIRMED)
        self.api.close_body = _fill()
        self.api.transaction = _tx()
        second = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(second.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertNotEqual(second.operation_id, operation.operation_id)

    def test_flat_snapshot_and_open_trade_do_not_confirm(self) -> None:
        label, _rows, _ids = _interpret_open_positions({"positions": []})
        self.assertEqual(label, "COMPLETE_EMPTY")
        with self.assertRaises(BrokerSnapshotError) as incomplete:
            _interpret_open_positions({})
        self.assertEqual(incomplete.exception.classification, "INCOMPLETE")
        row = _row()
        positions[row.symbol] = row
        self.api.fail_close = TimeoutError("synthetic")
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(account_disappeared_broker_position(row), "retained")
        self.assertIn("EUR_USD", positions)
        state = note_recovery_observation(operation.operation_id, "trade_still_open")
        self.assertEqual(state, CLOSE_OUTCOME_AMBIGUOUS)
        resolved = resolve_from_retrieved_transaction(operation.operation_id, {"transaction": _tx()}, account_id=ACCOUNT)
        self.assertEqual(resolved, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)

    def test_observation_is_not_submitted(self) -> None:
        import_position_from_broker("EUR_USD", 1000.0, 1.1, 1.0, 1.2, broker_trade_ids="T1")
        operation = asyncio.run(run_guarded_live_close(broker_observations["EUR_USD"], reason="test"))
        self.assertEqual(operation.error_classification, "management_not_permitted")
        self.assertEqual(self.api.calls, [])
        self.assertNotIn("EUR_USD", positions)

    def test_fault_after_intent_does_not_submit(self) -> None:
        active_journal()
        arm_active_journal_fault("after_intent_commit")
        row = _row()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="test"))
        self.assertEqual(self.api.calls, [])
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        reset_close_evidence_state()
        reset_journal_process_state()
        stored = active_journal().blocking_trade(account_binding(ACCOUNT), "EUR_USD", "T1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["confirmation_state"], CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(int(stored["submission_intent"]), 1)

    def test_two_threads_submit_once(self) -> None:
        self.api.close_body = _fill()
        self.api.transaction = _tx()
        row = _row()
        positions[row.symbol] = row
        barrier = threading.Barrier(2)
        results = []

        def worker() -> None:
            barrier.wait(2)
            try:
                operation = asyncio.run(run_guarded_live_close(row, reason="test"))
            except Exception as exc:
                results.append(type(exc).__name__)
                return
            results.append(operation.confirmation_state)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(len(results), 2)
        self.assertNotIn("TypeError", results)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertIn(CLOSE_FULLY_CONFIRMED, results)


if __name__ == "__main__":
    unittest.main()
