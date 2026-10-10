"""Phase A factual inventory for Stage G. Read-only descriptions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

HIST = Path("data") / "historical"


def inspect_csv(path: Path) -> dict[str, Any]:
    df = pd.read_csv(path)
    cols = list(df.columns)
    t = pd.to_datetime(df["time"], utc=True, errors="coerce") if "time" in df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    dups = int(t.duplicated().sum()) if len(t) else None
    gaps = None
    if len(t) > 2:
        delta = t.diff().dt.total_seconds().dropna()
        gaps = int((delta > 6 * 60).sum())
    return {
        "path": str(path).replace("\\", "/"),
        "rows": len(df),
        "columns": cols,
        "start": str(t.min()) if len(t) else None,
        "end": str(t.max()) if len(t) else None,
        "duplicate_timestamps": dups,
        "gaps_gt_6m": gaps,
        "bid_ask": all(c in cols for c in ("bid_close", "ask_close")),
        "timeframe": "M5 inferred from filename" if "_M5" in path.name else "UNKNOWN",
        "previously_examined": True,
        "genuine_fresh_holdout": False,
    }


def inventory() -> dict[str, Any]:
    files = sorted(HIST.glob("*_M5.csv")) if HIST.is_dir() else []
    return {
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "original_ai_rl": "ORIGINAL_DECISION_NOT_REPRODUCIBLE",
        "original_strategies": "KEEP_DISABLED",
        "stage_e_family": "STOP_EXPERIMENTAL_STRATEGY_FAMILY",
        "economic_events": "UNAVAILABLE",
        "financing": "UNAVAILABLE",
        "pairs": [inspect_csv(p) for p in files],
        "m1_present": False,
        "consensus_forecast": "not_modified",
    }
