"""Deterministic R.35 data-pipeline demonstration. No model, no network, no orders."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["DOTENV_PATH"] = str(OUT / "missing.env")

import dotenv

dotenv.load_dotenv = lambda *a, **k: False


class _Blocked(socket.socket):
    def connect(self, *_a, **_k):
        raise OSError("R35_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.dataset import build_research_summary
from forex_bot.research.learning.protocol import (
    EVALUATION_PROTOCOL,
    EVALUATION_PROTOCOL_SHA256,
    FEATURE_SCHEMA,
    FEATURE_SCHEMA_SHA256,
    LABEL_PROTOCOL,
    LABEL_PROTOCOL_SHA256,
)

import pandas as pd


def _inventory(path: Path) -> dict:
    frame = pd.read_csv(path)
    _clean, quality = validate_frame(frame)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": file_sha256(path),
        "instrument": path.stem.rsplit("_", 1)[0],
        "timeframe": path.stem.rsplit("_", 1)[1],
        "columns": list(frame.columns),
        **quality,
    }


def main() -> None:
    (OUT / "04_feature_schema.json").write_text(json.dumps(FEATURE_SCHEMA, indent=2), encoding="utf-8")
    (OUT / "06_label_protocol.json").write_text(json.dumps(LABEL_PROTOCOL, indent=2), encoding="utf-8")
    (OUT / "09_evaluation_protocol.json").write_text(json.dumps(EVALUATION_PROTOCOL, indent=2), encoding="utf-8")
    history = ROOT / "data" / "historical"
    inventory = [_inventory(path) for path in sorted(history.glob("*.csv"))]
    (OUT / "02_source_inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    source = history / "EUR_USD_M5.csv"
    first = build_research_summary(source, instrument="EUR_USD", timeframe="M5")
    second = build_research_summary(source, instrument="EUR_USD", timeframe="M5")
    comparison = {
        "summaries_match": first["summary_sha256"] == second["summary_sha256"],
        "journal_ids_match": first["journal_id_sha256"] == second["journal_id_sha256"],
        "feature_schema_sha256": FEATURE_SCHEMA_SHA256,
        "label_protocol_sha256": LABEL_PROTOCOL_SHA256,
        "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
        "source_sha256": first["dataset_sha256"],
    }
    (OUT / "10_demonstration.json").write_text(json.dumps(first, indent=2, default=str), encoding="utf-8")
    (OUT / "11_reproducibility.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    if not comparison["summaries_match"]:
        raise SystemExit("R35_DEMONSTRATION_NOT_REPRODUCIBLE")
    print(json.dumps({
        "rows_read": first["rows_read"],
        "feature_rows_valid": first["feature_rows_valid"],
        "warmup_exclusions": first["warmup_exclusions"],
        "labelled_observations": first["labelled_observations"],
        "unevaluable_observations": first["unevaluable_observations"],
        "journal_entries": first["journal_entries"],
        "prediction_unavailable_count": first["prediction_unavailable_count"],
        "summaries_match": True,
    }))


if __name__ == "__main__":
    main()
