"""Observe a production candidate. Return is discarded by callers. Never authorizes."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.v2_shadow.contract import (
    FundamentalSlots,
    V2ShadowDecision,
    _status_value,
)
from forex_bot.v2_shadow.decide import default_v2_decision
from forex_bot.v2_shadow.store import append_observation

logger = logging.getLogger(__name__)

FORWARD_KEYS = frozenset(
    {
        "forward_pips",
        "forward_return",
        "direction_correct",
        "mfe_pips",
        "mae_pips",
        "net_after_cost",
    }
)


def v2_shadow_enabled() -> bool:
    return (os.getenv("V2_SHADOW_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")


def _iso_utc(ts: datetime | None = None) -> str:
    dt = ts or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def make_decision_id(
    *,
    timestamp_utc: str,
    symbol: str,
    model_name: str,
    model_version: str,
    production_side: str,
) -> str:
    raw = f"{timestamp_utc}|{symbol}|{model_name}|{model_version}|{production_side}"
    return "v2sh_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _sv(value: Any, present: bool, *, computed: bool = True) -> dict[str, Any]:
    if not computed:
        return _status_value(None, "NOT_COMPUTED")
    if not present or value is None:
        return _status_value(None, "MISSING")
    try:
        if isinstance(value, float) and value != value:
            return _status_value(None, "MISSING")
    except (TypeError, ValueError):
        return _status_value(None, "MISSING")
    return _status_value(value, "AVAILABLE")


def _classify_inputs(inputs: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    available: list[str] = []
    missing: list[str] = []
    not_computed: list[str] = []
    for key, cell in inputs.items():
        if not isinstance(cell, dict) or "status" not in cell:
            continue
        st = cell["status"]
        if st == "AVAILABLE":
            available.append(key)
        elif st == "MISSING":
            missing.append(key)
        elif st == "NOT_COMPUTED":
            not_computed.append(key)
    return available, missing, not_computed


def build_observation(
    *,
    symbol: str,
    strategy_label: str,
    production_side: str,
    mid: float | None,
    timestamp_utc: str | None = None,
    candidate_source: str = "production_quant_stub",
    bid: float | None = None,
    ask: float | None = None,
    pip_size: float | None = None,
    atr: float | None = None,
    sma_fast: float | None = None,
    sma_slow: float | None = None,
    rsi: float | None = None,
    macd: float | None = None,
    boll_up: float | None = None,
    boll_down: float | None = None,
    ret_1: float | None = None,
    ret_5: float | None = None,
    ret_15: float | None = None,
    ret_30: float | None = None,
    hour_utc: int | None = None,
    day_of_week: int | None = None,
    usd_direction: str | None = None,
    broker_backed_position_count: int | None = None,
    gross_portfolio_exposure: float | None = None,
    same_usd_direction_count: int | None = None,
    rl_action: str | None = None,
    rl_state: str | None = None,
    rl_q_values: dict[str, float] | None = None,
    rl_epsilon: float | None = None,
    extras: dict[str, Any] | None = None,
) -> V2ShadowDecision:
    if extras:
        forbidden = FORWARD_KEYS.intersection(extras)
        if forbidden:
            raise ValueError(f"future fields are not allowed at decision time: {sorted(forbidden)}")

    policy = default_v2_decision()
    ts = timestamp_utc or _iso_utc()
    spread = None
    if bid is not None and ask is not None:
        spread = float(ask) - float(bid)
    atr_over_price = None
    if atr is not None and mid not in (None, 0):
        atr_over_price = float(atr) / float(mid)
    sma_diff = None
    sma_diff_atr = None
    if sma_fast is not None and sma_slow is not None:
        sma_diff = float(sma_fast) - float(sma_slow)
        if atr not in (None, 0):
            sma_diff_atr = sma_diff / float(atr)
    bb_pos = None
    if boll_up is not None and boll_down is not None and float(boll_up) != float(boll_down) and mid is not None:
        bb_pos = (float(mid) - float(boll_down)) / (float(boll_up) - float(boll_down))

    inputs: dict[str, Any] = {
        "production_stub_side": _sv(production_side, bool(production_side)),
        "strategy_label": _sv(strategy_label, bool(strategy_label)),
        "bid": _sv(bid, bid is not None),
        "ask": _sv(ask, ask is not None),
        "mid": _sv(mid, mid is not None),
        "spread": _sv(spread, spread is not None),
        "pip_size": _sv(pip_size, pip_size is not None),
        "atr": _sv(atr, atr is not None),
        "atr_over_price": _sv(atr_over_price, atr_over_price is not None),
        "sma_fast": _sv(sma_fast, sma_fast is not None),
        "sma_slow": _sv(sma_slow, sma_slow is not None),
        "sma_difference": _sv(sma_diff, sma_diff is not None),
        "sma_difference_over_atr": _sv(sma_diff_atr, sma_diff_atr is not None),
        "rsi": _sv(rsi, rsi is not None),
        "macd": _sv(macd, macd is not None),
        "macd_signal": _sv(None, False, computed=False),
        "adx": _sv(None, False, computed=False),
        "bollinger_position": _sv(bb_pos, bb_pos is not None),
        "ret_1": _sv(ret_1, ret_1 is not None),
        "ret_5": _sv(ret_5, ret_5 is not None),
        "ret_15": _sv(ret_15, ret_15 is not None),
        "ret_30": _sv(ret_30, ret_30 is not None),
        "hour_utc": _sv(hour_utc, hour_utc is not None),
        "day_of_week": _sv(day_of_week, day_of_week is not None),
        "usd_direction": _sv(usd_direction, usd_direction is not None),
        "broker_backed_position_count": _sv(
            broker_backed_position_count, broker_backed_position_count is not None
        ),
        "gross_portfolio_exposure": _sv(gross_portfolio_exposure, gross_portfolio_exposure is not None),
        "same_usd_direction_count": _sv(same_usd_direction_count, same_usd_direction_count is not None),
    }

    available, missing, not_computed = _classify_inputs(inputs)
    side = (production_side or "").upper()
    rl_act = (rl_action or "").upper() or None
    agree = None
    veto = None
    if rl_act:
        if rl_act == "SKIP":
            agree = False
            veto = True
        elif rl_act in ("BUY", "SELL"):
            agree = rl_act == side
            veto = not agree
    rl = {
        "action": rl_act,
        "state": rl_state,
        "agree": agree,
        "veto": veto,
        "q_values": dict(rl_q_values) if rl_q_values else None,
        "epsilon": rl_epsilon,
    }

    decision_id = make_decision_id(
        timestamp_utc=ts,
        symbol=symbol,
        model_name=str(policy["model_name"]),
        model_version=str(policy["model_version"]),
        production_side=side,
    )
    return V2ShadowDecision(
        decision_id=decision_id,
        timestamp_utc=ts,
        symbol=symbol,
        candidate_source=candidate_source,
        strategy_label=strategy_label or "",
        market_price_reference=mid,
        proposed_action=str(policy["proposed_action"]),  # type: ignore[arg-type]
        direction_probability_up=None,
        direction_probability_down=None,
        confidence=None,
        model_name=str(policy["model_name"]),
        model_version=str(policy["model_version"]),
        feature_schema_version=str(policy["feature_schema_version"]),
        reason_codes=list(policy["reason_codes"]),  # type: ignore[arg-type]
        data_available=available,
        data_missing=missing,
        data_not_computed=not_computed,
        shadow_only=True,
        inputs=inputs,
        fundamentals=FundamentalSlots().to_dict(),
        provenance=[],
        rl=rl,
    )


def maybe_observe_candidate(
    *,
    store_dir: Path | None = None,
    enabled: bool | None = None,
    **kwargs: Any,
) -> V2ShadowDecision | None:
    """
    Record a shadow observation if enabled. Return is informational only.

    Callers MUST ignore the return value for authorization. Exceptions propagate
    to the wrapper in bot_loop, which swallows them.
    """
    if enabled is None:
        enabled = v2_shadow_enabled()
    if not enabled:
        return None
    decision = build_observation(**kwargs)
    append_observation(decision, store_dir=store_dir)
    logger.info(
        "[V2 SHADOW] decision_id=%s symbol=%s production_side=%s v2_action=%s "
        "model=%s/%s confidence=%s reason=%s",
        decision.decision_id,
        decision.symbol,
        (decision.inputs.get("production_stub_side") or {}).get("value"),
        decision.proposed_action,
        decision.model_name,
        decision.model_version,
        decision.confidence,
        ",".join(decision.reason_codes),
    )
    return decision
