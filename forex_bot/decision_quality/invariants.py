"""BUY/SELL semantic invariants. Research-only; does not reverse live strategies."""

from __future__ import annotations

from typing import Any

from forex_bot.profit_protection import pip_size, unrealized_profit_pips
from forex_bot.trading import sl_tp_distance_for_entry


def side_invariants_ok(
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    *,
    tol: float = 1e-12,
) -> bool:
    """BUY: TP > entry and SL < entry. SELL: TP < entry and SL > entry."""
    d = (side or "").upper().strip()
    e, sl, tp = float(entry), float(stop_loss), float(take_profit)
    if d == "BUY":
        return tp > e + tol and sl < e - tol
    if d == "SELL":
        return tp < e - tol and sl > e + tol
    return False


def assert_side_invariants(side: str, entry: float, stop_loss: float, take_profit: float) -> None:
    if not side_invariants_ok(side, entry, stop_loss, take_profit):
        raise AssertionError(
            f"side invariants failed: {side} entry={entry} SL={stop_loss} TP={take_profit}"
        )


def sl_tp_from_production_distances(symbol: str, side: str, entry: float, atr: float | None) -> tuple[float, float]:
    """Apply production SL/TP distances to an entry (same as bot_loop after fill)."""
    sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr)
    d = (side or "").upper().strip()
    if d == "BUY":
        return float(entry) - float(sl_d), float(entry) + float(tp_d)
    return float(entry) + float(sl_d), float(entry) - float(tp_d)


def signed_pips(symbol: str, side: str, entry: float, price: float) -> float:
    """Positive when price moves in the predicted direction (production pip math)."""
    return float(unrealized_profit_pips(symbol, side, entry, price))


def expected_order_units_sign(side: str) -> int:
    """Documented v20 rule: BUY +1, SELL -1. Tests compare this to production conversion."""
    return 1 if (side or "").upper().strip() == "BUY" else -1


def example_live_trades() -> list[dict[str, Any]]:
    """User-reported live fills. Used only to confirm internal SL/TP consistency."""
    return [
        {
            "symbol": "GBP_USD",
            "strategy": "swing_mean_reversion",
            "side": "SELL",
            "entry": 1.34742,
            "stop_loss": 1.34783,
            "take_profit": 1.34661,
        },
        {
            "symbol": "USD_JPY",
            "strategy": "trend",
            "side": "BUY",
            "entry": 155.133,
            "stop_loss": 155.087,
            "take_profit": 155.225,
        },
    ]


def pip_distance(symbol: str, a: float, b: float) -> float:
    pip = pip_size(symbol)
    if pip <= 0:
        return 0.0
    return abs(float(a) - float(b)) / pip
