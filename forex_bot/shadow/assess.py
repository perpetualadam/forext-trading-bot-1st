"""Offline Stage E assessment. Label: EXPERIMENTAL_HEURISTIC_OFFLINE. No broker I/O."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from forex_bot.shadow.config import PAIRS, ShadowConfig
from forex_bot.shadow.cost_model import COST_SCENARIOS
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.reasons import STRATEGY_NAMES
from forex_bot.shadow.replay import _as_utc
from forex_bot.shadow.signals import build_feature_pack
from forex_bot.symbols import normalize_oanda_symbol

RESULT_LABEL = "EXPERIMENTAL_HEURISTIC_OFFLINE"
DEV_END = pd.Timestamp("2026-01-31 23:59:59+00:00")
VAL_END = pd.Timestamp("2026-04-30 23:59:59+00:00")
HIST_DIR = Path("data/historical")
MIN_TRADES_FOR_INFERENCE = 50


def load_m5(symbol: str) -> pd.DataFrame:
    path = HIST_DIR / f"{normalize_oanda_symbol(symbol)}_M5.csv"
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if "complete" in df.columns:
        df = df[df["complete"].astype(str).str.lower().isin(("true", "1"))].copy()
    return df


def split_by_dates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    t = df["time"]
    return {
        "development": df.loc[t <= DEV_END].copy(),
        "validation": df.loc[(t > DEV_END) & (t <= VAL_END)].copy(),
        "heldout": df.loc[t > VAL_END].copy(),
    }


def _gbp_map(gbp: pd.DataFrame) -> pd.Series:
    return gbp.set_index("time")["close"]


def _fx_at(gbp_close: pd.Series, ts: datetime) -> float | None:
    if gbp_close.empty:
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    try:
        loc = int(gbp_close.index.searchsorted(t, side="right") - 1)
    except (TypeError, ValueError, KeyError):
        return None
    if loc < 0:
        return None
    try:
        return float(gbp_close.iloc[loc])
    except (TypeError, ValueError, IndexError):
        return None


def _fx_array(gbp_close: pd.Series, times: pd.Series) -> np.ndarray:
    t = pd.to_datetime(times, utc=True)
    idx = gbp_close.index.searchsorted(t, side="right") - 1
    vals = gbp_close.to_numpy()
    out: np.ndarray = np.full(len(t), np.nan, dtype=float)
    ok = idx >= 0
    clipped = np.clip(idx, 0, max(len(vals) - 1, 0))
    if len(vals):
        out[ok] = vals[clipped[ok]]
    return out


def build_pair_cache(bars: pd.DataFrame, cfg: ShadowConfig) -> dict[int, dict[str, Any]]:
    work = bars.sort_values("time").reset_index(drop=True)
    return {
        cfg.scalp_lookback: build_feature_pack(work, cfg.scalp_lookback, cfg.history_window),
        cfg.swing_lookback: build_feature_pack(work, cfg.swing_lookback, cfg.history_window),
    }


def _attach_cache(engine: ShadowEngine, cache: dict[int, dict[str, Any]]) -> None:
    engine.feature_cache = cache
    engine.indicator_cache = {lb: pack["frame"] for lb, pack in cache.items()}


_BAR_KEYS = (
    "open",
    "high",
    "low",
    "close",
    "bid_open",
    "ask_open",
    "bid_high",
    "bid_low",
    "ask_high",
    "ask_low",
)


def _numeric_cols(df: pd.DataFrame) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for key in _BAR_KEYS:
        if key in df.columns:
            out[key] = df[key].to_numpy(dtype=float, copy=False)
    return out


def _bar_at(cols: dict[str, np.ndarray], i: int) -> dict[str, Any]:
    return {key: float(arr[i]) for key, arr in cols.items()}


def replay_frame(
    engine: ShadowEngine,
    symbol: str,
    bars: pd.DataFrame,
    gbp_close: pd.Series | None,
    cache: dict[int, dict[str, Any]] | None = None,
) -> None:
    engine.cfg.require_enabled()
    symbol = normalize_oanda_symbol(symbol)
    work = bars.sort_values("time").reset_index(drop=True)
    if cache is None:
        cache = build_pair_cache(work, engine.cfg)
    _attach_cache(engine, cache)
    fx_arr = _fx_array(gbp_close, work["time"]) if gbp_close is not None else None
    cols = _numeric_cols(work)
    times = [_as_utc(t) for t in work["time"].tolist()]
    dummy = work.iloc[:1]
    for i, ts in enumerate(times):
        fx = None
        if fx_arr is not None:
            raw = float(fx_arr[i])
            fx = None if math.isnan(raw) else raw
        engine.cursor = i
        engine.process_symbol_bar(
            symbol=symbol,
            history=dummy,
            bar_time=ts,
            fill_open=float(cols["open"][i]),
            gbp_usd_mid=fx,
            bar=_bar_at(cols, i),
            prev_bar_time=times[i - 1] if i else None,
        )


def _bootstrap_mean_ci(nets: list[float], rng: np.random.Generator, n_boot: int = 400) -> dict[str, Any]:
    if len(nets) < 10:
        return {"n": len(nets), "mean": None, "ci95": None, "method": "insufficient"}
    arr = np.asarray(nets, dtype=float)
    means: np.ndarray = np.empty(n_boot, dtype=float)
    n = len(arr)
    for b in range(n_boot):
        means[b] = float(arr[rng.integers(0, n, n)].mean())
    q = np.asarray(np.quantile(means, [0.025, 0.975]), dtype=float)
    lo = float(q[0])
    hi = float(q[1])
    return {
        "n": n,
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=1)) if n > 1 else 0.0,
        "ci95": [float(lo), float(hi)],
        "method": "iid_bootstrap_anti_conservative",
        "dependence_note": "Overlapping trades and USD-correlated pairs are not independent.",
    }


def _trade_stats(engine: ShadowEngine, *, period_seconds: float | None = None) -> dict[str, Any]:
    exits = [f for f in engine.fills if f.kind == "exit"]
    entries = [f for f in engine.fills if f.kind == "entry"]
    nets = [f.net_gbp for f in exits]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 1e-12 else None
    consec = 0
    max_consec = 0
    for x in nets:
        if x < 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    eq = engine.cfg.starting_nav_gbp
    peak = eq
    max_dd = 0.0
    for f in exits:
        eq += f.net_gbp
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    by_pair: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "net_gbp": 0.0, "wins": 0})
    by_strat: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "net_gbp": 0.0, "wins": 0})
    costs = 0.0
    units_hist: list[float] = []
    exit_reasons: dict[str, int] = defaultdict(int)
    pending: dict[tuple[str, str], datetime] = {}
    holds: list[float] = []
    for f in engine.fills:
        key = (f.symbol, f.strategy)
        if f.kind == "entry":
            pending[key] = f.timestamp
            units_hist.append(float(f.units))
        elif f.kind == "exit":
            opened = pending.pop(key, None)
            if opened is not None:
                holds.append((f.timestamp - opened).total_seconds())
            by_pair[f.symbol]["n"] += 1
            by_pair[f.symbol]["net_gbp"] += f.net_gbp
            by_pair[f.symbol]["wins"] += int(f.net_gbp > 0)
            by_strat[f.strategy]["n"] += 1
            by_strat[f.strategy]["net_gbp"] += f.net_gbp
            by_strat[f.strategy]["wins"] += int(f.net_gbp > 0)
            costs += f.costs_gbp
            exit_reasons[str(f.exit_reason or "unknown")] += 1
    rng = np.random.default_rng(7)
    uncertainty = _bootstrap_mean_ci(nets, rng)
    exposure = None
    if period_seconds and period_seconds > 0 and holds:
        exposure = float(sum(holds) / period_seconds)
    size_zero = int(engine.reason_counts.get("SIZE_INFEASIBLE", 0))
    return {
        "label": RESULT_LABEL,
        "not_original_bot": True,
        "signals_or_traces": dict(engine.reason_counts),
        "entries": len(entries),
        "closes": len(exits),
        "win_rate": (len(wins) / len(nets)) if nets else None,
        "gross_gbp": sum(f.gross_gbp for f in exits),
        "costs_gbp": costs,
        "net_gbp": sum(nets),
        "profit_factor": pf,
        "avg_win": (sum(wins) / len(wins)) if wins else None,
        "avg_loss": (sum(losses) / len(losses)) if losses else None,
        "max_dd_gbp": max_dd,
        "max_consecutive_losses": max_consec,
        "open_at_end": len(engine.positions),
        "equity_gbp": engine.equity_gbp,
        "start_nav_gbp": engine.cfg.starting_nav_gbp,
        "net_pct_start_nav": (sum(nets) / engine.cfg.starting_nav_gbp) if engine.cfg.starting_nav_gbp else None,
        "avg_hold_seconds": (sum(holds) / len(holds)) if holds else None,
        "exposure_time_frac": exposure,
        "mean_units": (sum(units_hist) / len(units_hist)) if units_hist else None,
        "min_units": min(units_hist) if units_hist else None,
        "size_infeasible": size_zero,
        "by_pair": dict(by_pair),
        "by_strategy": dict(by_strat),
        "exit_reasons": dict(exit_reasons),
        "uncertainty": uncertainty,
        "evidence_tag": "INSUFFICIENT_EVIDENCE" if len(nets) < MIN_TRADES_FOR_INFERENCE else "SAMPLED",
    }


def make_cfg(
    *,
    scenario: str,
    strategies: tuple[str, ...] = STRATEGY_NAMES,
    keep_traces: bool = False,
) -> ShadowConfig:
    return ShadowConfig(
        enabled=True,
        cost_scenario=scenario,
        quote_aware=True,
        result_label=RESULT_LABEL,
        keep_traces=keep_traces,
        history_window=250,
        strategies=strategies,
        starting_nav_gbp=97.15,
    )


def _period_seconds(chunk: pd.DataFrame) -> float | None:
    if chunk is None or chunk.empty or len(chunk) < 2:
        return None
    return float((chunk["time"].iloc[-1] - chunk["time"].iloc[0]).total_seconds())


def run_isolated(
    frames: dict[str, pd.DataFrame],
    gbp: pd.DataFrame,
    period: str,
    scenario: str,
    caches: dict[str, dict[int, dict[str, Any]]],
) -> dict[str, Any]:
    """One engine per strategy per pair. No cross-strategy competition."""
    gbp_close = _gbp_map(gbp)
    out: dict[str, Any] = {
        "label": RESULT_LABEL,
        "period": period,
        "scenario": scenario,
        "mode": "isolated_strategy_pair",
        "cells": {},
        "by_strategy": {},
    }
    strat_net = {s: 0.0 for s in STRATEGY_NAMES}
    strat_n = {s: 0 for s in STRATEGY_NAMES}
    strat_cost = {s: 0.0 for s in STRATEGY_NAMES}
    strat_dd = {s: 0.0 for s in STRATEGY_NAMES}
    for pair, df in frames.items():
        chunk = split_by_dates(df)[period].reset_index(drop=True)
        if chunk.empty:
            continue
        cache = caches[pair]
        sec = _period_seconds(chunk)
        engines = {
            name: ShadowEngine(cfg=make_cfg(scenario=scenario, strategies=(name,)))
            for name in STRATEGY_NAMES
        }
        for engine in engines.values():
            _attach_cache(engine, cache)
        fx_arr = _fx_array(gbp_close, chunk["time"])
        cols = _numeric_cols(chunk)
        times = [_as_utc(t) for t in chunk["time"].tolist()]
        dummy = chunk.iloc[:1]
        for i, ts in enumerate(times):
            raw = float(fx_arr[i])
            fx = None if math.isnan(raw) else raw
            bar = _bar_at(cols, i)
            prev = times[i - 1] if i else None
            for engine in engines.values():
                engine.cursor = i
                engine.process_symbol_bar(
                    symbol=pair,
                    history=dummy,
                    bar_time=ts,
                    fill_open=float(cols["open"][i]),
                    gbp_usd_mid=fx,
                    bar=bar,
                    prev_bar_time=prev,
                )
        for name, engine in engines.items():
            stats = _trade_stats(engine, period_seconds=sec)
            out["cells"][f"{name}|{pair}"] = stats
            strat_net[name] += float(stats["net_gbp"])
            strat_n[name] += int(stats["closes"])
            strat_cost[name] += float(stats["costs_gbp"])
            strat_dd[name] = max(strat_dd[name], float(stats["max_dd_gbp"]))
    out["by_strategy"] = {
        s: {
            "closes": strat_n[s],
            "net_gbp": strat_net[s],
            "costs_gbp": strat_cost[s],
            "max_dd_gbp_worst_pair": strat_dd[s],
        }
        for s in STRATEGY_NAMES
    }
    return out


def run_portfolio(
    frames: dict[str, pd.DataFrame],
    gbp: pd.DataFrame,
    period: str,
    scenario: str,
    caches: dict[str, dict[int, dict[str, Any]]],
) -> dict[str, Any]:
    gbp_close = _gbp_map(gbp)
    events: list[tuple[pd.Timestamp, str, int]] = []
    parts: dict[str, pd.DataFrame] = {}
    for pair, df in frames.items():
        chunk = split_by_dates(df)[period].reset_index(drop=True)
        parts[pair] = chunk
        for i, ts in enumerate(chunk["time"]):
            events.append((pd.Timestamp(ts), pair, i))
    events.sort()
    engine = ShadowEngine(cfg=make_cfg(scenario=scenario))
    fx_map = {pair: _fx_array(gbp_close, chunk["time"]) for pair, chunk in parts.items() if not chunk.empty}
    col_map = {pair: _numeric_cols(chunk) for pair, chunk in parts.items() if not chunk.empty}
    time_map = {pair: [_as_utc(t) for t in chunk["time"].tolist()] for pair, chunk in parts.items() if not chunk.empty}
    dummy_map = {pair: chunk.iloc[:1] for pair, chunk in parts.items() if not chunk.empty}
    for _ts, pair, i in events:
        cols = col_map[pair]
        times = time_map[pair]
        _attach_cache(engine, caches[pair])
        engine.cursor = i
        raw = float(fx_map[pair][i])
        fx = None if math.isnan(raw) else raw
        engine.process_symbol_bar(
            symbol=pair,
            history=dummy_map[pair],
            bar_time=times[i],
            fill_open=float(cols["open"][i]),
            gbp_usd_mid=fx,
            bar=_bar_at(cols, i),
            prev_bar_time=times[i - 1] if i else None,
        )
    span = None
    nonempty = [c for c in parts.values() if not c.empty]
    if nonempty:
        start = min(c["time"].iloc[0] for c in nonempty)
        end = max(c["time"].iloc[-1] for c in nonempty)
        span = float((end - start).total_seconds())
    stats = _trade_stats(engine, period_seconds=span)
    stats.update({"label": RESULT_LABEL, "period": period, "scenario": scenario, "mode": "portfolio"})
    return stats


def run_assessment(out_dir: Path) -> dict[str, Any]:
    frames = {p: load_m5(p) for p in PAIRS}
    gbp = frames["GBP_USD"]
    proto = make_cfg(scenario="base")
    coverage = {
        p: {
            "n": len(df),
            "start": str(df["time"].iloc[0]),
            "end": str(df["time"].iloc[-1]),
            "dev": len(split_by_dates(df)["development"]),
            "val": len(split_by_dates(df)["validation"]),
            "heldout": len(split_by_dates(df)["heldout"]),
        }
        for p, df in frames.items()
    }
    period_caches: dict[str, dict[str, dict[int, dict[str, Any]]]] = {}
    for period in ("development", "validation", "heldout"):
        period_caches[period] = {}
        for pair, df in frames.items():
            chunk = split_by_dates(df)[period].reset_index(drop=True)
            period_caches[period][pair] = build_pair_cache(chunk, proto)
    isolated: dict[str, Any] = {}
    portfolio: dict[str, Any] = {}
    for period in ("development", "validation", "heldout"):
        isolated[period] = {}
        portfolio[period] = {}
        for scenario in COST_SCENARIOS:
            isolated[period][scenario] = run_isolated(
                frames, gbp, period, scenario, period_caches[period]
            )
            portfolio[period][scenario] = run_portfolio(
                frames, gbp, period, scenario, period_caches[period]
            )
    blob = {
        "label": RESULT_LABEL,
        "not_original_bot": True,
        "coverage": coverage,
        "isolated": isolated,
        "portfolio": portfolio,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assessment_results.json").write_text(
        json.dumps(blob, indent=2, default=str), encoding="utf-8"
    )
    return blob


if __name__ == "__main__":
    run_assessment(Path("data/research/shadow_stage_e"))
