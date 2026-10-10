"""Write Stage G.1 artifacts without overwriting Stage G results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.conversion import (
    describe_stage_g_limitation,
    fixture_table,
)
from forex_bot.research.adaptive_ensemble.g1_freeze import (
    change_log,
    frozen_model_manifest,
)
from forex_bot.research.adaptive_ensemble.importer import (
    data_source_inventory,
    import_local_csv,
)
from forex_bot.research.adaptive_ensemble.portfolio import readiness_assessment
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol
from forex_bot.research.adaptive_ensemble.provenance import sha256_file
from forex_bot.research.adaptive_ensemble.validation_spec import future_validation_spec

G1_DIR = Path("data") / "research" / "adaptive_ensemble" / "g1"
STAGE_G_DIR = Path("data") / "research" / "adaptive_ensemble"
HIST = Path("data") / "historical"
PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"]
REPORTED_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def run(*, git_revision: str) -> dict[str, Any]:
    proto = load_protocol()
    hash_ok = proto["integrity_hash"] == REPORTED_HASH == integrity_hash(proto)
    g_files = {
        "protocol_v1.json": sha256_file(STAGE_G_DIR / "protocol_v1.json") if (STAGE_G_DIR / "protocol_v1.json").is_file() else None,
        "evaluation_results.json": sha256_file(STAGE_G_DIR / "evaluation_results.json")
        if (STAGE_G_DIR / "evaluation_results.json").is_file()
        else None,
        "assessment.json": sha256_file(STAGE_G_DIR / "assessment.json") if (STAGE_G_DIR / "assessment.json").is_file() else None,
    }
    sources = data_source_inventory()
    provenance = []
    quality = []
    new_after = 0
    for pair in PAIRS:
        path = HIST / f"{pair}_M5.csv"
        imported = import_local_csv(path, pair=pair)
        provenance.append(imported.provenance)
        if imported.quality:
            quality.append(imported.quality)
        new_after += int((imported.provenance.get("overlap_stage_eg") or {}).get("new_after_n") or 0)
    model = frozen_model_manifest(git_revision=git_revision, protocol_hash=proto["integrity_hash"])
    model_path = G1_DIR / "model_manifest.json"
    _write(model_path, model)
    model_hash = sha256_file(model_path)
    spec = future_validation_spec(protocol_hash=proto["integrity_hash"], model_manifest_hash=model_hash)
    _write(G1_DIR / "future_validation_spec.json", spec)
    _write(G1_DIR / "data_source_inventory.json", sources)
    _write(G1_DIR / "provenance_report.json", {"pairs": provenance, "new_post_aug2026_rows": new_after})
    _write(G1_DIR / "quality_report.json", {"pairs": quality})
    _write(G1_DIR / "multi_pair_readiness.json", readiness_assessment())
    _write(G1_DIR / "conversion_status.json", describe_stage_g_limitation())
    _write(G1_DIR / "change_log.json", {"changes": change_log()})
    classification = "VALIDATION_INFRASTRUCTURE_READY_DATA_PENDING"
    if not hash_ok:
        classification = "DATA_OR_SAFETY_INTEGRITY_BLOCKED"
    readiness = {
        "stage": "G.1",
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "stage_g_assessment_unchanged": "EXPLORATORY_NO_CREDIBLE_EDGE",
        "protocol_hash_verified": hash_ok,
        "stage_g_artifact_hashes": g_files,
        "git_revision": git_revision,
        "new_post_aug2026_rows": new_after,
        "external_data_acquired": False,
        "gbp_conversion": "GBP_CONVERSION_UNVERIFIED",
        "dynamic_state_schema": "exp_weights_v2",
        "classification": classification,
        "fixture_rate_table_rows": len(fixture_table()._rows),
        "validation_started": False,
    }
    _write(G1_DIR / "readiness_manifest.json", readiness)
    _write(G1_DIR / "baseline_audit.json", {
        "git_revision": git_revision,
        "protocol_id": proto["protocol_id"],
        "protocol_hash": proto["integrity_hash"],
        "protocol_hash_verified": hash_ok,
        "stage_g_artifacts_preserved": g_files,
    })
    return readiness


if __name__ == "__main__":
    print(json.dumps(run(git_revision="UNSET"), indent=2))
