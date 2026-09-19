"""One-shot persist helper for research-runner optimization stages."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MD = Path("reports/decision_quality/research_runner_optimization.md")
PROG = Path("reports/decision_quality/research_runner_optimization_progress.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def elapsed_s(started: str, finished: str) -> int:
    t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    return int((t1 - t0).total_seconds())


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_md(text: str) -> None:
    md = MD.read_text(encoding="utf-8")
    if text.strip()[:40] in md:
        return
    MD.write_text(md + text, encoding="utf-8")


def upsert_stage(stage: dict) -> None:
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    now = stage.get("finished_at_utc") or utc_now()
    prog["last_checkpoint_at_utc"] = now
    prog["current_stage"] = stage["stage_number"]
    if stage.get("status") == "completed" and stage["stage_number"] not in prog["completed_stages"]:
        prog["completed_stages"].append(stage["stage_number"])
    prog["stages"] = [s for s in prog["stages"] if s["stage_number"] != stage["stage_number"]]
    prog["stages"].append(stage)
    prog["stages"].sort(key=lambda s: s["stage_number"])
    atomic_write_json(PROG, prog)


def persist_stage6() -> None:
    started = "2026-09-18T09:42:48Z"
    finished = utc_now()
    elapsed = elapsed_s(started, finished)
    append_md(
        f"""
## Stage 6 — Implement performance optimization

**Status:** COMPLETED  
**Started:** {started}  
**Finished:** {finished}  
**Elapsed:** {elapsed}s

Wired `impl="reference"` (unchanged default) and `impl="optimized"` in `run_symbol_backtest`.

Optimized path (`fast_cache.py`):
- `SignalCache` precomputes `compute_indicators` once per lookback and closed M15/H1/H4 OHLC once.
- Per-bar `evaluate_signal_cached` reads prefix-correct indicator rows. If `_period_tuple(lookback, i+1)` differs from the full-frame periods (short prefixes), it recomputes the prefix so MA/ATR lengths match the reference.
- HTF labels use only bars with period end <= asof (same closed-candle rule as `resample_closed_ohlc`).
- VOLATILITY_FILTER / FX_WEEK / SESSION / NO_STRATEGY match `_blank`: lookback field 0, empty vote, research fields at lookback 50.
- Trade simulation, SL/TP, spread, and `bar_touches` are unchanged and shared.

First equivalence compare failed only on snapshot `lookback` (reference `_blank` uses 0 on VOLATILITY_FILTER; optimized had passed the strategy lookback). Decision/side/SL/TP/exits already matched. After matching `_blank`, equivalence passed.

Command: `python -m pytest tests/test_decision_quality_equivalence.py -q --tb=short`  
Result: **5 passed** in 6.30s.

No production trading files changed. Historical CSVs not modified. Default engine `impl` remains `reference` so existing tests stay on the original path.

---
"""
    )
    upsert_stage(
        {
            "stage_number": 6,
            "stage_name": "Implement performance optimization",
            "status": "completed",
            "started_at_utc": started,
            "finished_at_utc": finished,
            "elapsed_seconds": elapsed,
            "files_inspected": [
                "forex_bot/decision_quality/signal.py",
                "forex_bot/decision_quality/engine.py",
                "forex_bot/decision_quality/research_features.py",
                "forex_bot/decision_quality/fast_cache.py",
            ],
            "files_changed": [
                "forex_bot/decision_quality/fast_cache.py",
                "forex_bot/decision_quality/engine.py",
                "tests/test_decision_quality_equivalence.py",
                "reports/decision_quality/research_runner_optimization.md",
                "reports/decision_quality/research_runner_optimization_progress.json",
            ],
            "commands_run": [
                "python -m pytest tests/test_decision_quality_equivalence.py -q --tb=short"
            ],
            "tests_run": ["tests/test_decision_quality_equivalence.py"],
            "benchmark_results": {"equivalence_passed": 5, "equivalence_failed": 0},
            "short_finding_summary": (
                "Optimized impl wired. Equivalence 5/5 after matching _blank lookback=0 "
                "on VOLATILITY_FILTER. Trading semantics unchanged."
            ),
        }
    )
    print(f"[6/10] Implement performance optimization       completed {elapsed // 60:02d}m {elapsed % 60:02d}s")


if __name__ == "__main__":
    persist_stage6()
    sys.exit(0)
