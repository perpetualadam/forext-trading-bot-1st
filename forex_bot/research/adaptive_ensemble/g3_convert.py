"""Side-aware quote-to-GBP conversion for Stage G.3. Does not alter Stage G estimates."""

from __future__ import annotations

from datetime import datetime, timedelta

from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    ConversionResult,
    FxQuote,
    RateTable,
    quote_currency,
)

FRESH_HOURS = 24.0


def _leg(amount: float, quote: FxQuote) -> tuple[float, str]:
    """Convert amount of the quote currency of `quote.pair` into the base currency.

    Positive amount buys the base at the ask. Negative amount covers the debit by
    selling the base at the bid, which increases the loss magnitude.
    """
    if amount >= 0:
        return amount / quote.ask, "ask"
    return amount / quote.bid, "bid"


def _weekend_gap(prev: datetime, when: datetime) -> bool:
    span_h = (when - prev).total_seconds() / 3600.0
    return 24 < span_h <= 72 and prev.weekday() >= 4


def convert_signed(
    *,
    pnl_quote: float,
    pair: str,
    when: datetime,
    table: RateTable,
) -> ConversionResult:
    if pair.endswith("_GBP"):
        return ConversionResult("ok", float(pnl_quote), ["quote_is_gbp_identity"], {}, "identity", None)
    qccy = quote_currency(pair)
    if qccy is None:
        return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, [], {}, "UNAVAILABLE", "unknown_pair")
    path = [f"pnl_in_{qccy}"]
    times: dict[str, str] = {}
    amount = float(pnl_quote)
    if qccy != "USD":
        cross = {"JPY": "USD_JPY", "CAD": "USD_CAD", "CHF": "USD_CHF"}.get(qccy)
        if cross is None:
            return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, path, times, "UNAVAILABLE", "no_usd_cross")
        fx = table.last_at_or_before(cross, when)
        if fx is None:
            return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, path, times, "UNAVAILABLE", f"missing_{cross}")
        amount, side = _leg(amount, fx)
        path.append(f"{qccy}->USD via {cross} {side}")
        times[cross] = fx.time.isoformat()
    gbp_fx = table.last_at_or_before("GBP_USD", when)
    if gbp_fx is None:
        return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, path, times, "UNAVAILABLE", "missing_GBP_USD")
    age_h = (when - gbp_fx.time).total_seconds() / 3600.0
    if age_h > FRESH_HOURS and not _weekend_gap(gbp_fx.time, when):
        return ConversionResult("CONVERSION_STALE", None, path, times, gbp_fx.source, "stale_GBP_USD")
    gbp, side = _leg(amount, gbp_fx)
    path.append(f"USD->GBP via GBP_USD {side}")
    times["GBP_USD"] = gbp_fx.time.isoformat()
    note = "weekend_last_quote" if age_h > FRESH_HOURS else None
    return ConversionResult("ok", gbp, path, times, gbp_fx.source, note)


def freshness_example() -> timedelta:
    return timedelta(hours=FRESH_HOURS)
