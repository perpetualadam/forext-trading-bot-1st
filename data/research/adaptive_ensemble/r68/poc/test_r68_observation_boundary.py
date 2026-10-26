"""Offline ownership boundary for R.68.

Imports forex_bot.positions and forex_bot.execution only. Those modules do not
load dotenv. Reconciliation, bot_loop, app, trading, and config are read as
source text and are not imported.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    close_local_position,
    close_position,
    import_position_from_broker,
    open_position,
    position_management_permitted,
    positions,
    adjust_position_units_to_broker,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _row(symbol: str, kind: str, **kwargs) -> Position:
    base = dict(
        symbol=symbol,
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.08,
        take_profit=1.14,
        open_time=1.0,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind=kind,
    )
    base.update(kwargs)
    return Position(**base)


class ObservationBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        positions.clear()
        broker_observations.clear()

    def test_config_not_loaded(self) -> None:
        self.assertNotIn("forex_bot.config", sys.modules)
        self.assertNotIn("dotenv", sys.modules)

    def test_01_log_only_import_does_not_enter_managed_book(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.08, 1.14)
        self.assertNotIn("EUR_USD", positions)
        self.assertIn("EUR_USD", broker_observations)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_02_broker_mode_argument_does_not_grant_management(self) -> None:
        import_position_from_broker(
            "EUR_USD",
            1000,
            1.1,
            1.08,
            1.14,
            execution_kind="live",
        )
        obs = broker_observations["EUR_USD"]
        self.assertEqual(obs.execution_kind, "reconcile_import")
        self.assertTrue(obs.observation_only)
        self.assertNotIn("EUR_USD", positions)

    def test_03_auto_fix_source_skips_non_permitted_rows(self) -> None:
        text = _read("forex_bot/reconciliation.py")
        guard = text.index("if not posmod.position_management_permitted(pos):")
        disappear = text.index("account_disappeared_broker_position(pos)", guard)
        self.assertLess(guard, disappear)
        self.assertNotIn("displace_paper_position", text)

    def test_04_execution_kind_does_not_create_ownership(self) -> None:
        import_position_from_broker(
            "GBP_USD",
            -500,
            1.25,
            1.27,
            1.23,
            execution_kind="live",
        )
        obs = broker_observations["GBP_USD"]
        obs.execution_kind = "live"
        self.assertFalse(position_management_permitted(obs))

    def test_05_trade_id_does_not_grant_authority(self) -> None:
        import_position_from_broker(
            "USD_JPY",
            100,
            150.0,
            149.0,
            151.0,
            broker_trade_ids="999001",
            broker_order_id="999001",
        )
        obs = broker_observations["USD_JPY"]
        self.assertEqual(obs.broker_trade_ids, "999001")
        self.assertFalse(position_management_permitted(obs))

    def test_06_local_row_does_not_grant_authority(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.08, 1.14)
        positions["EUR_USD"] = broker_observations["EUR_USD"]
        self.assertIsNotNone(positions.get("EUR_USD"))
        self.assertFalse(position_management_permitted(positions["EUR_USD"]))

    def test_07_unknown_provenance_fails_closed(self) -> None:
        row = _row("EUR_USD", "unknown-broker")
        positions["EUR_USD"] = row
        self.assertFalse(position_management_permitted(row))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIn("EUR_USD", positions)

    def test_08_and_09_manage_source_returns_before_close(self) -> None:
        text = _read("forex_bot/bot_loop.py")
        guard = text.index("if not position_management_permitted(pos):")
        window = text[guard : guard + 2500]
        self.assertIn("return", window)
        block = text[guard : guard + 500]
        self.assertIn("return", block)
        self.assertNotIn("execute_trade(", block)
        self.assertNotIn("close_position(", block)
        self.assertNotIn("PositionClose(", block)

    def test_10_and_11_observation_is_not_locally_deleted(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.08, 1.14)
        positions["EUR_USD"] = broker_observations["EUR_USD"]
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIsNone(close_local_position("EUR_USD", reason="weekend_flatten"))
        self.assertIsNone(close_local_position("EUR_USD", reason="profit_protection"))
        self.assertEqual(positions["EUR_USD"].units, 1000.0)

    def test_12_observation_is_not_promoted_to_live(self) -> None:
        import_position_from_broker(
            "EUR_USD",
            1000,
            1.1,
            1.08,
            1.14,
            execution_kind="live",
        )
        self.assertEqual(broker_observations["EUR_USD"].execution_kind, "reconcile_import")
        self.assertNotEqual(broker_observations["EUR_USD"].execution_kind, "live")

    def test_13_manual_broker_observation_stays_out_of_the_book(self) -> None:
        import_position_from_broker("EUR_GBP", 250, 0.85, 0.84, 0.86)
        self.assertNotIn("EUR_GBP", positions)
        self.assertIsNone(close_position("EUR_GBP"))

    def test_14_observation_remains_visible(self) -> None:
        import_position_from_broker("AUD_USD", 10, 0.65, 0.64, 0.66)
        seen = broker_observations.get("AUD_USD")
        self.assertIsNotNone(seen)
        assert seen is not None
        self.assertTrue(seen.observation_only)
        self.assertEqual(seen.strategy_name, "reconcile_import")

    def test_15_bot_created_row_stays_manageable(self) -> None:
        bot = _row(
            "EUR_USD",
            "live",
            client_order_id="bot-cid-1",
            broker_order=True,
            observation_only=False,
        )
        open_position(bot)
        self.assertTrue(position_management_permitted(positions["EUR_USD"]))
        removed = close_position("EUR_USD")
        self.assertIs(removed, bot)
        self.assertNotIn("EUR_USD", positions)

    def test_16_paper_row_stays_manageable(self) -> None:
        for kind in ("paper", "simulated", "window_paper"):
            positions.clear()
            paper = _row("EUR_USD", kind, broker_order=False)
            open_position(paper)
            self.assertTrue(position_management_permitted(positions["EUR_USD"]))
            self.assertIs(close_position("EUR_USD"), paper)

    def test_17_and_18_stop_quote_and_profit_files_unchanged(self) -> None:
        prefixes = {
            "forex_bot/trading.py": "5ac39816",
            "forex_bot/live_manage.py": "60d87b86",
            "forex_bot/profit_protection.py": "d57dfce0",
            "forex_bot/execution.py": "6602e363",
            "forex_bot/oanda_exec.py": "f4beb250",
        }
        for rel, prefix in prefixes.items():
            digest = _sha256(ROOT / rel)
            self.assertTrue(digest.startswith(prefix), f"{rel} {digest}")

    def test_19_new_entry_status_remains_blocked(self) -> None:
        text = _read("forex_bot/bot_loop.py")
        self.assertIn("production_path_has_no_simulation_context", text)
        self.assertIn('status="blocked"', text)
        tree = ast.parse(text)
        parents: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        uses = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "continue_existing_production_broker":
                uses.append(parents.get(id(node)))
        self.assertEqual(len(uses), 1)
        self.assertIsInstance(uses[0], ast.Compare)

    def test_20_no_new_position_close_call_in_changed_sources(self) -> None:
        for rel in (
            "forex_bot/positions.py",
            "forex_bot/reconciliation.py",
            "forex_bot/broker_exit.py",
        ):
            body = _read(rel)
            self.assertNotIn("PositionClose(", body)
            self.assertNotIn("OrderCreate(", body)
            self.assertNotIn("TradeClose(", body)

    def test_21_import_then_weekend_delete_refused(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.08, 1.14)
        positions["EUR_USD"] = broker_observations["EUR_USD"]
        self.assertFalse(position_management_permitted(positions["EUR_USD"]))
        self.assertIsNone(close_local_position("EUR_USD", reason="weekend_flatten"))
        self.assertIn("EUR_USD", positions)

    def test_22_import_then_profit_protection_delete_refused(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.08, 1.14)
        positions["EUR_USD"] = broker_observations["EUR_USD"]
        self.assertIsNone(close_local_position("EUR_USD", reason="profit_protection"))
        self.assertIn("EUR_USD", positions)

    def test_23_sequential_reference_keeps_paper(self) -> None:
        paper = _row("EUR_USD", "window_paper")
        open_position(paper)
        held = positions["EUR_USD"]
        import_position_from_broker("EUR_USD", 4000, 1.2, 1.1, 1.3)
        self.assertIs(positions["EUR_USD"], held)
        self.assertEqual(held.execution_kind, "window_paper")
        self.assertTrue(position_management_permitted(held))
        self.assertTrue(broker_observations["EUR_USD"].observation_only)

    def test_23_concurrent_interleaving_not_verified(self) -> None:
        self.skipTest(
            "NOT_VERIFIED: two live tasks sharing the RAM book were not executed"
        )

    def test_24_legacy_observation_row_is_not_deleted(self) -> None:
        legacy = _row("EUR_USD", "reconcile_import", observation_only=True, broker_order=True)
        positions["EUR_USD"] = legacy
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIs(positions["EUR_USD"], legacy)

    def test_25_forged_live_on_imported_row_does_not_grant(self) -> None:
        legacy = _row(
            "EUR_USD",
            "live",
            observation_only=True,
            broker_order=True,
            broker_trade_ids="555",
        )
        positions["EUR_USD"] = legacy
        self.assertFalse(position_management_permitted(legacy))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIn("EUR_USD", positions)

    def test_26_stale_observation_is_not_resized(self) -> None:
        legacy = _row("EUR_USD", "reconcile_import", observation_only=True, units=1000.0)
        positions["EUR_USD"] = legacy
        self.assertFalse(adjust_position_units_to_broker("EUR_USD", 250.0))
        self.assertEqual(positions["EUR_USD"].units, 1000.0)

    def test_27_paper_and_broker_observation_for_same_instrument(self) -> None:
        paper = _row("EUR_USD", "paper", units=100.0, entry_price=1.1111)
        open_position(paper)
        import_position_from_broker("EUR_USD", 9000, 1.2222, 1.2, 1.3, execution_kind="live")
        self.assertIs(positions["EUR_USD"], paper)
        self.assertEqual(positions["EUR_USD"].units, 100.0)
        self.assertEqual(positions["EUR_USD"].entry_price, 1.1111)
        self.assertTrue(position_management_permitted(paper))
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_28_malformed_provenance_fails_closed(self) -> None:
        for kind in ("", " ", "???", "reconcile-import", "LIVE-FORGED", None):
            positions.clear()
            row = _row("EUR_USD", kind if kind is not None else "")
            if kind is None:
                row.execution_kind = None  # type: ignore[assignment]
            positions["EUR_USD"] = row
            self.assertFalse(position_management_permitted(row), kind)
            self.assertIsNone(close_position("EUR_USD"))
            self.assertIn("EUR_USD", positions)

    def test_synthetic_recorder_kind_stays_manageable(self) -> None:
        row = _row("EUR_USD", "synthetic")
        open_position(row)
        self.assertTrue(position_management_permitted(row))

    def test_bot_loop_and_exit_sources_parse(self) -> None:
        for rel in (
            "forex_bot/positions.py",
            "forex_bot/bot_loop.py",
            "forex_bot/reconciliation.py",
            "forex_bot/broker_exit.py",
        ):
            ast.parse(_read(rel))

    def test_disappear_path_refuses_observation_before_pop(self) -> None:
        text = _read("forex_bot/broker_exit.py")
        guard = text.index("if resident is not None and not position_management_permitted(resident):")
        pop = text.index("posmap.pop(sym, None)", guard)
        self.assertLess(guard, pop)
        self.assertIn('return "observation"', text[guard:pop])

    def test_case_c_does_not_count_a_managed_import(self) -> None:
        text = _read("forex_bot/reconciliation.py")
        observe = text.index("Case C: observe only")
        self.assertNotIn("fixes += 1", text[observe : observe + 400])
        self.assertIn("_import_broker_truth", text[observe : observe + 400])


if __name__ == "__main__":
    unittest.main()
