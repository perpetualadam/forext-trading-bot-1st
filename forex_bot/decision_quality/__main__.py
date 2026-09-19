"""Run: python -m forex_bot.decision_quality --out reports/decision_quality"""

from __future__ import annotations

import argparse
from pathlib import Path

from forex_bot.decision_quality.checkpoint import MODE_BASELINE, MODE_STOP_WIDTH
from forex_bot.decision_quality.isolation import assert_package_cannot_write_broker
from forex_bot.decision_quality.runner import RunnerAbort, run_work_units


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline decision-quality audit (no broker writes).")
    p.add_argument("--out", default="reports/decision_quality", help="Report directory")
    p.add_argument("--data-dir", default=None, help="Local CSV directory (default: ./data)")
    p.add_argument("--warmup", type=int, default=80)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--mode",
        choices=(MODE_BASELINE, MODE_STOP_WIDTH),
        default=MODE_BASELINE,
        help="baseline = six-symbol production SL/TP only. stop_width is explicit and separate.",
    )
    p.add_argument(
        "--impl",
        choices=("reference", "optimized"),
        default="optimized",
        help="Backtest implementation. optimized is the default research runner.",
    )
    p.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore completed checkpoint units and recompute them.",
    )
    p.add_argument(
        "--atr-multipliers",
        default="1.0,1.25,1.5,2.0",
        help="Used only with --mode stop_width. Comma-separated ATR SL widths.",
    )
    args = p.parse_args(argv)

    assert_package_cannot_write_broker()
    data_dir = Path(args.data_dir) if args.data_dir else None
    multipliers = tuple(float(x.strip()) for x in args.atr_multipliers.split(",") if x.strip())
    if args.mode == MODE_STOP_WIDTH and not multipliers:
        print("ERROR: --mode stop_width requires at least one --atr-multipliers value")
        return 2
    try:
        run_work_units(
            out_dir=Path(args.out),
            data_dir=data_dir,
            mode=args.mode,
            warmup=args.warmup,
            seed=args.seed,
            impl=args.impl,
            apply_session_hours=False,
            apply_fx_week=True,
            force_rerun=args.force_rerun,
            stop_multipliers=multipliers,
        )
    except RunnerAbort as exc:
        print(f"ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
