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
    """``POSITION_NOTIONAL_PCT_OF_NAV`` — per-trade target face value as a fraction of NAV."""
    return max(0.0, _env_float("POSITION_NOTIONAL_PCT_OF_NAV", 0.0))


def portfolio_gross_notional_pct_of_nav() -> float:
    """
    Book-level gross notional cap as a fraction of NAV.

    ``MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV`` when set (including explicit ``0``).
    If unset/blank, inherit ``POSITION_NOTIONAL_PCT_OF_NAV`` so existing 2% books stay 2%.
    """
    raw = os.getenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV")
    if raw is None or not str(raw).strip():
        return notional_pct_of_nav()
    try:
        return max(0.0, float(str(raw).strip()))
    except ValueError:
        return notional_pct_of_nav()


def portfolio_gross_pct_is_inherited() -> bool:
    raw = os.getenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV")
    return raw is None or not str(raw).strip()


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
    Max **portfolio** gross USD notional (same heuristic as :func:`approx_gross_usd_notional`).

    If the resolved portfolio % (explicit or inherited) is > 0:
    ``account_ccy_to_usd(NAV * portfolio_pct)``.
    Else ``MAX_GROSS_USD_NOTIONAL`` (0 = check off).
    """
    pct = portfolio_gross_notional_pct_of_nav()
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


def existing_gross_usd_by_symbol() -> dict[str, float]:
    """Per-symbol USD notional currently counted toward the book cap (open locals only)."""
    out: dict[str, float] = {}
    for sym, p in posmap.items():
        out[str(sym)] = approx_gross_usd_notional_for(sym, float(p.units), float(p.entry_price))
    return out


def exposure_snapshot() -> dict[str, Any]:
    cap = configured_max_gross_usd()
    gross = approx_gross_usd_notional()
    signed = approx_signed_usd_exposure()
    return {
        "gross_usd_notional_approx": round(gross, 2),
        "net_usd_exposure_approx": round(signed, 2),
        "max_gross_usd_notional_cap": cap,
        "notional_pct_of_nav": notional_pct_of_nav(),
        "portfolio_gross_notional_pct_of_nav": portfolio_gross_notional_pct_of_nav(),
        "portfolio_gross_pct_inherited": portfolio_gross_pct_is_inherited(),
        "exposure_cap_breached": cap > 0 and gross > cap,
    }


def notional_cap_decision(additional_gross_usd: float) -> dict[str, Any]:
    """
    Book-level gross USD notional check.

    Compares ``existing open locals + proposed add`` to :func:`configured_max_gross_usd`.
    Pending orders, margin, and cash are **not** in this sum. Cap 0 means the check is off.
    Equal-to-cap is allowed; only ``resulting > cap`` skips.
    """
    by_symbol = existing_gross_usd_by_symbol()
    existing = float(sum(by_symbol.values()))
    proposed = max(0.0, float(additional_gross_usd))
    resulting = existing + proposed
    cap = configured_max_gross_usd()
    exceeds = cap > 0 and resulting > cap + 1e-6
    return {
        "existing_gross_usd": existing,
        "existing_by_symbol": by_symbol,
        "proposed_add_usd": proposed,
        "resulting_gross_usd": resulting,
        "cap_usd": cap,
        "exceeds": exceeds,
        "cap_enabled": cap > 0,
        "position_notional_pct": notional_pct_of_nav(),
        "portfolio_gross_pct": portfolio_gross_notional_pct_of_nav(),
        "portfolio_gross_pct_inherited": portfolio_gross_pct_is_inherited(),
    }


def format_notional_cap_report(
    symbol: str,
    decision: dict[str, Any],
    *,
    nav: float | None = None,
    currency: str = "",
    allowed: bool,
    direction: str = "",
) -> str:
    """Full existing + proposed vs portfolio cap (skip alert or pass debug)."""
    by = decision.get("existing_by_symbol") or {}
    if by:
        parts = ", ".join(f"{s} {v:.2f}" for s, v in sorted(by.items()))
        per_symbol = f"[{parts}]"
    else:
        per_symbol = "[]"
    existing = float(decision["existing_gross_usd"])
    proposed = float(decision["proposed_add_usd"])
    resulting = float(decision["resulting_gross_usd"])
    cap = float(decision["cap_usd"])
    pct = float(decision.get("portfolio_gross_pct") or 0.0)
    inherit = " (inherited from POSITION_NOTIONAL_PCT_OF_NAV)" if decision.get(
        "portfolio_gross_pct_inherited"
    ) else ""
    nav_line = (
        f"Account NAV: {float(nav):.2f} {currency}"
        if nav is not None and currency
        else "Account NAV: (unknown)"
    )
    side = (direction or "").upper().strip()
    candidate = f"{symbol} {side}".strip()
    verb = "ALLOW because" if allowed else "SKIP because"
    cmp = "<=" if allowed else ">"
    headline = (
        f"{candidate}: notional cap check passed"
        if allowed
        else f"{candidate}: Skip open — notional cap"
    )
    reason = (
        "resulting gross is within configured portfolio cap"
        if allowed
        else "resulting gross exposure exceeds configured portfolio cap"
    )
    extra = "" if allowed else f"Rejection reason: {reason}\n"
    return (
        f"{headline}\n"
        f"Candidate symbol: {symbol}\n"
        f"Candidate side: {side or '(unspecified)'}\n"
        f"Existing counted gross exposure: {existing:.2f} USD\n"
        f"Per-symbol existing exposure: {per_symbol}\n"
        f"Proposed additional exposure: {proposed:.2f} USD\n"
        f"Resulting gross exposure: {resulting:.2f} USD\n"
        f"Maximum portfolio gross exposure: {cap:.2f} USD\n"
        f"Portfolio limit: {pct * 100:.2f}% of NAV{inherit}\n"
        f"{nav_line}\n"
        f"{extra}"
        f"Decision: {verb} {resulting:.2f} {cmp} {cap:.2f} "
        f"(open-position face value, not cash/margin; pending orders not counted)"
    )


def format_notional_cap_skip_alert(
    symbol: str,
    decision: dict[str, Any],
    *,
    nav: float | None = None,
    currency: str = "",
    direction: str = "",
) -> str:
    return format_notional_cap_report(
        symbol, decision, nav=nav, currency=currency, allowed=False, direction=direction
    )


def would_exceed_cap_if_opening(additional_gross_usd: float) -> bool:
    return bool(notional_cap_decision(additional_gross_usd)["exceeds"])
