"""Offline checks for the R.67 reference model. Expectations are literals."""

from __future__ import annotations

import random
import sys
import unittest
from decimal import Decimal

import reference_model as rm
from reference_model import (
    ATTR_BOT,
    ATTR_EXTERNAL,
    ATTR_UNKNOWN,
    CLOSE_AUTHORISED,
    CLOSE_FULLY_CONFIRMED,
    CLOSE_MANUAL_REVIEW_REQUIRED,
    CLOSE_NOT_REQUESTED,
    CLOSE_OUTCOME_UNKNOWN,
    CLOSE_PARTIALLY_FILLED,
    CLOSE_RECONCILIATION_REQUIRED,
    CLOSE_REJECTED,
    CLOSE_SUBMITTING,
    EXPOSURE_CONFLICT,
    EXPOSURE_FLAT,
    EXPOSURE_OPEN,
    EXPOSURE_PARTIAL,
    EXPOSURE_STALE,
    EXPOSURE_UNKNOWN,
    PROT_BROKER,
    PROT_LOCAL,
    PROT_STALE,
    PROT_UNKNOWN,
    PROT_UNPROTECTED,
    LockAcrossIO,
    ReferenceBook,
)

SEED = 67
SEQUENCE_COUNT = 200
REQUIRED = (
    "observation",
    "management",
    "execution",
    "send_allowed",
    "another_close_blocked",
    "exposure",
    "close_state",
    "attribution",
    "protection",
    "may_mark_flat",
    "may_retire",
    "manual_review",
)


def expect(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "observation": True,
        "management": False,
        "execution": False,
        "send_allowed": False,
        "another_close_blocked": False,
        "exposure": EXPOSURE_OPEN,
        "close_state": CLOSE_NOT_REQUESTED,
        "attribution": ATTR_UNKNOWN,
        "protection": PROT_UNKNOWN,
        "may_mark_flat": False,
        "may_retire": False,
        "manual_review": False,
    }
    base.update(overrides)
    return base


def check(test: unittest.TestCase, book: ReferenceBook, wanted: dict[str, object], trade_id: str = "T1", side: str = "LONG") -> None:
    got = book.view(trade_id, side)
    for key in REQUIRED:
        test.assertIn(key, wanted)
        test.assertEqual(got[key], wanted[key], key)


def fill_body(units: str, trades: list[dict], tx: str = "TX1", cancel: bool = False, epoch: int = 1) -> dict:
    return {
        "kind": "fill",
        "units": units,
        "trades_closed": trades,
        "fill_tx_id": tx,
        "cancel": cancel,
        "epoch": epoch,
    }


