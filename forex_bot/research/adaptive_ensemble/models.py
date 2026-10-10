"""Three adaptive approaches plus baselines. Weights update only after delayed outcomes."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.candidates import (
    BUY,
    GENERATORS,
    NO_TRADE,
    REGIME_MAP,
    SELL,
    CandidateSignal,
    all_signals,
)

SPREAD_ATR_MAX = {
    "base": 0.35,
    "conservative": 0.25,
    "severe": 0.15,
    "ablation_no_cost_filter": 99.0,
}


@dataclass
class Decision:
    direction: str
    reason: str
    model_id: str
    chosen: str | None
    signals: dict[str, str]
    abstain: bool


@dataclass
class WeightState:
    version: str = "exp_weights_v1"
    weights: dict[str, float] = field(default_factory=lambda: {k: 1.0 for k in GENERATORS})
    pending: list[dict[str, Any]] = field(default_factory=list)
    updates: int = 0

    def dump(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "weights": dict(self.weights),
            "pending": list(self.pending),
            "updates": self.updates,
        }

    @classmethod
    def load(cls, path: Path) -> WeightState:
        if not path.is_file():
            return cls()
        blob = json.loads(path.read_text(encoding="utf-8"))
        if blob.get("version") != "exp_weights_v1":
            return cls()
        st = cls()
        st.weights = {k: float(blob["weights"].get(k, 1.0)) for k in GENERATORS}
        st.pending = list(blob.get("pending") or [])
        st.updates = int(blob.get("updates") or 0)
        return st

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.dump(), indent=2, sort_keys=True), encoding="utf-8")


def _cost_block(snap: dict[str, Any], cost: str) -> str | None:
    soa = snap.get("spread_over_atr")
    if soa is None:
        return "missing_spread"
    try:
        v = float(soa)
    except (TypeError, ValueError):
        return "missing_spread"
    if math.isnan(v):
        return "missing_spread"
    if v > SPREAD_ATR_MAX[cost]:
        return "spread_excessive"
    return None


def _vote(signals: dict[str, CandidateSignal], *, min_agree: int, use_conf: bool) -> Decision:
    buys = 0.0
    sells = 0.0
    dirs = {}
    for cid, sig in signals.items():
        dirs[cid] = sig.direction
        w = float(sig.confidence or 1.0) if use_conf else 1.0
        if sig.direction == BUY:
            buys += w
        elif sig.direction == SELL:
            sells += w
    n_buy = sum(1 for s in signals.values() if s.direction == BUY)
    n_sell = sum(1 for s in signals.values() if s.direction == SELL)
    if n_buy and n_sell:
        return Decision(NO_TRADE, "signal_conflict", "vote", None, dirs, True)
    if n_buy < min_agree and n_sell < min_agree:
        return Decision(NO_TRADE, "agreement_threshold", "vote", None, dirs, True)
    if buys > sells:
        return Decision(BUY, "majority_buy", "vote", "ensemble", dirs, False)
    if sells > buys:
        return Decision(SELL, "majority_sell", "vote", "ensemble", dirs, False)
    return Decision(NO_TRADE, "tie", "vote", None, dirs, True)


def model_regime(snap: dict[str, Any], *, cost: str = "base") -> Decision:
    blocked = _cost_block(snap, cost)
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if blocked:
        return Decision(NO_TRADE, blocked, "regime_selection", None, dirs, True)
    if snap.get("status") != "ok":
        return Decision(NO_TRADE, "missing_data", "regime_selection", None, dirs, True)
    mapped = REGIME_MAP.get(str(snap.get("regime")), None)
    if mapped is None:
        return Decision(NO_TRADE, "regime_uncertain_or_unsuitable", "regime_selection", None, dirs, True)
    sig = sigs[mapped]
    if sig.direction == NO_TRADE:
        return Decision(NO_TRADE, sig.invalidation or "mapped_proxy_no_trade", "regime_selection", mapped, dirs, True)
    return Decision(sig.direction, "regime_mapped", "regime_selection", mapped, dirs, False)


def model_vote(snap: dict[str, Any], *, cost: str = "base", min_agree: int = 2, use_conf: bool = False) -> Decision:
    blocked = _cost_block(snap, cost)
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if blocked:
        return Decision(NO_TRADE, blocked, "vote", None, dirs, True)
    d = _vote(sigs, min_agree=min_agree, use_conf=use_conf)
    d.signals = dirs
    return d


def model_dynamic(snap: dict[str, Any], state: WeightState, *, cost: str = "base") -> Decision:
    blocked = _cost_block(snap, cost)
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if blocked:
        return Decision(NO_TRADE, blocked, "dynamic_weights", None, dirs, True)
    score_buy = 0.0
    score_sell = 0.0
    for cid, sig in sigs.items():
        w = max(0.0, min(5.0, float(state.weights.get(cid, 1.0))))
        if sig.direction == BUY:
            score_buy += w
        elif sig.direction == SELL:
            score_sell += w
    if score_buy == 0 and score_sell == 0:
        return Decision(NO_TRADE, "no_eligible_weighted_signal", "dynamic_weights", None, dirs, True)
    if abs(score_buy - score_sell) < 0.25:
        return Decision(NO_TRADE, "weighted_conflict_or_tie", "dynamic_weights", None, dirs, True)
    if score_buy > score_sell:
        return Decision(BUY, "weighted_buy", "dynamic_weights", "ensemble", dirs, False)
    return Decision(SELL, "weighted_sell", "dynamic_weights", "ensemble", dirs, False)


def apply_delayed_outcomes(state: WeightState, now_i: int, eta: float = 0.15) -> WeightState:
    remain = []
    for item in state.pending:
        if int(item["ready_i"]) > now_i:
            remain.append(item)
            continue
        cid = str(item["candidate_id"])
        pnl = float(item["pnl"])
        cur = float(state.weights.get(cid, 1.0))
        factor = 1.0 + eta if pnl > 0 else 1.0 - eta
        nxt = max(0.05, min(5.0, cur * factor))
        state.weights[cid] = nxt
        state.updates += 1
    state.pending = remain
    return state


def enqueue_outcome(state: WeightState, *, candidate_id: str, ready_i: int, pnl: float) -> None:
    state.pending.append({"candidate_id": candidate_id, "ready_i": int(ready_i), "pnl": float(pnl)})


def baseline_no_trade(snap: dict[str, Any], **_kw: Any) -> Decision:
    sigs = all_signals(snap)
    return Decision(NO_TRADE, "baseline_no_trade", "no_trade", None, {k: v.direction for k, v in sigs.items()}, True)


def baseline_single_trend(snap: dict[str, Any], *, cost: str = "base") -> Decision:
    blocked = _cost_block(snap, cost)
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if blocked:
        return Decision(NO_TRADE, blocked, "single_proxy_trend", None, dirs, True)
    sig = sigs["proxy_trend_ma_slope_v1"]
    if sig.direction == NO_TRADE:
        return Decision(NO_TRADE, sig.invalidation or "trend_no_trade", "single_proxy_trend", sig.candidate_id, dirs, True)
    return Decision(sig.direction, "single_trend", "single_proxy_trend", sig.candidate_id, dirs, False)


def baseline_rotate(snap: dict[str, Any], cursor: dict[str, int], *, cost: str = "base") -> Decision:
    blocked = _cost_block(snap, cost)
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if blocked:
        return Decision(NO_TRADE, blocked, "rotation", None, dirs, True)
    keys = list(GENERATORS)
    start = int(cursor.get("i", 0)) % len(keys)
    for k in range(len(keys)):
        cid = keys[(start + k) % len(keys)]
        sig = sigs[cid]
        if sig.direction != NO_TRADE:
            cursor["i"] = (start + k + 1) % len(keys)
            return Decision(sig.direction, "rotation_selected", "rotation", cid, dirs, False)
    return Decision(NO_TRADE, "rotation_none_eligible", "rotation", None, dirs, True)
