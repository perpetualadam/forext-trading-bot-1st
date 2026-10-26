"""Real OpenPositions classification and reconciliation under the R.69 harness."""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import reconciliation as rec  # noqa: E402
from forex_bot.broker_exit import reset_broker_exit_state  # noqa: E402
from forex_bot import broker_exit  # noqa: E402
from forex_bot import oanda_client  # noqa: E402
from forex_bot.orders import orders_by_client_id  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    open_position,
    position_management_permitted,
    positions,
)
import forex_bot.config as config_mod  # noqa: E402


CALLS: list[str] = []


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.body: object = {"positions": []}
        self.fail: BaseException | None = None
        self.hold = None
        self.release = None
        self.order = 0

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if name == "OrdersPending":
            return {"orders": []}
        if name == "TradeDetails":
            return {"trade": {"id": "T", "state": "OPEN", "currentUnits": "1"}}
        if name != "OpenPositions":
            raise isolation.IsolationBreach(name)
        if self.hold is not None and self.order == 0:
            self.order = 1
            self.hold.set()
            assert self.release.wait(5)
        if self.fail is not None:
            raise self.fail
        return self.body


def _row(kind: str, **kwargs) -> Position:
    data = dict(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=time.time() - 3600,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind=kind,
        client_order_id="bot-cid" if kind == "live" else "",
        broker_order_id="trade-1" if kind == "live" else "",
        broker_order=kind == "live",
    )
    data.update(kwargs)
    return Position(**data)


def _long(instrument: str, units: str = "1000", price: str = "1.1", ids: list | None = None) -> dict:
    return {
        "instrument": instrument,
        "long": {"units": units, "averagePrice": price, "tradeIDs": ids or []},
        "short": {"units": "0", "averagePrice": "0", "tradeIDs": []},
    }


def _reset() -> None:
    positions.clear()
    broker_observations.clear()
    orders_by_client_id.clear()
    reset_broker_exit_state()
    rec._last_broker_nets.clear()
    rec._last_trade_ids.clear()
    rec._have_broker_snapshot = False
    rec._logged_conflict.clear()
    rec._logged_match.clear()
    rec._logged_paper_preserved.clear()
    rec._snapshot["last_error"] = None
    rec._snapshot["broker_snapshot_class"] = "UNKNOWN"
    rec._last_snapshot_class = "UNKNOWN"
    CALLS.clear()
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["PERSIST_RECONCILE_STATE"] = "0"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["RECONCILE_ACTION"] = "log_only"
    os.environ["RECONCILE_ADJUST_UNITS"] = "false"
    os.environ["RECONCILE_AUTO_FIX_IN_PAPER"] = "false"
    os.environ["RECONCILE_IMPORT_BROKER_POSITIONS"] = "false"


def _arm(api: FakeAPI) -> None:
    oanda_client._api = api
    config_mod.Config.OANDA_ACCOUNT_ID = "001-002-0000001-003"
    config_mod.Config.OANDA_ACCESS_TOKEN = ""


