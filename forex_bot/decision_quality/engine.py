"""Deterministic offline backtester. Isolated from broker writes and live registries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from forex_bot.decision_quality.data import history_at
from forex_bot.decision_quality.execution_sim import (
    apply_entry_spread,
    bar_touches,
    excursion_pips,
    parse_bar_time,
    sl_pips,
)
from forex_bot.decision_quality.fast_cache import SignalCache, evaluate_signal_cached
from forex_bot.decision_quality.invariants import sl_tp_from_production_distances
from forex_bot.decision_quality.outcomes import TradeRecord, finalize_trade
from forex_bot.decision_quality.signal import evaluate_signal
from forex_bot.decision_quality.snapshot import DecisionSnapshot


@dataclass
class OpenSim:
    snap: DecisionSnapshot
    entry_idx: int
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    mfe: float = 0.0
    mae: float = 0.0
    t_mfe: float | None = None
    t_mae: float | None = None


@dataclass
class BacktestResult:
    symbol: str
    bars: int
    signals: int
    trades: list[TradeRecord] = field(default_factory=list)
    snapshots: list[DecisionSnapshot] = field(default_factory=list)
    coverage_note: str = ""
    execution_note: str = (
        "OHLC mid candles only: entry uses production half-spread on bar close; "
        "SL/TP use high/low with same-bar ambiguity counted separately and resolved as SL. "
        "Live evaluate() currently checks close-only; this simulator is path-aware on purpose."
    )


def run_symbol_backtest(
    symbol: str,
    df: pd.DataFrame,
    *,
    warmup: int = 80,
    seed: int = 42,
    apply_session_hours: bool = False,
    apply_fx_week: bool = True,
    apply_spread: bool = True,
    sl_atr_mult: float | None = None,
    impl: str = "reference",
) -> BacktestResult:
    """Walk bars in order. One open position at a time. No future bars in signal/entry.

    ``impl="reference"`` is the original prefix-copy path.
    ``impl="optimized"`` uses causal precomputes with the same decision semantics.
    """
    if impl not in ("reference", "optimized"):
        raise ValueError(f"unknown impl {impl!r}")
    if df.empty or len(df) <= warmup:
        return BacktestResult(
            symbol=symbol,
            bars=len(df),
            signals=0,
            coverage_note=f"insufficient bars ({len(df)}) vs warmup {warmup}",
        )

    open_pos: OpenSim | None = None
    trades: list[TradeRecord] = []
    snaps: list[DecisionSnapshot] = []
    signals = 0
    cache = SignalCache(df) if impl == "optimized" else None

    for i in range(warmup, len(df)):
        now = parse_bar_time(df["time"].iloc[i])

        if open_pos is not None:
            # Do not use the entry bar's range (signal/entry is at that close).
            if i > open_pos.entry_idx:
                hi = float(df["high"].iloc[i])
                lo = float(df["low"].iloc[i])
                fav, adv = excursion_pips(symbol, open_pos.snap.side, open_pos.entry_price, hi, lo)
                age = (now - open_pos.entry_time).total_seconds() / 60.0
                if fav > open_pos.mfe:
                    open_pos.mfe = fav
                    open_pos.t_mfe = age
                if adv > open_pos.mae:
                    open_pos.mae = adv
                    open_pos.t_mae = age
                touch = bar_touches(open_pos.snap.side, open_pos.stop_loss, open_pos.take_profit, hi, lo)
                if touch.exit_reason:
                    rec = finalize_trade(
                        open_pos.snap,
                        entry_time=open_pos.entry_time,
                        exit_time=now,
                        exit_reason=touch.exit_reason,
                        exit_price=float(touch.exit_price),
                        mfe_pips=open_pos.mfe,
                        mae_pips=open_pos.mae,
                        time_to_mfe_min=open_pos.t_mfe,
                        time_to_mae_min=open_pos.t_mae,
                        ambiguous=touch.ambiguous,
                        df=df,
                        entry_idx=open_pos.entry_idx,
                        exit_idx=i,
                    )
                    trades.append(rec)
                    open_pos = None
            continue

        bar_seed = int(seed + i * 10007 + (hash(symbol) % 100000))
        if impl == "optimized" and cache is not None:
            snap = evaluate_signal_cached(
                symbol,
                cache,
                i,
                now,
                seed=bar_seed,
                apply_session_hours=apply_session_hours,
                apply_fx_week=apply_fx_week,
            )
        else:
            snap = evaluate_signal(
                symbol,
                history_at(df, i),
                now,
                seed=bar_seed,
                apply_session_hours=apply_session_hours,
                apply_fx_week=apply_fx_week,
            )
        snaps.append(snap)
        if snap.decision not in ("BUY", "SELL"):
            continue
        signals += 1
        mid = float(snap.reference_mid)
        if apply_spread:
            entry, _half = apply_entry_spread(symbol, snap.side, mid)
        else:
            entry = mid
        atr = snap.atr
        if sl_atr_mult is not None and atr and atr > 0:
            sl_d = float(atr) * float(sl_atr_mult)
            tp_d = sl_d * 2.0
            if snap.side == "BUY":
                sl, tp = entry - sl_d, entry + tp_d
            else:
                sl, tp = entry + sl_d, entry - tp_d
        else:
            sl, tp = sl_tp_from_production_distances(symbol, snap.side, entry, atr)
        snap.entry_price = entry
        snap.stop_loss = sl
        snap.take_profit = tp
        snap.sl_distance = abs(entry - sl)
        snap.tp_distance = abs(tp - entry)
        open_pos = OpenSim(
            snap=snap,
            entry_idx=i,
            entry_time=now,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
        )

    if open_pos is not None:
        last_i = len(df) - 1
        last_t = parse_bar_time(df["time"].iloc[last_i])
        last_px = float(df["close"].iloc[last_i])
        rec = finalize_trade(
            open_pos.snap,
            entry_time=open_pos.entry_time,
            exit_time=last_t,
            exit_reason="eod",
            exit_price=last_px,
            mfe_pips=open_pos.mfe,
            mae_pips=open_pos.mae,
            time_to_mfe_min=open_pos.t_mfe,
            time_to_mae_min=open_pos.t_mae,
            ambiguous=False,
            df=df,
            entry_idx=open_pos.entry_idx,
            exit_idx=last_i,
        )
        trades.append(rec)

    _ = sl_pips
    return BacktestResult(symbol=symbol, bars=len(df), signals=signals, trades=trades, snapshots=snaps)
