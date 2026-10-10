"""Track A: original-bot replay adapter. Broker-disconnected. Read-only models.

Does not import oanda_exec, trading, bot_loop, or live_safety operator APIs.
Does not mutate forex_bot.strategy_meta.strategies.
RL without a supplied Q snapshot is NOT_REPRODUCIBLE — never fabricated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.indicators import compute_indicators
from forex_bot.session_rules import volatility_ok
from forex_bot.shadow.fidelity import EXACT, PARTIAL, UNAVAILABLE
from forex_bot.shadow.reasons import (
    SCALP_FAMILY,
    STRATEGY_NAMES,
    SWING_FAMILY,
    ShadowReason,
)
from forex_bot.shadow.signals import last_atr
from forex_bot.shadow.tracks import TRACK_A, TRACK_A_LABEL
from forex_bot.symbols import normalize_oanda_symbol

_STUB_SMA_EPS = 1e-6
_STUB_MOM_THR = 0.0001
_STUB_CONF_SCALE = 1000.0


@dataclass
class ShadowMetaSnapshot:
    """Local copy of meta scores. Never the live Strategy objects."""

    pnl: dict[str, list[float]] = field(default_factory=dict)
    active: dict[str, bool] = field(
        default_factory=lambda: {n: True for n in STRATEGY_NAMES}
    )


@dataclass
class TrackADecision:
    track: str = TRACK_A
    label: str = TRACK_A_LABEL
    eval_time: datetime | None = None
    symbol: str = ""
    strategy: str | None = None
    horizon: str | None = None
    lookback: int | None = None
    direction: str | None = None
    quant_allow: bool | None = None
    quant_confidence: float | None = None
    rl_action: str | None = None
    reason: str = ShadowReason.NOT_REPRODUCIBLE
    fidelity_overall: str = "NO"
    stages: dict[str, str] = field(default_factory=dict)
    detail: str = ""
    simulated: bool = True


def _sharpe(rows: list[float]) -> float:
    if len(rows) <= 10:
        return 0.0
    s = pd.Series(rows, dtype=float)
    return float(s.mean() / (s.std() + 1e-6))


def allocate_from_snapshot(snap: ShadowMetaSnapshot) -> dict[str, float]:
    scores: dict[str, float] = {}
    total = 0.0
    for name in STRATEGY_NAMES:
        if not snap.active.get(name, True):
            continue
        data = snap.pnl.get(name, [])
        s = max(_sharpe(data), 0.0)
        scores[name] = s
        total += s
    if not scores:
        return {}
    if total == 0.0:
        n = len(scores)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in scores.items()}


def select_name_argmax(weights: dict[str, float]) -> str | None:
    """PARTIAL vs live np.random.choice: highest weight, alphabetical tie-break."""
    if not weights:
        return None
    best = max(weights.values())
    names = sorted(k for k, v in weights.items() if v == best)
    return names[0]


def hybrid_family(atr_last: float, atr_median: float, threshold: float = 1.0) -> str:
    if atr_median <= 0 or math.isnan(atr_last):
        return "scalp"
    if atr_last >= atr_median * threshold:
        return "scalp"
    return "swing"


def quant_stub_vote(ma_fast: float, ma_slow: float, returns: float, atr: float) -> dict[str, Any]:
    """Source-equivalent to ai_ensemble._quant_stub_vote without skip-log I/O."""
    try:
        sma_fast = float(ma_fast)
        sma_slow = float(ma_slow)
    except (TypeError, ValueError):
        return {"allow": False, "confidence": 0.0, "direction": None, "fidelity": EXACT}
    if math.isnan(sma_fast) or math.isnan(sma_slow):
        return {"allow": False, "confidence": 0.0, "direction": None, "fidelity": EXACT}
    if sma_fast > sma_slow + _STUB_SMA_EPS:
        direction: str | None = "BUY"
    elif sma_fast < sma_slow - _STUB_SMA_EPS:
        direction = "SELL"
    else:
        return {"allow": False, "confidence": 0.0, "direction": None, "fidelity": EXACT}
    try:
        ret = float(returns)
    except (TypeError, ValueError):
        ret = 0.0
    if math.isnan(ret):
        ret = 0.0
    mom = abs(ret)
    vol_ok = atr > 0 and not math.isnan(atr)
    allow = mom > _STUB_MOM_THR and bool(vol_ok)
    conf = min(1.0, max(0.0, mom * _STUB_CONF_SCALE))
    return {"allow": allow, "confidence": conf, "direction": direction, "fidelity": EXACT}


def rl_decide(
    state: str,
    q_table: dict[str, dict[str, float]] | None,
) -> tuple[str | None, str]:
    """Do not fabricate actions. Missing Q → NOT_REPRODUCIBLE."""
    _ = state
    if not q_table:
        return None, ShadowReason.NOT_REPRODUCIBLE
    row = q_table.get(state)
    if not row:
        return None, ShadowReason.NOT_REPRODUCIBLE
    best = max(row.values())
    names = sorted(a for a, v in row.items() if v == best)
    return names[0], ShadowReason.PARTIALLY_REPRODUCIBLE


def evaluate_original_bar(
    *,
    symbol: str,
    history: pd.DataFrame,
    bar_time: datetime,
    snap: ShadowMetaSnapshot | None = None,
    q_table: dict[str, dict[str, float]] | None = None,
    hybrid: bool = True,
    scalp_lookback: int = 50,
    swing_lookback: int = 100,
    route_lookback: int = 60,
    hybrid_atr_threshold: float = 1.0,
) -> TrackADecision:
    """Replay one completed bar. Never touches live strategy objects or the broker."""
    symbol = normalize_oanda_symbol(symbol)
    stages: dict[str, str] = {
        "compute_indicators": EXACT,
        "volatility_ok": EXACT,
        "quant_stub": EXACT,
        "select_strategy": PARTIAL,
        "allocate": PARTIAL,
        "rl_decide": UNAVAILABLE,
        "broker_execution": UNAVAILABLE,
    }
    decision = TrackADecision(eval_time=bar_time, symbol=symbol, stages=stages)
    if history is None or history.empty or len(history) < 20:
        decision.reason = ShadowReason.INSUFFICIENT_DATA
        decision.detail = "need>=20_bars"
        return decision
    snap = snap or ShadowMetaSnapshot()
    df_route = compute_indicators(history, lookback=route_lookback)
    atr_series = df_route["atr"].dropna() if "atr" in df_route.columns else pd.Series(dtype=float)
    if hybrid and len(atr_series) >= 5:
        family = hybrid_family(
            float(df_route["atr"].iloc[-1]),
            float(atr_series.median()),
            hybrid_atr_threshold,
        )
        pool = tuple(SCALP_FAMILY) if family == "scalp" else tuple(SWING_FAMILY)
        lookback = scalp_lookback if family == "scalp" else swing_lookback
        horizon = family
    else:
        pool = STRATEGY_NAMES
        lookback = scalp_lookback
        horizon = "legacy"
    weights = {k: v for k, v in allocate_from_snapshot(snap).items() if k in pool}
    if not weights:
        weights = {k: 1.0 / len(pool) for k in pool}
    name = select_name_argmax(weights)
    decision.strategy = name
    decision.horizon = horizon
    decision.lookback = lookback
    df = compute_indicators(history, lookback=lookback)
    if df.empty or "atr" not in df.columns:
        decision.reason = ShadowReason.INSUFFICIENT_DATA
        return decision
    if not volatility_ok(df):
        decision.reason = ShadowReason.QUANT_REJECT
        decision.detail = "volatility_ok=false"
        return decision
    row = df.iloc[-1]
    ma_fast = float(row["ma_fast"]) if "ma_fast" in df.columns else float("nan")
    ma_slow = float(row["ma_slow"]) if "ma_slow" in df.columns else float("nan")
    atr_v = last_atr(df)
    ret_1 = float(df["close"].pct_change().iloc[-1]) if len(df) > 1 else 0.0
    vote = quant_stub_vote(ma_fast, ma_slow, ret_1, atr_v)
    decision.quant_allow = bool(vote["allow"])
    decision.quant_confidence = float(vote["confidence"])
    decision.direction = vote["direction"]
    if not vote["allow"]:
        decision.reason = ShadowReason.QUANT_REJECT
        decision.detail = "quant_stub_reject"
        decision.fidelity_overall = "PARTIAL"
        return decision
    rl_action, _rl_reason = rl_decide(
        f"{round(float(row.get('trend', 0.0) or 0.0), 4)}_{round(float(row.get('volatility', 0.0) or 0.0), 6)}",
        q_table,
    )
    decision.rl_action = rl_action
    if rl_action is None:
        decision.reason = ShadowReason.NOT_REPRODUCIBLE
        decision.detail = "rl_q_table_unavailable"
        decision.fidelity_overall = "NO"
        stages["rl_decide"] = UNAVAILABLE
        return decision
    stages["rl_decide"] = PARTIAL
    if rl_action == "SKIP" or (rl_action in ("BUY", "SELL") and rl_action != decision.direction):
        decision.reason = ShadowReason.QUANT_REJECT
        decision.detail = f"rl_gate:{rl_action}"
        decision.fidelity_overall = "PARTIAL"
        return decision
    decision.reason = ShadowReason.PARTIALLY_REPRODUCIBLE
    decision.detail = "quant_ok_rl_partial_argmax_strategy"
    decision.fidelity_overall = "PARTIAL"
    return decision
