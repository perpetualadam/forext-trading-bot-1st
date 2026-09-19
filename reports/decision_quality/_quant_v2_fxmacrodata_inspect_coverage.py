"""Inspect saved no-key coverage JSON. No new network calls."""

from __future__ import annotations

import json
from pathlib import Path

src = Path("data/research/external/fxmacrodata_probe/raw/v1_predictions_coverage_usd.json")
payload = json.loads(src.read_text(encoding="utf-8"))
print("access", payload.get("access"))
print("notes", payload.get("notes"))
print("prediction_classes", payload.get("prediction_classes"))
print("official_forecast_sources", payload.get("official_forecast_sources"))
wanted = {
    "inflation",
    "non_farm_payrolls",
    "policy_rate",
    "policy_rate_midpoint",
}
for row in payload.get("indicators") or []:
    if row.get("indicator") in wanted:
        print(row["indicator"], "has_consensus_source=", row.get("has_consensus_source"),
              "classes=", row.get("classes_with_sources"))
