"""Fidelity matrix for original-bot replay. EXACT only when source-equivalent under identical inputs."""

from __future__ import annotations

from typing import Any

EXACT = "EXACT"
PARTIAL = "PARTIAL"
UNAVAILABLE = "UNAVAILABLE"
NOT_TESTED = "NOT_TESTED"

# Stage-level claims. Do not upgrade to EXACT without deterministic evidence.
FIDELITY_MATRIX: dict[str, dict[str, Any]] = {
    "market_data": {
        "file": "forex_bot/oanda_client.py:fetch_ohlcv",
        "offline": "PARTIAL",
        "note": "Replay uses supplied candles only; live GET is not used. No look-ahead if caller walks chronologically.",
    },
    "compute_indicators": {
        "file": "forex_bot/indicators.py:compute_indicators",
        "offline": "EXACT",
        "note": "Pure function of OHLCV + lookback. Same source as live.",
    },
    "select_strategy": {
        "file": "forex_bot/strategy_meta.py:select_strategy",
        "offline": "PARTIAL",
        "note": "Hybrid ATR family routing is deterministic. Name draw uses np.random.choice; Track A uses argmax + alpha tie-break.",
    },
    "allocate": {
        "file": "forex_bot/strategy_meta.py:allocate",
        "offline": "PARTIAL",
        "note": "Requires a local PnL score snapshot. Must not read live strategies.active.",
    },
    "volatility_ok": {
        "file": "forex_bot/session_rules.py:volatility_ok",
        "offline": "EXACT",
        "note": "Pure function of ATR series.",
    },
    "quant_stub": {
        "file": "forex_bot/ai_ensemble.py:_quant_stub_vote",
        "offline": "EXACT",
        "note": "Live ENSEMBLE_MODE=quant, 1 LocalLLM, 0 API voters. Stub ignores nn_pred. Track A copies the math without skip-log I/O.",
    },
    "ai_api_voters": {
        "file": "forex_bot/ai_ensemble.py:_fill_external_voters",
        "offline": "UNAVAILABLE",
        "note": "Not attached in the current live process. Historical API votes were not logged.",
    },
    "nn_pred": {
        "file": "forex_bot/nn_pred.py:compute_nn_pred",
        "offline": "EXACT",
        "note": "Live NN_PRED_MODE=seq. Unused by the quant stub. SeqModel reconstructable from chronological closes.",
    },
    "rl_decide": {
        "file": "forex_bot/rl_agent.py:RLAgent.decide",
        "offline": "UNAVAILABLE",
        "note": "Epsilon-greedy over an in-memory Q table with no disk snapshot. Empty table + random.choice is not reproducible.",
    },
    "position_sizing": {
        "file": "forex_bot/trading.py:position_sizing",
        "offline": "PARTIAL",
        "note": "Notional-pct path copied without importing trading.py (which imports oanda_exec). Env at decision time may differ.",
    },
    "risk_filters": {
        "file": "forex_bot/bot_loop.py + portfolio_exposure.py",
        "offline": "PARTIAL",
        "note": "Shadow-only caps plus a local book. Live has no daily-loss/max-DD kill switch.",
    },
    "evolve": {
        "file": "forex_bot/bot_loop.py:evolve",
        "offline": "PARTIAL",
        "note": "Needs chronological per-strategy PnL lists. Must not write persist_evolve_disable.",
    },
    "broker_execution": {
        "file": "forex_bot/oanda_exec.py",
        "offline": "UNAVAILABLE",
        "note": "Intentionally not imported. Fills are simulated.",
    },
}


def overall_original_fidelity() -> str:
    """Live entries cannot be reproduced faithfully while RL Q-state is missing."""
    return "NO"
