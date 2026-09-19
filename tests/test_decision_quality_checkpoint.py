"""Baseline checkpoint / resume. Does not launch the 12-month dataset."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.decision_quality.checkpoint import (
    BASELINE_SYMBOLS,
    CheckpointIncompatibleError,
    identity_conflicts,
    load_json,
    load_or_create_checkpoint,
    planned_baseline_units,
    planned_stop_width_units,
    run_identity,
)
from forex_bot.decision_quality.runner import RunnerAbort, run_baseline, run_stop_width_experiments, run_work_units
from forex_bot.decision_quality.__main__ import main


def _write_csv(path: Path, n: int = 100, start: float = 1.1) -> None:
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    rows = []
    px = start
    for i in range(n):
        px += 0.00003
        rows.append(
            {
                "time": (t0 + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%S"),
                "open": px - 0.00001,
                "high": px + 0.00012,
                "low": px - 0.00012,
                "close": px,
                "volume": 1,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_canonical_baseline_is_exactly_six_symbols():
    assert len(BASELINE_SYMBOLS) == 6
    assert BASELINE_SYMBOLS == (
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "USD_CAD",
        "USD_CHF",
    )
    units = planned_baseline_units()
    assert [u["unit_id"] for u in units] == [f"{s}|baseline" for s in BASELINE_SYMBOLS]
    assert all(u["sl_atr_mult"] is None for u in units)
    assert len(planned_stop_width_units()) == 24


def test_incompatible_checkpoint_is_refused(tmp_path: Path):
    identity = run_identity(
        warmup=80,
        seed=42,
        impl="optimized",
        apply_session_hours=False,
        apply_fx_week=True,
        sl_atr_mult=None,
        mode="baseline",
    )
    units = planned_baseline_units(("EUR_USD",))
    path = tmp_path / "baseline_checkpoint.json"
    load_or_create_checkpoint(path, identity=identity, units=units)
    other = dict(identity)
    other["warmup"] = 90
    with pytest.raises(CheckpointIncompatibleError):
        load_or_create_checkpoint(path, identity=other, units=units)
    assert identity_conflicts(identity, other)


def test_baseline_persists_and_resumes(tmp_path: Path, capsys):
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    _write_csv(data / "GBP_USD_M5.csv", n=110, start=1.25)

    first = run_baseline(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD", "GBP_USD"),
        write_final_report=False,
    )
    printed = capsys.readouterr().out
    assert "[1/2] EUR_USD baseline started" in printed
    assert "[1/2] EUR_USD baseline completed" in printed
    assert "[2/2] GBP_USD baseline started" in printed
    assert "ATR" not in printed
    assert len(first) == 2
    ck = load_json(out / "baseline_checkpoint.json")
    assert ck["units"]["EUR_USD|baseline"]["status"] == "completed"
    assert ck["units"]["GBP_USD|baseline"]["status"] == "completed"
    eur_art = Path(ck["units"]["EUR_USD|baseline"]["result_path"])
    assert eur_art.is_file()
    assert (out / "checkpoints" / "baseline" / "GBP_USD__baseline.json").is_file()

    second = run_baseline(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD", "GBP_USD"),
        write_final_report=False,
    )
    printed2 = capsys.readouterr().out
    assert "skipped (checkpoint complete)" in printed2
    assert "[1/2] EUR_USD baseline started" not in printed2.split("skipped")[0] or printed2.count("started") == 0
    assert len(second) == 2
    assert len(second[0].trades) == len(first[0].trades)
    assert len(second[1].trades) == len(first[1].trades)


def test_resume_continues_after_partial_completion(tmp_path: Path, capsys):
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    run_baseline(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD", "GBP_USD"),
        write_final_report=False,
    )
    printed = capsys.readouterr().out
    assert "[1/2] EUR_USD baseline completed" in printed
    assert "GBP_USD baseline missing" in printed
    ck = load_json(out / "baseline_checkpoint.json")
    assert ck["units"]["EUR_USD|baseline"]["status"] == "completed"
    assert ck["units"]["GBP_USD|baseline"]["status"] == "missing"

    _write_csv(data / "GBP_USD_M5.csv", n=110, start=1.25)
    run_baseline(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD", "GBP_USD"),
        write_final_report=False,
    )
    printed2 = capsys.readouterr().out
    assert "EUR_USD baseline skipped" in printed2
    assert "[2/2] GBP_USD baseline started" in printed2
    assert "[2/2] GBP_USD baseline completed" in printed2
    ck2 = load_json(out / "baseline_checkpoint.json")
    assert ck2["units"]["GBP_USD|baseline"]["status"] == "completed"


def test_seed_change_refuses_resume(tmp_path: Path):
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    run_baseline(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD",),
        write_final_report=False,
    )
    with pytest.raises(RunnerAbort, match="incompatible checkpoint"):
        run_baseline(
            out_dir=out,
            data_dir=data,
            warmup=80,
            seed=99,
            impl="optimized",
            symbols=("EUR_USD",),
            write_final_report=False,
        )


def test_stop_width_units_are_explicit_and_separate():
    units = planned_stop_width_units()
    assert [u["unit_id"] for u in units[:4]] == [
        "EUR_USD|atr_1.00",
        "EUR_USD|atr_1.25",
        "EUR_USD|atr_1.50",
        "EUR_USD|atr_2.00",
    ]
    assert units[-1]["unit_id"] == "USD_CHF|atr_2.00"
    assert all(u["mode"] == "stop_width" for u in units)
    assert {u["symbol"] for u in units} == set(BASELINE_SYMBOLS)


def test_cli_default_is_baseline_not_stop_width():
    src = Path("forex_bot/decision_quality/__main__.py").read_text(encoding="utf-8")
    assert "default=MODE_BASELINE" in src
    assert "choices=(MODE_BASELINE, MODE_STOP_WIDTH)" in src
    assert "default=\"optimized\"" in src or "default='optimized'" in src


def test_main_baseline_does_not_create_stop_width_checkpoint(tmp_path: Path):
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    rc = main(["--out", str(out), "--data-dir", str(data), "--warmup", "80", "--seed", "42"])
    assert rc == 0
    assert (out / "baseline_checkpoint.json").is_file()
    assert not (out / "stop_width_checkpoint.json").exists()
    units = load_json(out / "baseline_checkpoint.json")["units"]
    assert list(units) == [f"{s}|baseline" for s in BASELINE_SYMBOLS]
    assert all("|atr_" not in uid for uid in units)


def test_stop_width_plumbing_one_synthetic_unit(tmp_path: Path, capsys):
    """Capability exists; this is not the 24-run research workload."""
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    run_stop_width_experiments(
        out_dir=out,
        data_dir=data,
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD",),
        stop_multipliers=(1.25,),
        write_final_report=False,
    )
    printed = capsys.readouterr().out
    assert "[1/1] EUR_USD ATR 1.25 started" in printed
    assert (out / "stop_width_checkpoint.json").is_file()
    assert not (out / "baseline_checkpoint.json").exists()
    ck = load_json(out / "stop_width_checkpoint.json")
    assert list(ck["units"]) == ["EUR_USD|atr_1.25"]


def test_baseline_mode_does_not_schedule_atr(tmp_path: Path, capsys):
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    _write_csv(data / "EUR_USD_M5.csv", n=110)
    run_work_units(
        out_dir=out,
        data_dir=data,
        mode="baseline",
        warmup=80,
        seed=42,
        impl="optimized",
        symbols=("EUR_USD",),
        write_final_report=False,
    )
    out_text = capsys.readouterr().out
    assert "ATR" not in out_text
    ck = load_json(out / "baseline_checkpoint.json")
    assert list(ck["units"]) == ["EUR_USD|baseline"]
    assert not (out / "stop_width_checkpoint.json").exists()
