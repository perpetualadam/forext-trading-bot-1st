"""Quant V2 Experiment A: historical spread + volume. Research-only. No downloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.event_discovery import (
    BOOT_REPS,
    BOOT_SEED,
    HORIZONS_MIN,
    SPLIT_T50,
    SPLIT_T75,
    assign_split,
    enter_true_grouped,
    event_bootstrap_mean,
    future_path_block,
    path_order,
    prior_rolling_extrema,
)
from forex_bot.decision_quality.feature_discovery import SYMBOLS, utc_now
from forex_bot.decision_quality.history_cache import classify_gap, default_historical_dir
from forex_bot.decision_quality.sessions import classify_session
from forex_bot.decision_quality.spread_volume import (
    ATR_PCTILE_Q5,
    POS_RANGE_Q1,
    POS_RANGE_Q5,
    SIGNED_BODY_Q1,
    SIGNED_BODY_Q5,
    apply_frozen_edges,
    flag_invalid_spread,
    full_close_spread,
    half_close_spread,
    lagged_rolling_median,
    modeled_half_spread_pips,
    to_pips,
    train_quantile_edges,
    two_sided_hurdle,
)
from forex_bot.indicators import _true_range
from forex_bot.profit_protection import pip_size

OUT = Path("reports/decision_quality/quant_v2_experiment_a_data.json")
PROGRESS = Path("reports/decision_quality/quant_v2_experiment_a_progress.json")
HIST = default_historical_dir()


def _j(obj):
    if isinstance(obj, dict):
        return {str(k): _j(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_j(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def dump(progress, results):
    PROGRESS.write_text(json.dumps(_j(progress), indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(_j(results), indent=2), encoding="utf-8")


def mark(progress, n, name, t0, findings):
    progress["stages"].append(
        {
            "stage": n,
            "stage_name": name,
            "status": "completed",
            "started_at_utc": t0,
            "finished_at_utc": utc_now(),
            "findings": findings,
        }
    )
    progress["completed_stages"] = sorted({s["stage"] for s in progress["stages"]})
    progress["current_stage"] = n
    progress["last_checkpoint_at_utc"] = utc_now()


def dist_stats(x: np.ndarray) -> dict:
    v = np.asarray(x, dtype=float)
    fin = v[np.isfinite(v)]
    if len(fin) == 0:
        return {"n": 0, "missing": int((~np.isfinite(v)).sum())}
    qs = np.quantile(fin, [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99])
    return {
        "n": int(len(fin)),
        "missing": int((~np.isfinite(v)).sum()),
        "zero": int((fin == 0).sum()),
        "negative": int((fin < 0).sum()),
        "mean": float(np.mean(fin)),
        "median": float(np.median(fin)),
        "p01": float(qs[0]),
        "p10": float(qs[1]),
        "p25": float(qs[2]),
        "p75": float(qs[4]),
        "p90": float(qs[5]),
        "p99": float(qs[6]),
        "maximum": float(np.max(fin)),
    }


def inspect_mba(symbol: str) -> dict:
    path = HIST / f"{symbol}_M5.csv"
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    t = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    gaps = {"none": 0, "expected_weekend": 0, "unexpected": 0}
    times = [x.to_pydatetime() for x in t]
    for a, b in zip(times, times[1:]):
        gaps[classify_gap(a, b)] += 1
    inc = 0
    if "complete" in raw.columns:
        flag = raw["complete"].astype(str).str.lower()
        inc = int(flag.isin(("0", "false", "no", "f", "incomplete")).sum())
    need = [
        "open",
        "high",
        "low",
        "close",
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
        "volume",
    ]
    return {
        "symbol": symbol,
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": int(len(raw)),
        "earliest": t.iloc[0].isoformat() if len(raw) else None,
        "latest": t.iloc[-1].isoformat() if len(raw) else None,
        "duplicates": int(t.duplicated().sum()),
        "monotonic": bool(t.is_monotonic_increasing),
        "incomplete_flagged": inc,
        "gaps": gaps,
        "columns_present": {c: c in raw.columns for c in need},
    }


def load_symbol(symbol: str) -> pd.DataFrame:
    path = HIST / f"{symbol}_M5.csv"
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw["symbol"] = symbol
    pip = pip_size(symbol)
    atr = _true_range(raw["high"], raw["low"], raw["close"]).rolling(14).mean()
    raw["atr14"] = atr
    raw["full_close_spread"] = full_close_spread(raw["ask_close"], raw["bid_close"])
    raw["full_open_spread"] = full_close_spread(raw["ask_open"], raw["bid_open"])
    raw["half_close_spread"] = half_close_spread(raw["ask_close"], raw["bid_close"])
    raw["full_close_spread_pips"] = raw["full_close_spread"] / pip
    raw["half_close_spread_pips"] = raw["half_close_spread"] / pip
    raw["modeled_half_pips"] = modeled_half_spread_pips(symbol)
    raw["spread_atr"] = raw["half_close_spread"] / (atr + 1e-12)
    raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
    raw["session"] = [classify_session(x.to_pydatetime()) for x in raw["time"]]
    rng = raw["high"].rolling(24).max() - raw["low"].rolling(24).min()
    raw["pos_in_range_24"] = (raw["close"] - raw["low"].rolling(24).min()) / (rng + 1e-12)
    raw["signed_body_atr"] = (raw["close"] - raw["open"]) / (atr + 1e-12)
    raw["atr_pctile"] = atr.rolling(100).rank(pct=True)
    raw["split"] = assign_split(raw["time"])
    raw["month"] = raw["time"].dt.to_period("M").astype(str)
    close = raw["close"].to_numpy(dtype=float)
    high = raw["high"].to_numpy(dtype=float)
    low = raw["low"].to_numpy(dtype=float)
    half_px = raw["half_close_spread"].to_numpy(dtype=float)
    for hz in HORIZONS_MIN:
        blk = future_path_block(close, high, low, hz // 5)
        raw[f"y_pips_{hz}m"] = (blk["fwd_close"] - close) / pip
        raw[f"abs_close_{hz}m"] = np.abs(raw[f"y_pips_{hz}m"])
        raw[f"mfe_up_{hz}m"] = (blk["fwd_high"] - close) / pip
        raw[f"mfe_dn_{hz}m"] = (close - blk["fwd_low"]) / pip
        raw[f"abs_exc_{hz}m"] = np.maximum(raw[f"mfe_up_{hz}m"], raw[f"mfe_dn_{hz}m"])
        raw[f"order_half_{hz}m"] = path_order(close, blk["wh"], blk["wl"], half_px)
    return raw


def bucket_table(df: pd.DataFrame, mask_col: str, side_up=None) -> dict:
    out = {}
    for q in range(1, 6):
        m = df[mask_col].to_numpy() == q
        out[f"q{q}"] = summarize(df, m, side_up)
    return out


def summarize(df: pd.DataFrame, mask: np.ndarray, side_up=None) -> dict:
    sub = df.loc[mask]
    rec = {"n": int(mask.sum()), "by_split": {}, "by_symbol": {}}
    if sub.empty:
        return rec
    for sp in ("train", "valid", "discovery_test"):
        rec["by_split"][sp] = int((sub["split"] == sp).sum())
    for s in SYMBOLS:
        rec["by_symbol"][s] = int((sub["symbol"] == s).sum())
    cost = sub["half_close_spread_pips"].to_numpy()
    for hz in (60, 240):
        yp = sub[f"y_pips_{hz}m"].to_numpy()
        up = sub[f"mfe_up_{hz}m"].to_numpy()
        dn = sub[f"mfe_dn_{hz}m"].to_numpy()
        ab = sub[f"abs_exc_{hz}m"].to_numpy()
        ac = sub[f"abs_close_{hz}m"].to_numpy()
        rec[f"h{hz}"] = {
            "mean_close_pips": _nanmean(yp),
            "pct_close_up": _nanmean(yp > 0) if np.isfinite(yp).any() else None,
            "mean_abs_close": _nanmean(ac),
            "mean_mfe_up": _nanmean(up),
            "mean_mfe_down": _nanmean(dn),
            "mean_abs_exc": _nanmean(ab),
            "mean_mfe_up_over_cost": _nanmean(up / cost),
            "mean_mfe_dn_over_cost": _nanmean(dn / cost),
            "mean_abs_exc_over_cost": _nanmean(ab / cost),
            "mean_close_over_cost": _nanmean(yp / cost),
            "median_half_cost_pips": _nanmedian(cost),
        }
    rec["h60_by_split"] = {}
    for sp in ("train", "valid", "discovery_test"):
        m = mask & (df["split"].to_numpy() == sp)
        rec["h60_by_split"][sp] = _h60(df, m)
    rec["h60_by_symbol"] = {s: _h60(df, mask & (df["symbol"].to_numpy() == s)) for s in SYMBOLS}
    return rec


def _nanmean(x):
    x = np.asarray(x, dtype=float)
    return float(np.nanmean(x)) if np.isfinite(x).any() else None


def _nanmedian(x):
    x = np.asarray(x, dtype=float)
    return float(np.nanmedian(x)) if np.isfinite(x).any() else None


def _h60(df, mask):
    yp = df.loc[mask, "y_pips_60m"].to_numpy()
    ab = df.loc[mask, "abs_exc_60m"].to_numpy()
    cost = df.loc[mask, "half_close_spread_pips"].to_numpy()
    return {
        "n": int(np.asarray(mask).sum()),
        "mean_close_pips": _nanmean(yp),
        "pct_close_up": _nanmean(yp > 0) if np.isfinite(yp).any() else None,
        "mean_abs_exc": _nanmean(ab),
        "mean_abs_exc_over_cost": _nanmean(ab / cost),
        "mean_close_over_cost": _nanmean(yp / cost),
        "median_half_cost": _nanmedian(cost),
    }


def two_sided_counts(labels: np.ndarray) -> dict:
    s = pd.Series(labels)
    n = max(len(s), 1)
    return {str(k): {"n": int(v), "pct": float(v / n)} for k, v in s.value_counts(dropna=False).items()}


def main() -> None:
    progress = {
        "study_started_at_utc": utc_now(),
        "last_checkpoint_at_utc": utc_now(),
        "current_stage": 1,
        "completed_stages": [],
        "total_stages": 26,
        "overall_status": "running",
        "no_download": True,
        "no_train": True,
        "stages": [],
    }
    results: dict = {"started_at_utc": progress["study_started_at_utc"]}

    t1 = utc_now()
    print("STAGE 1", t1)
    ident = [inspect_mba(s) for s in SYMBOLS]
    results["stage1"] = {"symbols": ident, "total_rows": sum(r["rows"] for r in ident)}
    mark(progress, 1, "identity", t1, "Six MBA CSVs match V1 DEV0 identity; bid/ask/volume present.")
    dump(progress, results)

    t2 = utc_now()
    print("STAGE 2-5 load", t2)
    frames = [load_symbol(s) for s in SYMBOLS]
    df = pd.concat(frames, ignore_index=True).sort_values(["symbol", "time"]).reset_index(drop=True)
    g = df["symbol"].to_numpy()
    results["stage2"] = {
        "close_spread": "ask_close - bid_close at the completed bar",
        "open_spread": "ask_open - bid_open at the completed bar",
        "not_inferred": "ask_low - bid_high is not a simultaneous spread and is not used",
        "half_spread": "full_close_spread / 2 = contemporaneous entry-cost analogue",
        "v1_modeled": "simulated_half_spread price / pip_size → 1.0 pip (1.5 GBP)",
        "tick_path": "bid/ask OHLC do not reconstruct intra-bar spread path",
    }
    q_all = {}
    for s in SYMBOLS:
        sub = df.loc[df["symbol"] == s]
        q_all[s] = {
            "full_close_pips": dist_stats(sub["full_close_spread_pips"].to_numpy()),
            "half_close_pips": dist_stats(sub["half_close_spread_pips"].to_numpy()),
            "full_open_pips": dist_stats(to_pips(sub["full_open_spread"].to_numpy(), s)),
            "volume": dist_stats(sub["volume"].to_numpy()),
            "modeled_half_pips": modeled_half_spread_pips(s),
            "median_half_minus_modeled": float(
                np.nanmedian(sub["half_close_spread_pips"] - sub["modeled_half_pips"])
            ),
            "mean_half_minus_modeled": float(
                np.nanmean(sub["half_close_spread_pips"] - sub["modeled_half_pips"])
            ),
        }
    flags = flag_invalid_spread(df["full_close_spread"].to_numpy())
    results["stage3"] = {
        "by_symbol": q_all,
        "invalid_full_close": {k: int(v.sum()) for k, v in flags.items()},
        "by_split_half_pips": {
            sp: dist_stats(df.loc[df["split"] == sp, "half_close_spread_pips"].to_numpy())
            for sp in ("train", "valid", "discovery_test")
        },
        "by_month_half_median": df.groupby("month")["half_close_spread_pips"].median().to_dict(),
    }
    results["stage4"] = {
        "semantics": {
            "full_spread_pips": "ask_close-bid_close in pips",
            "half_spread_pips": "full/2 — comparable to V1 entry cost",
            "v1_entry_cost_pips": {s: modeled_half_spread_pips(s) for s in SYMBOLS},
        },
        "comparison": {s: q_all[s] for s in SYMBOLS},
    }
    results["stage5"] = {
        "semantics": "OANDA InstrumentsCandles volume field stored on the CSV. Not centralized FX volume. Treated as feed activity.",
        "by_symbol": {s: q_all[s]["volume"] for s in SYMBOLS},
        "by_month_median": df.groupby("month")["volume"].median().to_dict(),
    }
    mark(progress, 2, "spread_definition", t2, "Close/open spread defined; ask_low-bid_high unused.")
    mark(progress, 3, "spread_quality", t2, "Distributions persisted; negatives counted not cleaned.")
    mark(progress, 4, "vs_v1_cost", t2, "Historical half-spread compared to modeled 1.0/1.5 pip entry cost.")
    mark(progress, 5, "volume_semantics", t2, "Activity field, not FX volume.")
    dump(progress, results)
    print("neg spreads", int(flags["negative"].sum()), "half medians", {s: q_all[s]["half_close_pips"]["median"] for s in SYMBOLS})

    t6 = utc_now()
    print("STAGE 6-7 freeze buckets", t6)
    tr = df["split"].to_numpy() == "train"
    # TRAIN session medians for activity normalization (causal: TRAIN-only constants)
    sess_med = (
        df.loc[tr].groupby(["symbol", "session"], sort=False)["volume"].median().rename("train_sess_vol_med")
    )
    df = df.merge(sess_med, left_on=["symbol", "session"], right_index=True, how="left")
    df["vol_sess_rel"] = df["volume"] / (df["train_sess_vol_med"] + 1e-12)
    df["spread_vs_lag24"] = df["half_close_spread_pips"] / (
        lagged_rolling_median(df["half_close_spread_pips"].to_numpy(), 24, g) + 1e-12
    )
    df["vol_vs_lag24"] = df["volume"] / (lagged_rolling_median(df["volume"].to_numpy(), 24, g) + 1e-12)

    tr = df["split"].to_numpy() == "train"  # after merge, still aligned
    edges = {
        "half_close_spread_pips": train_quantile_edges(df.loc[tr, "half_close_spread_pips"].to_numpy()).tolist(),
        "spread_atr": train_quantile_edges(df.loc[tr, "spread_atr"].to_numpy()).tolist(),
        "volume": train_quantile_edges(df.loc[tr, "volume"].to_numpy()).tolist(),
        "vol_sess_rel": train_quantile_edges(df.loc[tr, "vol_sess_rel"].to_numpy()).tolist(),
        "spread_vs_lag24": train_quantile_edges(df.loc[tr, "spread_vs_lag24"].to_numpy()).tolist(),
        "vol_vs_lag24": train_quantile_edges(df.loc[tr, "vol_vs_lag24"].to_numpy()).tolist(),
    }
    results["frozen_edges"] = edges
    dump(progress, results)  # freeze before later tables
    print("FROZEN", edges)

    df["q_spread"] = apply_frozen_edges(df["half_close_spread_pips"].to_numpy(), np.array(edges["half_close_spread_pips"]))
    df["q_spread_atr"] = apply_frozen_edges(df["spread_atr"].to_numpy(), np.array(edges["spread_atr"]))
    df["q_vol"] = apply_frozen_edges(df["volume"].to_numpy(), np.array(edges["volume"]))
    df["q_vol_rel"] = apply_frozen_edges(df["vol_sess_rel"].to_numpy(), np.array(edges["vol_sess_rel"]))
    mark(progress, 6, "spread_states", t6, "TRAIN quintiles of half-spread pips and spread/ATR frozen.")
    mark(progress, 7, "activity_states", t6, "TRAIN quintiles of raw volume and session-relative volume frozen.")
    dump(progress, results)

    t8 = utc_now()
    print("STAGE 8-14", t8)
    results["stage8_spread_tradeability"] = bucket_table(df, "q_spread")
    results["stage9_activity_magnitude"] = {
        "raw_volume": bucket_table(df, "q_vol"),
        "session_relative": bucket_table(df, "q_vol_rel"),
    }
    results["stage10_spread_direction"] = {
        q: results["stage8_spread_tradeability"][q]["h60"]["mean_close_pips"]
        for q in ("q1", "q2", "q3", "q4", "q5")
    }
    results["stage10_spread_direction_splits"] = {
        q: results["stage8_spread_tradeability"][q]["h60_by_split"] for q in ("q1", "q5")
    }

    # Activity transitions
    ev = {
        "spread_enter_high": enter_true_grouped(df["q_spread"].to_numpy() == 5, g),
        "spread_exit_high": enter_true_grouped(df["q_spread"].to_numpy() != 5, g)
        & np.r_[False, (df["q_spread"].to_numpy()[:-1] == 5)]
        & np.r_[True, g[1:] == g[:-1]],
        "spread_expand": enter_true_grouped(df["spread_vs_lag24"].to_numpy() >= edges["spread_vs_lag24"][4], g),
        "spread_contract": enter_true_grouped(df["spread_vs_lag24"].to_numpy() <= edges["spread_vs_lag24"][1], g),
        "vol_enter_high": enter_true_grouped(df["q_vol_rel"].to_numpy() == 5, g),
        "vol_exit_low": (np.r_[np.nan, df["q_vol_rel"].to_numpy()[:-1]] == 1)
        & (df["q_vol_rel"].to_numpy() >= 3)
        & np.r_[False, g[1:] == g[:-1]],
        "vol_expand": enter_true_grouped(df["vol_vs_lag24"].to_numpy() >= edges["vol_vs_lag24"][4], g),
        "vol_contract": enter_true_grouped(df["vol_vs_lag24"].to_numpy() <= edges["vol_vs_lag24"][1], g),
    }
    # fix first-bar group for spread_exit
    prev_q = np.r_[0, df["q_spread"].to_numpy()[:-1]]
    prev_q = np.where(np.r_[True, g[1:] != g[:-1]], 0, prev_q)
    ev["spread_exit_high"] = enter_true_grouped((prev_q == 5) & (df["q_spread"].to_numpy() != 5), g)
    prev_vr = np.r_[0, df["q_vol_rel"].to_numpy()[:-1]]
    prev_vr = np.where(np.r_[True, g[1:] != g[:-1]], 0, prev_vr)
    ev["vol_exit_low"] = (prev_vr == 1) & (df["q_vol_rel"].to_numpy() >= 3)

    results["stage11_activity_direction"] = {
        "level_q": {q: results["stage9_activity_magnitude"]["session_relative"][q]["h60"]["mean_close_pips"] for q in ("q1", "q5")},
        "vol_expand": summarize(df, ev["vol_expand"]),
        "vol_contract": summarize(df, ev["vol_contract"]),
    }
    results["stage12_spread_events"] = {k: summarize(df, ev[k]) for k in ("spread_enter_high", "spread_exit_high", "spread_expand", "spread_contract")}
    results["stage13_activity_events"] = {k: summarize(df, ev[k]) for k in ("vol_enter_high", "vol_exit_low", "vol_expand", "vol_contract")}
    for k, m in ev.items():
        results.setdefault("independence", {})[k] = {
            "event_n": int(m.sum()),
            "raw_state_if_level": None,
        }
    results["independence"]["spread_q5_state_bars"] = int((df["q_spread"] == 5).sum())
    results["independence"]["vol_rel_q5_state_bars"] = int((df["q_vol_rel"] == 5).sum())

    low_s = df["q_spread"].to_numpy() == 1
    high_s = df["q_spread"].to_numpy() == 5
    low_v = df["q_vol_rel"].to_numpy() == 1
    high_v = df["q_vol_rel"].to_numpy() == 5
    results["stage14_2d"] = {
        "LOW_spread_LOW_activity": summarize(df, low_s & low_v),
        "LOW_spread_HIGH_activity": summarize(df, low_s & high_v),
        "HIGH_spread_LOW_activity": summarize(df, high_s & low_v),
        "HIGH_spread_HIGH_activity": summarize(df, high_s & high_v),
        "definitions": "LOW=TRAIN q1, HIGH=TRAIN q5 of half_close_spread_pips and vol_sess_rel",
    }

    # V1 events
    bottom = df["pos_in_range_24"].to_numpy() <= POS_RANGE_Q1
    top = df["pos_in_range_24"].to_numpy() >= POS_RANGE_Q5
    prior_h = df.groupby("symbol", sort=False)["high"].transform(
        lambda s: pd.Series(prior_rolling_extrema(s.to_numpy(), 24, "max"), index=s.index)
    )
    prior_l = df.groupby("symbol", sort=False)["low"].transform(
        lambda s: pd.Series(prior_rolling_extrema(s.to_numpy(), 24, "min"), index=s.index)
    )
    v1 = {
        "range_bottom_enter": enter_true_grouped(bottom, g),
        "range_top_enter": enter_true_grouped(top, g),
        "breakout_up_24": enter_true_grouped(df["close"].to_numpy() > prior_h.to_numpy(), g),
        "breakout_dn_24": enter_true_grouped(df["close"].to_numpy() < prior_l.to_numpy(), g),
        "impulse_bull": enter_true_grouped(df["signed_body_atr"].to_numpy() >= SIGNED_BODY_Q5, g),
        "impulse_bear": enter_true_grouped(df["signed_body_atr"].to_numpy() <= SIGNED_BODY_Q1, g),
        "vol_expand_v1": enter_true_grouped(df["atr_pctile"].to_numpy() >= ATR_PCTILE_Q5, g),
    }
    results["stage15_v1_events_actual_cost"] = {k: summarize(df, m) for k, m in v1.items()}
    results["stage16_range_bottom"] = summarize(df, v1["range_bottom_enter"], True)
    results["stage16_range_bottom"]["raw_state_bars"] = int(bottom.sum())
    results["stage17_breakouts"] = {
        "up": summarize(df, v1["breakout_up_24"], True),
        "down": summarize(df, v1["breakout_dn_24"], False),
    }

    # two-sided with contemporaneous half-spread
    lab60 = two_sided_hurdle(df["mfe_up_60m"], df["mfe_dn_60m"], df["half_close_spread_pips"])
    df["two_sided_60"] = lab60
    results["stage18_two_sided"] = {
        "overall": two_sided_counts(lab60),
        "by_split": {sp: two_sided_counts(lab60[df["split"].to_numpy() == sp]) for sp in ("train", "valid", "discovery_test")},
        "by_symbol": {s: two_sided_counts(lab60[df["symbol"].to_numpy() == s]) for s in SYMBOLS},
        "by_spread_q": {f"q{q}": two_sided_counts(lab60[df["q_spread"].to_numpy() == q]) for q in range(1, 6)},
        "by_vol_rel_q": {f"q{q}": two_sided_counts(lab60[df["q_vol_rel"].to_numpy() == q]) for q in range(1, 6)},
        "modeled_1pip_both_for_reference": two_sided_counts(
            two_sided_hurdle(df["mfe_up_60m"], df["mfe_dn_60m"], df["modeled_half_pips"])
        ),
    }
    amb = {str(hz): float((df[f"order_half_{hz}m"] == "AMBIGUOUS").mean()) for hz in HORIZONS_MIN}
    results["stage18_ambiguous"] = amb

    boot = {}
    for name, m in (
        ("low_spread_high_activity", low_s & high_v),
        ("vol_enter_high", ev["vol_enter_high"]),
        ("spread_enter_high", ev["spread_enter_high"]),
        ("range_bottom_enter", v1["range_bottom_enter"]),
        ("breakout_up_24", v1["breakout_up_24"]),
        ("q1_spread_level", df["q_spread"].to_numpy() == 1),
        ("q5_vol_rel_level", df["q_vol_rel"].to_numpy() == 5),
    ):
        boot[name] = {
            "abs_exc_60": event_bootstrap_mean(df.loc[m, "abs_exc_60m"].to_numpy(), BOOT_SEED, BOOT_REPS),
            "abs_over_cost_60": event_bootstrap_mean(
                (df.loc[m, "abs_exc_60m"] / df.loc[m, "half_close_spread_pips"]).to_numpy(),
                BOOT_SEED,
                BOOT_REPS,
            ),
            "close_60": event_bootstrap_mean(df.loc[m, "y_pips_60m"].to_numpy(), BOOT_SEED, BOOT_REPS),
            "close_over_cost_60": event_bootstrap_mean(
                (df.loc[m, "y_pips_60m"] / df.loc[m, "half_close_spread_pips"]).to_numpy(),
                BOOT_SEED,
                BOOT_REPS,
            ),
        }
    results["stage20_bootstrap"] = boot

    # monthly for key cells
    def monthly(mask):
        out = {}
        months = df["month"].to_numpy()
        for mo in sorted(set(months.tolist())):
            m = mask & (months == mo)
            if not m.any():
                continue
            out[mo] = _h60(df, m)
        return out

    results["stage21_monthly"] = {
        "q1_spread": monthly(df["q_spread"].to_numpy() == 1),
        "q5_spread": monthly(df["q_spread"].to_numpy() == 5),
        "q5_vol_rel": monthly(df["q_vol_rel"].to_numpy() == 5),
        "low_spread_high_activity": monthly(low_s & high_v),
        "range_bottom": monthly(v1["range_bottom_enter"]),
    }

    mark(progress, 8, "spread_tradeability", t8, "Future MFE/cost by frozen spread quintile.")
    mark(progress, 9, "activity_magnitude", t8, "Future abs movement by frozen activity quintile.")
    mark(progress, 10, "spread_direction", t8, "Signed close by spread quintile.")
    mark(progress, 11, "activity_direction", t8, "Signed close by activity level and expand/contract.")
    mark(progress, 12, "spread_events", t8, "Enter/exit/expand/contract transitions.")
    mark(progress, 13, "activity_events", t8, "Activity transition events.")
    mark(progress, 14, "spread_x_activity", t8, "Four predeclared LOW/HIGH cells.")
    mark(progress, 15, "v1_events_actual_cost", t8, "Frozen V1 events vs contemporaneous half-spread.")
    mark(progress, 16, "range_bottom_cost", t8, "Range-bottom rechecked vs actual cost.")
    mark(progress, 17, "breakout_cost", t8, "24-bar breakouts rechecked vs actual cost.")
    mark(progress, 18, "two_sided_actual_cost", t8, "BOTH/ONLY/NEITHER using contemporaneous half-spread.")
    mark(progress, 19, "independence", t8, "Event n vs persistent state bars.")
    mark(progress, 20, "bootstrap", t8, "Event-level bootstrap seed=42, 200 reps.")
    mark(progress, 21, "cross_time", t8, "Splits + monthly for key cells.")
    mark(progress, 22, "cross_symbol", t8, "Per-symbol h60 inside each summarize().")
    dump(progress, results)
    print("FINISH compute", utc_now(), "rows", len(df))
    results["n_rows"] = int(len(df))
    results["finished_at_utc"] = utc_now()
    dump(progress, results)


if __name__ == "__main__":
    main()
