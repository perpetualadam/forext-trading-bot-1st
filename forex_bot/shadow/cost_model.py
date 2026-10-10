"""Versioned shadow cost model. Estimates vs measured fill-mid means.

COST_MODEL_VERSION = shadow_cost_v2
Measured values are mean |fill - submitted mid| from FILLED exec_orders (read-only
historical query, Stage D). They are not bid/ask quotes. Using them as a missing-quote
fallback is conservative versus the 1-pip paper table, not a claim of the true spread.
"""

from __future__ import annotations

import math

from forex_bot.symbols import normalize_oanda_symbol

COST_MODEL_VERSION = "shadow_cost_v2"

# Paper/table half-spreads (price). Estimates.
TABLE_HALF_SPREADS: dict[str, float] = {
    "EUR_USD": 0.0001,
    "GBP_USD": 0.00015,
    "USD_JPY": 0.01,
    "AUD_USD": 0.0001,
    "USD_CAD": 0.0001,
    "USD_CHF": 0.0001,
}

# Mean |fill_price - metadata.mid| on FILLED exec_orders (n≈89–185 per pair).
# Includes spread and some slippage. Labelled MEASURED_FILL_MID_MEAN, not a quote.
MEASURED_ABS_FILL_MINUS_MID: dict[str, float] = {
    "EUR_USD": 0.000147,
    "GBP_USD": 0.000178,
    "USD_JPY": 0.03457,
    "AUD_USD": 0.000158,
    "USD_CAD": 0.000120,
    "USD_CHF": 0.000154,
}

FINANCING_STATUS = "UNAVAILABLE"
OVERNIGHT_HOLDING_STATUS = "UNMODELED"

COST_SCENARIOS: tuple[str, ...] = ("base", "conservative", "severe")


def scenario_slip_multiplier(scenario: str, *, have_quotes: bool) -> float:
    """Base uses quotes only (no extra ATR slip). Missing quotes keep 1.0× ATR slip."""
    name = (scenario or "base").strip().lower()
    if name == "severe":
        return 2.0
    if name == "conservative":
        return 1.0
    return 0.0 if have_quotes else 1.0


def table_half_spread(symbol: str) -> float:
    s = normalize_oanda_symbol(symbol)
    return float(TABLE_HALF_SPREADS.get(s, 0.0001 if "JPY" not in s else 0.01))


def measured_abs_fill_minus_mid(symbol: str) -> float | None:
    s = normalize_oanda_symbol(symbol)
    v = MEASURED_ABS_FILL_MINUS_MID.get(s)
    return float(v) if v is not None else None


def conservative_half_spread(symbol: str) -> float:
    """Missing-quote fallback: max(table, measured |fill-mid|). Never the smaller of the two."""
    table = table_half_spread(symbol)
    measured = measured_abs_fill_minus_mid(symbol)
    if measured is None:
        return table
    return max(table, measured)


def quoted_half_spread(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    try:
        b = float(bid)
        a = float(ask)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0 or a < b:
        return None
    return (a - b) / 2.0


def adverse_offset(
    symbol: str,
    *,
    bid: float | None = None,
    ask: float | None = None,
    atr: float = 0.0,
    slippage_atr_fraction: float = 0.3,
) -> tuple[float, float, str]:
    """Return (spread_component, slippage_component, source)."""
    quoted = quoted_half_spread(bid, ask)
    slip = 0.0 if math.isnan(atr) else max(0.0, float(atr)) * float(slippage_atr_fraction)
    if quoted is not None:
        return float(quoted), float(slip), "quoted_bid_ask"
    return conservative_half_spread(symbol), float(slip), "conservative_fallback_v2"
