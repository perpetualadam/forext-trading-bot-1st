"""Research-only 2x2: momentum alignment x one-decision-per-M5.

Research isolation: no live execution imports, no .env reads, no stub edits.
Frozen specification — no search.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.ema_retracement import (
    FROZEN_LOOKBACK,
    SL_ATR_MULT,
    TP_R,
    _bar_extremes_for_side,
    _book_entry,
    load_m5_with_book,
    trade_stats,
)
from forex_bot.decision_quality.execution_sim import bar_touches
from forex_bot.decision_quality.history_cache import last_completed_bar_start
from forex_bot.decision_quality.stub_components import (
    HORIZONS_MIN,
    MOM_THR,
    atr_ok,
    current_stub_allow,
    episode_ids,
    first_qualifying_in_episode,
    magnitude_ok,
    sma_state,
)
from forex_bot.indicators import compute_indicators
from forex_bot.profit_protection import pip_size
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

RESEARCH_SYMBOLS: tuple[str, ...] = tuple(DEFAULT_FOREX_SYMBOLS)

# Stage 1 directional-quality chrono cuts. Frozen. Do not re-quantile.
TRAIN_LE = pd.Timestamp("2026-02-27 07:47:30+00:00")
VALID_LE = pd.Timestamp("2026-05-29 02:10:00+00:00")
STAGE1_FIRST_QUAL_N = 14104
STAGE1_TRAIN_N = 7052
STAGE1_VALID_N = 3528
STAGE1_TEST_N = 3524

CELLS: tuple[str, ...] = ("A0B0", "A1B0", "A0B1", "A1B1")
SPLITS: tuple[str, ...] = ("train", "valid", "test", "overall")


def aligned_stub_allow(
    state: np.ndarray,
    ret_1: np.ndarray,
    atr: np.ndarray,
    thr: float = MOM_THR,
) -> np.ndarray:
    """A1: SMA side unchanged; last-M5 return must agree in sign and exceed |thr|."""
    s = np.asarray(state)
    r = np.asarray(ret_1, dtype=float)
    ok_atr = atr_ok(atr)
    buy = (s > 0) & np.isfinite(r) & (r > float(thr))
    sell = (s < 0) & np.isfinite(r) & (r < -float(thr))
    return (buy | sell) & ok_atr


def gate_mask(state: np.ndarray, ret_1: np.ndarray, atr: np.ndarray, aligned: bool) -> np.ndarray:
    if aligned:
        return aligned_stub_allow(state, ret_1, atr, MOM_THR)
    return current_stub_allow(state, ret_1, atr)


def candle_key(symbol: str, ts: Any) -> tuple[str, pd.Timestamp]:
    return (str(symbol), pd.Timestamp(ts))


def assign_split(ts: Any) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    if t <= TRAIN_LE:
        return "train"
    if t <= VALID_LE:
        return "valid"
    return "test"


def last_completed_m5_key(symbol: str, entry_ts: Any) -> tuple[str, pd.Timestamp]:
    """Causal last completed M5 start at ``entry_ts``. No future bars."""
    t = pd.Timestamp(entry_ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    dt = t.to_pydatetime()
    start = last_completed_bar_start(dt, 5)
    return candle_key(symbol, pd.Timestamp(start, tz="UTC"))


def build_research_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    lookback = FROZEN_LOOKBACK[symbol]
    mid = df[["time", "open", "high", "low", "close"]].copy()
    ind = compute_indicators(mid.reset_index(drop=True), lookback=lookback)
    close = ind["close"].to_numpy(dtype=float)
    ma_fast = ind["ma_fast"].to_numpy(dtype=float)
    ma_slow = ind["ma_slow"].to_numpy(dtype=float)
    atr = ind["atr"].to_numpy(dtype=float)
    ret_1 = pd.Series(close).pct_change().to_numpy(dtype=float)
    state = sma_state(ma_fast, ma_slow)
    allow_a0 = current_stub_allow(state, ret_1, atr)
    allow_a1 = aligned_stub_allow(state, ret_1, atr)
    first_q = first_qualifying_in_episode(episode_ids(state), allow_a0)
    pip = pip_size(symbol)
    bid_c = pd.to_numeric(df["bid_close"], errors="coerce").to_numpy(dtype=float)
    ask_c = pd.to_numeric(df["ask_close"], errors="coerce").to_numpy(dtype=float)
    times = pd.to_datetime(ind["time"], utc=True)
    out = pd.DataFrame(
        {
            "time": times,
            "symbol": symbol,
            "close": close,
            "high": pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float),
            "low": pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float),
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "atr": atr,
            "ret_1": ret_1,
            "state": state,
            "stub_allow": allow_a0,
            "aligned_allow": allow_a1,
            "first_qual": first_q,
            "side": np.where(state > 0, "BUY", np.where(state < 0, "SELL", "")),
        }
    )
    for col in ("bid_close", "ask_close", "bid_high", "bid_low", "ask_high", "ask_low"):
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    n = len(out)
    risk = 2.0 * (atr / pip)
    for minutes in HORIZONS_MIN:
        steps = max(1, minutes // 5)
        bid_f = np.full(n, np.nan)
        ask_f = np.full(n, np.nan)
        if steps < n:
            bid_f[: n - steps] = bid_c[steps:]
            ask_f[: n - steps] = ask_c[steps:]
        buy = (bid_f - ask_c) / pip
        sell = (bid_c - ask_f) / pip
        orig = np.where(state > 0, buy, np.where(state < 0, sell, np.nan))
        out[f"fwd_{minutes}m_pips"] = orig
        out[f"fwd_{minutes}m_r"] = np.where(risk > 0, orig / risk, np.nan)
        out[f"fwd_{minutes}m_hit"] = orig > 0
    return out


def _walk_occupancy(
    frame: pd.DataFrame,
    symbol: str,
    start_i: int,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    sl_d: float,
) -> dict[str, Any]:
    n = len(frame)
    exit_px = None
    reason = "open"
    hold = 0
    j = start_i + 1
    first_mfe = None
    first_mae = None
    pip = pip_size(symbol)
    while j < n:
        nxt = frame.iloc[j]
        hi, lo = _bar_extremes_for_side(nxt, side)
        if first_mfe is None:
            if side == "BUY":
                first_mfe = (hi - entry) / pip
                first_mae = (entry - lo) / pip
            else:
                first_mfe = (entry - lo) / pip
                first_mae = (hi - entry) / pip
        touch = bar_touches(side, sl, tp, hi, lo)
        hold += 1
        if touch.hit_sl or touch.hit_tp:
            exit_px = float(touch.exit_price) if touch.exit_price is not None else sl
            reason = "ambiguous_sl" if touch.ambiguous else touch.exit_reason
            break
        j += 1
    if exit_px is None:
        last = frame.iloc[n - 1]
        if side == "BUY" and np.isfinite(last.get("bid_close", np.nan)):
            exit_px = float(last["bid_close"])
        elif side == "SELL" and np.isfinite(last.get("ask_close", np.nan)):
            exit_px = float(last["ask_close"])
        else:
            exit_px = float(last["close"])
        reason = "eod"
        hold = max(hold, n - start_i - 1)
        j = n - 1
    signed = (exit_px - entry) if side == "BUY" else (entry - exit_px)
    r_mult = signed / sl_d if sl_d > 0 else float("nan")
    row = frame.iloc[start_i]
    rec = {
        "symbol": symbol,
        "side": side,
        "time": row["time"],
        "entry": entry,
        "exit": exit_px,
        "r": float(r_mult),
        "reason": reason,
        "hold_bars": int(hold),
        "win": bool(np.isfinite(r_mult) and r_mult > 0),
        "source_candle": pd.Timestamp(row["time"]),
        "reentry": False,
        "exit_index": int(j),
        "first5m_mfe_pips": None if first_mfe is None else float(first_mfe),
        "first5m_mae_pips": None if first_mae is None else float(first_mae),
        "split": assign_split(row["time"]),
    }
    for minutes in (5, 15, 30, 60):
        rec[f"fwd_{minutes}m_pips"] = (
            float(row[f"fwd_{minutes}m_pips"]) if np.isfinite(row.get(f"fwd_{minutes}m_pips", np.nan)) else None
        )
        rec[f"fwd_{minutes}m_r"] = (
            float(row[f"fwd_{minutes}m_r"]) if np.isfinite(row.get(f"fwd_{minutes}m_r", np.nan)) else None
        )
        rec[f"fwd_{minutes}m_hit"] = (
            bool(row[f"fwd_{minutes}m_hit"]) if pd.notna(row.get(f"fwd_{minutes}m_hit")) else None
        )
    return rec


def simulate_cell_trades(
    frame: pd.DataFrame,
    signal: np.ndarray,
    symbol: str,
    *,
    allow_same_candle_reentry: bool,
) -> list[dict[str, Any]]:
    """One-position occupancy. B1 consumes (symbol, completed M5 time) once.

    B0 may take one additional entry after a first-forward-bar SL, still keyed
    to the same completed source candle. The second fill is modelled at the
    first exit price and managed from the next complete bar (no M1 path).
    """
    trades: list[dict[str, Any]] = []
    consumed: set[tuple[str, pd.Timestamp]] = set()
    n = len(frame)
    i = 0
    while i < n:
        if not bool(signal[i]):
            i += 1
            continue
        row = frame.iloc[i]
        st = int(row["state"])
        if st == 0:
            i += 1
            continue
        atr = float(row["atr"]) if np.isfinite(row["atr"]) else float("nan")
        if not np.isfinite(atr) or atr <= 0:
            i += 1
            continue
        key = candle_key(symbol, row["time"])
        if (not allow_same_candle_reentry) and key in consumed:
            i += 1
            continue
        side = "BUY" if st > 0 else "SELL"
        entry = _book_entry(row, side)
        sl_d = SL_ATR_MULT * atr
        sl = entry - sl_d if side == "BUY" else entry + sl_d
        tp = entry + sl_d * TP_R if side == "BUY" else entry - sl_d * TP_R
        rec = _walk_occupancy(frame, symbol, i, side, entry, sl, tp, sl_d)
        rec["reentry"] = False
        consumed.add(key)
        trades.append(rec)
        j = int(rec["exit_index"])
        fast_sl = rec["hold_bars"] == 1 and str(rec["reason"]).startswith("sl")
        if (
            allow_same_candle_reentry
            and fast_sl
            and j + 1 < n
        ):
            # Same source candle, new fill after the stop. Next complete bar only.
            re_entry = float(rec["exit"])
            re_sl = re_entry - sl_d if side == "BUY" else re_entry + sl_d
            re_tp = re_entry + sl_d * TP_R if side == "BUY" else re_entry - sl_d * TP_R
            dummy_start = j
            rec2 = _walk_occupancy(frame, symbol, dummy_start, side, re_entry, re_sl, re_tp, sl_d)
            rec2["time"] = row["time"]
            rec2["source_candle"] = rec["source_candle"]
            rec2["reentry"] = True
            rec2["split"] = rec["split"]
            rec2["parent_r"] = rec["r"]
            trades.append(rec2)
            i = int(rec2["exit_index"]) + 1
        else:
            i = j + 1
    return trades


def event_stats(frame: pd.DataFrame, mask: np.ndarray) -> dict[str, Any]:
    sub = frame.loc[mask]
    n = int(len(sub))
    if n == 0:
        return {"n": 0, "buy": 0, "sell": 0}
    out: dict[str, Any] = {
        "n": n,
        "buy": int((sub["state"] > 0).sum()),
        "sell": int((sub["state"] < 0).sum()),
    }
    for minutes in (5, 15, 30, 60):
        pips = sub[f"fwd_{minutes}m_pips"].to_numpy(dtype=float)
        r = sub[f"fwd_{minutes}m_r"].to_numpy(dtype=float)
        ok = np.isfinite(pips)
        x = pips[ok]
        rr = r[np.isfinite(r)]
        if len(x) == 0:
            out[f"{minutes}m"] = {"n": 0}
            continue
        wins = x[x > 0]
        losses = x[x < 0]
        gl = float(np.abs(losses.sum())) if len(losses) else 0.0
        out[f"{minutes}m"] = {
            "n": int(len(x)),
            "hit": float(np.mean(x > 0)),
            "mean_pips": float(np.mean(x)),
            "mean_r": float(np.mean(rr)) if len(rr) else None,
            "profit_factor": (float(wins.sum()) / gl) if gl > 0 else None,
        }
    return out


def occupancy_block(trades: list[dict[str, Any]]) -> dict[str, Any]:
    base = trade_stats(trades)
    rs = [t["r"] for t in trades if np.isfinite(t.get("r", np.nan))]
    if rs:
        base["r_std"] = float(np.std(rs, ddof=1)) if len(rs) > 1 else 0.0
        base["r_se"] = base["r_std"] / float(np.sqrt(len(rs))) if rs else None
    else:
        base["r_std"] = None
        base["r_se"] = None
    for minutes in (5, 15, 30, 60):
        hits = [t.get(f"fwd_{minutes}m_hit") for t in trades if t.get(f"fwd_{minutes}m_hit") is not None]
        rs_h = [t.get(f"fwd_{minutes}m_r") for t in trades if t.get(f"fwd_{minutes}m_r") is not None]
        base[f"{minutes}m_hit"] = float(np.mean(hits)) if hits else None
        base[f"{minutes}m_mean_r"] = float(np.mean(rs_h)) if rs_h else None
        base[f"{minutes}m_n"] = int(len(hits))
    mfe = [t.get("first5m_mfe_pips") for t in trades if t.get("first5m_mfe_pips") is not None]
    mae = [t.get("first5m_mae_pips") for t in trades if t.get("first5m_mae_pips") is not None]
    base["first5m_mfe_pips_mean"] = float(np.mean(mfe)) if mfe else None
    base["first5m_mae_pips_mean"] = float(np.mean(mae)) if mae else None
    base["fast_sl_n"] = int(sum(1 for t in trades if t.get("hold_bars") == 1 and str(t.get("reason", "")).startswith("sl") and not t.get("reentry")))
    base["reentry_n"] = int(sum(1 for t in trades if t.get("reentry")))
    return base


def split_trades(trades: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = {s: [] for s in SPLITS}
    for t in trades:
        out[t.get("split") or assign_split(t["time"])].append(t)
        out["overall"].append(t)
    return out


def classify_factor(valid_delta: float | None, test_delta: float | None, test_exp: float | None) -> str:
    """Frozen labels. C does not authorize deployment.

    Improvement = higher (less negative) expectancy on BOTH valid and test.
    """
    if valid_delta is None or test_delta is None or test_exp is None:
        return "A"
    if valid_delta <= 0 or test_delta <= 0:
        return "A"
    if test_exp > 0:
        return "C"
    return "B"


def vote_matches_a0(row: pd.Series) -> bool:
    vote = _quant_stub_vote(
        {
            "price": float(row["close"]),
            "ma_fast": float(row["ma_fast"]) if np.isfinite(row["ma_fast"]) else float(row["close"]),
            "ma_slow": float(row["ma_slow"]) if np.isfinite(row["ma_slow"]) else float(row["close"]),
            "returns": float(row["ret_1"]) if np.isfinite(row["ret_1"]) else 0.0,
            "atr": float(row["atr"]) if np.isfinite(row["atr"]) else 0.0,
        }
    )
    expected_side = str(row["side"] or "") or None
    if expected_side == "":
        expected_side = None
    return vote["direction"] == expected_side and bool(vote["allow"]) == bool(row["stub_allow"])


def reproduce_stage1_first_qual(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    parts = [df.loc[df["first_qual"]].copy() for df in frames.values()]
    ev = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if ev.empty:
        return {"pass": False, "n": 0}
    ev["split"] = [assign_split(t) for t in ev["time"]]
    n = int(len(ev))
    n_tr = int((ev["split"] == "train").sum())
    n_va = int((ev["split"] == "valid").sum())
    n_te = int((ev["split"] == "test").sum())
    ok_n = (
        abs(n - STAGE1_FIRST_QUAL_N) <= 5
        and abs(n_tr - STAGE1_TRAIN_N) <= 5
        and abs(n_va - STAGE1_VALID_N) <= 5
        and abs(n_te - STAGE1_TEST_N) <= 5
    )
    return {
        "pass": bool(ok_n),
        "n": n,
        "n_train": n_tr,
        "n_valid": n_va,
        "n_test": n_te,
        "expected": {
            "n": STAGE1_FIRST_QUAL_N,
            "n_train": STAGE1_TRAIN_N,
            "n_valid": STAGE1_VALID_N,
            "n_test": STAGE1_TEST_N,
            "train_le": str(TRAIN_LE),
            "valid_le": str(VALID_LE),
        },
    }


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def run_experiment() -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in RESEARCH_SYMBOLS:
        raw = load_m5_with_book(symbol)
        frames[symbol] = build_research_frame(raw, symbol)

    baseline = reproduce_stage1_first_qual(frames)
    if not baseline["pass"]:
        return {
            "baseline_reproduction": "FAIL",
            "baseline": baseline,
            "stop": True,
            "reason": "A0 first-qual event counts do not match the frozen Stage 1 baseline.",
        }

    cells: dict[str, list[dict[str, Any]]] = {c: [] for c in CELLS}
    event_masks: dict[str, dict[str, np.ndarray]] = {}
    for symbol, frame in frames.items():
        a0 = frame["stub_allow"].to_numpy(dtype=bool)
        a1 = frame["aligned_allow"].to_numpy(dtype=bool)
        event_masks[symbol] = {"A0": a0, "A1": a1}
        t_a0_b1 = simulate_cell_trades(frame, a0, symbol, allow_same_candle_reentry=False)
        t_a0_b0 = simulate_cell_trades(frame, a0, symbol, allow_same_candle_reentry=True)
        t_a1_b1 = simulate_cell_trades(frame, a1, symbol, allow_same_candle_reentry=False)
        t_a1_b0 = simulate_cell_trades(frame, a1, symbol, allow_same_candle_reentry=True)
        cells["A0B0"].extend(t_a0_b0)
        cells["A0B1"].extend(t_a0_b1)
        cells["A1B0"].extend(t_a1_b0)
        cells["A1B1"].extend(t_a1_b1)

    a0_event_n = int(sum(int(m["A0"].sum()) for m in event_masks.values()))
    a1_event_n = int(sum(int(m["A1"].sum()) for m in event_masks.values()))

    def cell_report(trades: list[dict[str, Any]]) -> dict[str, Any]:
        parts = split_trades(trades)
        out = {s: occupancy_block(parts[s]) for s in SPLITS}
        out["by_symbol"] = {}
        for sym in RESEARCH_SYMBOLS:
            out["by_symbol"][sym] = occupancy_block([t for t in trades if t["symbol"] == sym])
        out["by_side"] = {
            "BUY": occupancy_block([t for t in trades if t["side"] == "BUY"]),
            "SELL": occupancy_block([t for t in trades if t["side"] == "SELL"]),
        }
        return out

    reports = {name: cell_report(trs) for name, trs in cells.items()}

    def exp(name: str, split: str) -> float | None:
        return reports[name][split].get("expectancy_r")

    momentum = {
        "A1B0_minus_A0B0": {s: _delta(exp("A1B0", s), exp("A0B0", s)) for s in SPLITS},
        "A1B1_minus_A0B1": {s: _delta(exp("A1B1", s), exp("A0B1", s)) for s in SPLITS},
    }
    onem5 = {
        "A0B1_minus_A0B0": {s: _delta(exp("A0B1", s), exp("A0B0", s)) for s in SPLITS},
        "A1B1_minus_A1B0": {s: _delta(exp("A1B1", s), exp("A1B0", s)) for s in SPLITS},
    }
    combo = {s: _delta(exp("A1B1", s), exp("A0B0", s)) for s in SPLITS}

    reentries = [t for t in cells["A0B0"] if t.get("reentry")]
    parents = []
    for t in reentries:
        parents.append(t.get("parent_r"))
    same_candle = {
        "duplicate_opportunities_a0": int(sum(1 for t in cells["A0B1"] if t.get("hold_bars") == 1 and str(t.get("reason", "")).startswith("sl"))),
        "reentries_taken_a0b0": int(len(reentries)),
        "reentry_mean_r": float(np.mean([t["r"] for t in reentries])) if reentries else None,
        "parent_mean_r": float(np.mean(parents)) if parents else None,
        "reentry_win_rate": float(np.mean([t["win"] for t in reentries])) if reentries else None,
        "direction_same_as_parent": True,
    }

    event_by_split: dict[str, dict[str, Any]] = {}
    for gate, key in (("A0", "stub_allow"), ("A1", "aligned_allow")):
        ev = pd.concat([df.loc[df[key]].copy() for df in frames.values()], ignore_index=True)
        ev["split"] = [assign_split(t) for t in ev["time"]]
        event_by_split[gate] = {
            s: event_stats(ev, (ev["split"] == s).to_numpy() if s != "overall" else np.ones(len(ev), dtype=bool))
            for s in SPLITS
        }

    return {
        "baseline_reproduction": "PASS",
        "baseline": baseline,
        "stop": False,
        "cuts": {"train_le": str(TRAIN_LE), "valid_le": str(VALID_LE)},
        "momentum_threshold": MOM_THR,
        "sl_atr_mult": SL_ATR_MULT,
        "tp_r": TP_R,
        "candidate_events": {
            "A0": a0_event_n,
            "A1": a1_event_n,
            "A1_retention_vs_A0": (a1_event_n / a0_event_n) if a0_event_n else None,
            "A1_removed": a0_event_n - a1_event_n,
        },
        "event_level": event_by_split,
        "cells": reports,
        "occupancy_retention_vs_A0B0": {
            name: (
                reports[name]["overall"]["n"] / reports["A0B0"]["overall"]["n"]
                if reports["A0B0"]["overall"]["n"]
                else None
            )
            for name in CELLS
        },
        "momentum_effect": momentum,
        "one_m5_effect": onem5,
        "interaction_vs_A0B0": combo,
        "same_candle_reentry": same_candle,
        "classification": {
            "momentum": classify_factor(
                momentum["A1B0_minus_A0B0"]["valid"],
                momentum["A1B0_minus_A0B0"]["test"],
                exp("A1B0", "test"),
            ),
            "one_m5": classify_factor(
                onem5["A0B1_minus_A0B0"]["valid"],
                onem5["A0B1_minus_A0B0"]["test"],
                exp("A0B1", "test"),
            ),
            "combination": classify_factor(
                combo["valid"],
                combo["test"],
                exp("A1B1", "test"),
            ),
        },
        "strategy_labels": "NOT_RECONSTRUCTED",
        "m1_available": False,
    }
