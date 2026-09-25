"""Attach research outcomes AFTER the shadow decision is persisted. No live orders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from forex_bot.v2_shadow.contract import ShadowOutcome, V2ShadowDecision

HORIZONS_MIN = (5, 15, 30, 60, 120, 240)


def _ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _f(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _input_value(decision: V2ShadowDecision, key: str) -> Any:
    cell = (decision.inputs or {}).get(key) or {}
    if cell.get("status") != "AVAILABLE":
        return None
    return cell.get("value")


def _bar_after(bars: list[dict[str, Any]], start: datetime, minutes: int) -> dict[str, Any] | None:
    target = start + timedelta(minutes=minutes)
    chosen = None
    for bar in bars:
        ts = _ts(bar.get("ts") or bar.get("time"))
        if ts is None or ts <= start:
            continue
        if ts > target:
            break
        chosen = bar
    return chosen


def _path(bars: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    out = []
    for bar in bars:
        ts = _ts(bar.get("ts") or bar.get("time"))
        if ts is None:
            continue
        if start < ts <= end:
            out.append(bar)
    return out


def _side_metrics(
    *,
    side: str,
    entry: float,
    pip: float,
    future_close: float | None,
    path: list[dict[str, Any]],
    risk_pips: float | None,
) -> dict[str, Any]:
    if pip <= 0:
        return {"status": "MISSING", "reason": "invalid_pip"}
    if side == "BUY":
        fwd = None if future_close is None else (future_close - entry) / pip
        mfe = 0.0
        mae = 0.0
        for bar in path:
            hi = _f(bar.get("bid_high"))
            lo = _f(bar.get("bid_low"))
            if hi is not None:
                mfe = max(mfe, (hi - entry) / pip)
            if lo is not None:
                mae = max(mae, (entry - lo) / pip)
    else:
        fwd = None if future_close is None else (entry - future_close) / pip
        mfe = 0.0
        mae = 0.0
        for bar in path:
            lo = _f(bar.get("ask_low"))
            hi = _f(bar.get("ask_high"))
            if lo is not None:
                mfe = max(mfe, (entry - lo) / pip)
            if hi is not None:
                mae = max(mae, (hi - entry) / pip)
    ret = None if future_close is None or entry in (None, 0) else (
        (future_close - entry) / entry if side == "BUY" else (entry - future_close) / entry
    )
    r = None
    if fwd is not None and risk_pips and risk_pips > 0:
        r = fwd / risk_pips
    return {
        "status": "AVAILABLE" if fwd is not None else "MISSING",
        "entry": entry,
        "future_close": future_close,
        "forward_pips": fwd,
        "forward_return": ret,
        "forward_r": r,
        "direction_correct": None if fwd is None else bool(fwd > 0),
        "mfe_pips": mfe if path else None,
        "mae_pips": mae if path else None,
        "mfe_source": "research_bid_ask_path",
        "estimated_cost": None,
        "net_after_cost": fwd,
    }


def score_shadow_decision(
    decision: V2ShadowDecision,
    bars: list[dict[str, Any]],
    *,
    scored_at_utc: str | None = None,
    risk_pips: float | None = None,
) -> ShadowOutcome:
    """
    Score previously written shadow decisions. Does not mutate ``decision``.

    BUY economics: hypothetical entry ask → future bid close.
    SELL economics: hypothetical entry bid → future ask close.
    SKIP still records both sides as opportunity-cost.
    """
    start = _ts(decision.timestamp_utc)
    if start is None:
        raise ValueError("decision timestamp is not parseable")
    pip = _f(_input_value(decision, "pip_size")) or 0.0
    ask = _f(_input_value(decision, "ask"))
    bid = _f(_input_value(decision, "bid"))
    spread = _f(_input_value(decision, "spread"))
    atr = _f(_input_value(decision, "atr"))
    if risk_pips is None and atr is not None and pip > 0:
        risk_pips = 2.0 * (atr / pip)

    notes = [
        "research_executable_side",
        "not_production_mfe",
        f"proposed_action={decision.proposed_action}",
    ]
    horizons: dict[str, Any] = {}
    ordered = sorted(bars, key=lambda b: str(b.get("ts") or b.get("time") or ""))
    for minutes in HORIZONS_MIN:
        future = _bar_after(ordered, start, minutes)
        end = start + timedelta(minutes=minutes)
        path = _path(ordered, start, end)
        buy_close = _f((future or {}).get("bid_close")) if future else None
        sell_close = _f((future or {}).get("ask_close")) if future else None
        buy = (
            _side_metrics(
                side="BUY",
                entry=ask,
                pip=pip,
                future_close=buy_close,
                path=path,
                risk_pips=risk_pips,
            )
            if ask is not None
            else {"status": "MISSING", "reason": "no_ask_at_decision"}
        )
        sell = (
            _side_metrics(
                side="SELL",
                entry=bid,
                pip=pip,
                future_close=sell_close,
                path=path,
                risk_pips=risk_pips,
            )
            if bid is not None
            else {"status": "MISSING", "reason": "no_bid_at_decision"}
        )
        if spread is not None and pip:
            cost_pips = abs(spread) / pip
            if buy.get("forward_pips") is not None:
                buy["estimated_cost"] = cost_pips
                # ask→bid already includes the spread; do not subtract again.
                buy["net_after_cost"] = buy["forward_pips"]
            if sell.get("forward_pips") is not None:
                sell["estimated_cost"] = cost_pips
                sell["net_after_cost"] = sell["forward_pips"]
        if buy.get("forward_pips") is not None:
            buy["entry_side"] = "ask"
            buy["exit_side"] = "bid"
        if sell.get("forward_pips") is not None:
            sell["entry_side"] = "bid"
            sell["exit_side"] = "ask"
        unsigned_up = None
        if buy.get("forward_pips") is not None:
            unsigned_up = bool(buy["forward_pips"] > 0)
        horizons[str(minutes)] = {
            "buy": buy,
            "sell": sell,
            "skip_opportunity": {
                "buy_would_cover_cost": unsigned_up,
                "sell_would_cover_cost": (
                    bool(sell["forward_pips"] > 0) if sell.get("forward_pips") is not None else None
                ),
            },
        }

    scored = scored_at_utc or datetime.now(timezone.utc).isoformat()
    return ShadowOutcome(
        decision_id=decision.decision_id,
        scored_at_utc=scored,
        model_name=decision.model_name,
        model_version=decision.model_version,
        horizons=horizons,
        notes=notes,
    )
