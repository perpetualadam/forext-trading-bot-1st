"""Checkpointed research runner. Baseline is standalone; stop-width is opt-in."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from forex_bot.decision_quality.checkpoint import (
    BASELINE_SYMBOLS,
    MODE_BASELINE,
    MODE_STOP_WIDTH,
    CheckpointIncompatibleError,
    file_identity,
    load_or_create_checkpoint,
    load_result_artifact,
    planned_baseline_units,
    planned_stop_width_units,
    run_identity,
    save_checkpoint,
    utc_now,
    write_result_artifact,
)
from forex_bot.decision_quality.data import SeriesCoverage, inventory_local_ohlcv, load_symbol_frame
from forex_bot.decision_quality.engine import BacktestResult, run_symbol_backtest
from forex_bot.decision_quality.live_trades import try_load_live_diagnostics
from forex_bot.decision_quality.outcomes import summarize_closed
from forex_bot.decision_quality.reports import write_reports


class RunnerAbort(RuntimeError):
    """Incompatible checkpoint or missing required inputs."""


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_hms(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def _fmt_elapsed(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"


def _fmt_metric(val) -> str:
    if val is None:
        return "n/a"
    if isinstance(val, float) and val == float("inf"):
        return "inf"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _coverage_by_symbol(coverage: list[SeriesCoverage]) -> dict[str, SeriesCoverage]:
    by_sym: dict[str, SeriesCoverage] = {}
    for cov in coverage:
        prev = by_sym.get(cov.symbol)
        if prev is None or cov.bars > prev.bars:
            by_sym[cov.symbol] = cov
    return by_sym


def _artifact_dir(out_dir: Path, mode: str) -> Path:
    return Path(out_dir) / "checkpoints" / mode


def _artifact_path(out_dir: Path, mode: str, unit_id: str) -> Path:
    safe = unit_id.replace("|", "__")
    return _artifact_dir(out_dir, mode) / f"{safe}.json"


def _print(msg: str) -> None:
    print(msg, flush=True)


def _run_one_backtest(
    symbol: str,
    csv_path: Path,
    *,
    warmup: int,
    seed: int,
    impl: str,
    apply_session_hours: bool,
    apply_fx_week: bool,
    sl_atr_mult: float | None,
) -> BacktestResult:
    df = load_symbol_frame(csv_path)
    return run_symbol_backtest(
        symbol,
        df,
        warmup=warmup,
        seed=seed,
        apply_session_hours=apply_session_hours,
        apply_fx_week=apply_fx_week,
        sl_atr_mult=sl_atr_mult,
        impl=impl,
    )


def run_work_units(
    *,
    out_dir: Path,
    data_dir: Path | None,
    mode: str,
    warmup: int = 80,
    seed: int = 42,
    impl: str = "optimized",
    apply_session_hours: bool = False,
    apply_fx_week: bool = True,
    force_rerun: bool = False,
    symbols: tuple[str, ...] | None = None,
    stop_multipliers: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0),
    write_final_report: bool = True,
) -> list[BacktestResult]:
    """
    Execute planned research work units with per-unit persist + resume.

    ``mode="baseline"``: exactly one baseline unit per symbol.
    ``mode="stop_width"``: one unit per symbol × ATR multiplier (not launched by default).
    """
    if mode not in (MODE_BASELINE, MODE_STOP_WIDTH):
        raise ValueError(f"unknown research mode {mode!r}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sl_atr_mult_identity = None if mode == MODE_BASELINE else "per_unit"
    identity = run_identity(
        warmup=warmup,
        seed=seed,
        impl=impl,
        apply_session_hours=apply_session_hours,
        apply_fx_week=apply_fx_week,
        sl_atr_mult=sl_atr_mult_identity,
        mode=mode,
    )
    units = (
        planned_baseline_units(symbols)
        if mode == MODE_BASELINE
        else planned_stop_width_units(symbols, stop_multipliers)
    )
    ck_name = "baseline_checkpoint.json" if mode == MODE_BASELINE else "stop_width_checkpoint.json"
    ck_path = out_dir / ck_name
    try:
        checkpoint = load_or_create_checkpoint(
            ck_path, identity=identity, units=units, force_rerun=force_rerun
        )
    except CheckpointIncompatibleError as exc:
        raise RunnerAbort(str(exc)) from exc

    coverage = inventory_local_ohlcv(data_dir)
    by_sym = _coverage_by_symbol(coverage)
    results: list[BacktestResult] = []
    total = len(units)

    for index, planned in enumerate(units, start=1):
        unit_id = planned["unit_id"]
        unit = checkpoint["units"][unit_id]
        symbol = planned["symbol"]
        sl_mult = planned["sl_atr_mult"]
        label = "baseline" if mode == MODE_BASELINE else f"ATR {float(sl_mult):.2f}"
        prefix = f"[{index}/{total}] {symbol} {label}"
        artifact = _artifact_path(out_dir, mode, unit_id)

        if unit.get("status") == "completed" and not force_rerun:
            if unit.get("result_path") and Path(unit["result_path"]).is_file():
                loaded = load_result_artifact(Path(unit["result_path"]))
                results.append(loaded)
                _print(
                    f"{prefix} skipped (checkpoint complete) "
                    f"trades={unit.get('trade_count')}"
                )
                continue
            unit["status"] = "pending"

        cov = by_sym.get(symbol)
        if cov is None or not cov.path or cov.bars <= warmup:
            unit.update(
                {
                    "status": "missing",
                    "started_at_utc": utc_now(),
                    "finished_at_utc": utc_now(),
                    "elapsed_seconds": 0,
                    "input_csv": cov.path if cov else None,
                    "trade_count": 0,
                    "signal_count": 0,
                    "bars": cov.bars if cov else 0,
                }
            )
            save_checkpoint(ck_path, checkpoint)
            _print(f"{prefix} missing historical CSV or insufficient bars")
            continue

        csv_path = Path(cov.path)
        file_meta = file_identity(csv_path)
        if (
            unit.get("status") == "completed"
            and unit.get("input_sha256")
            and unit["input_sha256"] != file_meta["input_sha256"]
        ):
            raise RunnerAbort(
                f"refusing to reuse {unit_id}: input CSV hash changed "
                f"({unit['input_sha256']} vs {file_meta['input_sha256']})"
            )

        started = _clock()
        unit["status"] = "running"
        unit["started_at_utc"] = started.strftime("%Y-%m-%dT%H:%M:%SZ")
        unit.update(file_meta)
        unit["result_path"] = str(artifact)
        save_checkpoint(ck_path, checkpoint)
        _print(f"{prefix} started { _fmt_hms(started) } UTC")

        result = _run_one_backtest(
            symbol,
            csv_path,
            warmup=warmup,
            seed=seed,
            impl=impl,
            apply_session_hours=apply_session_hours,
            apply_fx_week=apply_fx_week,
            sl_atr_mult=None if mode == MODE_BASELINE else sl_mult,
        )
        write_result_artifact(artifact, result)
        finished = _clock()
        elapsed = (finished - started).total_seconds()
        summary = summarize_closed(result.trades)
        unit.update(
            {
                "status": "completed",
                "finished_at_utc": finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "elapsed_seconds": round(elapsed, 3),
                "trade_count": len(result.trades),
                "signal_count": result.signals,
                "bars": result.bars,
                "result_path": str(artifact),
                "expectancy_r": summary.get("expectancy_r"),
                "profit_factor": summary.get("profit_factor"),
                "win_rate": summary.get("win_rate"),
                "total_r": summary.get("total_r"),
                "max_drawdown_r": summary.get("max_drawdown_r"),
            }
        )
        save_checkpoint(ck_path, checkpoint)
        results.append(result)
        _print(
            f"{prefix} completed {_fmt_elapsed(elapsed)} "
            f"bars={result.bars} trades={len(result.trades)} "
            f"exp_R={_fmt_metric(summary.get('expectancy_r'))} "
            f"PF={_fmt_metric(summary.get('profit_factor'))} "
            f"wr={_fmt_metric(summary.get('win_rate'))} "
            f"total_R={_fmt_metric(summary.get('total_r'))} "
            f"maxDD_R={_fmt_metric(summary.get('max_drawdown_r'))}"
        )

    if write_final_report and results and all(
        checkpoint["units"][u["unit_id"]].get("status") == "completed" for u in units
    ):
        extra = None
        report_results = results
        if mode == MODE_STOP_WIDTH:
            extra = {}
            by_symbol: dict[str, BacktestResult] = {}
            for planned in units:
                unit = checkpoint["units"][planned["unit_id"]]
                art = unit.get("result_path")
                if not art or not Path(art).is_file():
                    continue
                loaded = load_result_artifact(Path(art))
                extra.setdefault(f"atr_{float(planned['sl_atr_mult']):.2f}", []).extend(loaded.trades)
                by_symbol.setdefault(loaded.symbol, loaded)
            report_results = list(by_symbol.values())
        report = write_reports(
            out_dir=out_dir,
            results=report_results,
            coverage=coverage,
            extra_stop_runs=extra,
        )
        live_rows, live_note = try_load_live_diagnostics()
        (out_dir / "live_trades_note.txt").write_text(
            live_note + (f"\nrows={len(live_rows)}\n" if live_rows else "\n"),
            encoding="utf-8",
        )
        _print(f"Wrote {report}")
        _print(f"Simulated trades: {sum(len(r.trades) for r in results)}")
        _print(f"Coverage series: {len(coverage)}")
        _print(live_note)

    return results


def run_baseline(**kwargs) -> list[BacktestResult]:
    return run_work_units(mode=MODE_BASELINE, **kwargs)


def run_stop_width_experiments(**kwargs) -> list[BacktestResult]:
    """Explicit opt-in. The default CLI never calls this."""
    return run_work_units(mode=MODE_STOP_WIDTH, **kwargs)
