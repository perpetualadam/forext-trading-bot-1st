"""Synthetic risk-state seed for offline tests. Not a production threshold."""

from __future__ import annotations

import json
import os
from pathlib import Path


def install_synthetic_risk_context(stage: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    path = stage / "r25_synthetic_risk_state.json"
    document = {
        "schema_version": 1,
        "peak_equity": 1_000_000_000_000.0,
        "day_baselines": {"2026-01-07": 1_000_000_000.0},
        "realised_by_day": {"2026-01-07": 0.0},
        "account_id": "synthetic-offline",
        "currency": "USD",
        "revision": 1,
        "events": {},
        "exposure_positions": [],
        "exposure_orders": [],
        "reconciliation": {
            "status": "synthetic_offline",
            "account_id": "synthetic-offline",
            "currency": "USD",
            "snapshot_id": "synthetic-seed",
            "as_of": "2026-01-07T12:00:00+00:00",
            "equity_source": "synthetic_seed",
            "sequence_evidence": "absent",
            "last_sequence": None,
        },
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "2"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
    os.environ["RISK_STATE_PATH"] = str(path)
