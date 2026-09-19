"""Machine-readable decision snapshot for offline analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DecisionSnapshot:
    timestamp: datetime
    symbol: str
    side: str
    strategy: str
    horizon: str
    route: str
    entry_price: float
    reference_mid: float
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    lookback: int = 0
    atr: float | None = None
    atr_percentile: float | None = None
    spread: float | None = None
    spread_pips: float | None = None
    spread_over_atr: float | None = None
    ma_fast: float | None = None
    ma_slow: float | None = None
    rsi: float | None = None
    macd: float | None = None
    trend: float | None = None
    volatility: float | None = None
    ema_slope: float | None = None
    ema_separation_atr: float | None = None
    adx: float | None = None
    distance_from_mean_atr: float | None = None
    recent_range_atr: float | None = None
    volatility_state: str = ""
    session: str = ""
    hour_utc: int | None = None
    hour_london: int | None = None
    day_of_week: int | None = None
    m5_trend: str = ""
    m15_trend: str = ""
    h1_trend: str = ""
    h4_trend: str = ""
    htf_agreement: str = ""
    regime: str = ""
    signal_confidence: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    sl_distance: float | None = None
    tp_distance: float | None = None
    pre_move_atr: float | None = None
    dist_swing_atr: float | None = None
    research_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            d["timestamp"] = ts.isoformat()
        return d
