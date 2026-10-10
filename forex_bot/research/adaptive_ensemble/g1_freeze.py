"""Frozen Stage G model package plus G.1 versioned repair layer. Does not retune."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.candidates import GENERATORS, REGIME_MAP
from forex_bot.research.adaptive_ensemble.features import FEATURE_VERSION
from forex_bot.research.adaptive_ensemble.models import SPREAD_ATR_MAX
from forex_bot.research.adaptive_ensemble.protocol import (
    PROTOCOL,
    PROTOCOL_ID,
    PROTOCOL_VERSION,
)
from forex_bot.research.adaptive_ensemble.simulate import SLIPPAGE
from forex_bot.research.adaptive_ensemble.state_v2 import (
    CHANGE_CLASS,
    ETA,
    SCHEMA,
    WEIGHT_MAX,
    WEIGHT_MIN,
)

PKG = Path(__file__).resolve().parent
STAGE_G_FILES = [
    "protocol.py",
    "features.py",
    "candidates.py",
    "models.py",
    "simulate.py",
    "evaluate.py",
]
G1_REPAIR_FILES = [
    "state_v2.py",
    "conversion.py",
    "quality.py",
    "provenance.py",
    "importer.py",
    "accounting.py",
    "portfolio.py",
]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _pkg_ver(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "UNAVAILABLE"


def frozen_model_manifest(*, git_revision: str, protocol_hash: str) -> dict[str, Any]:
    exec_ = dict(PROTOCOL["execution"])
    return {
        "manifest_id": "stage_g_model_package_v1",
        "frozen_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_hash": protocol_hash,
        "feature_version": FEATURE_VERSION,
        "candidate_ids": list(GENERATORS.keys()),
        "candidate_versions": {cid: "1" for cid in GENERATORS},
        "regime_map": dict(REGIME_MAP),
        "vote_min_agree": 2,
        "vote_use_confidence": False,
        "dynamic_weight_schema_stage_g": "exp_weights_v1",
        "dynamic_weight_eta": ETA,
        "weight_bounds": [WEIGHT_MIN, WEIGHT_MAX],
        "initial_weights": {k: 1.0 for k in GENERATORS},
        "spread_atr_filters": dict(SPREAD_ATR_MAX),
        "slippage_atr": dict(SLIPPAGE),
        "no_trade_rules": [
            "no eligible candidate",
            "regime uncertain/unsuitable",
            "signal conflict",
            "spread_excessive",
            "missing features",
        ],
        "execution_assumptions": exec_,
        "risk_assumptions": {
            "daily_loss_halt_pct": exec_["daily_loss_halt_pct"],
            "max_dd_halt_pct": exec_["max_dd_halt_pct"],
            "start_nav_gbp": exec_["start_nav_gbp"],
            "start_nav_label": exec_["start_nav_label"],
            "financing": "UNAVAILABLE",
        },
        "code_file_sha256": {name: _sha(PKG / name) for name in STAGE_G_FILES if (PKG / name).is_file()},
        "git_revision_at_g1": git_revision,
        "python": sys.version.split()[0],
        "dependencies": {
            "pandas": _pkg_ver("pandas"),
            "numpy": _pkg_ver("numpy"),
        },
        "g1_repair_layer": {
            "dynamic_weight_schema": SCHEMA,
            "change_class": CHANGE_CLASS,
            "files": {name: _sha(PKG / name) for name in G1_REPAIR_FILES if (PKG / name).is_file()},
            "inherits_stage_g_historical_results": False,
            "note": "v2 fail-closed state and conversion interface; Stage G v1 silent reset preserved.",
        },
        "stage_g_findings_immutable": {
            "assessment": "EXPLORATORY_NO_CREDIBLE_EDGE",
            "retune": False,
        },
    }


def change_log() -> list[dict[str, str]]:
    return [
        {
            "item": "isolation.FORBIDDEN expanded with oanda_client and oanda_candles_read",
            "class": "NON_BEHAVIOURAL_INFRASTRUCTURE",
        },
        {
            "item": "WeightStateV2 fail-closed persistence",
            "class": CHANGE_CLASS,
        },
        {
            "item": "timestamped GBP conversion interface",
            "class": "NON_BEHAVIOURAL_INFRASTRUCTURE",
        },
        {
            "item": "Stage G quote_to_gbp / WeightState.load / evaluate warmup left unchanged",
            "class": "RESEARCH_MODEL_CHANGE_FORBIDDEN_IN_G1",
        },
    ]
