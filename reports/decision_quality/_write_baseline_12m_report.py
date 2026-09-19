"""Write the 12-month QUANT/OFFLINE baseline report from checkpoint artifacts."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from forex_bot.decision_quality.breakdowns import directional_accuracy, performance_breakdowns
from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact
from forex_bot.decision_quality.filters import run_filter_experiments
from forex_bot.decision_quality.forensics import classify_loss, stop_quality_rows
from forex_bot.decision_quality.outcomes import summarize_closed
from forex_bot.decision_quality.walk_forward import chronological_splits
from forex_bot.session_rules import fx_market_open_at

OUT_DIR = Path("reports/decision_quality")
CK = OUT_DIR / "baseline_checkpoint.json"
DEDICATED = OUT_DIR / "baseline_12m_quant_offline.md"
CANONICAL = OUT_DIR / "decision_quality_report.md"
HIST = Path("data/historical")


def _fmt(val) -> str:
    if val is None:
        return "n/a"
    if isinstance(val, float):
        if val == float("inf"):
            return "inf"
        return f"{val:.4f}"
    return str(val)


def _pct(val) -> str:
    if val is None:
        return "n/a"
    return f"{100.0 * float(val):.2f}%"


def _side_counts(trades) -> tuple[int, int]:
    buy = sum(1 for t in trades if (t.snapshot.side or "").upper() == "BUY")
    sell = sum(1 for t in trades if (t.snapshot.side or "").upper() == "SELL")
    return buy, sell


def _data_quality(symbol: str) -> dict:
    path = HIST / f"{symbol}_M5.csv"
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    ts = pd.to_datetime(raw["time"], utc=True, errors="coerce")
    naive = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    dups = int(naive.duplicated().sum())
    unparseable = int(ts.isna().sum())
    incomplete = 0
    if "complete" in raw.columns:
        complete = raw["complete"]
        incomplete = int((~complete.astype(str).str.lower().isin(("true", "1", "yes"))).sum())
    ordered = naive.sort_values()
    deltas = ordered.diff().dropna()
    expected = pd.Timedelta(minutes=5)
    weekend_gaps = 0
    unexpected_gaps = 0
    unexpected_examples: list[str] = []
    for prev, nxt, delta in zip(ordered.iloc[:-1], ordered.iloc[1:], deltas):
        if delta <= expected:
            continue
        mid = prev.to_pydatetime() + expected
        if not fx_market_open_at(mid) or not fx_market_open_at(nxt.to_pydatetime()):
            weekend_gaps += 1
            continue
        unexpected_gaps += 1
        if len(unexpected_examples) < 5:
            unexpected_examples.append(
                f"{prev} → {nxt} ({delta})"
            )
    return {
        "path": str(path),
        "bars": int(len(raw)),
        "earliest": str(ordered.iloc[0]) if len(ordered) else "",
        "latest": str(ordered.iloc[-1]) if len(ordered) else "",
        "duplicates": dups,
        "unparseable_times": unparseable,
        "incomplete_candles": incomplete,
        "weekend_or_closed_gaps": weekend_gaps,
        "unexpected_gaps": unexpected_gaps,
        "unexpected_examples": unexpected_examples,
    }


def _table(rows: list[dict], keys: list[tuple[str, str]]) -> list[str]:
    header = "| " + " | ".join(k[0] for k in keys) + " |"
    sep = "| " + " | ".join("---" if k[0] != "group" and k[0] != "split" and k[0] != "filter" else "---" for k in keys) + " |"
    lines = [header, sep]
    for row in rows:
        cells = []
        for title, key in keys:
            val = row.get(key)
            if key in ("win_rate",) and isinstance(val, float):
                cells.append(_pct(val))
            elif key.endswith("_r") or key in ("profit_factor", "expectancy_r", "median_r", "total_r", "max_drawdown_r"):
                cells.append(_fmt(val))
            else:
                cells.append(_fmt(val) if not isinstance(val, str) else val)
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def main() -> None:
    ck = load_json(CK)
    units = ck["units"]
    results = []
    for symbol in BASELINE_SYMBOLS:
        unit = units[f"{symbol}|baseline"]
        results.append((symbol, unit, load_result_artifact(Path(unit["result_path"]))))

    all_trades = [t for _, _, r in results for t in r.trades]
    overall = summarize_closed(all_trades)
    groups = performance_breakdowns(all_trades)
    stop_q = stop_quality_rows(all_trades)
    splits = chronological_splits(all_trades)
    filters = run_filter_experiments(all_trades)
    fwd = directional_accuracy(all_trades)
    loss_cats = Counter(classify_loss(t) for t in all_trades if t.realised_r is not None and t.realised_r <= 0)
    late = [t for t in all_trades if t.snapshot.pre_move_atr is not None and t.snapshot.pre_move_atr >= 1.5]
    late_sum = summarize_closed(late)
    not_late = [t for t in all_trades if t.snapshot.pre_move_atr is None or t.snapshot.pre_move_atr < 1.5]
    not_late_sum = summarize_closed(not_late)
    dq = {symbol: _data_quality(symbol) for symbol in BASELINE_SYMBOLS}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runtimes = [float(u.get("elapsed_seconds") or 0) for _, u, _ in results]
    total_runtime = sum(runtimes)
    buy_n, sell_n = _side_counts(all_trades)

    lines: list[str] = [
        "# SIX-PAIR 12-MONTH QUANT/OFFLINE BASELINE",
        "",
        "**Window:** 2025-09 through 2026-08 UTC  ",
        "**Implementation:** `impl=optimized`  ",
        "**Methodology:** production quant + routing + SL/TP (research replay)  ",
        "**This is NOT a live-bot historical replay.** Live production also applies an always-on RL agreement/veto gate (stochastic on unseen states) and downstream risk/execution. Those are excluded here.",
        "",
        f"Report written: {now}",
        "",
        "Do not confuse this with the old EUR_USD / 450-bar / 12-trade sample.",
        "",
        "## Scope confirmation",
        "",
        "- Six baseline work units only: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF",
        "- Stop-width / ATR 1.00 / 1.25 / 1.50 / 2.00: **NOT RUN IN BASELINE PHASE**",
        "- RL historical replay: **NOT RUN IN BASELINE PHASE**",
        "- API voter replay: **NOT RUN IN BASELINE PHASE**",
        "- Parameter/grid/strategy optimization: **NOT RUN**",
        "- Historical CSVs were not modified",
        "",
        "## 1. Dataset coverage",
        "",
        "| symbol | bars | earliest UTC | latest UTC | CSV |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for symbol in BASELINE_SYMBOLS:
        q = dq[symbol]
        lines.append(
            f"| {symbol} | {q['bars']} | {q['earliest']} | {q['latest']} | `{q['path']}` |"
        )

    lines += [
        "",
        "## 2. Overall metrics",
        "",
        f"- trade_count: **{overall['trade_count']}**",
        f"- BUY / SELL: **{buy_n}** / **{sell_n}**",
        f"- win_rate: {_pct(overall['win_rate'])}  (n={overall['trade_count']})",
        f"- expectancy R: **{_fmt(overall['expectancy_r'])}**",
        f"- profit_factor: {_fmt(overall['profit_factor'])}",
        f"- total R: **{_fmt(overall['total_r'])}**",
        f"- max drawdown R: {_fmt(overall['max_drawdown_r'])}",
        f"- median R: {_fmt(overall['median_r'])}",
        f"- wins / losses: {overall['wins']} / {overall['losses']}",
        f"- ambiguous SL/TP bars: {overall['ambiguous_count']}",
        "",
        "Primary metrics are expectancy, profit factor, drawdown, and sample size — not win rate.",
        "",
        "## 3. Per-symbol metrics",
        "",
        "| symbol | bars | trades | BUY | SELL | win_rate | exp_R | PF | total_R | maxDD_R | median_R | runtime |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for symbol, unit, result in results:
        s = summarize_closed(result.trades)
        b, sl = _side_counts(result.trades)
        elapsed = float(unit.get("elapsed_seconds") or 0)
        lines.append(
            f"| {symbol} | {result.bars} | {s['trade_count']} | {b} | {sl} | {_pct(s['win_rate'])} | "
            f"{_fmt(s['expectancy_r'])} | {_fmt(s['profit_factor'])} | {_fmt(s['total_r'])} | "
            f"{_fmt(s['max_drawdown_r'])} | {_fmt(s['median_r'])} | {elapsed:.1f}s |"
        )

    def section(title: str, key: str) -> None:
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(
            _table(
                groups[key],
                [
                    ("group", "group"),
                    ("n", "trade_count"),
                    ("win_rate", "win_rate"),
                    ("exp_R", "expectancy_r"),
                    ("PF", "profit_factor"),
                    ("total_R", "total_r"),
                    ("maxDD_R", "max_drawdown_r"),
                    ("median_R", "median_r"),
                ],
            )
        )

    section("4. BUY vs SELL", "direction")
    section("5. Strategy-label breakdown", "strategy")
    lines.append("")
    lines.append("Strategy labels route lookback/horizon; they do not set BUY/SELL. Direction is the quant stub.")
    section("6. Higher-timeframe context", "htf")
    section("7. Regime breakdown", "regime")
    section("8. Session breakdown", "session")

    lines += ["", "## 9. Forward directional returns", ""]
    for minutes, payload in fwd.items():
        lines.append(
            f"- {minutes}: n={payload.get('sample_size', 0)} hit_rate={_fmt(payload.get('hit_rate'))} "
            f"mean_pips={_fmt(payload.get('mean_signed_pips'))} median_pips={_fmt(payload.get('median_signed_pips'))}"
        )

    lines += [
        "",
        "## 10. Stop / MFE / MAE",
        "",
        f"- stopped_n: {stop_q.get('stopped_n')}",
        f"- later reached original TP: {_fmt(stop_q.get('pct_later_reached_tp'))}",
        f"- later +0.5R: {_fmt(stop_q.get('pct_later_plus_0_5r'))}",
        f"- later +1R: {_fmt(stop_q.get('pct_later_plus_1r'))}",
        f"- later +2R: {_fmt(stop_q.get('pct_later_plus_2r'))}",
        f"- median SL/ATR: {_fmt(stop_q.get('median_sl_over_atr'))}",
        f"- median MAE/ATR: {_fmt(stop_q.get('median_mae_over_atr'))}",
        f"- median MFE/ATR: {_fmt(stop_q.get('median_mfe_over_atr'))}",
        f"- overall avg MFE R: {_fmt(overall.get('avg_mfe_r'))}",
        f"- overall avg MAE R: {_fmt(overall.get('avg_mae_r'))}",
        "",
        "## 11. Post-stop analysis",
        "",
        "Derived from completed baseline trades only (no extra backtest).",
        "",
        f"- Loss categories (first matching rule): {dict(loss_cats)}",
        "",
        "## 12. Entry-timing / possible late entries",
        "",
        f"- pre_move_atr >= 1.5 ATR (possible late): n={late_sum['trade_count']} "
        f"exp_R={_fmt(late_sum['expectancy_r'])} PF={_fmt(late_sum['profit_factor'])} wr={_pct(late_sum['win_rate'])}",
        f"- otherwise: n={not_late_sum['trade_count']} "
        f"exp_R={_fmt(not_late_sum['expectancy_r'])} PF={_fmt(not_late_sum['profit_factor'])} wr={_pct(not_late_sum['win_rate'])}",
        "",
        "This is a measurement, not a live filter change.",
        "",
        "## 13. Chronological train / validation / test",
        "",
        "Trades split by entry time: first 50% IN-SAMPLE (train), next 25% VALIDATION, last 25% TEST / OUT-OF-SAMPLE.",
        "No parameters were tuned on the test period in this run.",
        "",
        "| split | label | n | win_rate | exp_R | PF | total_R | maxDD_R |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "train": "IN-SAMPLE",
        "valid": "VALIDATION",
        "test": "TEST / OUT-OF-SAMPLE",
    }
    for name in ("train", "valid", "test"):
        s = summarize_closed(splits[name])
        lines.append(
            f"| {name} | {labels[name]} | {s['trade_count']} | {_pct(s['win_rate'])} | "
            f"{_fmt(s['expectancy_r'])} | {_fmt(s['profit_factor'])} | {_fmt(s['total_r'])} | "
            f"{_fmt(s['max_drawdown_r'])} |"
        )

    lines += [
        "",
        "## 14. Existing baseline filter analyses",
        "",
        "Each candidate filter is scored on the already-completed baseline trades (train discovery / valid / untouched test).",
        "These are **not** additional historical backtests and were **not** applied live.",
        "",
        "| filter | split | retained | removed | filt exp_R | base exp_R | filt PF |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in filters:
        lines.append(
            f"| {row['filter']} | {row['split']} | {row['retained_n']} | {row['removed_n']} | "
            f"{_fmt(row['filtered_expectancy_r'])} | {_fmt(row['baseline_expectancy_r'])} | "
            f"{_fmt(row['filtered_profit_factor'])} |"
        )

    lines += ["", "## 15. Data-quality warnings", ""]
    for symbol in BASELINE_SYMBOLS:
        q = dq[symbol]
        lines.append(
            f"- **{symbol}**: bars={q['bars']} duplicates={q['duplicates']} "
            f"incomplete={q['incomplete_candles']} unparseable_times={q['unparseable_times']} "
            f"weekend/closed gaps={q['weekend_or_closed_gaps']} unexpected_gaps={q['unexpected_gaps']}"
        )
        for ex in q["unexpected_examples"]:
            lines.append(f"  - unexpected: {ex}")
    lines += [
        "",
        "No missing candles were manufactured. No interpolation. No data discarded to improve results.",
        "",
        "## 16. Live-vs-offline limitation",
        "",
        "This analysis is a **QUANT / OFFLINE BASELINE**.",
        "",
        "Live path: quant direction → always-on RL agreement/veto → risk/execution.",
        "Unseen RL states are stochastic BUY/SELL/SKIP with probability 1/3 each.",
        "This baseline does **not** include RL or API voters and must not be described as an exact historical replay of the live bot.",
        "",
        "## 17. Runtime per symbol",
        "",
        "| symbol | started UTC | finished UTC | elapsed_s | status | trades | artifact |",
        "| --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for symbol, unit, result in results:
        lines.append(
            f"| {symbol} | {unit.get('started_at_utc')} | {unit.get('finished_at_utc')} | "
            f"{_fmt(unit.get('elapsed_seconds'))} | {unit.get('status')} | "
            f"{unit.get('trade_count')} | `{unit.get('result_path')}` |"
        )

    lines += [
        "",
        f"## 18. Total wall-clock runtime",
        "",
        f"- Sum of per-symbol elapsed seconds: **{total_runtime:.1f}s** ({total_runtime/60.0:.1f} min)",
        f"- Checkpoint created: {ck.get('created_at_utc')}",
        f"- Checkpoint updated: {ck.get('updated_at_utc')}",
        "",
        "## 19. Checkpoint status",
        "",
    ]
    for symbol in BASELINE_SYMBOLS:
        unit = units[f"{symbol}|baseline"]
        lines.append(
            f"- `{symbol}|baseline`: **{unit.get('status')}** trades={unit.get('trade_count')} "
            f"sha256={(unit.get('input_sha256') or '')[:12]}…"
        )
    ident = ck.get("identity") or {}
    lines += [
        "",
        f"- mode={ident.get('mode')} impl={ident.get('impl')} warmup={ident.get('warmup')} seed={ident.get('seed')}",
        f"- sl_atr_mult={ident.get('sl_atr_mult')} apply_fx_week={ident.get('apply_fx_week')}",
        "",
        "## 20. Experiments not run",
        "",
        "- ATR / stop-width alternatives: **NOT RUN IN BASELINE PHASE**",
        "- Random-RL / RL historical gate: **NOT RUN IN BASELINE PHASE**",
        "- API replay: **NOT RUN IN BASELINE PHASE**",
        "",
        "No strategy, SL/TP, or filter changes are recommended or applied from this report.",
        "",
    ]
    text = "\n".join(lines) + "\n"
    tmp1 = DEDICATED.with_name(DEDICATED.name + ".tmp")
    tmp1.write_text(text, encoding="utf-8")
    tmp1.replace(DEDICATED)
    tmp2 = CANONICAL.with_name(CANONICAL.name + ".tmp")
    tmp2.write_text(text, encoding="utf-8")
    tmp2.replace(CANONICAL)
    print(f"wrote {DEDICATED} and {CANONICAL} trades={overall['trade_count']}")


if __name__ == "__main__":
    main()
