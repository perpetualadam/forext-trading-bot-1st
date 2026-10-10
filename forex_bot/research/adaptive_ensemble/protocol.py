"""Frozen Stage G research protocol. Do not overwrite after seeing results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble import LABEL, PROTOCOL_ID

PROTOCOL_VERSION = "1"
DEFAULT_PATH = Path("data") / "research" / "adaptive_ensemble" / "protocol_v1.json"

PROTOCOL: dict[str, Any] = {
    "protocol_id": PROTOCOL_ID,
    "version": PROTOCOL_VERSION,
    "label": LABEL,
    "status": "FROZEN",
    "research_question": (
        "Does a market-aware adaptive selection or ensemble approach improve net, "
        "risk-adjusted outcomes over simple, prespecified benchmarks after realistic "
        "costs, without relying on hindsight or excessive model complexity?"
    ),
    "secondary_questions": [
        "Which regime features are computable without look-ahead?",
        "Does voting improve decision quality versus a single proxy?",
        "Do delayed-outcome exponential weights outperform equal weights?",
        "Does NO TRADE reduce low-quality exposure?",
        "Are any apparent gains concentrated in one pair or short window?",
        "Are improvements robust to severe costs?",
        "Does extra complexity justify itself versus rotation or no-trade?",
    ],
    "hypotheses": {
        "H1_regime": "Trend proxies may be more suitable in persistent directional regimes; this is untested.",
        "H2_vote": "Requiring agreement among distinct proxies may reduce conflicting trades.",
        "H3_weights": "Delayed exponential weights may down-weight recently costly proxies.",
        "H4_no_trade": "Abstaining when regime is uncertain or spread/ATR is high may cut cost drag.",
    },
    "candidates": [
        "proxy_trend_ma_slope_v1",
        "proxy_rsi_mean_reversion_v1",
        "proxy_atr_expansion_breakout_v1",
    ],
    "candidate_notes": (
        "These are new Stage G research hypotheses, not reconstructions of the original "
        "AI/RL bot and not retunes of the rejected Stage E heuristic family."
    ),
    "original_strategies": "KEEP_DISABLED",
    "stage_e_family": "STOP_EXPERIMENTAL_STRATEGY_FAMILY",
    "original_ai_rl_fidelity": "ORIGINAL_DECISION_NOT_REPRODUCIBLE",
    "pairs": ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"],
    "timeframe": "M5 completed bars",
    "data_provenance": "data/historical/*_M5.csv Stage E inventory Sep 2025–Aug 2026",
    "previously_examined_period": "2025-09-01/2026-08-31",
    "genuine_fresh_holdout": False,
    "development_fraction": 0.40,
    "validation_fraction": 0.20,
    "previously_examined_remainder_fraction": 0.40,
    "remainder_label": "PREVIOUSLY_EXAMINED_NOT_UNSEEN",
    "execution": {
        "fill": "next_bar_executable_bid_ask",
        "same_bar_sl_tp": "conservative_skip_if_ambiguous",
        "start_nav_gbp": 97.0,
        "start_nav_label": "SIMULATION_ASSUMPTION_NOT_BROKER_BALANCE",
        "units": 1000.0,
        "gbp_usd_fx": 1.35,
        "gbp_fx_label": "ESTIMATE",
        "financing": "UNAVAILABLE",
        "daily_loss_halt_pct": 0.02,
        "max_dd_halt_pct": 0.05,
        "max_hold_bars": 24,
        "sl_atr": 1.5,
        "tp_atr": 2.0,
        "decision_stride": 12,
    },
    "cost_scenarios": ["base", "conservative", "severe"],
    "baselines": [
        "no_trade",
        "single_proxy_trend",
        "deterministic_rotation",
        "equal_weight_vote",
        "regime_selection",
        "dynamic_exp_weights",
    ],
    "metrics": [
        "trade_count",
        "gross_pnl_gbp",
        "net_pnl_gbp",
        "profit_factor",
        "win_rate",
        "max_drawdown",
        "abstention_rate",
        "exposure_bars",
        "turnover",
    ],
    "min_trades_for_comparison": 30,
    "uncertainty": "block-bootstrap of trade P&L is not claimed; overlapping holds are dependent",
    "stop_conditions": [
        "No genuine unseen future period exists; do not claim final holdout validation.",
        "Do not retune after viewing remainder results.",
        "A system with zero trades is not profitable.",
        "Sign flip under severe costs rejects an edge claim.",
    ],
    "decision_rules": {
        "RESEARCH_INFRASTRUCTURE_ONLY": "Insufficient fidelity or no genuine holdout for a trading claim.",
        "EXPLORATORY_NO_CREDIBLE_EDGE": "Adaptive methods do not beat no-trade and rotation after severe costs.",
        "EXPLORATORY_PROMISING_REQUIRES_FRESH_VALIDATION": "Exploratory remainder looks better but data is previously examined.",
        "RESEARCH_BLOCKED_DATA_OR_SAFETY": "Leakage, accounting, or isolation defect.",
    },
}


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    body = {k: v for k, v in payload.items() if k != "integrity_hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def integrity_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def freeze_document(*, frozen_utc: str | None = None) -> dict[str, Any]:
    doc = dict(PROTOCOL)
    doc["frozen_utc"] = frozen_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc["integrity_hash"] = integrity_hash(doc)
    return doc


def write_protocol(path: Path | None = None) -> dict[str, Any]:
    dest = path or DEFAULT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        existing = json.loads(dest.read_text(encoding="utf-8"))
        if existing.get("integrity_hash") == integrity_hash(existing):
            return existing
        raise RuntimeError("existing protocol hash mismatch; refuse overwrite")
    doc = freeze_document()
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return doc


def load_protocol(path: Path | None = None) -> dict[str, Any]:
    dest = path or DEFAULT_PATH
    blob = json.loads(dest.read_text(encoding="utf-8"))
    if integrity_hash(blob) != blob.get("integrity_hash"):
        raise ValueError("protocol integrity failure")
    return blob
