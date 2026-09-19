"""Bounded reference vs optimized benchmark. Does not run the 12-month six-pair job."""

from __future__ import annotations

import json
import time
from pathlib import Path

from forex_bot.decision_quality.data import load_symbol_frame
from forex_bot.decision_quality.engine import run_symbol_backtest


def _trade_key(t):
    s = t.snapshot
    return (
        s.timestamp,
        s.decision,
        s.side,
        s.strategy,
        s.lookback,
        None if s.entry_price is None else round(float(s.entry_price), 8),
        None if s.stop_loss is None else round(float(s.stop_loss), 8),
        None if s.take_profit is None else round(float(s.take_profit), 8),
        t.exit_reason,
        t.exit_time,
        None if t.realised_pips is None else round(float(t.realised_pips), 6),
        None if t.realised_r is None else round(float(t.realised_r), 6),
        s.h1_trend,
        s.h4_trend,
        s.regime,
    )


def assert_equivalent(a, b) -> None:
    if a.signals != b.signals or len(a.trades) != len(b.trades):
        raise AssertionError(f"counts differ ref={a.signals}/{len(a.trades)} opt={b.signals}/{len(b.trades)}")
    if [s.decision for s in a.snapshots] != [s.decision for s in b.snapshots]:
        raise AssertionError("decision sequence differs")
    if [s.lookback for s in a.snapshots] != [s.lookback for s in b.snapshots]:
        raise AssertionError("lookback sequence differs")
    if [_trade_key(t) for t in a.trades] != [_trade_key(t) for t in b.trades]:
        raise AssertionError("trade tuples differ")

CSV = Path("data/historical/EUR_USD_M5.csv")
OUT_TXT = Path("reports/decision_quality/bench_optimized_vs_reference.txt")
OUT_JSON = Path("reports/decision_quality/bench_optimized_vs_reference.json")
WARMUP = 80
SEED = 42
HEADLINE_BARS = 800
SCALE_BARS = (400, 800, 1600, 2400)
OPT_ONLY_BARS = (5000, 8000)


def _run(df, impl: str):
    return run_symbol_backtest(
        "EUR_USD",
        df,
        warmup=WARMUP,
        seed=SEED,
        apply_session_hours=False,
        apply_fx_week=True,
        impl=impl,
    )


def _timed(df, impl: str):
    t0 = time.perf_counter()
    result = _run(df, impl)
    return time.perf_counter() - t0, result


def main() -> None:
    full = load_symbol_frame(CSV)
    payload: dict = {"symbol": "EUR_USD", "warmup": WARMUP, "seed": SEED, "csv": str(CSV)}
    lines = [
        "Bounded EUR_USD benchmark (not the 12-month six-pair baseline)",
        f"csv={CSV} total_rows={len(full)}",
        "",
    ]

    df800 = full.iloc[:HEADLINE_BARS].reset_index(drop=True)
    ref_s, ref = _timed(df800, "reference")
    opt_s, opt = _timed(df800, "optimized")
    assert_equivalent(ref, opt)
    speedup = ref_s / opt_s if opt_s > 0 else None
    payload["headline_800"] = {
        "reference_s": round(ref_s, 4),
        "optimized_s": round(opt_s, 4),
        "speedup": None if speedup is None else round(speedup, 3),
        "equivalent": True,
        "signals": ref.signals,
        "trades": len(ref.trades),
    }
    lines += [
        f"HEADLINE {HEADLINE_BARS} bars:",
        f"  REFERENCE {ref_s:.4f}s  signals={ref.signals} trades={len(ref.trades)}",
        f"  OPTIMIZED {opt_s:.4f}s  signals={opt.signals} trades={len(opt.trades)}",
        f"  SPEEDUP   {speedup:.3f}x  equivalent=YES",
        "",
        "SCALE (both impls):",
    ]

    scale = []
    for n in SCALE_BARS:
        df = full.iloc[:n].reset_index(drop=True)
        rs, rr = _timed(df, "reference")
        os_, oo = _timed(df, "optimized")
        same_trades = [_trade_key(t) for t in rr.trades] == [_trade_key(t) for t in oo.trades]
        same_signals = rr.signals == oo.signals
        scale.append(
            {
                "bars": n,
                "reference_s": round(rs, 4),
                "optimized_s": round(os_, 4),
                "speedup": round(rs / os_, 3) if os_ else None,
                "signals_match": same_signals,
                "trades_match": same_trades,
                "trades": len(rr.trades),
            }
        )
        lines.append(
            f"  n={n:5d}  ref={rs:.4f}s  opt={os_:.4f}s  "
            f"speedup={rs/os_:.2f}x  trades={len(rr.trades)} match={same_trades and same_signals}"
        )

    payload["scale"] = scale
    lines.append("")
    lines.append("OPTIMIZED-ONLY larger windows:")
    opt_only = []
    last_opt_s = opt_s
    last_n = HEADLINE_BARS
    for n in OPT_ONLY_BARS:
        if n > len(full):
            continue
        df = full.iloc[:n].reset_index(drop=True)
        os_, oo = _timed(df, "optimized")
        opt_only.append(
            {
                "bars": n,
                "optimized_s": round(os_, 4),
                "trades": len(oo.trades),
                "signals": oo.signals,
            }
        )
        lines.append(f"  n={n:5d}  opt={os_:.4f}s  trades={len(oo.trades)} signals={oo.signals}")
        last_opt_s = os_
        last_n = n

    payload["optimized_larger"] = opt_only
    per_bar = last_opt_s / last_n if last_n else None
    year_bars = 74555
    proj_one = per_bar * year_bars if per_bar else None
    proj_six = proj_one * 6 if proj_one else None
    payload["projection"] = {
        "measured_bars": last_n,
        "measured_s": None if last_opt_s is None else round(last_opt_s, 4),
        "seconds_per_bar": per_bar,
        "assumed_year_bars": year_bars,
        "projected_one_symbol_s": proj_one,
        "projected_six_symbol_s": proj_six,
        "assumption": "linear scale from largest optimized window; includes trade-sim cost on that window",
    }
    lines += [
        "",
        f"Linear projection from n={last_n} ({last_opt_s:.4f}s):",
        f"  per_bar={per_bar:.6e}s",
        f"  one 12-month symbol (~{year_bars} bars) ~ {proj_one:.1f}s",
        f"  six symbols sequential ~ {proj_six:.1f}s",
        "",
        "This script did not launch the six-pair 12-month baseline.",
    ]
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp = OUT_JSON.with_name(OUT_JSON.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT_JSON)
    print(OUT_TXT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
