"""Explicit shadow assumptions. Live env is never required and never mutated."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from forex_bot.shadow.cost_model import COST_MODEL_VERSION, TABLE_HALF_SPREADS
from forex_bot.shadow.reasons import STRATEGY_NAMES
from forex_bot.shadow.tracks import TRACK_B_LABEL

PAIRS: tuple[str, ...] = (
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
)

# Table half-spreads (estimates). Runtime missing-quote fallback is cost_model v2.
HALF_SPREADS: dict[str, float] = dict(TABLE_HALF_SPREADS)


@dataclass(frozen=True)
class ShadowConfig:
    """Conservative defaults aligned with the live book, plus shadow-only loss caps."""

    enabled: bool = False
    label: str = "SIMULATED_SHADOW_NOT_BROKER"
    track_b_label: str = TRACK_B_LABEL
    cost_model_version: str = COST_MODEL_VERSION
    starting_nav_gbp: float = 97.15
    notional_pct_of_nav: float = 0.02
    max_portfolio_notional_pct: float = 0.06
    per_trade_risk_pct: float = 0.005
    max_portfolio_stop_risk_pct: float = 0.02
    max_concurrent_positions: int = 3
    max_same_usd_direction: int = 2
    sl_atr_mult: float = 2.0
    tp_risk_reward: float = 2.0
    slippage_atr_fraction: float = 0.3
    scalp_spread_mult: float = 1.2
    swing_spread_mult: float = 0.8
    max_half_spread_over_atr: float = 0.35
    scalp_lookback: int = 50
    swing_lookback: int = 100
    min_bars: int = 40
    stale_bar_seconds: float = 700.0  # > one M5 bar plus slack
    fx_session_always: bool = True
    fx_week_close_hour: int = 21
    weekend_flatten_minutes: float = 15.0
    daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.05
    gbp_usd_fallback: float = 1.35
    timeframe_seconds: int = 300
    strategies: tuple[str, ...] = STRATEGY_NAMES
    pairs: tuple[str, ...] = PAIRS
    store_dir: Path | None = None
    cost_scenario: str = "base"
    quote_aware: bool = True
    result_label: str = "EXPERIMENTAL_HEURISTIC_OFFLINE"
    keep_traces: bool = True
    history_window: int = 0

    extra: dict[str, str] = field(default_factory=dict)

    def require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("shadow evaluation is disabled until an operator opts in")
