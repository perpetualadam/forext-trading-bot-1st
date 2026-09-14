"""Approximate portfolio exposure caps (USD-quoted heuristic; best-effort)."""

from __future__ import annotations

import logging
import os
from typing import Any

from forex_bot.positions import positions as posmap

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    v = (os.getenv(name) or "").strip()
    return float(v) if v else default


def _norm_symbol(symbol: str) -> str:
    return (symbol or "").upper().replace("-", "_")


_CCY_USD_FALLBACK = {
    "GBP": 1.35,
    "EUR": 1.17,
    "AUD": 0.65,
    "CAD": 0.73,
    "CHF": 1.12,
    "NZD": 0.60,
    "JPY": 0.0067,
}


def notional_pct_of_nav() -> float:
    """``POSITION_NOTIONAL_PCT_OF_NAV`` — e.g. 0.02 = each / total cap is 2% of NAV."""
    return max(0.0, _env_float("POSITION_NOTIONAL_PCT_OF_NAV", 0.0))


def account_ccy_to_usd(amount: float) -> float:
    """Convert account-currency amount to approx USD using last CCY_USD mid or a fallback."""
    from forex_bot.state import broker_currency, last_mid

    ccy = (broker_currency() or "USD").upper()
    amt = float(amount)
    if ccy in ("USD", ""):
        return amt
    pair = f"{ccy}_USD"
    px = last_mid(pair)
    if px and px > 0:
        return amt * px
    return amt * _CCY_USD_FALLBACK.get(ccy, 1.0)


def units_for_account_notional(symbol: str, price: float, account_notional: float) -> float:
    """Units so face-value ≈ ``account_notional`` in account currency (OANDA unit conventions)."""
    s = (symbol or "").upper().replace("-", "_").replace("/", "_")
    px = abs(float(price))
    target_usd = account_ccy_to_usd(account_notional)
    if target_usd <= 0 or px <= 0:
        return 0.0
    if s.startswith("USD_") and len(s) > 4:
        return target_usd
    return target_usd / px


def configured_max_gross_usd() -> float:
    """
    Max book notional in the same USD heuristic as :func:`approx_gross_usd_notional`.

    If ``POSITION_NOTIONAL_PCT_OF_NAV`` > 0, cap = that fraction of broker NAV (converted to USD).
    Else ``MAX_GROSS_USD_NOTIONAL`` (0 = off).
    """
    pct = notional_pct_of_nav()
    if pct > 0:
        from forex_bot.state import current_equity

        return max(0.0, account_ccy_to_usd(current_equity() * pct))
    return max(0.0, _env_float("MAX_GROSS_USD_NOTIONAL", 0.0))


def approx_gross_usd_notional_for(symbol: str, units: float, price: float) -> float:
    """
    Rough gross notional in USD for a proposed or open position.

    - *USD as quote* (e.g. EUR_USD): ``abs(units) * price`` ≈ notional in quote (USD).
    - *USD as base* (e.g. USD_JPY): ``abs(units)`` treated as USD notional (OANDA convention).
    - Other crosses: same as EUR_USD-style (approximation).
    """
    s = _norm_symbol(symbol)
    u = abs(float(units))
    ep = abs(float(price))
    if s.startswith("USD_") and len(s) > 4:
        return u
    return u * ep


def approx_gross_usd_notional() -> float:
    """Sum of :func:`approx_gross_usd_notional_for` across open positions."""
    total = 0.0
    for sym, p in posmap.items():
        total += approx_gross_usd_notional_for(sym, float(p.units), float(p.entry_price))
    return float(total)


def approx_signed_usd_exposure() -> float:
    """
    Rough net USD delta (signed).

    Buying EUR_USD is long EUR / short USD → negative USD exposure.
    Buying USD_JPY is long USD → positive USD exposure.
    """
    net = 0.0
    for sym, p in posmap.items():
        s = _norm_symbol(sym)
        u = float(p.units) if p.direction == "BUY" else -float(p.units)
        ep = float(p.entry_price)
        if s.endswith("_USD") and not s.startswith("USD_"):
            # Long base / short USD
            net -= u * ep
        elif s.startswith("USD_"):
            net += u
    return float(net)


def exposure_snapshot() -> dict[str, Any]:
    cap = configured_max_gross_usd()
    gross = approx_gross_usd_notional()
    signed = approx_signed_usd_exposure()
    return {
        "gross_usd_notional_approx": round(gross, 2),
        "net_usd_exposure_approx": round(signed, 2),
        "max_gross_usd_notional_cap": cap,
        "notional_pct_of_nav": notional_pct_of_nav(),
        "exposure_cap_breached": cap > 0 and gross > cap,
    }


def would_exceed_cap_if_opening(additional_gross_usd: float) -> bool:
    cap = configured_max_gross_usd()
    if cap <= 0:
        return False
    return approx_gross_usd_notional() + max(0.0, float(additional_gross_usd)) > cap + 1e-6
