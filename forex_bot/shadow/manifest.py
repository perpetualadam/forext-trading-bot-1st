"""Stage E local evaluation snapshot. Not a prospective preregistration."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHADOW = Path(__file__).resolve().parent


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest() -> dict:
    files = [
        "signals.py",
        "config.py",
        "cost_model.py",
        "accounting.py",
        "engine.py",
        "risk.py",
        "assess.py",
        "classify.py",
        "diagnose.py",
        "replay.py",
        "protocol.py",
    ]
    hashes = {name: _sha256_file(SHADOW / name) for name in files}
    datasets = {}
    hist = ROOT / "data" / "historical"
    for path in sorted(hist.glob("*_M5.csv")):
        datasets[path.name] = _sha256_file(path)
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        rev = "unknown"
    return {
        "kind": "STAGE_E_LOCAL_EVALUATION_MANIFEST",
        "not_a_preregistration": True,
        "label": "EXPERIMENTAL_HEURISTIC_OFFLINE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": rev,
        "source_hashes": hashes,
        "combined_rules_hash": _sha256_text(
            hashes["signals.py"] + hashes["config.py"] + hashes["cost_model.py"]
        ),
        "dataset_hashes": datasets,
        "methodology": {
            "cadence": "M5 completed bars",
            "fill": "next-bar open; bid/ask when present",
            "collision": "stop-loss wins; gap through stop at quote-open",
            "splits": {
                "development": "2025-09-01 .. 2026-01-31 UTC",
                "validation": "2026-02-01 .. 2026-04-30 UTC",
                "heldout": "2026-05-01 .. 2026-08-31 UTC",
            },
            "cost_scenarios": ["base", "conservative", "severe"],
            "start_nav_gbp": 97.15,
            "notional_pct": 0.02,
            "classification_thresholds": {
                "min_heldout_trades": 50,
                "min_profit_factor": 1.2,
                "max_dd_frac_of_nav": 0.05,
                "require_validation_positive": True,
                "require_conservative_positive": True,
                "severe_net_floor_frac": -0.02,
                "max_single_pair_abs_share": 0.70,
            },
            "no_tuning_on_heldout": True,
        },
        "contamination_note": (
            "These M5 files were used in decision_quality research. Stage C/D "
            "heuristics were not grid-searched on this corpus, but the period "
            "overlaps live trading and prior research. Held-out is chronological only."
        ),
    }


def write_manifest(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob = build_manifest()
    dest.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    return dest


if __name__ == "__main__":
    path = write_manifest(ROOT / "data" / "research" / "shadow_stage_e" / "evaluation_manifest.json")
    print(path)
