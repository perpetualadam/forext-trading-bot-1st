"""Read-only calculations. Does not import forex_bot.config or open a network client."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot.positions import Position, position_management_permitted  # noqa: E402
from forex_bot.profit_protection import (  # noqa: E402
    activation_trigger_pips,
    apply_profit_protection,
    atr_to_pips,
    original_tp_distance_pips,
    pip_size,
    profit_giveback_atr_multiplier,
    profit_giveback_pips,
    profit_protection_atr_period,
    profit_protection_trigger_percent,
    resolve_giveback_pips,
    unrealized_profit_pips,
)
from forex_bot.reconciliation import BrokerSnapshotError, _interpret_open_positions  # noqa: E402
from forex_bot.trading import (  # noqa: E402
    position_sizing,
    sl_tp_price_distances,
    stop_risk_account_ccy,
)


def _pos(symbol: str, direction: str, entry: float, tp: float) -> Position:
    sl = entry - 0.002 if direction == "BUY" else entry + 0.002
    return Position(
        symbol=symbol,
        direction=direction,
        units=1000,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        open_time=1.0,
        strategy_name="audit",
        rl_state="held",
        execution_kind="paper",
    )


class ProfitProtectionAudit(unittest.TestCase):
    def test_defaults_match_the_historical_numbers(self) -> None:
        self.assertEqual(profit_protection_trigger_percent(), 0.67)
        self.assertEqual(profit_protection_atr_period(), 14)
        self.assertEqual(profit_giveback_atr_multiplier(), 0.5)
        self.assertEqual(profit_giveback_pips(), 4.0)

    def test_jpy_and_non_jpy_pip_size(self) -> None:
        self.assertEqual(pip_size("EUR_USD"), 0.0001)
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        self.assertNotEqual(pip_size("USD_JPY"), pip_size("EUR_USD"))

    def test_activation_is_67_percent_of_original_tp_for_both_sides(self) -> None:
        buy = _pos("EUR_USD", "BUY", 1.1000, 1.1030)
        sell = _pos("EUR_USD", "SELL", 1.1000, 1.0970)
        self.assertAlmostEqual(original_tp_distance_pips(buy), 30.0)
        self.assertAlmostEqual(activation_trigger_pips(buy), 20.1)
        self.assertAlmostEqual(original_tp_distance_pips(sell), 30.0)
        self.assertAlmostEqual(activation_trigger_pips(sell), 20.1)
        wrong = unrealized_profit_pips("EUR_USD", "SELL", 1.1000, 1.1020)
        self.assertLess(wrong, 0.0)

    def test_atr_giveback_and_fallback(self) -> None:
        pos = _pos("EUR_USD", "BUY", 1.1000, 1.1030)
        self.assertAlmostEqual(atr_to_pips("EUR_USD", 0.0010), 10.0)
        gb, source = resolve_giveback_pips(pos, atr_price=0.0010)
        self.assertEqual(source, "atr")
        self.assertAlmostEqual(gb, 5.0)
        missing, missing_source = resolve_giveback_pips(pos, atr_price=None)
        self.assertEqual(missing_source, "fallback")
        self.assertAlmostEqual(missing, 4.0)
        jpy = atr_to_pips("USD_JPY", 0.15)
        self.assertAlmostEqual(jpy, 15.0)

    def test_ratchet_does_not_move_backwards(self) -> None:
        pos = _pos("EUR_USD", "BUY", 1.1000, 1.1030)
        first = apply_profit_protection(pos, 1.1025, atr_price=0.0004)
        self.assertTrue(first.active)
        held = pos.profit_protection_exit_pips
        second = apply_profit_protection(pos, 1.1025, atr_price=0.0040)
        self.assertGreaterEqual(second.exit_threshold_pips, held)
        self.assertGreaterEqual(pos.max_profit_pips, first.max_profit_pips)

    def test_observation_is_not_managed(self) -> None:
        pos = _pos("EUR_USD", "BUY", 1.1, 1.2)
        pos.execution_kind = "reconcile_import"
        pos.observation_only = True
        self.assertFalse(position_management_permitted(pos))

    def test_incomplete_snapshot_is_not_empty(self) -> None:
        with self.assertRaises(BrokerSnapshotError) as caught:
            _interpret_open_positions({})
        self.assertEqual(caught.exception.classification, "INCOMPLETE")
        classification, detail, _ids = _interpret_open_positions({"positions": []})
        self.assertEqual(classification, "COMPLETE_EMPTY")
        self.assertEqual(detail, {})

    def test_sizing_examples_are_quote_currency_not_gbp(self) -> None:
        os.environ["POSITION_NOTIONAL_PCT_OF_NAV"] = "0"
        os.environ["POSITION_RISK_PCT"] = "0.01"
        os.environ["POSITION_RISK_PCT_MAX"] = "0.01"
        os.environ["MIN_STOP_DISTANCE_PRICE"] = "0"
        os.environ["USE_ATR_STOPS"] = "false"
        sl, tp = sl_tp_price_distances("EUR_USD")
        self.assertAlmostEqual(sl, 0.0020)
        self.assertAlmostEqual(tp, 0.0040)
        jpy_sl, jpy_tp = sl_tp_price_distances("USD_JPY")
        self.assertAlmostEqual(jpy_sl, 0.20)
        self.assertAlmostEqual(jpy_tp, 0.40)
        eur_risk = stop_risk_account_ccy("EUR_USD", 1.10, 0.0020, 50000)
        self.assertAlmostEqual(eur_risk, 100.0)
        units = position_sizing("EUR_USD", 1.10, 1.0980, 10000.0, risk_pct=0.01)
        self.assertAlmostEqual(units, 50000.0)
        self.assertNotIn("load_dotenv", {item[0] for item in isolation.ATTEMPTS})
        self.assertNotIn("socket.connect", {item[0] for item in isolation.ATTEMPTS})


if __name__ == "__main__":
    unittest.main()
