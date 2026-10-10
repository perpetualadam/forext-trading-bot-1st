"""Timestamp-aware quote-to-GBP conversion. Does not invent missing rates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GBP_CONVERSION_UNVERIFIED = "GBP_CONVERSION_UNVERIFIED"
UNAVAILABLE = "UNAVAILABLE"

QUOTE_CCY = {
    "EUR_USD": "USD",
    "GBP_USD": "USD",
    "AUD_USD": "USD",
    "USD_JPY": "JPY",
    "USD_CAD": "CAD",
    "USD_CHF": "CHF",
}

USD_CROSS = {
    "JPY": "USD_JPY",
    "CAD": "USD_CAD",
    "CHF": "USD_CHF",
}


def _as_utc(ts: datetime | str) -> datetime:
    if isinstance(ts, str):
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        t = ts
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


@dataclass(frozen=True)
class FxQuote:
    time: datetime
    pair: str
    bid: float
    ask: float
    source: str


@dataclass
class ConversionResult:
    status: str
    gbp: float | None
    path: list[str]
    rate_times: dict[str, str]
    source: str
    reason: str | None


class RateTable:
    """Completed FX quotes usable only at or before the conversion timestamp."""

    def __init__(self, quotes: list[FxQuote] | None = None) -> None:
        self._rows: list[FxQuote] = []
        for q in quotes or []:
            self.add(q)

    def add(self, quote: FxQuote) -> None:
        if quote.bid > quote.ask or quote.bid <= 0 or quote.ask <= 0:
            raise ValueError("invalid fx quote")
        if not math.isfinite(quote.bid) or not math.isfinite(quote.ask):
            raise ValueError("nonfinite fx quote")
        self._rows.append(
            FxQuote(_as_utc(quote.time), quote.pair, float(quote.bid), float(quote.ask), quote.source)
        )
        self._rows.sort(key=lambda r: (r.pair, r.time))

    def last_at_or_before(self, pair: str, when: datetime) -> FxQuote | None:
        limit = _as_utc(when)
        found: FxQuote | None = None
        for row in self._rows:
            if row.pair != pair:
                continue
            if row.time > limit:
                break
            found = row
        return found


def quote_currency(pair: str) -> str | None:
    return QUOTE_CCY.get(pair)


def convert_pnl(
    *,
    pnl_quote: float,
    pair: str,
    when: datetime | str,
    table: RateTable,
    units_comment: str = "quote-currency P&L",
) -> ConversionResult:
    """Convert realised quote-currency P&L to GBP using no-future quotes.

    USD P&L uses GBP_USD ask (USD per GBP) so GBP = USD / ask.
    JPY/CAD/CHF P&L first converts to USD via the USD_xxx ask, then to GBP.
    Missing rates return GBP_CONVERSION_UNVERIFIED. Rates are never invented.
    """
    del units_comment
    ts = _as_utc(when)
    qccy = quote_currency(pair)
    if pair.endswith("_GBP") or qccy == "GBP":
        return ConversionResult("ok", float(pnl_quote), ["quote_is_gbp_identity"], {}, "identity", None)
    if qccy is None:
        return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, [], {}, UNAVAILABLE, "unknown_pair")
    path: list[str] = [f"pnl_in_{qccy}"]
    times: dict[str, str] = {}
    usd = pnl_quote
    if qccy != "USD":
        cross = USD_CROSS.get(qccy)
        if cross is None:
            return ConversionResult(GBP_CONVERSION_UNVERIFIED, None, path, times, UNAVAILABLE, "no_usd_cross")
        fx = table.last_at_or_before(cross, ts)
        if fx is None:
            return ConversionResult(
                GBP_CONVERSION_UNVERIFIED, None, path, times, UNAVAILABLE, f"missing_{cross}"
            )
        usd = pnl_quote / fx.ask
        path.append(f"{qccy}->USD via {cross} ask={fx.ask}")
        times[cross] = fx.time.isoformat()
    gbp_fx = table.last_at_or_before("GBP_USD", ts)
    if gbp_fx is None:
        return ConversionResult(
            GBP_CONVERSION_UNVERIFIED, None, path, times, UNAVAILABLE, "missing_GBP_USD"
        )
    gbp = usd / gbp_fx.ask
    path.append(f"USD->GBP via GBP_USD ask={gbp_fx.ask}")
    times["GBP_USD"] = gbp_fx.time.isoformat()
    return ConversionResult("ok", gbp, path, times, gbp_fx.source, None)


def stage_g_fixed_estimate(pnl_quote: float, pair: str, gbp_usd: float = 1.35) -> ConversionResult:
    """Document the frozen Stage G estimator. Not valid independent conversion."""
    from forex_bot.research.adaptive_ensemble.simulate import quote_to_gbp

    return ConversionResult(
        "STAGE_G_ESTIMATE_NOT_VERIFIED",
        quote_to_gbp(pnl_quote, pair, gbp_usd),
        ["stage_g_fixed_divisor", pair, f"gbp_usd={gbp_usd}"],
        {},
        "ESTIMATE",
        "do_not_use_for_independent_validation",
    )


def fixture_table() -> RateTable:
    t0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    return RateTable(
        [
            FxQuote(t0, "GBP_USD", 1.3490, 1.3500, "synthetic_fixture"),
            FxQuote(t0, "USD_JPY", 149.90, 150.00, "synthetic_fixture"),
            FxQuote(t0, "USD_CAD", 1.3590, 1.3600, "synthetic_fixture"),
            FxQuote(t0, "USD_CHF", 0.7990, 0.8000, "synthetic_fixture"),
        ]
    )


def describe_stage_g_limitation() -> dict[str, Any]:
    return {
        "status": GBP_CONVERSION_UNVERIFIED,
        "stage_g_method": "fixed gbp_usd=1.35 divisor",
        "usd_jpy_stage_g": "incorrect if used: JPY P&L divided by 1.35",
        "historical_rate_series": UNAVAILABLE,
        "independent_validation": "blocked until timestamped conversion quotes exist",
    }