def _run(api: FakeAPI):
    _arm(api)
    return rec.reconcile_positions_log_only()


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()
        self.api = FakeAPI()
        self._real_disappear = broker_exit.account_disappeared_broker_position

        def _wrapped(pos):
            CALLS.append("account_disappeared_broker_position")
            return self._real_disappear(pos)

        broker_exit.account_disappeared_broker_position = _wrapped

    def tearDown(self) -> None:
        broker_exit.account_disappeared_broker_position = self._real_disappear

    def _class(self) -> str:
        return str(rec._snapshot.get("broker_snapshot_class"))

    def test_valid_empty_is_complete_empty(self) -> None:
        self.api.body = {"positions": []}
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_EMPTY")
        self.assertIsNone(rec._snapshot["last_error"])
        self.assertTrue(rec._have_broker_snapshot)
        self.assertEqual(rec._last_broker_nets, {})
        self.assertNotIn("PositionClose", self.api.calls)

    def test_missing_key_is_incomplete_and_preserves_prior(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD")]}
        _run(self.api)
        self.api.body = {}
        _run(self.api)
        self.assertEqual(self._class(), "INCOMPLETE")
        self.assertIn("EUR_USD", rec._last_broker_nets)
        self.assertNotIn("account_disappeared_broker_position", CALLS)

    def test_null_string_and_dict_positions_are_malformed(self) -> None:
        for body in ({"positions": None}, {"positions": "invalid"}, {"positions": {}}):
            _reset()
            self.api = FakeAPI()
            _arm(self.api)
            self.api.body = {"positions": [_long("GBP_USD", "10", "1.2")]}
            _run(self.api)
            self.api.body = body
            _run(self.api)
            self.assertEqual(self._class(), "MALFORMED", body)
            self.assertIn("GBP_USD", rec._last_broker_nets)
            self.assertNotIn("account_disappeared_broker_position", CALLS)

    def test_valid_nonempty_records_observation_only(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.body = {"positions": [_long("EUR_USD", "1000", "1.1", ["900"])]}
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_NONEMPTY")
        self.assertNotIn("EUR_USD", positions)
        obs = broker_observations["EUR_USD"]
        self.assertTrue(obs.observation_only)
        self.assertFalse(position_management_permitted(obs))
        self.assertEqual(obs.broker_trade_ids, "900")

    def test_missing_instrument_rejects_the_whole_body(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD"), {"long": {"units": "1"}, "short": {"units": "0"}}]}
        _run(self.api)
        self.assertEqual(self._class(), "MALFORMED")
        self.assertFalse(rec._have_broker_snapshot)
        self.assertNotIn("EUR_USD", broker_observations)

    def test_missing_side_invalid_units_and_nonfinite(self) -> None:
        cases = [
            {"positions": [{"instrument": "EUR_USD", "long": {"units": "1", "averagePrice": "1.1"}}]},
            {"positions": [_long("EUR_USD", "nope")]},
            {"positions": [_long("EUR_USD", "NaN")]},
            {"positions": [_long("EUR_USD", "Infinity")]},
        ]
        for body in cases:
            _reset()
            self.api = FakeAPI()
            self.api.body = body
            _run(self.api)
            self.assertEqual(self._class(), "MALFORMED", body)
            self.assertFalse(rec._have_broker_snapshot)

    def test_both_sides_are_a_conflict(self) -> None:
        self.api.body = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {"units": "1000", "averagePrice": "1.1", "tradeIDs": ["L"]},
                    "short": {"units": "-400", "averagePrice": "1.11", "tradeIDs": ["S"]},
                }
            ]
        }
        _run(self.api)
        self.assertEqual(self._class(), "CONFLICT")
        self.assertNotIn("EUR_USD", positions)
        self.assertNotIn("EUR_USD", broker_observations)

    def test_multiple_instruments_and_missing_trade_ids(self) -> None:
        self.api.body = {
            "positions": [
                {"instrument": "EUR_USD", "long": {"units": "5", "averagePrice": "1.1"}, "short": {"units": "0", "averagePrice": "0"}},
                {"instrument": "usd/cad", "long": {"units": "0", "averagePrice": "0"}, "short": {"units": "-7", "averagePrice": "1.36"}},
            ]
        }
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_NONEMPTY")
        self.assertEqual(set(broker_observations), {"EUR_USD", "USD_CAD"})
        self.assertEqual(broker_observations["EUR_USD"].broker_trade_ids, "")
        self.assertNotIn("EUR_USD", positions)

    def test_one_malformed_entry_preserves_the_previous_snapshot(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD")]}
        _run(self.api)
        self.api.body = {"positions": [_long("GBP_USD"), {"instrument": "USD_JPY"}]}
        _run(self.api)
        self.assertEqual(self._class(), "MALFORMED")
        self.assertIn("EUR_USD", rec._last_broker_nets)
        self.assertNotIn("GBP_USD", rec._last_broker_nets)

    def test_flat_row_plus_open_row_for_the_same_instrument_is_a_conflict(self) -> None:
        flat = _long("EUR_USD", "0", "0")
        self.api.body = {"positions": [flat, _long("EUR_USD", "20")]}
        _run(self.api)
        self.assertEqual(self._class(), "CONFLICT")
        self.assertFalse(rec._have_broker_snapshot)
        self.assertNotIn("EUR_USD", broker_observations)

    def test_duplicate_instrument_is_a_conflict(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD", "10"), _long("EUR_USD", "20")]}
        _run(self.api)
        self.assertEqual(self._class(), "CONFLICT")
        self.assertFalse(rec._have_broker_snapshot)

    def test_unknown_instrument_stays_an_observation(self) -> None:
        self.api.body = {"positions": [_long("FOO_BAR", "10", "1.0")]}
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_NONEMPTY")
        self.assertNotIn("FOO_BAR", positions)
        self.assertFalse(position_management_permitted(broker_observations["FOO_BAR"]))

    def test_request_exception_and_timeout_and_empty_body(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD")]}
        _run(self.api)
        for failure in (RuntimeError("synthetic"), TimeoutError("synthetic timeout"), None):
            prior = dict(rec._last_broker_nets)
            if failure is None:
                self.api.fail = None
                self.api.body = None
            else:
                self.api.fail = failure
            _run(self.api)
            self.api.fail = None
            self.assertIn(self._class(), {"REQUEST_FAILED", "MALFORMED"})
            self.assertEqual(rec._last_broker_nets, prior)
            self.assertNotIn("account_disappeared_broker_position", CALLS)

    def test_valid_then_incomplete_then_valid_empty_sequence(self) -> None:
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        live = _row("live")
        open_position(live)
        self.api.body = {"positions": [_long("EUR_USD", "1000", "1.1")]}
        _run(self.api)
        self.assertIn("EUR_USD", positions)
        self.api.body = {}
        _run(self.api)
        self.assertEqual(self._class(), "INCOMPLETE")
        self.assertIs(positions["EUR_USD"], live)
        self.assertNotIn("account_disappeared_broker_position", CALLS)
        self.api.body = {"positions": []}
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_EMPTY")
        self.assertNotIn("EUR_USD", positions)
        self.assertIn("account_disappeared_broker_position", CALLS)
        self.assertNotIn("PositionClose", self.api.calls)

    def test_malformed_then_valid_publishes_the_valid_body(self) -> None:
        self.api.body = {"positions": None}
        _run(self.api)
        self.assertFalse(rec._have_broker_snapshot)
        self.api.body = {"positions": [_long("EUR_USD")]}
        _run(self.api)
        self.assertEqual(self._class(), "COMPLETE_NONEMPTY")
        self.assertIn("EUR_USD", broker_observations)
        self.assertNotIn("EUR_USD", positions)

    def test_live_rows_survive_invalid_evidence(self) -> None:
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        os.environ["RECONCILE_ADJUST_UNITS"] = "true"
        for body, failure, label in (
            ({}, None, "INCOMPLETE"),
            ({"positions": "bad"}, None, "MALFORMED"),
            (None, TimeoutError("down"), "REQUEST_FAILED"),
            (
                {
                    "positions": [
                        {
                            "instrument": "EUR_USD",
                            "long": {"units": "1", "averagePrice": "1.1"},
                            "short": {"units": "-1", "averagePrice": "1.1"},
                        }
                    ]
                },
                None,
                "CONFLICT",
            ),
        ):
            _reset()
            os.environ["RECONCILE_ACTION"] = "auto_fix"
            os.environ["RECONCILE_ADJUST_UNITS"] = "true"
            self.api = FakeAPI()
            live = _row("live", units=1000)
            open_position(live)
            self.api.body = {"positions": [_long("EUR_USD", "1000", "1.1")]}
            _run(self.api)
            CALLS.clear()
            self.api.fail = failure
            self.api.body = body
            _run(self.api)
            self.api.fail = None
            self.assertEqual(self._class(), label)
            self.assertIs(positions["EUR_USD"], live)
            self.assertEqual(positions["EUR_USD"].units, 1000)
            self.assertNotIn("account_disappeared_broker_position", CALLS)
            self.assertNotIn("PositionClose", self.api.calls)

    def test_observation_and_paper_survive_invalid_snapshots(self) -> None:
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        paper = _row("window_paper", broker_order=False, units=10)
        open_position(paper)
        positions["GBP_USD"] = _row("reconcile_import", symbol="GBP_USD", observation_only=True, broker_order=True)
        for body in ({}, {"positions": None}, {"positions": "x"}):
            self.api.body = body
            self.api.fail = None
            _run(self.api)
            self.assertIs(positions["EUR_USD"], paper)
            self.assertEqual(paper.units, 10)
            self.assertTrue(positions["GBP_USD"].observation_only)
            self.assertNotIn("account_disappeared_broker_position", CALLS)

    def test_paper_plus_valid_broker_observation(self) -> None:
        paper = _row("paper", broker_order=False, units=10)
        open_position(paper)
        self.api.body = {"positions": [_long("EUR_USD", "9000", "1.2")]}
        _run(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_older_empty_does_not_replace_a_newer_book(self) -> None:
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        live = _row("live")
        open_position(live)
        older = FakeAPI()
        newer = FakeAPI()
        older.body = {"positions": []}
        newer.body = {"positions": [_long("EUR_USD", "1000", "1.1")]}
        older.hold = threading.Event()
        older.release = threading.Event()
        config_mod.Config.OANDA_ACCOUNT_ID = "001-002-0000001-003"

        def run_older() -> None:
            oanda_client._api = older
            rec.reconcile_positions_log_only()

        def run_newer() -> None:
            assert older.hold.wait(5)
            oanda_client._api = newer
            rec.reconcile_positions_log_only()
            older.release.set()

        first = threading.Thread(target=run_older)
        second = threading.Thread(target=run_newer)
        first.start()
        second.start()
        first.join(5)
        second.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertIn("EUR_USD", rec._last_broker_nets)
        self.assertIs(positions.get("EUR_USD"), live)
        self.assertNotIn("PositionClose", older.calls + newer.calls)

    def _overlap(self, older_body, newer_body, older_fail=None) -> None:
        older = FakeAPI()
        newer = FakeAPI()
        older.body = older_body
        newer.body = newer_body
        older.fail = older_fail
        older.hold = threading.Event()
        older.release = threading.Event()
        config_mod.Config.OANDA_ACCOUNT_ID = "001-002-0000001-003"
        errors: list[str] = []

        def run_older() -> None:
            try:
                oanda_client._api = older
                rec.reconcile_positions_log_only()
            except Exception as exc:
                errors.append(type(exc).__name__)

        def run_newer() -> None:
            try:
                assert older.hold.wait(5)
                oanda_client._api = newer
                rec.reconcile_positions_log_only()
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                older.release.set()

        first = threading.Thread(target=run_older)
        second = threading.Thread(target=run_newer)
        first.start()
        second.start()
        first.join(5)
        second.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])

    def test_older_valid_does_not_replace_a_newer_valid_book(self) -> None:
        self._overlap({"positions": [_long("EUR_USD")]}, {"positions": [_long("GBP_USD", "10", "1.2")]})
        self.assertEqual(set(rec._last_broker_nets), {"GBP_USD"})
        self.assertNotIn("EUR_USD", rec._last_broker_nets)

    def test_older_malformed_does_not_clear_a_newer_book(self) -> None:
        self._overlap({"positions": None}, {"positions": [_long("GBP_USD", "10", "1.2")]})
        self.assertIn("GBP_USD", rec._last_broker_nets)

    def test_older_failure_does_not_clear_a_newer_book(self) -> None:
        self._overlap({"positions": []}, {"positions": [_long("GBP_USD", "10", "1.2")]}, RuntimeError("older failed"))
        self.assertIn("GBP_USD", rec._last_broker_nets)

    def test_observation_survives_an_incomplete_replacement(self) -> None:
        self.api.body = {"positions": [_long("EUR_USD")]}
        _run(self.api)
        obs = broker_observations["EUR_USD"]
        self.api.body = {}
        _run(self.api)
        self.assertIs(broker_observations["EUR_USD"], obs)
        self.assertTrue(obs.observation_only)
        self.assertFalse(position_management_permitted(obs))

    def test_missing_client_is_unknown_not_flat(self) -> None:
        prior = dict(rec._last_broker_nets)
        oanda_client._api = None
        config_mod.Config.OANDA_ACCOUNT_ID = ""
        rec.reconcile_positions_log_only()
        self.assertEqual(self._class(), "UNKNOWN")
        self.assertIn("unavailable", str(rec._snapshot["last_error"]))
        self.assertEqual(rec._last_broker_nets, prior)
        self.assertNotIn("account_disappeared_broker_position", CALLS)

    def test_entry_path_text_remains_blocked(self) -> None:
        text = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        self.assertIn('status="blocked"', text)
        self.assertIn('!= "continue_existing_production_broker"', text)

    def test_no_dotenv_or_remote_socket(self) -> None:
        kinds = {item[0] for item in isolation.ATTEMPTS}
        self.assertNotIn("load_dotenv", kinds)
        self.assertNotIn("socket.connect", kinds)


if __name__ == "__main__":
    unittest.main()
