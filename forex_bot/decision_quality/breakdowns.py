"""Grouped performance tables. Sample size is always first-class."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from forex_bot.decision_quality.outcomes import TradeRecord, summarize_closed


def group_by(records: list[TradeRecord], key_fn: Callable[[TradeRecord], str]) -> list[dict[str, Any]]:
    buckets: dict[str, list[TradeRecord]] = defaultdict(list)
    for rec in records:
        buckets[str(key_fn(rec))].append(rec)
    rows: list[dict[str, Any]] = []
    for key in sorted(buckets):
        summary = summarize_closed(buckets[key])
        summary["group"] = key
        summary["sample_size"] = summary["trade_count"]
        rows.append(summary)
    return rows


def performance_breakdowns(records: list[TradeRecord]) -> dict[str, list[dict[str, Any]]]:
    return {
        "symbol": group_by(records, lambda t: t.snapshot.symbol),
        "strategy": group_by(records, lambda t: t.snapshot.strategy or "unknown"),
        "horizon": group_by(records, lambda t: t.snapshot.horizon or "unknown"),
        "direction": group_by(records, lambda t: t.snapshot.side or "none"),
        "session": group_by(records, lambda t: t.snapshot.session or "unknown"),
        "regime": group_by(records, lambda t: t.snapshot.regime or "unknown"),
        "day_of_week": group_by(records, lambda t: str(t.snapshot.day_of_week)),
        "hour_london": group_by(records, lambda t: str(t.snapshot.hour_london)),
        "htf": group_by(records, lambda t: t.snapshot.htf_agreement or "unknown"),
        "volatility": group_by(records, lambda t: t.snapshot.volatility_state or "unknown"),
        "spread_bucket": group_by(records, _spread_bucket),
    }


def _spread_bucket(rec: TradeRecord) -> str:
    x = rec.snapshot.spread_over_atr
    if x is None:
        return "unknown"
    if x < 0.10:
        return "spread_atr_lt_0.10"
    if x < 0.25:
        return "spread_atr_0.10_0.25"
    return "spread_atr_gte_0.25"


def directional_accuracy(records: list[TradeRecord]) -> dict[str, Any]:
    """Hit rate of signed forward close returns — not profitability."""
    out: dict[str, Any] = {}
    for minutes in (5, 15, 30, 60):
        hits: list[float] = []
        vals: list[float] = []
        for rec in records:
            hit = rec.forward.get(f"{minutes}m_hit")
            pips = rec.forward.get(f"{minutes}m_pips")
            if hit is None or pips is None:
                continue
            hits.append(1.0 if hit else 0.0)
            vals.append(float(pips))
        n = len(vals)
        if n == 0:
            out[f"{minutes}m"] = {"sample_size": 0}
            continue
        series = pd_series(vals)
        out[f"{minutes}m"] = {
            "sample_size": n,
            "hit_rate": sum(hits) / n,
            "mean_signed_pips": sum(vals) / n,
            "median_signed_pips": float(series.median()),
        }
    return out


def pd_series(vals: list[float]):
    import pandas as pd

    return pd.Series(vals)
