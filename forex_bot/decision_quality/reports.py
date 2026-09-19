"""Write CSV + markdown reports. Offline only."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from forex_bot.decision_quality.breakdowns import directional_accuracy, performance_breakdowns
from forex_bot.decision_quality.data import SeriesCoverage
from forex_bot.decision_quality.engine import BacktestResult
from forex_bot.decision_quality.filters import run_filter_experiments
from forex_bot.decision_quality.forensics import (
    feature_value_rows,
    losing_trade_rows,
    stop_quality_rows,
)
from forex_bot.decision_quality.live_path import LIVE_CALL_PATH, PRODUCTION_REUSED
from forex_bot.decision_quality.outcomes import TradeRecord, summarize_closed
from forex_bot.decision_quality.walk_forward import chronological_splits, walk_forward_windows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _fmt(val: Any) -> str:
    if val is None:
        return "n/a"
    if isinstance(val, float):
        if val == float("inf"):
            return "inf"
        return f"{val:.4f}"
    return str(val)


def write_reports(
    *,
    out_dir: Path,
    results: list[BacktestResult],
    coverage: list[SeriesCoverage],
    extra_stop_runs: dict[str, list[TradeRecord]] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    trades = [t for r in results for t in r.trades]
    baseline = summarize_closed(trades)
    groups = performance_breakdowns(trades)
    _write_csv(out_dir / "baseline_summary.csv", [{**baseline, "group": "ALL"}])
    _write_csv(out_dir / "performance_by_symbol.csv", groups["symbol"])
    _write_csv(out_dir / "performance_by_strategy.csv", groups["strategy"])
    _write_csv(out_dir / "performance_by_direction.csv", groups["direction"])
    _write_csv(out_dir / "performance_by_session.csv", groups["session"])
    _write_csv(out_dir / "performance_by_regime.csv", groups["regime"])
    _write_csv(out_dir / "higher_timeframe_alignment.csv", groups["htf"])
    stop_q = stop_quality_rows(trades)
    _write_csv(out_dir / "stop_quality.csv", [stop_q])
    post_rows = [
        {
            "symbol": t.snapshot.symbol,
            "side": t.snapshot.side,
            "exit_reason": t.exit_reason,
            **{f"post_{k}": v for k, v in t.post_stop.items()},
        }
        for t in trades
        if t.post_stop
    ]
    _write_csv(out_dir / "post_stop_analysis.csv", post_rows)
    _write_csv(out_dir / "losing_trade_forensics.csv", losing_trade_rows(trades))
    experiments = run_filter_experiments(trades)
    _write_csv(out_dir / "filter_experiments.csv", experiments)
    splits = chronological_splits(trades)
    wf_rows = []
    for i, (train, test) in enumerate(walk_forward_windows(trades), start=1):
        wf_rows.append(
            {
                "fold": i,
                **{f"train_{k}": v for k, v in summarize_closed(train).items()},
                **{f"test_{k}": v for k, v in summarize_closed(test).items()},
            }
        )
    for name, part in splits.items():
        wf_rows.append({"fold": name, **{f"{name}_{k}": v for k, v in summarize_closed(part).items()}})
    _write_csv(out_dir / "walk_forward_results.csv", wf_rows)
    _write_csv(out_dir / "feature_value.csv", feature_value_rows(trades))
    _write_csv(out_dir / "coverage.csv", [_coverage_row(c) for c in coverage])
    if extra_stop_runs:
        stop_exp = []
        for label, recs in extra_stop_runs.items():
            row = summarize_closed(recs)
            row["stop_rule"] = label
            stop_exp.append(row)
        _write_csv(out_dir / "hypothetical_stop_widths.csv", stop_exp)

    md = _markdown(
        results=results,
        coverage=coverage,
        baseline=baseline,
        groups=groups,
        stop_q=stop_q,
        experiments=experiments,
        splits=splits,
        extra_stop_runs=extra_stop_runs or {},
    )
    report_path = out_dir / "decision_quality_report.md"
    report_path.write_text(md, encoding="utf-8")
    (out_dir / "live_call_path.json").write_text(
        json.dumps({"path": LIVE_CALL_PATH, "reused": PRODUCTION_REUSED}, indent=2),
        encoding="utf-8",
    )
    return report_path


def _coverage_row(c: SeriesCoverage) -> dict[str, Any]:
    return {
        "symbol": c.symbol,
        "timeframe": c.timeframe,
        "path": c.path,
        "earliest": c.earliest.isoformat() if c.earliest else None,
        "latest": c.latest.isoformat() if c.latest else None,
        "bars": c.bars,
        "missing": c.missing_reason,
    }


def _markdown(
    *,
    results: list[BacktestResult],
    coverage: list[SeriesCoverage],
    baseline: dict[str, Any],
    groups: dict[str, list[dict[str, Any]]],
    stop_q: dict[str, Any],
    experiments: list[dict],
    splits: dict[str, list],
    extra_stop_runs: dict[str, list],
) -> str:
    trades = [t for r in results for t in r.trades]
    n = baseline["trade_count"]
    lines = [
        "# Decision quality report (offline)",
        "",
        "This report does **not** change live trading. Strategy names do not set BUY/SELL;",
        "direction comes from the production quant stub (`ma_fast` vs `ma_slow` + momentum).",
        "",
        "## Live call path (frozen)",
        "",
    ]
    lines.extend(f"- {step}" for step in LIVE_CALL_PATH)
    lines += ["", "## Historical data coverage", ""]
    for c in coverage:
        if c.bars == 0:
            lines.append(f"- **{c.symbol} {c.timeframe}**: MISSING — {c.missing_reason}")
        else:
            lines.append(
                f"- **{c.symbol} {c.timeframe}**: {c.bars} bars {c.earliest} → {c.latest} ({c.path})"
            )
    lines += [
        "",
        "## Execution ambiguity",
        "",
        results[0].execution_note if results else "no results",
        "",
        "## Baseline (all simulated trades)",
        "",
        f"- sample_size (closed trades): **{n}**",
        f"- wins / losses: {baseline['wins']} / {baseline['losses']}",
        f"- win_rate: {_fmt(baseline['win_rate'])}",
        f"- expectancy R/trade: {_fmt(baseline['expectancy_r'])}",
        f"- profit_factor: {_fmt(baseline['profit_factor'])}",
        f"- total R: {_fmt(baseline['total_r'])}",
        f"- max drawdown R: {_fmt(baseline['max_drawdown_r'])}",
        f"- median R: {_fmt(baseline['median_r'])}",
        f"- ambiguous SL/TP bars: {baseline['ambiguous_count']}",
        "",
        "Primary metrics are expectancy, profit factor, drawdown, and sample size — not win rate.",
        "",
        "## WHY IS THE BOT LOSING?",
        "",
    ]
    if n < 20:
        lines.append(
            f"Sample size is {n}. That is too small to claim a stable cause. "
            "Statements below are measurements on the available data only."
        )
    else:
        lines.append("Measured associations on the available sample (not proof of causality):")
    lines += ["", _why_section(trades, baseline, groups, stop_q, experiments), ""]
    lines += ["## Breakdowns (sample size in every row)", ""]
    for title, key in (
        ("Symbol", "symbol"),
        ("Strategy", "strategy"),
        ("BUY vs SELL", "direction"),
        ("Session (London clock)", "session"),
        ("Regime", "regime"),
        ("Higher-timeframe alignment", "htf"),
    ):
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| group | n | win_rate | exp_R | PF | total_R | maxDD_R |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in groups[key]:
            lines.append(
                f"| {row['group']} | {row['trade_count']} | {_fmt(row['win_rate'])} | "
                f"{_fmt(row['expectancy_r'])} | {_fmt(row['profit_factor'])} | "
                f"{_fmt(row['total_r'])} | {_fmt(row['max_drawdown_r'])} |"
            )
        lines.append("")
    acc = directional_accuracy(trades)
    lines += ["## Directional forward returns (ignores SL path)", ""]
    for minutes, payload in acc.items():
        lines.append(
            f"- {minutes}: n={payload.get('sample_size', 0)} hit_rate={_fmt(payload.get('hit_rate'))} "
            f"mean_pips={_fmt(payload.get('mean_signed_pips'))} median_pips={_fmt(payload.get('median_signed_pips'))}"
        )
    lines += [
        "",
        "## Stop-loss quality",
        "",
        f"- stopped_n: {stop_q.get('stopped_n')}",
        f"- later reached original TP: {_fmt(stop_q.get('pct_later_reached_tp'))}",
        f"- later +0.5R: {_fmt(stop_q.get('pct_later_plus_0_5r'))}",
        f"- later +1R: {_fmt(stop_q.get('pct_later_plus_1r'))}",
        f"- later +2R: {_fmt(stop_q.get('pct_later_plus_2r'))}",
        f"- median SL/ATR: {_fmt(stop_q.get('median_sl_over_atr'))}",
        f"- median MAE/ATR: {_fmt(stop_q.get('median_mae_over_atr'))}",
        "",
        "## Walk-forward / out-of-sample",
        "",
        f"- train n={len(splits.get('train', []))} valid n={len(splits.get('valid', []))} "
        f"test n={len(splits.get('test', []))}",
        "",
        "## Filter experiments (each filter alone; train discovery / valid+test confirmation)",
        "",
    ]
    for row in experiments:
        if row.get("split") != "test":
            continue
        lines.append(
            f"- {row['filter']} OOS: retained={row['retained_n']} removed={row['removed_n']} "
            f"exp_R={_fmt(row['filtered_expectancy_r'])} (baseline {_fmt(row['baseline_expectancy_r'])}) "
            f"PF={_fmt(row['filtered_profit_factor'])}"
        )
    lines += ["", "## Recommended live changes — NOT IMPLEMENTED", ""]
    lines.append("See the agent summary. No live thresholds, sessions, or routing were changed.")
    lines += ["", "## Limitations", ""]
    lines.append("- Only local CSVs were used; OANDA was not queried.")
    lines.append("- RL gate and API voters are excluded so the audit stays deterministic.")
    lines.append("- Live close management is close-only; this simulator uses high/low.")
    lines.append("- Tiny samples must not be treated as strategy proof.")
    return "\n".join(lines) + "\n"


def _why_section(trades, baseline, groups, stop_q, experiments) -> str:
    bits: list[str] = []
    n = baseline["trade_count"]
    if n == 0:
        return "No simulated trades were closed. Cannot explain losses from this sample."
    worst_sym = min(groups["symbol"], key=lambda r: (r["expectancy_r"] is None, r["expectancy_r"] or 0))
    if worst_sym["trade_count"] >= 5 and (worst_sym["expectancy_r"] or 0) < 0:
        bits.append(
            f"{worst_sym['group']} produced negative expectancy "
            f"({_fmt(worst_sym['expectancy_r'])} R) across {worst_sym['trade_count']} trades."
        )
    against = [r for r in groups["htf"] if "against_h1" in r["group"] and r["trade_count"] >= 5]
    if against and (against[0]["expectancy_r"] or 0) < 0:
        bits.append(
            f"Signals against H1 ({against[0]['group']}) had expectancy "
            f"{_fmt(against[0]['expectancy_r'])} R on {against[0]['trade_count']} trades."
        )
    if stop_q.get("stopped_n") and stop_q.get("pct_later_reached_tp"):
        bits.append(
            f"Of {stop_q['stopped_n']} stop-outs, {_fmt(stop_q['pct_later_reached_tp'])} "
            "later reached the original TP (possible stop-too-tight, not proven)."
        )
    if not bits:
        bits.append(
            f"Closed-trade expectancy is {_fmt(baseline['expectancy_r'])} R on {n} trades. "
            "No single grouping is large enough for a stronger claim."
        )
    return "\n".join(f"- {b}" for b in bits)
