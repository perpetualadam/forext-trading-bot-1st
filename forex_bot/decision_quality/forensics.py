"""Losing-trade classification with documented, deterministic rules. Not causal proof."""

from __future__ import annotations

from typing import Any

from forex_bot.decision_quality.outcomes import TradeRecord, summarize_closed

LOSS_CATEGORIES = (
    "possible_stop_too_tight",
    "possible_late_entry",
    "higher_timeframe_conflict",
    "mean_reversion_vs_trend_conflict",
    "high_spread_noise",
    "direction_failure",
    "unclear",
)


def classify_loss(rec: TradeRecord) -> str:
    """First matching rule wins. Criteria are explicit and research-only."""
    if rec.realised_r is None or rec.realised_r > 0:
        return "not_a_loss"
    post = rec.post_stop
    if rec.exit_reason in ("sl", "ambiguous_sl_tp"):
        if post.get("reached_original_tp") or post.get("plus_1r"):
            return "possible_stop_too_tight"
    if rec.snapshot.pre_move_atr is not None and rec.snapshot.pre_move_atr >= 1.5:
        return "possible_late_entry"
    align = rec.snapshot.htf_agreement or ""
    if "against_h1" in align or "against_h4" in align:
        return "higher_timeframe_conflict"
    name = (rec.snapshot.strategy or "").lower()
    regime = rec.snapshot.regime
    if "mean_reversion" in name and regime in ("TRENDING_UP", "TRENDING_DOWN"):
        fade_vs_trend = (
            (rec.snapshot.side == "SELL" and regime == "TRENDING_UP")
            or (rec.snapshot.side == "BUY" and regime == "TRENDING_DOWN")
        )
        if fade_vs_trend:
            return "mean_reversion_vs_trend_conflict"
    spread = rec.snapshot.spread_over_atr
    if spread is not None and spread >= 0.30:
        return "high_spread_noise"
    if rec.exit_reason in ("sl", "ambiguous_sl_tp") and not post.get("moved_original_direction"):
        return "direction_failure"
    return "unclear"


def losing_trade_rows(records: list[TradeRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in records:
        if rec.realised_r is None or rec.realised_r > 0:
            continue
        snap = rec.snapshot
        rows.append(
            {
                "symbol": snap.symbol,
                "timestamp": snap.timestamp.isoformat(),
                "side": snap.side,
                "strategy": snap.strategy,
                "entry": snap.entry_price,
                "sl": snap.stop_loss,
                "tp": snap.take_profit,
                "result_r": rec.realised_r,
                "atr": snap.atr,
                "sl_over_atr": rec.sl_over_atr,
                "mfe_pips": rec.mfe_pips,
                "mae_pips": rec.mae_pips,
                "mfe_r": rec.mfe_r,
                "mae_r": rec.mae_r,
                "h1": snap.h1_trend,
                "h4": snap.h4_trend,
                "regime": snap.regime,
                "session": snap.session,
                "reason_codes": "|".join(snap.reason_codes),
                "pre_move_atr": snap.pre_move_atr,
                "post_sl_reached_tp": rec.post_stop.get("reached_original_tp"),
                "category": classify_loss(rec),
            }
        )
    return rows


def feature_value_rows(records: list[TradeRecord]) -> list[dict[str, Any]]:
    """Compare expectancy when a condition strongly supports / weakly supports / conflicts."""
    rows: list[dict[str, Any]] = []

    def bucket_htf(rec: TradeRecord) -> str:
        a = rec.snapshot.htf_agreement or ""
        if "aligned_h1" in a and "aligned_h4" in a:
            return "strongly_supports"
        if "against_h1" in a or "against_h4" in a:
            return "conflicts"
        return "weakly_supports"

    def bucket_ma(rec: TradeRecord) -> str:
        sep = rec.snapshot.ema_separation_atr
        if sep is None:
            return "weakly_supports"
        if rec.snapshot.side == "BUY":
            if sep > 0.4:
                return "strongly_supports"
            if sep < 0:
                return "conflicts"
        else:
            if sep < -0.4:
                return "strongly_supports"
            if sep > 0:
                return "conflicts"
        return "weakly_supports"

    def bucket_rsi(rec: TradeRecord) -> str:
        rsi = rec.snapshot.rsi
        if rsi is None:
            return "weakly_supports"
        if rec.snapshot.side == "BUY":
            if rsi < 30:
                return "strongly_supports"
            if rsi > 70:
                return "conflicts"
        else:
            if rsi > 70:
                return "strongly_supports"
            if rsi < 30:
                return "conflicts"
        return "weakly_supports"

    for feature, fn in (("htf_alignment", bucket_htf), ("ma_separation", bucket_ma), ("rsi", bucket_rsi)):
        for label in ("strongly_supports", "weakly_supports", "conflicts"):
            subset = [r for r in records if fn(r) == label]
            summary = summarize_closed(subset)
            rows.append(
                {
                    "feature": feature,
                    "condition": label,
                    "sample_size": summary["trade_count"],
                    "expectancy_r": summary["expectancy_r"],
                    "profit_factor": summary["profit_factor"],
                    "win_rate": summary["win_rate"],
                    "total_r": summary["total_r"],
                }
            )
    return rows


def stop_quality_rows(records: list[TradeRecord]) -> dict[str, Any]:
    stopped = [r for r in records if r.exit_reason in ("sl", "ambiguous_sl_tp")]
    n = len(stopped)
    if n == 0:
        return {
            "stopped_n": 0,
            "pct_later_reached_tp": None,
            "pct_later_plus_0_5r": None,
            "pct_later_plus_1r": None,
            "pct_later_plus_2r": None,
        }

    def pct(key: str) -> float:
        return sum(1 for r in stopped if r.post_stop.get(key)) / n

    sl_atrs = [r.sl_over_atr for r in records if r.sl_over_atr is not None]
    mae_atrs = [r.mae_atr for r in records if r.mae_atr is not None]
    mfe_atrs = [r.mfe_atr for r in records if r.mfe_atr is not None]
    return {
        "stopped_n": n,
        "pct_later_reached_tp": pct("reached_original_tp"),
        "pct_later_plus_0_5r": pct("plus_0_5r"),
        "pct_later_plus_1r": pct("plus_1r"),
        "pct_later_plus_2r": pct("plus_2r"),
        "median_sl_over_atr": _median(sl_atrs),
        "median_mae_over_atr": _median(mae_atrs),
        "median_mfe_over_atr": _median(mfe_atrs),
    }


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])
