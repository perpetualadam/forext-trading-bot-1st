"""R.86 read-only snapshot provenance and exposure reporting.

Isolation is imported before operational modules. The report does not write a
journal or submit a broker request. OpenPositions is not treated as complete.
"""

from __future__ import annotations

import asyncio
import hashlib
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

from forex_bot import config as config_mod  # noqa: E402
from forex_bot import live_safety, oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_PARTIALLY_CONFIRMED,
    reset_close_evidence_state,
    run_guarded_live_close,
)
from forex_bot.close_journal import (  # noqa: E402
    account_binding,
    active_journal,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.exposure_report import (  # noqa: E402
    ACTIVE_MANAGEABLE_EXPOSURE,
    BROKER_OBSERVED_EXPOSURE,
    COMPLETE_VERIFIED,
    FAILED,
    INCOMPLETE,
    QUARANTINED_JOURNAL_REMAINDER,
    STALE,
    UNKNOWN_COMPLETENESS,
    UNKNOWN_EXPOSURE,
    UNRESOLVED_EXPOSURE,
    assess_supplied_pages,
    classify_open_positions_body,
    exposure_report,
)
from forex_bot.position_recovery import quarantined_positions  # noqa: E402
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    execute_startup_sequence,
    reset_startup_recovery_memory,
)

