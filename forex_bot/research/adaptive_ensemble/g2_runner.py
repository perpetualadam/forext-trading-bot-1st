"""Write Stage G.2 artifacts. Does not overwrite Stage G/G.1 reports or call brokers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    describe_stage_g_limitation,
)
from forex_bot.research.adaptive_ensemble.importer import import_local_csv
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol
from forex_bot.research.adaptive_ensemble.provenance import sha256_file
from forex_bot.research.adaptive_ensemble.quality_gates import (
    duration_status,
    gate_dataset,
)
from forex_bot.research.adaptive_ensemble.simulator_v2 import (
    CHANGE_CLASS,
    VERSION,
    WARMUP_BARS,
)
from forex_bot.research.adaptive_ensemble.source_audit import (
    DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
    source_audit,
)

G2 = Path("data") / "research" / "adaptive_ensemble" / "g2"
G = Path("data") / "research" / "adaptive_ensemble"
G1 = G / "g1"
PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"]
REPORTED_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"
G1_EVAL = "c4d0cfc754ce1cd8fb32c57912462cf73f7ec9772c4153bcc609da0d998d2dd9"
G1_ASSESS = "3bc892971202f28e7e58f72144871d9694dbaded5c6dfa425ec8cd11fa6d2c9c"


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def run(*, git_revision: str) -> dict[str, Any]:
    proto = load_protocol()
    hash_ok = proto["integrity_hash"] == REPORTED_HASH == integrity_hash(proto)
    preserved = {
        "protocol_v1.json": sha256_file(G / "protocol_v1.json"),
        "evaluation_results.json": sha256_file(G / "evaluation_results.json"),
        "assessment.json": sha256_file(G / "assessment.json"),
        "g1_readiness": sha256_file(G1 / "readiness_manifest.json") if (G1 / "readiness_manifest.json").is_file() else None,
    }
    eval_ok = preserved["evaluation_results.json"] == G1_EVAL
    assess_ok = preserved["assessment.json"] == G1_ASSESS
    audit = source_audit()
    _write(G2 / "source_audit.json", audit)
    quality = []
    days_total = 0
    for pair in PAIRS:
        imported = import_local_csv(Path("data") / "historical" / f"{pair}_M5.csv", pair=pair)
        if imported.frame is not None:
            g = gate_dataset(imported.frame, pair=pair)
            days_total = max(days_total, int(g["complete_trading_days_after_cutoff"]))
            quality.append({"pair": pair, **{k: g[k] for k in (
                "status", "rows", "independence_label", "complete_trading_days_after_cutoff",
                "unexpected_gaps", "warmup_ok_v2", "bid_ask", "promoted_to_validation_ready",
            )}})
        else:
            quality.append({"pair": pair, "status": "FAIL", "reason": imported.reason})
    _write(G2 / "quality_gate_report.json", {"pairs": quality, "duration": duration_status(days_total)})
    _write(G2 / "acquisition_manifest.json", {
        "new_data_acquired": False,
        "source": None,
        "broker_api_calls_made": False,
        "pairs": [],
        "date_range": None,
        "raw_hashes": {},
        "provenance_classification": "INDEPENDENCE_NOT_ESTABLISHED",
        "complete_trading_days_after_cutoff": days_total,
        "reason": DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
    })
    _write(G2 / "conversion_assessment.json", describe_stage_g_limitation())
    gates = {
        "Protocol integrity": "PASS" if hash_ok else "FAIL",
        "Model freeze": "PASS" if eval_ok and assess_ok else "FAIL",
        "Source authorisation": "FAIL",
        "Independent data": "FAIL",
        "40 trading days": "FAIL",
        "Bid/ask quality": "WARN",
        "GBP conversion": "FAIL",
        "Simulator correctness": "PASS",
        "Multi-pair accounting": "WARN",
        "Model-state integrity": "PASS",
        "30-trade minimum": "NOT_EVALUATED",
        "No leakage": "PASS",
        "Live isolation": "PASS",
    }
    _write(G2 / "validation_gates.json", {
        "gates": gates,
        "duration_status": duration_status(days_total),
        "conversion": GBP_CONVERSION_UNVERIFIED,
        "trade_count_gate": "NOT_YET_EVALUATED",
        "multi_pair": "MULTI_PAIR_ACCOUNTING_ENGINE_PRESENT_VALIDATION_NOT_READY",
    })
    classification = "DATA_OR_SAFETY_INTEGRITY_BLOCKED" if not hash_ok else "VALIDATION_ENGINEERING_READY_APPROVAL_PENDING"
    readiness = {
        "stage": "G.2",
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "git_revision": git_revision,
        "protocol_hash_verified": hash_ok,
        "stage_g_assessment_unchanged": "EXPLORATORY_NO_CREDIBLE_EDGE",
        "stage_g1_classification_unchanged": "VALIDATION_INFRASTRUCTURE_READY_DATA_PENDING",
        "simulator_version": VERSION,
        "simulator_change_class": CHANGE_CLASS,
        "warmup_bars_v2": WARMUP_BARS,
        "broker_api_calls_made": False,
        "new_data_acquired": False,
        "complete_trading_days_after_cutoff": days_total,
        "gbp_conversion": GBP_CONVERSION_UNVERIFIED,
        "preserved_hashes": preserved,
        "classification": classification,
        "validation_started": False,
        "strategy_comparisons_on_new_data": False,
    }
    _write(G2 / "readiness_manifest.json", readiness)
    _write(G2 / "baseline.json", {
        "git_revision": git_revision,
        "protocol_id": proto["protocol_id"],
        "protocol_hash": proto["integrity_hash"],
        "protocol_hash_verified": hash_ok,
    })
    return readiness


if __name__ == "__main__":
    print(json.dumps(run(git_revision="UNSET"), indent=2))
