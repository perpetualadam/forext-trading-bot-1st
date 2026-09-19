"""Production signal wrapper: indicators, routing, quant stub, SL/TP. No broker I/O."""

from __future__ import annotations

import math
import random
from datetime import datetime

import numpy as np
import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.invariants import sl_tp_from_production_distances
from forex_bot.decision_quality.research_features import (
    distance_from_swing_atr,
    htf_alignment,
    htf_trend_labels,
    indicator_research_fields,
    pre_entry_extension_atr,
)
from forex_bot.decision_quality.sessions import classify_session, hour_london, hour_utc
from forex_bot.decision_quality.snapshot import DecisionSnapshot
from forex_bot.indicators import compute_indicators
from forex_bot.session_rules import fx_market_open_at, in_active_session_at, volatility_ok
from forex_bot.strategy_meta import select_strategy
from forex_bot.trading import simulated_half_spread


def _env_int(name: str, default: int) -> int:
    import os

    raw = (os.getenv(name) or "").strip()
    return int(raw) if raw else default


def seeded_select_strategy(symbol: str, routing_df: pd.DataFrame, seed: int) -> tuple[str | None, int, str]:
    """Same algorithm as production ``select_strategy``, with isolated RNG."""
    rng_state = random.getstate()
    np_state = np.random.get_state()
    random.seed(int(seed) % (2**32))
    np.random.seed(int(seed) % (2**32))
    try:
        return select_strategy(symbol, routing_df)
    finally:
        random.setstate(rng_state)
        np.random.set_state(np_state)


def production_quant_decision(df: pd.DataFrame, lookback: int) -> dict:
    """Exact live default direction path: compute_indicators + _quant_stub_vote."""
    ind = compute_indicators(df, lookback=lookback)
    if ind.empty:
        return {"allow": False, "confidence": 0.0, "direction": None, "df": ind}
    last = ind.iloc[-1]
    price = float(last["close"])
    ma_fast = float(last["ma_fast"]) if last["ma_fast"] == last["ma_fast"] else price
    ma_slow = float(last["ma_slow"]) if last["ma_slow"] == last["ma_slow"] else price
    atr = float(last["atr"]) if last["atr"] == last["atr"] else 0.0
    ret_1 = float(ind["close"].pct_change().iloc[-1]) if len(ind) > 1 else 0.0
    vote = _quant_stub_vote(
        {
            "price": price,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "returns": ret_1,
            "atr": atr,
        }
    )
    vote["df"] = ind
    vote["price"] = price
    vote["atr"] = atr
    return vote


def evaluate_signal(
    symbol: str,
    raw: pd.DataFrame,
    now_utc: datetime,
    *,
    seed: int = 42,
    apply_session_hours: bool = False,
    apply_fx_week: bool = True,
    apply_volatility_filter: bool = True,
) -> DecisionSnapshot:
    """
    Offline equivalent of the live *signal* path (not RL, not API voters, not risk gates).

    Live still uses those gates. This function freezes the quant + routing + SL/TP math.
    """
    reasons: list[str] = []
    route_lb = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
    if apply_fx_week and not fx_market_open_at(now_utc):
        reasons.append("FX_WEEK_CLOSED")
        return _blank(symbol, raw, now_utc, "NO_SIGNAL", reasons)
    if apply_session_hours and not in_active_session_at(symbol, now_utc):
        reasons.append("SESSION_HOURS_CLOSED")
        return _blank(symbol, raw, now_utc, "NO_SIGNAL", reasons)

    df_route = compute_indicators(raw, lookback=route_lb)
    strategy_name, lookback, horizon = seeded_select_strategy(symbol, df_route, seed)
    if strategy_name is None:
        reasons.append("NO_STRATEGY_ALLOCATION")
        return _blank(symbol, raw, now_utc, "NO_SIGNAL", reasons)

    vote = production_quant_decision(raw, lookback)
    ind = vote["df"]
    if apply_volatility_filter and not ind.empty and not volatility_ok(ind):
        reasons.append("VOLATILITY_FILTER")
        return _blank(symbol, raw, now_utc, "NO_SIGNAL", reasons, strategy=strategy_name, horizon=horizon)

    if not vote.get("allow") or vote.get("direction") not in ("BUY", "SELL"):
        if vote.get("direction") is None:
            reasons.append("NO_SIGNAL_MA_FLAT")
        else:
            reasons.append("NO_SIGNAL_MOMENTUM_OR_ATR")
        return _snapshot(
            symbol,
            raw,
            now_utc,
            strategy=strategy_name,
            horizon=horizon,
            lookback=lookback,
            side="",
            decision="NO_SIGNAL",
            reasons=reasons,
            vote=vote,
            route="quant_stub+select_strategy",
        )

    side = str(vote["direction"]).upper()
    price = float(vote["price"])
    atr = vote.get("atr")
    if atr is not None and (math.isnan(float(atr)) or float(atr) <= 0):
        atr = None
    sl, tp = sl_tp_from_production_distances(symbol, side, price, atr)
    reasons.append("QUANT_STUB_SIGNAL")
    return _snapshot(
        symbol,
        raw,
        now_utc,
        strategy=strategy_name,
        horizon=horizon,
        lookback=lookback,
        side=side,
        decision=side,
        reasons=reasons,
        vote=vote,
        route="quant_stub+select_strategy",
        stop_loss=sl,
        take_profit=tp,
        entry_price=price,
    )