ACCOUNT = "001-002-0000001-003"
PERMIT = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.permit"
MARKER = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed"
ZIP = ROOT / "data/research/adaptive_ensemble/r85/R85_SOURCE_REVIEW.zip"
GATES = (
    ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r59/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r60/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r61/live_session_gate.py",
)
HASHES = {
    "forex_bot/oanda_exec.py": "e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5",
    "forex_bot/profit_protection.py": "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
    "forex_bot/startup_recovery.py": "69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _body(units: str, *, trade: str = "T1", instrument: str = "EUR_USD", account: str = ACCOUNT, side: str = "long") -> dict:
    other = "short" if side == "long" else "long"
    return {
        "accountID": account,
        "positions": [
            {
                "instrument": instrument,
                "long": {"units": units if side == "long" else "0", "tradeIDs": [trade] if side == "long" and units != "0" else []},
                "short": {"units": units if side == "short" else "0", "tradeIDs": [trade] if side == "short" and units != "0" else []},
            }
        ],
    }


def _observe(body, **kwargs):
    defaults = dict(
        expected_account=ACCOUNT,
        origin="synthetic",
        recovery_epoch=1,
        observed_at_utc="2026-10-26T13:00:00Z",
        request_start_monotonic=10,
        response_complete_monotonic=12,
        chronology="LOCAL_AFTER_CLOSE",
    )
    defaults.update(kwargs)
    return classify_open_positions_body(body, **defaults)


def _partial_rows():
    quarantined = (
        {
            "instrument": "EUR_USD",
            "direction": "BUY",
            "trade_id": "T1",
            "units": "1000",
            "original_units": "1000",
            "account": ACCOUNT,
        },
    )
    closes = (
        {
            "instrument": "EUR_USD",
            "trade_id": "T1",
            "direction": "BUY",
            "confirmation_state": CLOSE_PARTIALLY_CONFIRMED,
            "confirmed_units": "400",
            "remaining_units": "600",
            "original_units": "1000",
        },
    )
    return quarantined, closes


class Broker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in {"PositionClose", "TransactionDetails", "AccountSummary", "InstrumentsCandles", "PricingInfo"}:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
        if name == "PositionClose":
            return {"longOrderFillTransaction": {"id": "TX-R86", "instrument": "EUR_USD", "units": "-400"}}
        if name == "TransactionDetails":
            return {
                "transaction": {
                    "id": "TX-R86",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "-400",
                    "tradeReduced": {"tradeID": "T1", "units": "-400"},
                }
            }
        return {"account": {"NAV": "10000"}, "candles": []}


class R86Tests(unittest.TestCase):
    def test_01_archive_integrity(self) -> None:
        self.assertEqual(ZIP.stat().st_size, 153847)
        self.assertEqual(_sha(ZIP), "766e0bc37f1ba3b2d1f0d58c216cc5d9c7f467aa9630954cfe0ed2d283102864")

    def test_02_operational_hashes(self) -> None:
        for relative, digest in HASHES.items():
            self.assertEqual(_sha(ROOT / relative), digest, relative)

    def test_03_gates_disabled(self) -> None:
        for gate in GATES:
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))

    def test_04_permit_absent(self) -> None:
        self.assertFalse(PERMIT.exists())

    def test_05_marker_unchanged(self) -> None:
        self.assertEqual(_sha(MARKER), "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c")

    def test_06_network_isolation_blocks_unknown_request(self) -> None:
        broker = Broker()

        class Unexpected:
            pass

        with self.assertRaises(isolation.IsolationBreach):
            broker.request(Unexpected())

    def test_07_valid_source_identity(self) -> None:
        observed = _observe(_body("600"))
        self.assertEqual(observed["endpoint"], "OpenPositions")
        self.assertEqual(observed["expected_account"], ACCOUNT)
        self.assertEqual(observed["observed_account"], ACCOUNT)

    def test_08_missing_source_identity(self) -> None:
        observed = _observe({"positions": []}, expected_account="")
        self.assertIsNone(observed["observed_account"])
        self.assertNotEqual(observed["completeness"], COMPLETE_VERIFIED)

    def test_09_wrong_account(self) -> None:
        observed = _observe(_body("600", account="other-account"))
        self.assertEqual(observed["validation"], "account_mismatch")
        self.assertEqual(observed["completeness"], FAILED)

    def test_10_missing_timestamp(self) -> None:
        observed = _observe(_body("600"), observed_at_utc=None)
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed, current_epoch=1)
        self.assertFalse(report["authoritative_current"])
        self.assertIsNone(observed["observed_at_utc"])

    def test_11_controlled_timestamp(self) -> None:
        observed = _observe(_body("600"), observed_at_utc="2026-10-26T13:00:00Z")
        self.assertEqual(observed["observed_at_utc"], "2026-10-26T13:00:00Z")
        self.assertLess(observed["request_start_monotonic"], observed["response_complete_monotonic"])

    def test_12_stale_epoch(self) -> None:
        observed = _observe(_body("600"), recovery_epoch=1)
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed, current_epoch=2)
        self.assertFalse(report["authoritative_current"])
        self.assertEqual(report["lines"][0]["evidence_quality"], "stale_not_current")

    def test_13_retrieval_failure(self) -> None:
        observed = _observe(None, error="request_failed")
        self.assertEqual(observed["completeness"], FAILED)
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed)
        self.assertEqual(report["unknown_exposure_count"], 1)
        self.assertIsNone(report["lines"][0]["units"])

    def test_14_malformed_response(self) -> None:
        observed = _observe(["not", "a", "dict"])
        self.assertEqual(observed["validation"], "malformed")
        self.assertEqual(observed["completeness"], INCOMPLETE)

    def test_15_unknown_completeness(self) -> None:
        observed = _observe(_body("600"))
        self.assertEqual(observed["completeness"], UNKNOWN_COMPLETENESS)
        self.assertNotEqual(observed["completeness"], COMPLETE_VERIFIED)

    def test_16_explicit_incomplete(self) -> None:
        observed = _observe({"accountID": ACCOUNT})
        self.assertEqual(observed["completeness"], INCOMPLETE)
        self.assertFalse(observed["flat_verified"])

    def test_17_empty_unknown_is_not_flat(self) -> None:
        observed = _observe({"accountID": ACCOUNT, "positions": []})
        self.assertEqual(observed["completeness"], UNKNOWN_COMPLETENESS)
        self.assertEqual(observed["trade_count"], 0)
        self.assertFalse(observed["flat_verified"])
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed, current_epoch=1)
        self.assertFalse(report["flat"])
        self.assertGreater(report["unknown_exposure_count"], 0)

    def test_18_empty_verified_complete_is_not_supported(self) -> None:
        observed = _observe({"accountID": ACCOUNT, "positions": []})
        self.assertNotEqual(observed["completeness"], COMPLETE_VERIFIED)
        self.assertEqual(observed["pagination_state"], "NOT_REPRESENTED")

    def test_19_pagination_not_represented(self) -> None:
        result = assess_supplied_pages([{"index": "1", "missing": True, "trades": []}])
        self.assertEqual(result["completeness"], INCOMPLETE)
        self.assertFalse(result["flat_verified"])

    def test_20_duplicate_page_and_trade(self) -> None:
        page = {"index": "1", "account": ACCOUNT, "trades": [{"instrument": "EUR_USD", "trade_id": "T1"}]}
        self.assertEqual(assess_supplied_pages([page, dict(page)])["reason"], "repeated_page")
        duplicated = {
            "index": "2",
            "account": ACCOUNT,
            "trades": [
                {"instrument": "EUR_USD", "trade_id": "T1"},
                {"instrument": "EUR_USD", "trade_id": "T1"},
            ],
        }
        self.assertEqual(assess_supplied_pages([duplicated])["reason"], "duplicate_trade")

    def test_21_inconsistent_accounts_across_pages(self) -> None:
        pages = [
            {"index": "1", "account": ACCOUNT, "trades": [{"instrument": "EUR_USD", "trade_id": "T1"}]},
            {"index": "2", "account": "other", "trades": [{"instrument": "GBP_USD", "trade_id": "T2"}]},
        ]
        self.assertEqual(assess_supplied_pages(pages)["reason"], "mixed_account")

    def test_22_stale_cached_snapshot(self) -> None:
        observed = _observe(_body("1000"), cached=True, chronology="STALE_CACHE")
        self.assertEqual(observed["completeness"], STALE)
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed, current_epoch=1)
        self.assertFalse(report["authoritative_current"])
        self.assertEqual(report["lines"][0]["evidence_quality"], "stale_not_current")

    def test_23_snapshot_before_close(self) -> None:
        observed = _observe(_body("1000"), chronology="LOCAL_BEFORE_CLOSE")
        self.assertEqual(observed["completeness"], STALE)
        self.assertIsNone(observed["transaction_watermark"])

    def test_24_snapshot_after_close_without_watermark(self) -> None:
        observed = _observe(_body("600"), chronology="AFTER_JOURNAL_COMMIT")
        self.assertIsNone(observed["transaction_watermark"])
        self.assertFalse(observed["broker_order_known"])
        self.assertFalse(observed["suitable_for_recovery"])

    def test_25_active_manageable_exposure(self) -> None:
        report = exposure_report(
            managed=({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T9", "units": "100", "account": ACCOUNT},),
            quarantined=(),
            close_rows=(),
            observation=None,
        )
        self.assertEqual(report["lines"][0]["category"], ACTIVE_MANAGEABLE_EXPOSURE)
        self.assertTrue(report["lines"][0]["manageable"])
        self.assertEqual(report["managed_units_by_instrument"]["EUR_USD"]["BUY"], "100")

    def test_26_partial_quarantine_400_of_1000(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=None)
        line = report["lines"][0]
        self.assertEqual(line["category"], QUARANTINED_JOURNAL_REMAINDER)
        self.assertEqual(line["units"], Decimal("600"))
        self.assertEqual(line["original_units"], Decimal("1000"))
        self.assertEqual(line["confirmed_closed_units"], Decimal("400"))
        self.assertFalse(line["manageable"])
        self.assertFalse(line["confirmed"])

    def test_27_broker_observed_600_is_unverified(self) -> None:
        quarantined, closes = _partial_rows()
        observed = _observe(_body("600"))
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=observed, current_epoch=1)
        broker = [line for line in report["lines"] if line["category"] == BROKER_OBSERVED_EXPOSURE]
        journal = [line for line in report["lines"] if line["category"] == QUARANTINED_JOURNAL_REMAINDER]
        self.assertEqual(broker[0]["units"], Decimal("600"))
        self.assertEqual(broker[0]["evidence_quality"], "unverified_single_response")
        self.assertEqual(journal[0]["units"], Decimal("600"))
        self.assertFalse(broker[0]["confirmed"])
        self.assertIsNone(report["cross_instrument_raw_unit_total"])

    def test_28_broker_observed_1000_conflict(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=_observe(_body("1000")), current_epoch=1)
        broker = next(line for line in report["lines"] if line["category"] == BROKER_OBSERVED_EXPOSURE)
        journal = next(line for line in report["lines"] if line["category"] == QUARANTINED_JOURNAL_REMAINDER)
        self.assertNotEqual(broker["units"], journal["units"])
        self.assertEqual(journal["units"], Decimal("600"))

    def test_29_broker_observed_zero_is_not_a_verified_flat(self) -> None:
        quarantined, closes = _partial_rows()
        observed = _observe({"accountID": ACCOUNT, "positions": []})
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=observed, current_epoch=1)
        self.assertFalse(report["flat_verified"])
        self.assertEqual(report["quarantined_journal_units_by_instrument"]["EUR_USD"]["BUY"], "600")

    def test_30_conflicting_direction(self) -> None:
        quarantined, closes = _partial_rows()
        observed = _observe(_body("-600", side="short"))
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=observed, current_epoch=1)
        broker = next(line for line in report["lines"] if line["category"] == BROKER_OBSERVED_EXPOSURE)
        self.assertEqual(broker["direction"], "SELL")
        self.assertEqual(report["lines"][0]["direction"], "BUY")

    def test_31_wrong_trade_id(self) -> None:
        quarantined, closes = _partial_rows()
        observed = _observe(_body("600", trade="T-OTHER"))
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=observed, current_epoch=1)
        ids = {line["trade_id"] for line in report["lines"]}
        self.assertIn("T1", ids)
        self.assertIn("T-OTHER", ids)

    def test_32_full_close_remainder_zero(self) -> None:
        quarantined = ({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T1", "units": "1000", "original_units": "1000"},)
        closes = ({"instrument": "EUR_USD", "trade_id": "T1", "confirmation_state": CLOSE_FULLY_CONFIRMED, "confirmed_units": "1000", "remaining_units": "0"},)
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=None)
        self.assertEqual(report["lines"][0]["units"], Decimal("0"))
        self.assertGreaterEqual(report["lines"][0]["units"], 0)

    def test_33_full_close_conflicting_snapshot(self) -> None:
        quarantined = ({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T1", "units": "1000", "original_units": "1000"},)
        closes = ({"instrument": "EUR_USD", "trade_id": "T1", "confirmation_state": CLOSE_FULLY_CONFIRMED, "confirmed_units": "1000", "remaining_units": "0"},)
        before = closes[0]["confirmation_state"]
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=_observe(_body("1000")), current_epoch=1)
        self.assertEqual(closes[0]["confirmation_state"], before)
        self.assertEqual(report["lines"][0]["units"], Decimal("0"))
        self.assertEqual(report["lines"][1]["units"], Decimal("1000"))

    def test_34_ambiguous_close_invents_no_units(self) -> None:
        quarantined = ({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T1", "units": "1000", "original_units": "1000"},)
        closes = ({"instrument": "EUR_USD", "trade_id": "T1", "confirmation_state": "CLOSE_RECONCILIATION_REQUIRED", "confirmed_units": None, "remaining_units": None},)
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=_observe(_body("600")), current_epoch=1)
        unresolved = next(line for line in report["lines"] if line["category"] == UNRESOLVED_EXPOSURE)
        self.assertIsNone(unresolved["units"])
        self.assertIsNone(unresolved["confirmed_closed_units"])

    def test_35_missing_observation_is_not_zero(self) -> None:
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=None)
        self.assertEqual(report["lines"][0]["category"], UNKNOWN_EXPOSURE)
        self.assertIsNone(report["lines"][0]["units"])
        self.assertFalse(report["flat"])

    def test_36_unknown_exposure_explicit(self) -> None:
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=_observe(None, error="down"))
        self.assertEqual(report["unknown_exposure_count"], 1)
        self.assertNotEqual(report["lines"][0]["units"], Decimal("0"))

    def test_37_quarantined_units_visible(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=None)
        self.assertIn("EUR_USD", report["quarantined_journal_units_by_instrument"])
        self.assertEqual(report["managed_units_by_instrument"], {})

    def test_38_no_double_counting(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=_observe(_body("600")), current_epoch=1)
        identities = [(line["category"], line["trade_id"]) for line in report["lines"]]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertIsNone(report["cross_instrument_raw_unit_total"])

    def test_39_two_instruments_are_not_summed(self) -> None:
        managed = (
            {"instrument": "EUR_USD", "direction": "BUY", "trade_id": "E", "units": "10"},
            {"instrument": "USD_JPY", "direction": "BUY", "trade_id": "J", "units": "20"},
        )
        report = exposure_report(managed=managed, quarantined=(), close_rows=(), observation=None)
        self.assertEqual(set(report["managed_units_by_instrument"]), {"EUR_USD", "USD_JPY"})
        self.assertIsNone(report["cross_instrument_raw_unit_total"])

    def test_40_two_trades_one_instrument(self) -> None:
        managed = (
            {"instrument": "EUR_USD", "direction": "BUY", "trade_id": "A", "units": "10"},
            {"instrument": "EUR_USD", "direction": "BUY", "trade_id": "B", "units": "15"},
        )
        report = exposure_report(managed=managed, quarantined=(), close_rows=(), observation=None)
        self.assertEqual(report["managed_units_by_instrument"]["EUR_USD"]["BUY"], "25")
        self.assertEqual(len([line for line in report["lines"] if line["category"] == ACTIVE_MANAGEABLE_EXPOSURE]), 2)

    def test_41_opposite_directions_not_netted(self) -> None:
        managed = (
            {"instrument": "EUR_USD", "direction": "BUY", "trade_id": "A", "units": "10"},
            {"instrument": "EUR_USD", "direction": "SELL", "trade_id": "B", "units": "4"},
        )
        report = exposure_report(managed=managed, quarantined=(), close_rows=(), observation=None)
        bucket = report["managed_units_by_instrument"]["EUR_USD"]
        self.assertEqual(bucket["BUY"], "10")
        self.assertEqual(bucket["SELL"], "4")

    def test_42_no_cross_currency_raw_total(self) -> None:
        report = exposure_report(
            managed=(
                {"instrument": "EUR_USD", "direction": "BUY", "trade_id": "E", "units": "1000"},
                {"instrument": "USD_JPY", "direction": "SELL", "trade_id": "J", "units": "1000"},
            ),
            quarantined=(),
            close_rows=(),
            observation=None,
        )
        self.assertIsNone(report["cross_instrument_raw_unit_total"])
        self.assertNotIn("total_units", report)

    def test_43_reporting_is_read_only(self) -> None:
        source = (ROOT / "forex_bot/exposure_report.py").read_text(encoding="utf-8")
        self.assertNotIn("api.request", source)
        self.assertNotIn("OrderCreate", source)
        self.assertNotIn("PositionClose", source)
        self.assertNotIn("journal.mark", source)
        self.assertNotIn("positions[", source)

    def test_44_no_journal_mutation(self) -> None:
        closes = [{"instrument": "EUR_USD", "trade_id": "T1", "confirmation_state": CLOSE_PARTIALLY_CONFIRMED, "confirmed_units": "400", "remaining_units": "600"}]
        before = dict(closes[0])
        exposure_report(
            managed=(),
            quarantined=({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T1", "units": "1000", "original_units": "1000"},),
            close_rows=closes,
            observation=None,
        )
        self.assertEqual(closes[0], before)

    def test_45_no_quarantine_release(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(managed=(), quarantined=quarantined, close_rows=closes, observation=_observe(_body("600")), current_epoch=1)
        self.assertFalse(report["quarantine_released"])
        self.assertFalse(any(line["manageable"] for line in report["lines"] if line["category"] != ACTIVE_MANAGEABLE_EXPOSURE))

    def test_46_no_position_book_mutation(self) -> None:
        book = [{"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T9", "units": "100"}]
        before = dict(book[0])
        exposure_report(managed=book, quarantined=(), close_rows=(), observation=None)
        self.assertEqual(book[0], before)

    def test_47_future_timestamp_is_not_current(self) -> None:
        observed = _observe(_body("600"), observed_at_utc="2026-10-27T00:00:00Z")
        report = exposure_report(
            managed=(),
            quarantined=(),
            close_rows=(),
            observation=observed,
            current_epoch=1,
            reference_now_utc="2026-10-26T13:00:00Z",
        )
        self.assertFalse(report["authoritative_current"])
        self.assertEqual(report["lines"][0]["evidence_quality"], "stale_not_current")

    def test_48_watermark_absent_does_not_order_the_broker(self) -> None:
        observed = _observe(_body("600"), chronology="AFTER_CONFIRMATION")
        self.assertIsNone(observed["transaction_watermark"])
        self.assertFalse(observed["broker_order_known"])

    def test_49_profit_protection_unchanged(self) -> None:
        self.assertEqual(HASHES["forex_bot/profit_protection.py"], _sha(ROOT / "forex_bot/profit_protection.py"))

    def test_50_malformed_input_is_unavailable_not_zero(self) -> None:
        report = exposure_report(managed=({"instrument": "", "direction": "BUY", "units": "1"},), quarantined=(), close_rows=(), observation=None)
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["lines"][0]["units"])
        self.assertFalse(report["flat"])

    def test_51_missing_middle_and_final_pages(self) -> None:
        middle = assess_supplied_pages(
            [
                {"index": "1", "trades": [{"instrument": "EUR_USD", "trade_id": "T1"}]},
                {"index": "2", "missing": True, "trades": []},
                {"index": "3", "trades": [{"instrument": "EUR_USD", "trade_id": "T3"}]},
            ]
        )
        final = assess_supplied_pages(
            [
                {"index": "1", "trades": [{"instrument": "EUR_USD", "trade_id": "T1"}]},
                {"index": "2", "missing": True, "trades": []},
            ]
        )
        self.assertEqual(middle["reason"], "missing_page")
        self.assertEqual(final["reason"], "missing_page")
        self.assertNotEqual(middle["completeness"], COMPLETE_VERIFIED)

    def test_52_page_failure_loop_and_unexpected_token(self) -> None:
        self.assertEqual(assess_supplied_pages([{"index": "1", "error": "boom", "trades": []}])["completeness"], FAILED)
        self.assertEqual(assess_supplied_pages([{"index": "1", "loop": True, "trades": []}])["reason"], "pagination_loop")
        self.assertEqual(assess_supplied_pages([{"index": "1", "unexpected_token": True, "trades": []}])["reason"], "unexpected_token")

    def test_53_supplied_pages_never_verified_complete(self) -> None:
        result = assess_supplied_pages(
            [
                {"index": "1", "account": ACCOUNT, "trades": [{"instrument": "EUR_USD", "trade_id": "T1"}]},
                {"index": "2", "account": ACCOUNT, "trades": [{"instrument": "GBP_USD", "trade_id": "T2"}]},
            ]
        )
        self.assertEqual(result["completeness"], UNKNOWN_COMPLETENESS)
        self.assertFalse(result["flat_verified"])

    def test_54_sell_and_jpy_partial_shapes(self) -> None:
        for instrument, direction, side, units in (
            ("EUR_USD", "SELL", "short", "-400"),
            ("USD_JPY", "BUY", "long", "600"),
            ("USD_JPY", "SELL", "short", "-600"),
        ):
            observed = _observe(_body(units, instrument=instrument, side=side))
            self.assertEqual(observed["completeness"], UNKNOWN_COMPLETENESS)
            self.assertEqual(observed["trades"][0]["instrument"], instrument)
            self.assertEqual(observed["trades"][0]["direction"], direction)

    def test_55_active_and_quarantined_together(self) -> None:
        quarantined, closes = _partial_rows()
        report = exposure_report(
            managed=({"instrument": "GBP_USD", "direction": "BUY", "trade_id": "G", "units": "50"},),
            quarantined=quarantined,
            close_rows=closes,
            observation=None,
        )
        categories = {line["category"] for line in report["lines"]}
        self.assertIn(ACTIVE_MANAGEABLE_EXPOSURE, categories)
        self.assertIn(QUARANTINED_JOURNAL_REMAINDER, categories)
        self.assertNotEqual(report["managed_units_by_instrument"], report["quarantined_journal_units_by_instrument"])

    def test_56_stale_owner_report_is_not_current(self) -> None:
        observed = _observe(_body("600"), recovery_epoch=1, process_id=111)
        report = exposure_report(managed=(), quarantined=(), close_rows=(), observation=observed, current_epoch=2)
        self.assertFalse(report["authoritative_current"])
        self.assertEqual(report["broker_requests"], 0)
        self.assertFalse(report["journal_mutated"])


class R86CycleTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        quarantined_positions.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "journal.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)
        self.broker = Broker()
        oanda_client._api = self.broker
        self.exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})

    def tearDown(self) -> None:
        live_safety.assert_new_live_exposure_allowed = self.exposure
        oanda_client._api = None
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        quarantined_positions.clear()
        try:
            self.journal.close()
        except Exception:
            pass
        self.temp.cleanup()
        self.assertFalse(PERMIT.exists())

    def _partial(self) -> None:
        pos = Position(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.1,
            stop_loss=1.05,
            take_profit=1.2,
            open_time=1.0,
            strategy_name="r86",
            rl_state="held",
            execution_kind="live",
            broker_trade_ids="T1",
            position_instance_id="INST-R86",
            position_generation=1,
            profit_protection_exit_pips=40.0,
        )
        positions["EUR_USD"] = pos
        operation = asyncio.run(run_guarded_live_close(pos, reason="r86"))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)

    def _view(self, units: str) -> dict:
        row = active_journal()._conn.execute("SELECT * FROM managed_positions").fetchone()
        return {
            "snapshot": "COMPLETE",
            "trades": [
                {
                    "trade_id": row["trade_id"],
                    "instrument": row["instrument"],
                    "direction": row["direction"],
                    "units": units,
                    "account_binding": row["account_binding"],
                    "provenance": "synthetic",
                }
            ],
        }

    def test_57_operational_cycle_incomplete_snapshot(self) -> None:
        self._partial()
        before = dict(active_journal()._conn.execute("SELECT * FROM close_operations").fetchone())
        reset_startup_recovery_memory()
        startup = execute_startup_sequence({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(startup["state"], "RECOVERY_BLOCKED")
        from forex_bot import bot_loop

        asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        after = dict(active_journal()._conn.execute("SELECT * FROM close_operations").fetchone())
        self.assertEqual(after["confirmation_state"], before["confirmation_state"])
        self.assertEqual(after["remaining_units"], before["remaining_units"])
        self.assertEqual(after["network_permit"], before["network_permit"])
        self.assertNotIn("OrderCreate", self.broker.calls)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        managed = dict(active_journal()._conn.execute("SELECT profit_protection_exit_pips FROM managed_positions").fetchone())
        self.assertEqual(Decimal(managed["profit_protection_exit_pips"]), Decimal("40"))
        report = exposure_report(
            managed=(),
            quarantined=({"instrument": "EUR_USD", "direction": "BUY", "trade_id": "T1", "units": "1000", "original_units": "1000"},),
            close_rows=(dict(after),),
            observation=_observe(None, error="incomplete"),
            current_epoch=1,
        )
        self.assertFalse(report["flat"])
        self.assertEqual(report["broker_requests"], 0)
        self.assertEqual(report["lines"][0]["units"], Decimal("600"))

    def test_58_operational_cycle_conflicting_snapshot(self) -> None:
        self._partial()
        reset_startup_recovery_memory()
        startup = execute_startup_sequence(self._view("1000"))
        self.assertFalse(any(item.get("manageable") for item in startup["decisions"]))
        from forex_bot import bot_loop

        book_before = dict(positions)
        asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        self.assertEqual(set(positions), set(book_before))
        self.assertNotIn("OrderCreate", self.broker.calls)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertFalse(PERMIT.exists())


if __name__ == "__main__":
    unittest.main()
