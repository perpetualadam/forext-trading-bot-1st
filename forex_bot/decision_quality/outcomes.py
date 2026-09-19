"""Trade outcome metrics, forward returns, and post-stop observation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from forex_bot.decision_quality.execution_sim import (
    bar_touches,
    excursion_pips,
    parse_bar_time,
    r_multiple,
    signed_pips,
    sl_pips,
)
from forex_bot.decision_quality.snapshot import DecisionSnapshot

FORWARD_HORIZONS_MIN = (5, 15, 30, 60)
POST_STOP_HORIZONS_MIN = (5, 15, 30, 60)


@dataclass
class TradeRecord:
    snapshot: DecisionSnapshot
    entry_time: datetime
    exit_time: datetime | None
    exit_reason: str
    exit_price: float | None
    realised_pips: float | None
    realised_r: float | None
    win: bool | None
    mfe_pips: float
    mae_pips: float
    mfe_r: float | None
    mae_r: float | None
    mfe_atr: float | None
    mae_atr: float | None
    time_to_mfe_min: float | None
    time_to_mae_min: float | None
    time_in_trade_min: float | None
    sl_distance_pips: float
    tp_distance_pips: float
    sl_over_atr: float | None
    tp_over_atr: float | None
    max_tp_progress: float | None
    ambiguous: bool
    post_stop: dict[str, Any] = field(default_factory=dict)
    forward: dict[str, Any] = field(default_factory=dict)
    filter_tags: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        snap = self.snapshot.to_dict()
        row = {
            **snap,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "exit_price": self.exit_price,
            "realised_pips": self.realised_pips,
            "realised_r": self.realised_r,
            "win": self.win,
            "mfe_pips": self.mfe_pips,
            "mae_pips": self.mae_pips,
            "mfe_r": self.mfe_r,
            "mae_r": self.mae_r,
            "mfe_atr": self.mfe_atr,
            "mae_atr": self.mae_atr,
            "time_to_mfe_min": self.time_to_mfe_min,
            "time_to_mae_min": self.time_to_mae_min,
            "time_in_trade_min": self.time_in_trade_min,
            "sl_distance_pips": self.sl_distance_pips,
            "tp_distance_pips": self.tp_distance_pips,
            "sl_over_atr": self.sl_over_atr,
            "tp_over_atr": self.tp_over_atr,
            "max_tp_progress": self.max_tp_progress,
            "ambiguous": self.ambiguous,
        }
        for key, val in self.post_stop.items():
            row[f"post_stop_{key}"] = val
        for key, val in self.forward.items():
            row[f"fwd_{key}"] = val
        return row


def _bars_ahead(df: pd.DataFrame, start_idx: int, minutes: int, bar_minutes: int = 5) -> int | None:
    steps = max(1, int(round(minutes / bar_minutes)))
    j = start_idx + steps
    if j >= len(df):
        return None
    return j


def forward_returns(
    df: pd.DataFrame,
    entry_idx: int,
    symbol: str,
    side: str,
    entry: float,
    *,
    bar_minutes: int = 5,
    extra_minutes: tuple[int, ...] = (),
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    horizons = tuple(FORWARD_HORIZONS_MIN) + tuple(extra_minutes)
    for minutes in horizons:
        j = _bars_ahead(df, entry_idx, minutes, bar_minutes)
        key = f"{minutes}m"
        if j is None:
            out[f"{key}_pips"] = None
            out[f"{key}_hit"] = None
            continue
        px = float(df["close"].iloc[j])
        pips = signed_pips(symbol, side, entry, px)
        out[f"{key}_pips"] = pips
        out[f"{key}_hit"] = bool(pips > 0)
    return out


def observe_after_stop(
    df: pd.DataFrame,
    exit_idx: int,
    symbol: str,
    side: str,
    entry: float,
    take_profit: float,
    sl_distance_pips: float,
    *,
    bar_minutes: int = 5,
) -> dict[str, Any]:
    """Research-only path after an SL (or ambiguous-as-SL) exit. Uses later bars on purpose."""
    out: dict[str, Any] = {
        "reached_original_tp": False,
        "minutes_to_original_tp": None,
        "max_favorable_pips_after": 0.0,
        "moved_original_direction": False,
    }
    if exit_idx + 1 >= len(df):
        return out
    rest = df.iloc[exit_idx + 1 :]
    max_fav = 0.0
    reached_tp = False
    mins_to_tp = None
    exit_time = parse_bar_time(df["time"].iloc[exit_idx])
    for _, row in rest.iterrows():
        hi, lo = float(row["high"]), float(row["low"])
        fav, _adv = (signed_pips(symbol, side, entry, hi), 0.0)
        if (side or "").upper() == "SELL":
            fav = signed_pips(symbol, side, entry, lo)
        max_fav = max(max_fav, fav)
        touch = bar_touches(side, entry, take_profit, hi, lo)
        # Re-use bar_touches: treat original TP as TP and entry as dummy SL that we ignore.
        if (side or "").upper() == "BUY":
            hit_tp = hi >= float(take_profit)
        else:
            hit_tp = lo <= float(take_profit)
        if hit_tp and not reached_tp:
            reached_tp = True
            mins_to_tp = (parse_bar_time(row["time"]) - exit_time).total_seconds() / 60.0
        _ = touch
    out["reached_original_tp"] = reached_tp
    out["minutes_to_original_tp"] = mins_to_tp
    out["max_favorable_pips_after"] = max_fav
    out["moved_original_direction"] = max_fav > 0
    for r_tgt, name in ((0.5, "plus_0_5r"), (1.0, "plus_1r"), (2.0, "plus_2r")):
        need = sl_distance_pips * r_tgt
        out[name] = bool(max_fav >= need) if sl_distance_pips > 0 else False
    for minutes in POST_STOP_HORIZONS_MIN:
        j = _bars_ahead(df, exit_idx, minutes, bar_minutes)
        key = f"{minutes}m"
        if j is None:
            out[f"{key}_pips"] = None
            continue
        out[f"{key}_pips"] = signed_pips(symbol, side, entry, float(df["close"].iloc[j]))
    return out


def summarize_closed(records: list[TradeRecord]) -> dict[str, Any]:
    closed = [t for t in records if t.exit_reason and t.realised_r is not None]
    n = len(closed)
    if n == 0:
        return {
            "trade_count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "avg_winner_r": None,
            "avg_loser_r": None,
            "expectancy_r": None,
            "median_r": None,
            "profit_factor": None,
            "total_r": 0.0,
            "avg_mfe_r": None,
            "avg_mae_r": None,
            "max_drawdown_r": 0.0,
            "ambiguous_count": 0,
        }
    rs = [float(t.realised_r) for t in closed]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = float("inf") if gross_loss <= 1e-12 and gross_win > 0 else (gross_win / gross_loss if gross_loss else None)
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    mfe = [t.mfe_r for t in closed if t.mfe_r is not None]
    mae = [t.mae_r for t in closed if t.mae_r is not None]
    return {
        "trade_count": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / n,
        "avg_winner_r": (sum(wins) / len(wins)) if wins else None,
        "avg_loser_r": (sum(losses) / len(losses)) if losses else None,
        "expectancy_r": sum(rs) / n,
        "median_r": float(pd.Series(rs).median()),
        "profit_factor": pf,
        "total_r": sum(rs),
        "avg_mfe_r": (sum(mfe) / len(mfe)) if mfe else None,
        "avg_mae_r": (sum(mae) / len(mae)) if mae else None,
        "max_drawdown_r": max_dd,
        "ambiguous_count": sum(1 for t in closed if t.ambiguous),
    }


def _empty_trade(snap: DecisionSnapshot, entry_time: datetime, sl_p: float, tp_p: float) -> TradeRecord:
    atr = snap.atr
    return TradeRecord(
        snapshot=snap,
        entry_time=entry_time,
        exit_time=None,
        exit_reason="open",
        exit_price=None,
        realised_pips=None,
        realised_r=None,
        win=None,
        mfe_pips=0.0,
        mae_pips=0.0,
        mfe_r=None,
        mae_r=None,
        mfe_atr=None,
        mae_atr=None,
        time_to_mfe_min=None,
        time_to_mae_min=None,
        time_in_trade_min=None,
        sl_distance_pips=sl_p,
        tp_distance_pips=tp_p,
        sl_over_atr=(sl_p / (atr / _pip_or(snap))) if atr and atr > 0 else None,
        tp_over_atr=None,
        max_tp_progress=None,
        ambiguous=False,
    )


def _pip_or(snap: DecisionSnapshot) -> float:
    from forex_bot.profit_protection import pip_size

    return pip_size(snap.symbol) or 0.0001


def finalize_trade(
    snap: DecisionSnapshot,
    *,
    entry_time: datetime,
    exit_time: datetime,
    exit_reason: str,
    exit_price: float,
    mfe_pips: float,
    mae_pips: float,
    time_to_mfe_min: float | None,
    time_to_mae_min: float | None,
    ambiguous: bool,
    df: pd.DataFrame,
    entry_idx: int,
    exit_idx: int,
) -> TradeRecord:
    symbol, side, entry = snap.symbol, snap.side, float(snap.entry_price)
    sl = float(snap.stop_loss)
    tp = float(snap.take_profit)
    sl_p = sl_pips(symbol, entry, sl)
    tp_p = sl_pips(symbol, entry, tp)
    realised = signed_pips(symbol, side, entry, exit_price)
    rr = r_multiple(realised, sl_p)
    atr = snap.atr
    atr_pips = None
    if atr and atr > 0:
        from forex_bot.profit_protection import pip_size

        pip = pip_size(symbol)
        atr_pips = atr / pip if pip else None
    hold = (exit_time - entry_time).total_seconds() / 60.0
    rec = TradeRecord(
        snapshot=snap,
        entry_time=entry_time,
        exit_time=exit_time,
        exit_reason=exit_reason,
        exit_price=exit_price,
        realised_pips=realised,
        realised_r=rr,
        win=bool(realised > 0) if exit_reason != "eod" else (realised > 0),
        mfe_pips=mfe_pips,
        mae_pips=mae_pips,
        mfe_r=r_multiple(mfe_pips, sl_p),
        mae_r=r_multiple(mae_pips, sl_p),
        mfe_atr=(mfe_pips / atr_pips) if atr_pips else None,
        mae_atr=(mae_pips / atr_pips) if atr_pips else None,
        time_to_mfe_min=time_to_mfe_min,
        time_to_mae_min=time_to_mae_min,
        time_in_trade_min=hold,
        sl_distance_pips=sl_p,
        tp_distance_pips=tp_p,
        sl_over_atr=(sl_p / atr_pips) if atr_pips else None,
        tp_over_atr=(tp_p / atr_pips) if atr_pips else None,
        max_tp_progress=(mfe_pips / tp_p) if tp_p > 0 else None,
        ambiguous=ambiguous,
        forward=forward_returns(df, entry_idx, symbol, side, entry),
    )
    if exit_reason in ("sl", "ambiguous_sl_tp"):
        rec.post_stop = observe_after_stop(df, exit_idx, symbol, side, entry, tp, sl_p)
    return rec
