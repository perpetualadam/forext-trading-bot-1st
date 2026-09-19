"""Offline candidate filters. Each is tested alone against baseline. Not applied live."""

from __future__ import annotations

from typing import Callable

from forex_bot.decision_quality.outcomes import TradeRecord, summarize_closed
from forex_bot.decision_quality.walk_forward import chronological_splits

FilterFn = Callable[[TradeRecord], bool]


def _h1_agree(rec: TradeRecord) -> bool:
    return "aligned_h1" in (rec.snapshot.htf_agreement or "")


def _h4_no_severe_conflict(rec: TradeRecord) -> bool:
    return "against_h4" not in (rec.snapshot.htf_agreement or "")


def _regime_match(rec: TradeRecord) -> bool:
    name = (rec.snapshot.strategy or "").lower()
    regime = rec.snapshot.regime
    if "mean_reversion" in name:
        return regime == "RANGING"
    if "trend" in name or "breakout" in name:
        return regime in ("TRENDING_UP", "TRENDING_DOWN")
    return True


def _adx_trendish(rec: TradeRecord) -> bool:
    adx = rec.snapshot.adx
    name = (rec.snapshot.strategy or "").lower()
    if adx is None:
        return True
    if "mean_reversion" in name:
        return adx < 20
    if "trend" in name:
        return adx >= 20
    return True


def _not_high_vol(rec: TradeRecord) -> bool:
    return rec.snapshot.regime != "HIGH_VOLATILITY" and rec.snapshot.volatility_state != "high"


def _spread_ok(rec: TradeRecord) -> bool:
    x = rec.snapshot.spread_over_atr
    return x is None or x < 0.25


def _session_active(rec: TradeRecord) -> bool:
    return rec.snapshot.session in ("london", "london_ny_overlap")


def _not_late_entry(rec: TradeRecord) -> bool:
    x = rec.snapshot.pre_move_atr
    return x is None or x < 1.5


FILTERS: dict[str, FilterFn] = {
    "h1_direction_agreement": _h1_agree,
    "h4_severe_conflict_avoid": _h4_no_severe_conflict,
    "regime_match": _regime_match,
    "adx_filter": _adx_trendish,
    "volatility_filter": _not_high_vol,
    "spread_atr_filter": _spread_ok,
    "session_london_or_overlap": _session_active,
    "entry_extension_filter": _not_late_entry,
}


def apply_filter(records: list[TradeRecord], fn: FilterFn) -> tuple[list[TradeRecord], list[TradeRecord]]:
    kept = [r for r in records if fn(r)]
    dropped = [r for r in records if not fn(r)]
    return kept, dropped


def experiment_row(name: str, baseline: list[TradeRecord], kept: list[TradeRecord], dropped: list[TradeRecord]) -> dict:
    base = summarize_closed(baseline)
    filt = summarize_closed(kept)
    return {
        "experiment": name,
        "baseline_n": base["trade_count"],
        "retained_n": filt["trade_count"],
        "removed_n": len(dropped),
        "baseline_expectancy_r": base["expectancy_r"],
        "filtered_expectancy_r": filt["expectancy_r"],
        "baseline_profit_factor": base["profit_factor"],
        "filtered_profit_factor": filt["profit_factor"],
        "baseline_win_rate": base["win_rate"],
        "filtered_win_rate": filt["win_rate"],
        "baseline_avg_r": base["expectancy_r"],
        "filtered_avg_r": filt["expectancy_r"],
        "baseline_max_dd_r": base["max_drawdown_r"],
        "filtered_max_dd_r": filt["max_drawdown_r"],
        "sample_size": filt["trade_count"],
    }


def run_filter_experiments(records: list[TradeRecord]) -> list[dict]:
    """Discover on train, score valid + untouched test. Never fit on the full set."""
    splits = chronological_splits(records)
    rows: list[dict] = []
    for name, fn in FILTERS.items():
        for split_name in ("train", "valid", "test"):
            part = splits[split_name]
            kept, dropped = apply_filter(part, fn)
            row = experiment_row(f"{name}:{split_name}", part, kept, dropped)
            row["split"] = split_name
            row["filter"] = name
            rows.append(row)
    return rows
