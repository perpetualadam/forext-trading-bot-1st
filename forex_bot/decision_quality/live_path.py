"""Frozen map of the *current* live decision path.

This module documents production call flow. It does not change routing, signals,
SL/TP, sizing, or execution. The offline engine reuses the named production
functions below instead of re-implementing them.
"""

from __future__ import annotations

# Exact live evaluate() path (do not refactor production for the audit).
LIVE_CALL_PATH = (
    "symbol",
    "candle load M5 (HYBRID_OHLCV_COUNT)",
    "manage open risk first (close-only SL/TP vs last close; profit_protection; weekend flatten)",
    "pre_trade_entry_blocked_reason (reconcile / operational gates)",
    "compute_indicators(route_lookback=HYBRID_ROUTE_LOOKBACK)",
    "select_strategy → horizon scalp|swing|legacy + lookback",
    "compute_indicators(lookback) + volatility_ok",
    "seq_model + compute_nn_pred",
    "ai.vote (quant stub and/or API voters) → allow + BUY/SELL",
    "rl_agent.decide (SKIP blocks; BUY/SELL must match AI)",
    "v2_shadow observe (record-only; exception ignored; return discarded; no authority)",
    "sl_tp_distance_for_entry + position_sizing + notional/risk/USD-direction guards",
    "is_live_trading / open_fill_path → broker | simulate | window_paper",
    "broker market open or local fill; SL/TP placed from fill ± distances",
)

PRODUCTION_REUSED = {
    "indicators": "forex_bot.indicators.compute_indicators",
    "routing": "forex_bot.strategy_meta.select_strategy",
    "quant_direction": "forex_bot.ai_ensemble._quant_stub_vote",
    "sl_tp": "forex_bot.trading.sl_tp_distance_for_entry",
    "half_spread": "forex_bot.trading.simulated_half_spread",
    "session_week": "forex_bot.session_rules.fx_market_open_at",
    "session_hours": "forex_bot.session_rules.in_active_session_at",
    "volatility_filter": "forex_bot.session_rules.volatility_ok",
    "pips": "forex_bot.profit_protection.unrealized_profit_pips",
    "pip_size": "forex_bot.profit_protection.pip_size",
}

# Live direction is NOT computed from the strategy name. Names (trend, swing_mean_reversion, …)
# only label the meta-learner / hybrid pool. BUY/SELL comes from the AI ensemble (default:
# ma_fast vs ma_slow + momentum threshold).
STRATEGY_NAME_DOES_NOT_SET_SIDE = True

# Live SL/TP management in evaluate() compares the latest *close* only, not high/low.
LIVE_EXIT_USES_CLOSE_ONLY = True
