"""Exploratory chronological evaluation. Previously examined data is not a fresh holdout."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble import LABEL
from forex_bot.research.adaptive_ensemble.candidates import NO_TRADE
from forex_bot.research.adaptive_ensemble.features import (
    compute_feature_frame,
    snapshot_at,
)
from forex_bot.research.adaptive_ensemble.models import (
    WeightState,
    apply_delayed_outcomes,
    baseline_no_trade,
    baseline_rotate,
    baseline_single_trend,
    enqueue_outcome,
    model_dynamic,
    model_regime,
    model_vote,
)
from forex_bot.research.adaptive_ensemble.protocol import PROTOCOL
from forex_bot.research.adaptive_ensemble.simulate import (
    Book,
    Trade,
    fill_price,
    mark_exit,
    quote_to_gbp,
)

WARMUP = 80
EXEC = PROTOCOL["execution"]


def metrics(book: Book, n_bars: int) -> dict[str, Any]:
    pnls = [t.pnl_gbp for t in book.trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = float(sum(wins))
    gross_loss = float(sum(losses))
    pf = gross_win / abs(gross_loss) if gross_loss else (float("inf") if gross_win else 0.0)
    peak = EXEC["start_nav_gbp"]
    max_dd = 0.0
    eq = EXEC["start_nav_gbp"]
    for t in book.trades:
        eq += t.pnl_gbp
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    net = float(sum(pnls))
    return {
        "label": LABEL,
        "trade_count": len(book.trades),
        "gross_pnl_gbp": round(gross_win + abs(gross_loss), 6),
        "net_pnl_gbp": round(net, 6),
        "profit_factor": None if not math.isfinite(pf) else round(pf, 4),
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
        "max_drawdown": round(max_dd, 6),
        "final_nav": round(EXEC["start_nav_gbp"] + net, 6),
        "abstentions": book.abstentions,
        "decisions": book.decisions,
        "abstention_rate": round(book.abstentions / book.decisions, 4) if book.decisions else None,
        "halted": book.halted,
        "n_bars": n_bars,
        "financing": "UNAVAILABLE",
        "gbp_fx_label": "ESTIMATE",
        "start_nav_label": "SIMULATION_ASSUMPTION_NOT_BROKER_BALANCE",
        "evidence_class": "PREVIOUSLY_EXAMINED_EXPLORATORY",
    }


def _enter(frame: pd.DataFrame, i: int, direction: str, cost: str, pair: str, model_id: str, regime: str) -> Trade | None:
    entry_i = i + 1
    px = fill_price(frame, entry_i, direction, cost)
    if px is None:
        return None
    atr = float(frame.iloc[i]["feat_atr"])
    sl_d = EXEC["sl_atr"] * atr
    tp_d = EXEC["tp_atr"] * atr
    if direction == "BUY":
        sl, tp = px - sl_d, px + tp_d
    else:
        sl, tp = px + sl_d, px - tp_d
    exit_i, exit_px, why = mark_exit(frame, entry_i, direction, px, sl, tp, int(EXEC["max_hold_bars"]))
    units = float(EXEC["units"])
    signed = 1.0 if direction == "BUY" else -1.0
    pnl_q = (exit_px - px) * signed * units
    pnl_g = quote_to_gbp(pnl_q, pair, float(EXEC["gbp_usd_fx"]))
    return Trade(pair, direction, entry_i, exit_i, px, exit_px, pnl_q, pnl_g, why, model_id, regime)


def run_model(
    frame: pd.DataFrame,
    *,
    pair: str,
    cost: str,
    chooser: Callable[..., Any],
    start: int,
    end: int,
    dynamic: bool = False,
    weights_path: Path | None = None,
) -> Book:
    book = Book(nav=float(EXEC["start_nav_gbp"]), peak=float(EXEC["start_nav_gbp"]))
    cursor: dict[str, int] = {"i": 0}
    state = WeightState.load(weights_path) if (dynamic and weights_path) else WeightState()
    stride = int(EXEC["decision_stride"])
    i = max(start, WARMUP)
    while i < end - 2:
        if book.open_pos is not None and i <= int(book.open_pos["exit_i"]):
            i += 1
            continue
        if dynamic:
            apply_delayed_outcomes(state, i)
        snap = snapshot_at(frame, i)
        if chooser is baseline_rotate:
            dec = chooser(snap, cursor, cost=cost)
        elif chooser is model_dynamic:
            dec = chooser(snap, state, cost=cost)
        else:
            dec = chooser(snap, cost=cost)
        book.decisions += 1
        if dec.abstain or dec.direction == NO_TRADE:
            book.abstentions += 1
            i += stride
            continue
        if book.halted:
            book.abstentions += 1
            i += stride
            continue
        trade = _enter(frame, i, dec.direction, cost, pair, dec.model_id, str(snap.get("regime")))
        if trade is None:
            book.abstentions += 1
            i += stride
            continue
        book.trades.append(trade)
        book.realised += trade.pnl_gbp
        book.nav = float(EXEC["start_nav_gbp"]) + book.realised
        book.peak = max(book.peak, book.nav)
        dd = (book.peak - book.nav) / book.peak if book.peak else 0.0
        if trade.pnl_gbp <= -float(EXEC["daily_loss_halt_pct"]) * float(EXEC["start_nav_gbp"]):
            book.halted = "daily_loss"
        if dd >= float(EXEC["max_dd_halt_pct"]):
            book.halted = "max_drawdown"
        if dynamic:
            cid = dec.chosen if dec.chosen and dec.chosen in state.weights else "proxy_trend_ma_slope_v1"
            enqueue_outcome(state, candidate_id=cid, ready_i=trade.exit_i, pnl=trade.pnl_gbp)
        book.open_pos = {"exit_i": trade.exit_i}
        i = trade.exit_i + 1
    if dynamic and weights_path:
        state.save(weights_path)
    return book


def split_bounds(n: int) -> tuple[int, int, int]:
    d = int(n * float(PROTOCOL["development_fraction"]))
    v = int(n * float(PROTOCOL["validation_fraction"]))
    return max(WARMUP, 0), d, d + v


def summarise_by(trades: list[Trade], key: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for t in trades:
        k = str(getattr(t, key))
        rec = out.setdefault(k, {"n": 0.0, "net": 0.0})
        rec["n"] += 1
        rec["net"] += t.pnl_gbp
    return out


CHOOSERS: dict[str, tuple[Callable[..., Any], bool]] = {
    "no_trade": (baseline_no_trade, False),
    "single_proxy_trend": (baseline_single_trend, False),
    "deterministic_rotation": (baseline_rotate, False),
    "equal_weight_vote": (model_vote, False),
    "regime_selection": (model_regime, False),
    "dynamic_exp_weights": (model_dynamic, True),
}


def evaluate_frame(
    frame: pd.DataFrame,
    *,
    pair: str,
    cost: str,
    lo: int,
    hi: int,
    work: Path | None = None,
    precomputed: pd.DataFrame | None = None,
) -> dict[str, Any]:
    feat = precomputed if precomputed is not None else compute_feature_frame(frame)
    results: dict[str, Any] = {}
    for name, (fn, dyn) in CHOOSERS.items():
        wp = (work / f"weights_{name}_{cost}.json") if (dyn and work) else None
        book = run_model(feat, pair=pair, cost=cost, chooser=fn, start=lo, end=hi, dynamic=dyn, weights_path=wp)
        rec = metrics(book, hi - lo)
        rec["per_regime"] = summarise_by(book.trades, "regime")
        rec["exits"] = {}
        for t in book.trades:
            rec["exits"][t.reason_exit] = rec["exits"].get(t.reason_exit, 0) + 1
        results[name] = rec
    return results


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