def _blank(
    symbol: str,
    raw: pd.DataFrame,
    now_utc: datetime,
    decision: str,
    reasons: list[str],
    *,
    strategy: str = "",
    horizon: str = "",
) -> DecisionSnapshot:
    return _snapshot(
        symbol,
        raw,
        now_utc,
        strategy=strategy,
        horizon=horizon,
        lookback=0,
        side="",
        decision=decision,
        reasons=reasons,
        vote={},
        route="quant_stub+select_strategy",
    )


def _snapshot(
    symbol: str,
    raw: pd.DataFrame,
    now_utc: datetime,
    *,
    strategy: str,
    horizon: str,
    lookback: int,
    side: str,
    decision: str,
    reasons: list[str],
    vote: dict,
    route: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    entry_price: float | None = None,
) -> DecisionSnapshot:
    mid = float(raw["close"].iloc[-1]) if not raw.empty else 0.0
    research = indicator_research_fields(raw, lookback or 50)
    labels = htf_trend_labels(raw, now_utc)
    atr = research.get("atr")
    spread = simulated_half_spread(symbol)
    from forex_bot.profit_protection import pip_size

    pip = pip_size(symbol)
    spread_pips = spread / pip if pip else None
    spread_atr = (spread / atr) if atr and atr > 0 else None
    sl_d = abs(entry_price - stop_loss) if entry_price is not None and stop_loss is not None else None
    tp_d = abs(take_profit - entry_price) if entry_price is not None and take_profit is not None else None
    pre_move = pre_entry_extension_atr(raw, side or "BUY", atr) if side else None
    swing = distance_from_swing_atr(raw, side or "BUY", atr) if side else None
    return DecisionSnapshot(
        timestamp=now_utc,
        symbol=symbol,
        side=side,
        strategy=strategy,
        horizon=horizon,
        route=route,
        entry_price=float(entry_price) if entry_price is not None else mid,
        reference_mid=mid,
        decision=decision,
        reason_codes=list(reasons),
        lookback=lookback,
        atr=atr,
        atr_percentile=research.get("atr_percentile"),
        spread=spread,
        spread_pips=spread_pips,
        spread_over_atr=spread_atr,
        ma_fast=research.get("ma_fast"),
        ma_slow=research.get("ma_slow"),
        rsi=research.get("rsi"),
        macd=research.get("macd"),
        trend=research.get("trend"),
        volatility=research.get("volatility"),
        ema_slope=research.get("ema_slope"),
        ema_separation_atr=research.get("ema_separation_atr"),
        adx=research.get("adx"),
        distance_from_mean_atr=research.get("distance_from_mean_atr"),
        recent_range_atr=research.get("recent_range_atr"),
        volatility_state=str(research.get("volatility_state") or ""),
        session=classify_session(now_utc),
        hour_utc=hour_utc(now_utc),
        hour_london=hour_london(now_utc),
        day_of_week=int(now_utc.weekday()),
        m5_trend=labels.get("M5", ""),
        m15_trend=labels.get("M15", ""),
        h1_trend=labels.get("H1", ""),
        h4_trend=labels.get("H4", ""),
        htf_agreement=htf_alignment(side, labels) if side else "",
        regime=str(research.get("regime") or ""),
        signal_confidence=float(vote["confidence"]) if vote.get("confidence") is not None else None,
        stop_loss=stop_loss,
        take_profit=take_profit,
        sl_distance=sl_d,
        tp_distance=tp_d,
        pre_move_atr=pre_move,
        dist_swing_atr=swing,
        research_only=True,
    )