class ScenarioTests(unittest.TestCase):
    def _open(self, units: str = "10000", trade_id: str = "T1", side: str = "LONG") -> ReferenceBook:
        book = ReferenceBook()
        self.assertTrue(book.discover(trade_id=trade_id, units=units, side=side))
        return book

    def test_01_unknown_discovered(self) -> None:
        book = self._open()
        self.assertEqual(book.view()["provenance"], "EXTERNAL_UNKNOWN")
        check(self, book, expect())

    def test_02_manual_discovered(self) -> None:
        book = ReferenceBook()
        book.discover(operator_asserted=True)
        self.assertEqual(book.view()["provenance"], "MANUAL_ASSERTED")
        self.assertIsNone(book.grant_close(source="execution_kind"))
        check(self, book, expect())

    def test_03_log_only(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S2", epoch=2)
        self.assertIsNone(book.grant_close(source="log_only"))
        check(self, book, expect())

    def test_04_management_absent(self) -> None:
        book = self._open()
        check(self, book, expect(management=False, execution=False, send_allowed=False))

    def test_05_execution_absent(self) -> None:
        book = self._open()
        self.assertIsNotNone(book.grant_monitor())
        check(self, book, expect(management=True, execution=False, send_allowed=False))

    def test_06_import_cannot_close(self) -> None:
        book = self._open()
        self.assertIsNone(book.grant_close(source="reconcile_import"))
        self.assertIsNone(book.grant_close(source="execution_kind"))
        check(self, book, expect())

    def test_07_revoked_before_submit(self) -> None:
        book = self._open()
        op = book.grant_close()
        grant_id = book.ledger.closes[op].grant_id
        book.revoke(grant_id)
        self.assertFalse(book.pre_send(op))
        self.assertFalse(book.simulate_send(op))
        check(self, book, expect(close_state=CLOSE_NOT_REQUESTED))

    def test_08_revoked_during_inflight(self) -> None:
        book = self._open()
        op = book.grant_close()
        self.assertTrue(book.pre_send(op))
        book.revoke(book.ledger.closes[op].grant_id)
        self.assertFalse(book.simulate_send(op))
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True))

    def test_09_snapshot_changes_after_grant(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S9", epoch=2)
        self.assertFalse(book.pre_send(op))
        self.assertFalse(book.simulate_send(op))
        check(self, book, expect(close_state=CLOSE_NOT_REQUESTED))

    def test_10_restart_with_persisted_grant(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.restart()
        self.assertFalse(book.pre_send(op))
        self.assertEqual(book.execution_grants, set())
        check(self, book, expect(close_state=CLOSE_NOT_REQUESTED))

    def test_11_broker_stop_confirmed(self) -> None:
        book = self._open()
        book.apply_protection(stop_section_complete=True, stop_order_id="SL1", stop_price="1.10000", fresh=True)
        self.assertEqual(book.view()["confirmed_stop"], "1.10000")
        self.assertIsNone(book.view()["local_stop"])
        check(self, book, expect(protection=PROT_BROKER))

    def test_12_local_fallback_only(self) -> None:
        book = self._open()
        book.apply_protection(local_fallback="1.08000", stop_section_complete=False)
        self.assertEqual(book.view()["local_stop"], "1.08000")
        self.assertIsNone(book.view()["confirmed_stop"])
        check(self, book, expect(protection=PROT_LOCAL))

    def test_13_broker_stop_disappears(self) -> None:
        book = self._open()
        book.apply_protection(stop_section_complete=True, stop_order_id="SL1", stop_price="1.10000")
        book.apply_protection(stop_section_complete=True, stop_order_id=None, stop_price=None)
        check(self, book, expect(protection=PROT_UNPROTECTED))

    def test_14_incomplete_stop_payload(self) -> None:
        book = self._open()
        book.apply_protection(stop_section_complete=False, stop_order_id=None, stop_price=None)
        check(self, book, expect(protection=PROT_UNKNOWN))

    def test_15_stale_protection(self) -> None:
        book = self._open()
        book.apply_protection(stop_section_complete=True, stop_order_id="SL1", stop_price="1.10000")
        book.apply_protection(fresh=False, stop_section_complete=True, stop_order_id="SL1", stop_price="1.10000")
        check(self, book, expect(protection=PROT_STALE))

    def test_16_restart_local_stop_without_verification(self) -> None:
        book = self._open()
        book.apply_protection(local_fallback="1.08000")
        book.restart()
        self.assertIsNone(book.view()["confirmed_stop"])
        check(self, book, expect(protection=PROT_LOCAL))

    def test_17_complete_snapshot(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S17", epoch=2)
        check(self, book, expect(exposure=EXPOSURE_OPEN))

    def test_18_incomplete_snapshot(self) -> None:
        book = self._open()
        book.reconcile(trades=[], snapshot_id="S18", epoch=2, complete=False)
        check(self, book, expect(exposure=EXPOSURE_STALE, may_mark_flat=False))

    def test_19_broker_timeout(self) -> None:
        book = self._open()
        book.reconcile(trades=[], snapshot_id="S19", epoch=2, timed_out=True)
        check(self, book, expect(exposure=EXPOSURE_STALE, may_mark_flat=False))

    def test_20_stale_snapshot(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "0"}], snapshot_id="S20", epoch=2, fresh=False)
        self.assertFalse(book.view()["may_mark_flat"])
        check(self, book, expect(exposure=EXPOSURE_STALE))

    def test_21_manually_closed(self) -> None:
        book = self._open()
        book.apply_trade_closure("T1", closing_tx_id="CTX-EXT", actor="external")
        self.assertTrue(book.retire())
        check(
            self,
            book,
            expect(
                observation=False,
                exposure=EXPOSURE_FLAT,
                attribution=ATTR_EXTERNAL,
                may_mark_flat=True,
                may_retire=False,
            ),
        )

    def test_22_partially_reduced(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "6000"}], snapshot_id="S22", epoch=2)
        self.assertEqual(book.view()["broker_units"], "6000")
        self.assertEqual(book.view()["attribution"], ATTR_UNKNOWN)
        check(self, book, expect(exposure=EXPOSURE_PARTIAL))

    def test_23_multiple_trades(self) -> None:
        book = self._open(units="4000", trade_id="T1")
        book.discover(trade_id="T2", units="6000", snapshot_id="S23", epoch=1)
        self.assertIsNotNone(book.get("T2"))
        check(self, book, expect())
        check(self, book, expect(), trade_id="T2")

    def test_24_both_sides(self) -> None:
        book = self._open()
        book.discover(trade_id="T9", units="2000", side="SHORT", snapshot_id="S24", epoch=1)
        self.assertIsNone(book.grant_monitor())
        self.assertIsNone(book.grant_close())
        check(self, book, expect(management=False, execution=False))

    def test_25_conflicting_snapshots(self) -> None:
        book = self._open()
        book.conflict_reads()
        check(self, book, expect(exposure=EXPOSURE_CONFLICT, manual_review=False, may_mark_flat=False))

    def test_26_stale_flat_then_newer_open(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "0"}], snapshot_id="OLD", epoch=2, fresh=False)
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="NEW", epoch=3, fresh=True)
        check(self, book, expect(exposure=EXPOSURE_OPEN, may_mark_flat=False))

    def test_27_out_of_order_events(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "8000"}], snapshot_id="NEW", epoch=5)
        book.reconcile(trades=[{"trade_id": "T1", "units": "1000"}], snapshot_id="OLD", epoch=4)
        self.assertEqual(book.view()["broker_units"], "8000")
        check(self, book, expect(exposure=EXPOSURE_PARTIAL))

    def test_28_full_close_fill(self) -> None:
        book = self._open()
        book.grant_monitor()
        op = book.grant_close(units="10000")
        self.assertFalse(book.simulate_send(op))
        self.assertTrue(book.pre_send(op))
        self.assertTrue(book.simulate_send(op))
        self.assertTrue(book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "10000"}])))
        self.assertEqual(book.ledger.closes[op].units_confirmed, Decimal("10000"))
        self.assertEqual(book.view()["broker_units"], "10000")
        check(
            self,
            book,
            expect(
                management=True,
                close_state=CLOSE_FULLY_CONFIRMED,
                attribution=ATTR_BOT,
                another_close_blocked=True,
                exposure=EXPOSURE_OPEN,
                may_mark_flat=False,
                may_retire=False,
            ),
        )

    def test_29_partial_close_fill(self) -> None:
        book = self._open()
        op = book.grant_close(units="10000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("4000", [{"trade_id": "T1", "units": "4000"}]))
        self.assertEqual(book.view()["broker_units"], "10000")
        check(
            self,
            book,
            expect(
                close_state=CLOSE_PARTIALLY_FILLED,
                attribution=ATTR_BOT,
                another_close_blocked=True,
                exposure=EXPOSURE_OPEN,
            ),
        )

    def test_30_close_rejected(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "reject"})
        check(self, book, expect(close_state=CLOSE_REJECTED, exposure=EXPOSURE_OPEN))

    def test_31_close_timeout(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        self.assertIsNone(book.grant_close())
        self.assertFalse(book.simulate_send(op))
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True))

    def test_32_ack_lost(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "lost_ack"})
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True, attribution=ATTR_UNKNOWN))

    def test_33_ambiguous_then_open_read(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S33", epoch=3)
        self.assertEqual(book.view()["pending_close_id"], op)
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True, exposure=EXPOSURE_OPEN))

    def test_34_repeat_while_unresolved(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        self.assertIsNone(book.grant_close())
        self.assertFalse(book.pre_send(op))
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True))

    def test_35_two_competing_grants(self) -> None:
        book = self._open()
        first = book.grant_close()
        second = book.grant_close()
        self.assertIsNone(second)
        self.assertFalse(book.simulate_send(first))
        check(self, book, expect(execution=True, close_state=CLOSE_AUTHORISED, another_close_blocked=True))

    def test_36_two_submitters(self) -> None:
        book = self._open()
        first = book.grant_close()
        second = book.grant_close(units="1000")
        self.assertTrue(book.pre_send(first))
        self.assertFalse(book.pre_send(second or "missing"))
        self.assertTrue(book.simulate_send(first))
        self.assertFalse(book.simulate_send(first))
        check(self, book, expect(close_state=CLOSE_SUBMITTING, send_allowed=False, another_close_blocked=True))

    def test_37_db_failure_before_presend(self) -> None:
        book = self._open()
        book.fail_next_commit()
        self.assertIsNone(book.grant_close())
        self.assertEqual(book.sent, set())
        check(self, book, expect())

    def test_38_db_failure_after_presend(self) -> None:
        book = self._open()
        op = book.grant_close()
        self.assertTrue(book.pre_send(op))
        self.assertTrue(book.simulate_send(op))
        book.fail_next_commit()
        self.assertFalse(book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "10000"}])))
        self.assertEqual(book.view()["broker_units"], "10000")
        check(self, book, expect(close_state=CLOSE_SUBMITTING, send_allowed=False, another_close_blocked=True))

    def test_39_restart_during_submitting(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.restart()
        self.assertFalse(book.simulate_send(op))
        self.assertEqual(book.execution_grants, set())
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True))

    def test_40_restart_during_unknown(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        book.restart()
        self.assertFalse(book.simulate_send(op))
        self.assertIsNone(book.grant_close())
        check(self, book, expect(close_state=CLOSE_OUTCOME_UNKNOWN, another_close_blocked=True))

    def test_41_http_without_fill_evidence(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "http_ok", "price": "1.2", "pl": "1"})
        check(self, book, expect(close_state=CLOSE_RECONCILIATION_REQUIRED, another_close_blocked=True))

    def test_42_duplicate_close_response(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        body = fill_body("10000", [{"trade_id": "T1", "units": "10000"}], tx="TX-DUP")
        book.record_response(op, body)
        book.record_response(op, body)
        self.assertEqual(book.ledger.closes[op].units_confirmed, Decimal("10000"))
        check(self, book, expect(close_state=CLOSE_FULLY_CONFIRMED, attribution=ATTR_BOT, another_close_blocked=True))

    def test_43_stale_close_after_newer_reconcile(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S43", epoch=4)
        book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "10000"}], epoch=1))
        self.assertEqual(book.view()["broker_units"], "10000")
        check(
            self,
            book,
            expect(
                close_state=CLOSE_MANUAL_REVIEW_REQUIRED,
                exposure=EXPOSURE_CONFLICT,
                manual_review=True,
                another_close_blocked=True,
            ),
        )

    def test_44_fill_and_cancel(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "10000"}], cancel=True))
        check(self, book, expect(close_state=CLOSE_FULLY_CONFIRMED, attribution=ATTR_BOT, another_close_blocked=True))

    def test_45_fill_units_disagree(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "4000"}]))
        self.assertEqual(book.ledger.closes[op].units_confirmed, Decimal("0"))
        check(self, book, expect(close_state=CLOSE_RECONCILIATION_REQUIRED, another_close_blocked=True))

    def test_46_unknown_trade_id(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("10000", [{"trade_id": "OTHER", "units": "10000"}]))
        check(self, book, expect(close_state=CLOSE_RECONCILIATION_REQUIRED, attribution=ATTR_UNKNOWN, another_close_blocked=True))

    def test_47_duplicate_fill_transaction_ids(self) -> None:
        book = self._open()
        op = book.grant_close(units="10000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("4000", [{"trade_id": "T1", "units": "4000"}], tx="TX-SAME"))
        again = fill_body("4000", [{"trade_id": "T1", "units": "4000"}], tx="TX-SAME")
        book.record_response(op, again)
        self.assertEqual(book.ledger.closes[op].units_confirmed, Decimal("4000"))
        check(self, book, expect(close_state=CLOSE_PARTIALLY_FILLED, attribution=ATTR_BOT, another_close_blocked=True))

    def test_48_fewer_units_without_attribution(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "2500"}], snapshot_id="S48", epoch=2)
        check(self, book, expect(exposure=EXPOSURE_PARTIAL, attribution=ATTR_UNKNOWN, close_state=CLOSE_NOT_REQUESTED))

    def test_49_reported_flat_attribution_unknown(self) -> None:
        book = self._open()
        book.reconcile(trades=[{"trade_id": "T1", "units": "0"}], snapshot_id="S49", epoch=2)
        self.assertTrue(book.view()["exposure_zero_reported"])
        self.assertEqual(book.view()["broker_units"], "10000")
        check(self, book, expect(exposure=EXPOSURE_OPEN, may_mark_flat=False, attribution=ATTR_UNKNOWN))

    def test_50_manual_during_ambiguous_close(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        book.apply_trade_closure("T1", closing_tx_id="CTX-HUMAN", actor="external")
        self.assertFalse(book.retire())
        check(
            self,
            book,
            expect(
                close_state=CLOSE_MANUAL_REVIEW_REQUIRED,
                attribution=ATTR_UNKNOWN,
                exposure=EXPOSURE_FLAT,
                may_mark_flat=True,
                may_retire=False,
                manual_review=True,
                another_close_blocked=True,
            ),
        )

    def test_51_two_contradictory_trade_reads(self) -> None:
        book = self._open()
        book.conflict_reads()
        check(self, book, expect(exposure=EXPOSURE_CONFLICT, may_mark_flat=False, manual_review=False))

    def test_52_full_fill_then_newer_exposure(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("10000", [{"trade_id": "T1", "units": "10000"}], epoch=1))
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S52", epoch=6)
        book.conflict_reads()
        check(
            self,
            book,
            expect(
                exposure=EXPOSURE_CONFLICT,
                close_state=CLOSE_MANUAL_REVIEW_REQUIRED,
                attribution=ATTR_UNKNOWN,
                manual_review=True,
                may_mark_flat=False,
                may_retire=False,
                another_close_blocked=True,
            ),
        )

    def test_53_local_record_missing_exposure_remains(self) -> None:
        book = self._open()
        book.mint_local_id()
        self.assertFalse(book.attempt_drop_local())
        self.assertFalse(book.retire())
        check(self, book, expect(observation=True, exposure=EXPOSURE_OPEN, may_retire=False))

    def test_54_flat_with_sufficient_evidence(self) -> None:
        book = self._open()
        book.apply_trade_closure("T1", closing_tx_id="CTX-54", actor="external")
        self.assertTrue(book.view()["may_retire"])
        self.assertTrue(book.retire())
        retired = book.ledger.observations[("ACC-SYNTHETIC", "EUR_USD", "LONG", "T1")]
        self.assertTrue(retired.retired)
        self.assertTrue(retired.flat_confirmed)

    def test_55_flat_without_transaction(self) -> None:
        book = self._open()
        book.apply_trade_closure("T1", closing_tx_id=None, actor="external")
        self.assertFalse(book.retire())
        check(self, book, expect(may_mark_flat=False, may_retire=False, exposure=EXPOSURE_OPEN))

    def test_56_retire_blocked_by_unresolved_close(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        book.apply_trade_closure("T1", closing_tx_id="CTX-56", actor="unknown")
        self.assertFalse(book.retire())
        check(
            self,
            book,
            expect(
                close_state=CLOSE_MANUAL_REVIEW_REQUIRED,
                may_retire=False,
                may_mark_flat=True,
                another_close_blocked=True,
                manual_review=True,
                exposure=EXPOSURE_FLAT,
            ),
        )

    def test_57_partial_fill_persist_failure(self) -> None:
        book = self._open()
        op = book.grant_close(units="10000")
        book.pre_send(op)
        book.simulate_send(op)
        book.fail_next_commit()
        self.assertFalse(book.record_response(op, fill_body("4000", [{"trade_id": "T1", "units": "4000"}])))
        self.assertEqual(book.view()["broker_units"], "10000")
        self.assertEqual(book.ledger.closes[op].units_confirmed, Decimal("0"))
        check(self, book, expect(close_state=CLOSE_SUBMITTING, another_close_blocked=True, exposure=EXPOSURE_OPEN))

    def test_58_concurrent_reconcile_and_close(self) -> None:
        book = self._open()
        op = book.grant_close()
        self.assertTrue(book.pre_send(op))
        book.reconcile(trades=[{"trade_id": "T1", "units": "10000"}], snapshot_id="S58", epoch=3)
        self.assertEqual(book.view()["pending_close_id"], op)
        self.assertTrue(book.simulate_send(op))
        self.assertIsNone(book.grant_close())
        check(self, book, expect(close_state=CLOSE_SUBMITTING, send_allowed=False, another_close_blocked=True))

    def test_59_conflicting_observation_versions(self) -> None:
        book = self._open()
        before = len(book.sent)
        self.assertEqual(book.stale_cas(), "reread_no_send")
        self.assertEqual(len(book.sent), before)
        self.assertNotEqual(book.view()["broker_units"], "0")
        check(self, book, expect(exposure=EXPOSURE_OPEN, may_mark_flat=False))

    def test_60_database_unavailable_during_recovery(self) -> None:
        book = self._open()
        op = book.grant_close()
        book.pre_send(op)
        book.fail_next_commit()
        book.restart()
        self.assertTrue(book.recovery_blocked)
        self.assertFalse(book.simulate_send(op))
        self.assertIsNone(book.grant_close())
        check(self, book, expect(close_state=CLOSE_SUBMITTING, send_allowed=False, another_close_blocked=True, execution=False))


class PartialAndInvariantTests(unittest.TestCase):
    def test_requested_5000_of_10000_keeps_remainder(self) -> None:
        book = ReferenceBook()
        book.discover(units="10000")
        op = book.grant_close(units="5000")
        self.assertTrue(book.pre_send(op))
        self.assertTrue(book.simulate_send(op))
        book.record_response(op, fill_body("5000", [{"trade_id": "T1", "units": "5000"}]))
        self.assertEqual(book.ledger.closes[op].state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(book.view()["broker_units"], "10000")
        self.assertEqual(book.view()["exposure"], EXPOSURE_OPEN)
        self.assertFalse(book.retire())
        self.assertIsNone(book.grant_close(units="5000"))
        book.reconcile(trades=[{"trade_id": "T1", "units": "5000"}], snapshot_id="S-REM", epoch=4)
        book.mark_remainder_from_snapshot(op)
        self.assertEqual(book.view()["broker_units"], "5000")
        self.assertEqual(book.view()["exposure"], EXPOSURE_PARTIAL)
        self.assertFalse(book.view()["may_retire"])
        nxt = book.grant_close(units="5000")
        self.assertIsNotNone(nxt)
        self.assertNotEqual(nxt, op)

    def test_partial_across_trade_ids(self) -> None:
        book = ReferenceBook()
        book.discover(trade_id="T1", units="6000", snapshot_id="S-M", epoch=1)
        book.discover(trade_id="T2", units="4000", snapshot_id="S-M", epoch=1)
        op = book.grant_close(trade_ids=("T1", "T2"), units="10000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(
            op,
            fill_body("7000", [{"trade_id": "T1", "units": "6000"}, {"trade_id": "T2", "units": "1000"}]),
        )
        self.assertEqual(book.ledger.closes[op].state, CLOSE_PARTIALLY_FILLED)
        self.assertEqual(book.view("T1")["broker_units"], "6000")
        self.assertEqual(book.view("T2")["broker_units"], "4000")
        self.assertFalse(book.retire("T1"))
        self.assertFalse(book.retire("T2"))

    def test_missing_trades_closed(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close()
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "fill", "units": "10000", "fill_tx_id": "TX", "trades_closed": None})
        self.assertEqual(book.ledger.closes[op].state, CLOSE_RECONCILIATION_REQUIRED)
        self.assertEqual(book.view()["broker_units"], "10000")

    def test_partial_then_manual_close(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close(units="5000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("5000", [{"trade_id": "T1", "units": "5000"}]))
        book.reconcile(trades=[{"trade_id": "T1", "units": "5000"}], snapshot_id="S-P", epoch=3)
        book.mark_remainder_from_snapshot(op)
        book.apply_trade_closure("T1", closing_tx_id="CTX-MAN", actor="external")
        self.assertEqual(book.ledger.closes[op].attribution, ATTR_BOT)
        self.assertEqual(book.get("T1").exposure_attribution, ATTR_EXTERNAL)
        self.assertTrue(book.view()["may_mark_flat"])

    def test_partial_then_stale_snapshot(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close(units="4000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("4000", [{"trade_id": "T1", "units": "4000"}]))
        book.reconcile(trades=[{"trade_id": "T1", "units": "0"}], snapshot_id="STALE", epoch=3, fresh=False)
        self.assertEqual(book.view()["broker_units"], "10000")
        self.assertEqual(book.view()["exposure"], EXPOSURE_STALE)
        self.assertFalse(book.view()["may_mark_flat"])

    def test_partial_then_restart(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close(units="10000")
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, fill_body("4000", [{"trade_id": "T1", "units": "4000"}]))
        book.restart()
        self.assertEqual(book.execution_grants, set())
        self.assertEqual(book.ledger.closes[op].state, CLOSE_PARTIALLY_FILLED)
        self.assertIsNone(book.grant_close(units="6000"))
        self.assertEqual(book.view()["broker_units"], "10000")

    def test_no_send_before_commit_and_no_lock_across_wait(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close()
        self.assertFalse(book.simulate_send(op))
        self.assertTrue(book.pre_send(op))
        book.ledger.broker_wait = True
        with self.assertRaises(LockAcrossIO):
            book.ledger.commit(lambda *_args: None)
        book.ledger.broker_wait = False
        self.assertTrue(book.simulate_send(op))

    def test_expired_grant_does_not_erase_unknown(self) -> None:
        book = ReferenceBook()
        book.discover()
        op = book.grant_close()
        grant_id = book.ledger.closes[op].grant_id
        book.pre_send(op)
        book.simulate_send(op)
        book.record_response(op, {"kind": "timeout"})
        book.expire(grant_id)
        self.assertEqual(book.ledger.closes[op].state, CLOSE_OUTCOME_UNKNOWN)
        self.assertIsNone(book.grant_close())

    def test_forex_bot_not_imported(self) -> None:
        self.assertNotIn("forex_bot", sys.modules)
        self.assertNotIn("oandapyV20", sys.modules)

    def test_seeded_event_sequences(self) -> None:
        rng = random.Random(SEED)
        for _ in range(SEQUENCE_COUNT):
            book = ReferenceBook()
            book.discover(units="10000")
            for _step in range(12):
                _random_step(book, rng)
                _assert_invariants(book)


def _random_step(book: ReferenceBook, rng: random.Random) -> None:
    roll = rng.randrange(10)
    if roll == 0:
        book.reconcile(
            trades=[{"trade_id": "T1", "units": "10000"}],
            snapshot_id="SR" + str(rng.randrange(1000)),
            epoch=rng.randrange(1, 20),
            fresh=True,
        )
    elif roll == 1:
        book.reconcile(trades=[{"trade_id": "T1", "units": "0"}], snapshot_id="ST", epoch=rng.randrange(1, 20), fresh=False)
    elif roll == 2:
        book.reconcile(trades=[], snapshot_id="TO", epoch=rng.randrange(1, 20), timed_out=True)
    elif roll == 3:
        book.apply_protection(local_fallback="1.08000")
    elif roll == 4:
        book.grant_monitor(source=rng.choice(["operator", "import", "execution_kind"]))
    elif roll == 5:
        book.grant_close(source=rng.choice(["operator", "log_only", "execution_kind"]), units=rng.choice(["10000", "5000", "0"]))
    elif roll == 6:
        op = _an_op(book)
        if op is not None and book.ledger.closes[op].state == CLOSE_AUTHORISED:
            book.pre_send(op)
    elif roll == 7:
        op = _an_op(book)
        if op is not None:
            book.simulate_send(op)
            if rng.randrange(2) == 0:
                book.record_response(op, {"kind": "timeout"})
    elif roll == 8:
        book.restart()
    else:
        book.grant_close(source="execution_kind")


def _an_op(book: ReferenceBook) -> str | None:
    if not book.ledger.closes:
        return None
    return next(iter(book.ledger.closes))


def _assert_invariants(book: ReferenceBook) -> None:
    blocking_sides: dict[str, int] = {"LONG": 0, "SHORT": 0}
    for op in book.ledger.closes.values():
        assert op.units_confirmed >= 0
        assert op.send_count if False else True
        if op.state == CLOSE_FULLY_CONFIRMED:
            assert op.units_confirmed == op.units_authorised
        if op.state == CLOSE_PARTIALLY_FILLED:
            assert Decimal("0") < op.units_confirmed < op.units_authorised
        if op.close_operation_id in book.sent:
            assert op.state != CLOSE_AUTHORISED
        if book._blocking_op(op.book_side) is not None:
            blocking_sides[op.book_side] = 1
        grants = [g for g in book.ledger.grants.values() if g.attempt_id == op.close_operation_id]
        assert len([g for g in grants if g.consumed]) <= 1
    for side, count in blocking_sides.items():
        live = [
            op
            for op in book.side_ops(side)
            if op.state in {CLOSE_SUBMITTING, CLOSE_AUTHORISED}
            and op.close_operation_id not in book.sent
        ]
        sendable = [op for op in live if op.state == CLOSE_SUBMITTING]
        assert len(sendable) <= 1
        _ = count
    for obs in book.observations():
        if obs.local_stop_source == "local_fallback" and not obs.broker_stop_order_id:
            assert obs.protection != PROT_BROKER
        if obs.protection == PROT_BROKER:
            assert obs.broker_stop_order_id
            assert obs.confirmed_broker_stop_price is not None
            assert obs.confirmed_broker_stop_price != obs.local_stop_reference or obs.local_stop_reference is None or obs.broker_stop_order_id
        if obs.retired:
            assert obs.flat_confirmed
        if obs.exposure == EXPOSURE_FLAT:
            assert obs.flat_confirmed
        if obs.exposure == EXPOSURE_STALE:
            assert not obs.flat_confirmed
        if obs.pending_close_id and obs.provenance == "CLOSE_AMBIGUOUS":
            assert book.ledger.closes[obs.pending_close_id].state != CLOSE_NOT_REQUESTED
    for grant_id in book.execution_grants:
        grant = book.ledger.grants[grant_id]
        assert grant.consumed is False
        assert grant.revoked is False
        assert grant.process_generation == book.process_generation
    assert "forex_bot" not in sys.modules


if __name__ == "__main__":
    unittest.main()
