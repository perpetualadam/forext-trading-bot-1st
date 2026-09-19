"""One-shot cProfile of existing run_symbol_backtest on a bounded slice. Research-only."""

from __future__ import annotations

import cProfile
import pstats
import time
from io import StringIO
from pathlib import Path

from forex_bot.decision_quality.data import load_symbol_frame
from forex_bot.decision_quality.engine import run_symbol_backtest

CSV = Path("data/historical/EUR_USD_M5.csv")
BARS = 800
WARMUP = 80
OUT = Path("reports/decision_quality/profile_small_eurusd_800.txt")


def main() -> None:
    df = load_symbol_frame(CSV).iloc[:BARS].copy().reset_index(drop=True)
    t0 = time.perf_counter()
    prof = cProfile.Profile()
    prof.enable()
    result = run_symbol_backtest(
        "EUR_USD",
        df,
        warmup=WARMUP,
        seed=42,
        apply_session_hours=False,
        apply_fx_week=True,
    )
    prof.disable()
    elapsed = time.perf_counter() - t0

    buf = StringIO()
    stats = pstats.Stats(prof, stream=buf)
    stats.strip_dirs().sort_stats("cumulative")
    buf.write(
        f"workload=EUR_USD first {BARS} bars warmup={WARMUP} "
        f"signals={result.signals} trades={len(result.trades)} "
        f"snapshots={len(result.snapshots)} wall_s={elapsed:.4f}\n\n"
    )
    buf.write("=== top 40 by cumulative time ===\n")
    stats.print_stats(40)
    buf.write("\n=== top 25 by tottime (self) ===\n")
    stats.sort_stats("tottime")
    stats.print_stats(25)
    OUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"wrote {OUT} wall_s={elapsed:.4f} trades={len(result.trades)} signals={result.signals}")


if __name__ == "__main__":
    main()
