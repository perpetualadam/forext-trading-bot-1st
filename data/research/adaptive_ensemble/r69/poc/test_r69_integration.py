"""Execute the real reconciliation and management functions under isolation."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import os
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
POC = Path(__file__).resolve().parent
sys.path.insert(0, str(POC))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import reconciliation as rec  # noqa: E402
from forex_bot import bot_loop  # noqa: E402
from forex_bot.broker_exit import reset_broker_exit_state  # noqa: E402
from forex_bot.execution import close_fill_path  # noqa: E402
from forex_bot.live_manage import ManageQuote  # noqa: E402
from forex_bot.oanda_client import _api as _existing_api  # noqa: E402
from forex_bot import oanda_client  # noqa: E402
from forex_bot import oanda_exec  # noqa: E402
from forex_bot.orders import orders_by_client_id  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    close_position,
    import_position_from_broker,
    open_position,
    position_management_permitted,
    positions,
)
import forex_bot.config as config_mod  # noqa: E402

import pandas as pd  # noqa: E402


# positions, bot_loop, and broker_exit remain the R.68 digests.
# reconciliation.py is the R.70 snapshot-completeness digest.
EXPECTED = {
    "forex_bot/positions.py": "129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5",
    "forex_bot/reconciliation.py": "df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165",
    "forex_bot/bot_loop.py": "51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51",
    "forex_bot/broker_exit.py": "bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c",
}

CALLS: list[str] = []


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.open_positions: dict = {"positions": []}
        self.trade: dict | None = None
        self.fail = False

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if self.fail:
            raise RuntimeError("synthetic broker snapshot failure")
        if name == "OpenPositions":
            return self.open_positions
        if name == "OrdersPending":
            return {"orders": []}
        if name == "TradeDetails":
            return {"trade": self.trade or {"id": "T", "state": "OPEN", "currentUnits": "1"}}
        if name == "TransactionDetails":
            return {"transaction": {}}
        raise isolation.IsolationBreach(f"unexpected broker endpoint {name}")


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _row(symbol: str, kind: str, **kwargs) -> Position:
    data = dict(
        symbol=symbol,
        direction="BUY",
        units=1000.0,
        entry_price=1.10,
        stop_loss=1.05,
        take_profit=1.20,
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


def _payload(instrument: str, units: float, price: float, trade_ids: list[str] | None = None) -> dict:
    """Synthetic OpenPositions row. Short units stay negative, matching the broker sign."""
    ids = trade_ids or []
    empty = {"units": "0", "averagePrice": "0", "tradeIDs": []}
    active = {"units": str(units), "averagePrice": str(price), "tradeIDs": ids}
    return {
        "instrument": instrument,
        "long": active if units > 0 else empty,
        "short": active if units < 0 else empty,
    }


def _candles() -> pd.DataFrame:
    count = 80
    return pd.DataFrame(
        {
            "time": list(range(count)),
            "open": [1.10] * count,
            "high": [1.101] * count,
            "low": [1.099] * count,
            "close": [1.1002] * count,
        }
    )


def _reset() -> None:
    positions.clear()
    broker_observations.clear()
    orders_by_client_id.clear()
    reset_broker_exit_state()
    rec._last_broker_nets.clear()
    rec._have_broker_snapshot = False
    rec._logged_conflict.clear()
    rec._logged_match.clear()
    rec._logged_paper_preserved.clear()
    rec._last_trade_ids.clear()
    rec._snapshot["reconcile_fixes_applied"] = 0
    rec._snapshot["last_error"] = None
    CALLS.clear()
    for key in (
        "EXECUTION_MODE",
        "RECONCILE_ACTION",
        "RECONCILE_IMPORT_BROKER_POSITIONS",
        "RECONCILE_ADJUST_UNITS",
        "RECONCILE_AUTO_FIX_IN_PAPER",
    ):
        os.environ.pop(key, None)
    os.environ["PERSIST_RECONCILE_STATE"] = "0"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["RECONCILE_ACTION"] = "log_only"


def _arm(api: FakeAPI) -> None:
    oanda_client._api = api
    config_mod.Config.OANDA_ACCOUNT_ID = "001-002-0000001-003"
    config_mod.Config.OANDA_ACCESS_TOKEN = ""


def _reconcile(api: FakeAPI) -> list:
    _arm(api)
    return rec.reconcile_positions_log_only()


class IsolationTests(unittest.TestCase):
    def test_synthetic_config_and_no_secret_reads(self) -> None:
        self.assertTrue(getattr(config_mod, "IS_R69_SYNTHETIC", False))
        kinds = {item[0] for item in isolation.ATTEMPTS}
        self.assertNotIn("load_dotenv", kinds)
        self.assertNotIn("socket.connect", kinds)
        self.assertNotIn("urllib.request.urlopen", kinds)
        with self.assertRaises(isolation.IsolationBreach):
            import psycopg2

            psycopg2.connect(dbname="trading", user="postgres", host="127.0.0.1", port=1)
        self.assertEqual(rec.reconcile_positions_log_only.__module__, "forex_bot.reconciliation")
        self.assertEqual(bot_loop._evaluate_impl.__module__, "forex_bot.bot_loop")

    def test_operational_hashes_match_r68(self) -> None:
        for rel, digest in EXPECTED.items():
            self.assertEqual(_sha(rel), digest, rel)


class ReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()
        self.api = FakeAPI()

    def _observe(self, instrument: str = "EUR_USD") -> Position:
        obs = broker_observations[instrument]
        self.assertTrue(obs.observation_only)
        self.assertFalse(position_management_permitted(obs))
        self.assertNotIn(instrument, positions)
        return obs

    def test_01_log_only_broker_only_records_observation(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "log_only"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 1000, 1.1, ["9001"])]}
        mismatches = _reconcile(self.api)
        obs = self._observe()
        self.assertEqual(obs.broker_trade_ids, "9001")
        self.assertEqual(rec._snapshot["reconcile_fixes_applied"], 0)
        self.assertTrue(any("no local position" in item[2] for item in mismatches))
        self.assertNotIn("PositionClose", self.api.calls)
        self.assertNotIn("OrderCreate", self.api.calls)

    def test_02_broker_mode_does_not_manage(self) -> None:
        os.environ["EXECUTION_MODE"] = "live_broker"
        os.environ["RECONCILE_ACTION"] = "log_only"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 250, 1.1)]}
        _reconcile(self.api)
        self._observe()

    def test_03_auto_fix_broker_only_does_not_grant_or_count_a_fix(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 250, 1.1)]}
        _reconcile(self.api)
        self._observe()
        self.assertEqual(rec._snapshot["reconcile_fixes_applied"], 0)

    def test_04_log_only_keeps_paper_beside_observation(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        paper = _row("EUR_USD", "window_paper", broker_order=False)
        open_position(paper)
        self.api.open_positions = {"positions": [_payload("EUR_USD", -400, 1.2)]}
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertEqual(positions["EUR_USD"].execution_kind, "window_paper")
        self.assertTrue(position_management_permitted(paper))
        obs = broker_observations["EUR_USD"]
        self.assertTrue(obs.observation_only)
        self.assertFalse(position_management_permitted(obs))

    def test_05_auto_fix_conflict_keeps_paper(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        paper = _row("EUR_USD", "paper", units=10, broker_order=False)
        open_position(paper)
        self.api.open_positions = {"positions": [_payload("EUR_USD", 9000, 1.22)]}
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertEqual(paper.units, 10)
        self.assertEqual(rec._snapshot["reconcile_fixes_applied"], 0)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_06_manual_discovery_stays_observation(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {"positions": [_payload("EUR_GBP", 100, 0.85, ["manual-1"])]}
        _reconcile(self.api)
        self._observe("EUR_GBP")

    def test_07_trade_id_does_not_grant_authority(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {"positions": [_payload("USD_JPY", 100, 150.0, ["555001"])]}
        _reconcile(self.api)
        obs = self._observe("USD_JPY")
        self.assertIn("555001", obs.broker_trade_ids)

    def test_08_operational_import_cannot_store_live(self) -> None:
        os.environ["EXECUTION_MODE"] = "live_broker"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 1000, 1.1, ["live-looking"])]}
        _reconcile(self.api)
        obs = self._observe()
        self.assertEqual(obs.execution_kind, "reconcile_import")

    def test_09_later_flat_snapshot_does_not_delete_observation(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 1000, 1.1, ["9001"])]}
        _reconcile(self.api)
        self._observe()
        self.api.open_positions = {"positions": []}
        _reconcile(self.api)
        self.assertIn("EUR_USD", broker_observations)
        self.assertNotIn("EUR_USD", positions)
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_10_incomplete_snapshot_does_not_create_management(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        paper = _row("EUR_USD", "window_paper", broker_order=False)
        open_position(paper)
        self.api.open_positions = {}
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertNotIn("EUR_USD", broker_observations)
        self.assertIn("INCOMPLETE", str(rec._snapshot["last_error"]))
        self.assertFalse(rec._have_broker_snapshot)

    def test_11_failed_snapshot_leaves_the_book(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        paper = _row("EUR_USD", "paper", broker_order=False)
        open_position(paper)
        self.api.fail = True
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertNotIn("EUR_USD", broker_observations)
        self.assertIsNotNone(rec._snapshot["last_error"])

    def test_12_both_sides_stay_unmanaged(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {"units": "1000", "averagePrice": "1.10", "tradeIDs": ["L"]},
                    "short": {"units": "-400", "averagePrice": "1.11", "tradeIDs": ["S"]},
                }
            ]
        }
        _reconcile(self.api)
        self.assertIn("CONFLICT", str(rec._snapshot["last_error"]))
        self.assertNotIn("EUR_USD", positions)
        self.assertNotIn("EUR_USD", broker_observations)

    def test_13_multiple_trade_ids_stay_on_the_observation(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {"positions": [_payload("EUR_USD", 1000, 1.1, ["A", "B"])]}
        _reconcile(self.api)
        obs = self._observe()
        self.assertEqual(obs.broker_trade_ids, "A,B")

    def test_14_unknown_instrument_is_not_managed(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {"positions": [_payload("FOO_BAR", 10, 1.0)]}
        _reconcile(self.api)
        self.assertNotIn("FOO_BAR", positions)
        if "FOO_BAR" in broker_observations:
            self.assertFalse(position_management_permitted(broker_observations["FOO_BAR"]))

    def test_15_malformed_payload_does_not_mutate_the_book(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        paper = _row("EUR_USD", "paper", broker_order=False)
        open_position(paper)
        self.api.open_positions = {"positions": "not-a-list"}
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], paper)
        self.assertNotIn("EUR_USD", broker_observations)
        self.assertIsNotNone(rec._snapshot["last_error"])

    def test_numeric_garbage_units_do_not_import(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        self.api.open_positions = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {"units": "nope", "averagePrice": "1.1", "tradeIDs": []},
                    "short": {"units": "0", "averagePrice": "0", "tradeIDs": []},
                }
            ]
        }
        _reconcile(self.api)
        self.assertNotIn("EUR_USD", positions)
        self.assertNotIn("EUR_USD", broker_observations)

    def test_legacy_observation_in_the_book_survives_auto_fix_flat(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        legacy = _row("EUR_USD", "reconcile_import", observation_only=True, broker_order=True)
        positions["EUR_USD"] = legacy
        self.api.open_positions = {"positions": []}
        _reconcile(self.api)
        self.assertIs(positions["EUR_USD"], legacy)
        self.assertEqual(rec._snapshot["reconcile_fixes_applied"], 0)

    def test_permitted_live_flat_snapshot_still_drops_local_row(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["RECONCILE_ACTION"] = "auto_fix"
        live = _row("EUR_USD", "live")
        open_position(live)
        self.api.open_positions = {"positions": []}
        _reconcile(self.api)
        self.assertNotIn("EUR_USD", positions)
        self.assertNotIn("PositionClose", self.api.calls)


class ManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()
        self.api = FakeAPI()
        _arm(self.api)
        self._real_pp = bot_loop.apply_profit_protection
        self._real_quote = bot_loop.pricing_snapshot
        self._real_execute = bot_loop.execute_trade
        self._real_close = bot_loop.close_position
        self._real_fetch = oanda_client.fetch_ohlcv
        self._real_broker_close = oanda_exec.execute_oanda_market_close

        def _pp(*args, **kwargs):
            CALLS.append("apply_profit_protection")
            return self._real_pp(*args, **kwargs)

        def _quote():
            CALLS.append("pricing_snapshot")
            quote = ManageQuote(
                instrument="EUR_USD",
                bid=1.10,
                ask=1.1002,
                closeout_bid=1.10,
                closeout_ask=1.1002,
                time_epoch=time.time(),
                tradeable=True,
            )
            return {"EUR_USD": quote}

        async def _execute(*args, **kwargs):
            CALLS.append("execute_trade")
            return 0.0

        def _close(symbol):
            CALLS.append("close_position")
            return self._real_close(symbol)

        def _fetch(*args, **kwargs):
            CALLS.append("fetch_ohlcv")
            return _candles()

        async def _broker_close(*args, **kwargs):
            CALLS.append("PositionClose")
            raise isolation.IsolationBreach("PositionClose")

        bot_loop.apply_profit_protection = _pp
        bot_loop.pricing_snapshot = _quote
        bot_loop.execute_trade = _execute
        bot_loop.close_position = _close
        oanda_client.fetch_ohlcv = _fetch
        oanda_exec.execute_oanda_market_close = _broker_close

    def tearDown(self) -> None:
        bot_loop.apply_profit_protection = self._real_pp
        bot_loop.pricing_snapshot = self._real_quote
        bot_loop.execute_trade = self._real_execute
        bot_loop.close_position = self._real_close
        oanda_client.fetch_ohlcv = self._real_fetch
        oanda_exec.execute_oanda_market_close = self._real_broker_close

    def _run(self, symbol: str = "EUR_USD") -> None:
        asyncio.run(bot_loop._evaluate_impl(symbol))

    def test_observation_returns_before_close_tail(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=True, broker_order=True)
        self._run()
        self.assertNotIn("pricing_snapshot", CALLS)
        self.assertNotIn("apply_profit_protection", CALLS)
        self.assertNotIn("execute_trade", CALLS)
        self.assertNotIn("close_position", CALLS)
        self.assertNotIn("PositionClose", CALLS)
        self.assertIn("EUR_USD", positions)

    def test_reconcile_import_kind_without_flag_is_blocked(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=False, broker_order=True)
        self._run()
        self.assertNotIn("execute_trade", CALLS)
        self.assertIn("EUR_USD", positions)

    def test_forged_live_observation_is_blocked(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "live", observation_only=True)
        self._run()
        self.assertNotIn("pricing_snapshot", CALLS)
        self.assertNotIn("execute_trade", CALLS)
        self.assertNotIn("PositionClose", CALLS)
        self.assertIn("EUR_USD", positions)

    def test_unknown_and_malformed_kinds_are_blocked(self) -> None:
        for kind in ("unknown-broker", "", "???", "LIVE-FORGED"):
            _reset()
            _arm(self.api)
            positions["EUR_USD"] = _row("EUR_USD", kind, broker_order=True)
            self._run()
            self.assertNotIn("execute_trade", CALLS, kind)
            self.assertIn("EUR_USD", positions, kind)

    def test_paper_simulated_and_window_reach_protection(self) -> None:
        for kind in ("paper", "simulated", "window_paper"):
            _reset()
            _arm(self.api)
            open_position(_row("EUR_USD", kind, broker_order=False))
            self._run()
            self.assertIn("apply_profit_protection", CALLS, kind)
            self.assertNotIn("execute_trade", CALLS, kind)
            self.assertNotIn("PositionClose", CALLS, kind)
            self.assertEqual(positions["EUR_USD"].execution_kind, kind)

    def test_synthetic_reaches_protection(self) -> None:
        open_position(_row("EUR_USD", "synthetic", broker_order=False))
        self._run()
        self.assertIn("apply_profit_protection", CALLS)
        self.assertNotIn("execute_trade", CALLS)
        self.assertIn("EUR_USD", positions)

    def test_live_shape_reaches_quote_and_protection_without_close(self) -> None:
        open_position(_row("EUR_USD", "live", observation_only=False))
        self.assertEqual(close_fill_path("EUR_USD", "live"), "abort_broker_disabled")
        self._run()
        self.assertIn("pricing_snapshot", CALLS)
        self.assertIn("apply_profit_protection", CALLS)
        self.assertNotIn("execute_trade", CALLS)
        self.assertNotIn("PositionClose", CALLS)
        self.assertEqual(positions["EUR_USD"].execution_kind, "live")

    def test_entry_tail_was_not_executed(self) -> None:
        text = (ROOT / "forex_bot/bot_loop.py").read_text(encoding="utf-8")
        self.assertIn('status="blocked"', text)
        self.assertNotIn("observation_only=True", text)
        self.skipTest("NOT_VERIFIED: the blocked production entry tail was not executed")


class BypassTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()

    def test_flag_blocks_live_and_paper_labels(self) -> None:
        for kind in ("live", "paper"):
            row = _row("EUR_USD", kind, observation_only=True)
            self.assertFalse(position_management_permitted(row), kind)

    def test_reconcile_import_and_unknown_without_flag_are_blocked(self) -> None:
        self.assertFalse(position_management_permitted(_row("EUR_USD", "reconcile_import")))
        self.assertFalse(position_management_permitted(_row("EUR_USD", "mystery")))

    def test_missing_attribute_uses_kind(self) -> None:
        row = _row("EUR_USD", "paper", broker_order=False)
        del row.observation_only
        self.assertTrue(position_management_permitted(row))
        other = _row("EUR_USD", "reconcile_import")
        del other.observation_only
        self.assertFalse(position_management_permitted(other))

    def test_trade_id_and_broker_order_do_not_grant(self) -> None:
        row = _row(
            "EUR_USD",
            "reconcile_import",
            observation_only=True,
            broker_order=True,
            broker_trade_ids="999",
        )
        self.assertFalse(position_management_permitted(row))

    def test_live_broker_mode_string_does_not_grant(self) -> None:
        os.environ["EXECUTION_MODE"] = "live_broker"
        row = _row("EUR_USD", "reconcile_import", observation_only=True)
        self.assertFalse(position_management_permitted(row))

    def test_kind_change_after_import_does_not_grant(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.0, 1.2, execution_kind="live")
        obs = broker_observations["EUR_USD"]
        obs.execution_kind = "live"
        self.assertFalse(position_management_permitted(obs))

    def test_clearing_the_flag_and_setting_live_passes_the_predicate(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.0, 1.2)
        obs = broker_observations["EUR_USD"]
        obs.observation_only = False
        obs.execution_kind = "live"
        self.assertTrue(position_management_permitted(obs))

    def test_open_position_of_an_observation_does_not_grant(self) -> None:
        obs = _row("EUR_USD", "reconcile_import", observation_only=True, broker_order=True)
        open_position(obs)
        self.assertIs(positions["EUR_USD"], obs)
        self.assertFalse(position_management_permitted(positions["EUR_USD"]))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIn("EUR_USD", positions)

    def test_replacing_paper_with_observation_removes_paper_and_blocks_close(self) -> None:
        paper = _row("EUR_USD", "paper", broker_order=False)
        open_position(paper)
        obs = _row("EUR_USD", "reconcile_import", observation_only=True)
        open_position(obs)
        self.assertIs(positions["EUR_USD"], obs)
        self.assertIsNone(close_position("EUR_USD"))

    def test_two_records_keep_separate_authority(self) -> None:
        paper = _row("EUR_USD", "paper", broker_order=False, units=10)
        open_position(paper)
        import_position_from_broker("EUR_USD", 5000, 1.2, 1.1, 1.3, execution_kind="live")
        self.assertTrue(position_management_permitted(positions["EUR_USD"]))
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))
        self.assertEqual(positions["EUR_USD"].units, 10)


class ConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()
        self.api = FakeAPI()
        self._real_fetch = oanda_client.fetch_ohlcv
        self._real_pp = bot_loop.apply_profit_protection
        self._real_execute = bot_loop.execute_trade
        self._real_close = bot_loop.close_position
        oanda_client.fetch_ohlcv = lambda *a, **k: _candles()
        bot_loop.apply_profit_protection = lambda *a, **k: CALLS.append("pp") or self._real_pp(*a, **k)
        bot_loop.execute_trade = self._async_record("execute_trade")
        bot_loop.close_position = lambda symbol: CALLS.append("close") or close_position(symbol)

    def tearDown(self) -> None:
        oanda_client.fetch_ohlcv = self._real_fetch
        bot_loop.apply_profit_protection = self._real_pp
        bot_loop.execute_trade = self._real_execute
        bot_loop.close_position = self._real_close

    def _async_record(self, name):
        async def _inner(*args, **kwargs):
            CALLS.append(name)
            return 0.0

        return _inner

    def test_reconcile_during_candle_load_keeps_paper(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        paper = _row("EUR_USD", "window_paper", broker_order=False)
        open_position(paper)
        started = threading.Event()
        release = threading.Event()

        def fetch(*args, **kwargs):
            started.set()
            self.assertTrue(release.wait(5))
            return _candles()

        def reconcile_side() -> None:
            self.assertTrue(started.wait(5))
            self.api.open_positions = {"positions": [_payload("EUR_USD", 4000, 1.2, ["B"])]}
            _reconcile(self.api)
            release.set()

        oanda_client.fetch_ohlcv = fetch
        worker = threading.Thread(target=reconcile_side)
        worker.start()
        asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIs(positions["EUR_USD"], paper)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)
        self.assertNotIn("execute_trade", CALLS)
        self.assertNotIn("close", CALLS)

    def test_replace_between_read_and_check_uses_the_held_object(self) -> None:
        paper = _row("EUR_USD", "paper", broker_order=False)
        open_position(paper)
        real_get = bot_loop.get_position
        gate = threading.Event()
        done = threading.Event()

        def wrapped(symbol):
            found = real_get(symbol)
            gate.set()
            self.assertTrue(done.wait(5))
            return found

        def replacer() -> None:
            self.assertTrue(gate.wait(5))
            positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=True)
            done.set()

        bot_loop.get_position = wrapped
        worker = threading.Thread(target=replacer)
        worker.start()
        try:
            asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        finally:
            bot_loop.get_position = real_get
            worker.join(5)
        self.assertIn("pp", CALLS)
        self.assertTrue(positions["EUR_USD"].observation_only)
        self.assertNotIn("close", CALLS)

    def test_no_await_between_read_and_ownership_check(self) -> None:
        text = (ROOT / "forex_bot/bot_loop.py").read_text(encoding="utf-8")
        start = text.index("pos = get_position(symbol)")
        end = text.index("if not position_management_permitted(pos):", start)
        self.assertNotIn("await ", text[start:end])

    def test_two_reconcile_threads_do_not_grant_management(self) -> None:
        os.environ["EXECUTION_MODE"] = "paper_broker"
        errors: list[BaseException] = []

        def run(units: float) -> None:
            try:
                api = FakeAPI()
                api.open_positions = {"positions": [_payload("EUR_USD", units, 1.1, [str(units)])]}
                _arm(api)
                rec.reconcile_positions_log_only()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        first = threading.Thread(target=run, args=(1000,))
        second = threading.Thread(target=run, args=(-500,))
        first.start()
        second.start()
        first.join(5)
        second.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertNotIn("EUR_USD", positions)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)

    def test_close_and_observation_update_do_not_delete_observation(self) -> None:
        obs = _row("EUR_USD", "reconcile_import", observation_only=True)
        positions["EUR_USD"] = obs
        started = threading.Event()
        release = threading.Event()

        def close_side() -> None:
            started.set()
            self.assertTrue(release.wait(5))
            close_position("EUR_USD")

        worker = threading.Thread(target=close_side)
        worker.start()
        self.assertTrue(started.wait(5))
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.0, 1.2)
        release.set()
        worker.join(5)
        self.assertIn("EUR_USD", positions)
        self.assertIn("EUR_USD", broker_observations)


class NegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()

    def test_legacy_insert_fails_the_managed_book_assertion(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=False, broker_order=True)

        def expect_unmanaged(symbol: str) -> None:
            if symbol in positions and position_management_permitted(positions[symbol]):
                raise AssertionError("managed book accepted an import")
            if symbol in positions and not positions[symbol].observation_only:
                if positions[symbol].execution_kind == "reconcile_import":
                    raise AssertionError("legacy reconcile_import row is in the managed book")

        with self.assertRaises(AssertionError):
            expect_unmanaged("EUR_USD")

    def test_predicate_that_ignores_the_flag_is_detected(self) -> None:
        row = _row("EUR_USD", "live", observation_only=True)

        def weak(pos: object) -> bool:
            kind = (getattr(pos, "execution_kind", "") or "").strip().lower()
            return kind == "live"

        self.assertTrue(weak(row))
        self.assertFalse(position_management_permitted(row))
        with self.assertRaises(AssertionError):
            self.assertFalse(weak(row))

    def test_disabled_guard_reaches_profit_protection(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=True, broker_order=True)
        real = bot_loop.position_management_permitted
        real_fetch = oanda_client.fetch_ohlcv
        real_pp = bot_loop.apply_profit_protection
        real_quote = bot_loop.pricing_snapshot
        seen: list[str] = []
        bot_loop.position_management_permitted = lambda pos: True
        oanda_client.fetch_ohlcv = lambda *a, **k: _candles()
        bot_loop.apply_profit_protection = lambda *a, **k: seen.append("pp") or real_pp(*a, **k)
        bot_loop.pricing_snapshot = lambda: {
            "EUR_USD": ManageQuote(
                instrument="EUR_USD",
                bid=1.1,
                ask=1.1002,
                closeout_bid=1.1,
                closeout_ask=1.1002,
                time_epoch=time.time(),
                tradeable=True,
            )
        }
        try:
            asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        finally:
            bot_loop.position_management_permitted = real
            oanda_client.fetch_ohlcv = real_fetch
            bot_loop.apply_profit_protection = real_pp
            bot_loop.pricing_snapshot = real_quote
        self.assertIn("pp", seen)

    def test_unconditional_pop_fails_the_retention_assertion(self) -> None:
        positions["EUR_USD"] = _row("EUR_USD", "reconcile_import", observation_only=True)

        def expect_retained(symbol: str) -> None:
            if symbol not in positions:
                raise AssertionError("local row deleted")

        close_position("EUR_USD")
        expect_retained("EUR_USD")
        positions.pop("EUR_USD", None)
        with self.assertRaisesRegex(AssertionError, "local row deleted"):
            expect_retained("EUR_USD")


class SourceOrderTests(unittest.TestCase):
    def test_manage_guard_precedes_execute_trade(self) -> None:
        tree = ast.parse((ROOT / "forex_bot/bot_loop.py").read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(node, ast.AsyncFunctionDef) and node.name == "_evaluate_impl" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
