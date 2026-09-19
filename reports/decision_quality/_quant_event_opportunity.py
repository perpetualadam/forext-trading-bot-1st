"""Vectorized event/opportunity discovery. Definitions frozen before results."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.event_discovery import (
    ATR_PATH_MULTS,
    BOOT_SEED,
    BREAKOUT_LOOKBACKS,
    COMBOS,
    COST_MULTS,
    HORIZONS_MIN,
    POS_RANGE_Q1,
    POS_RANGE_Q5,
    SPLIT_T50,
    SPLIT_T75,
    USD_BASE,
    USD_QUOTE,
    assign_split,
    enter_true_grouped,
    event_bootstrap_mean,
    future_path_block,
    half_spread_pips,
    other_pairs_usd_context,
    path_order,
    prior_rolling_extrema,
    session_transition,
    train_quantile_edges,
)
from forex_bot.decision_quality.feature_discovery import SYMBOLS, build_symbol_frame, inspect_symbol, utc_now
from forex_bot.profit_protection import pip_size

OUT_JSON = Path("reports/decision_quality/quant_event_opportunity_data.json")
PROGRESS = Path("reports/decision_quality/quant_event_opportunity_progress.json")
CACHE = Path("data/research/quant_features/six_pair_features.pkl")


def _j(obj):
    if isinstance(obj, dict):
        return {str(k): _j(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_j(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def dump(progress, results):
    PROGRESS.write_text(json.dumps(_j(progress), indent=2), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(_j(results), indent=2), encoding="utf-8")


def mark(progress, n, name, t0, findings, extra=None):
    rec = {
        "stage": n,
        "stage_name": name,
        "status": "completed",
        "started_at_utc": t0,
        "finished_at_utc": utc_now(),
        "findings": findings,
    }
    if extra:
        rec.update(extra)
    progress["stages"].append(rec)
    progress["completed_stages"] = sorted({s["stage"] for s in progress["stages"]})
    progress["last_checkpoint_at_utc"] = utc_now()
    progress["current_stage"] = n


def summarize_events(df: pd.DataFrame, mask: np.ndarray, side_up: bool | None) -> dict:
    """side_up True = expect UP opportunity; False = DOWN; None = magnitude only."""
    sub = df.loc[mask]
    out = {
        "event_n": int(mask.sum()),
        "by_split": {},
        "by_symbol": {},
        "horizons": {},
    }
    if sub.empty:
        return out
    for sp in ("train", "valid", "discovery_test"):
        out["by_split"][sp] = int((sub["split"] == sp).sum())
    for s in SYMBOLS:
        out["by_symbol"][s] = int((sub["symbol"] == s).sum())
    times = pd.to_datetime(sub["time"])
    if len(times) > 1:
        gaps = times.sort_values().diff().dt.total_seconds().dropna() / 60.0
        out["median_minutes_between"] = float(gaps.median()) if len(gaps) else None
    else:
        out["median_minutes_between"] = None
    for hz in HORIZONS_MIN:
        close_pips = sub[f"y_pips_{hz}m"].to_numpy()
        mfe_up = sub[f"mfe_up_{hz}m"].to_numpy()
        mfe_dn = sub[f"mfe_dn_{hz}m"].to_numpy()
        abs_exc = np.nanmax(np.vstack([mfe_up, mfe_dn]), axis=0)
        cost = sub["half_spread_pips"].to_numpy()
        row = {
            "n": int(np.isfinite(close_pips).sum()),
            "mean_close_pips": float(np.nanmean(close_pips)) if np.isfinite(close_pips).any() else None,
            "median_close_pips": float(np.nanmedian(close_pips)) if np.isfinite(close_pips).any() else None,
            "pct_close_up": float(np.nanmean(close_pips > 0)) if np.isfinite(close_pips).any() else None,
            "mean_mfe_up": float(np.nanmean(mfe_up)) if np.isfinite(mfe_up).any() else None,
            "mean_mfe_down": float(np.nanmean(mfe_dn)) if np.isfinite(mfe_dn).any() else None,
            "mean_abs_exc": float(np.nanmean(abs_exc)) if np.isfinite(abs_exc).any() else None,
            "hurdle": {},
        }
        fav = mfe_up if side_up is True else (mfe_dn if side_up is False else abs_exc)
        for m in COST_MULTS:
            need = cost * m
            ok = np.isfinite(fav) & np.isfinite(need)
            row["hurdle"][str(m)] = float(np.mean(fav[ok] >= need[ok])) if ok.any() else None
        # path order at 1x cost and 0.5 ATR
        for key in (f"order_cost1_{hz}m", f"order_atr05_{hz}m"):
            if key in sub.columns:
                vc = sub[key].value_counts(dropna=False)
                row[key] = {str(k): int(v) for k, v in vc.items()}
        if side_up is True:
            row["rev_close_pct"] = float(np.nanmean(close_pips < 0)) if np.isfinite(close_pips).any() else None
        elif side_up is False:
            row["rev_close_pct"] = float(np.nanmean(close_pips > 0)) if np.isfinite(close_pips).any() else None
        out["horizons"][str(hz)] = row
        # splits at 60m only extra
    # 60m by split
    out["h60_by_split"] = {}
    for sp in ("train", "valid", "discovery_test"):
        m = mask & (df["split"].to_numpy() == sp)
        yp = df.loc[m, "y_pips_60m"].to_numpy()
        up = df.loc[m, "mfe_up_60m"].to_numpy()
        dn = df.loc[m, "mfe_dn_60m"].to_numpy()
        out["h60_by_split"][sp] = {
            "n": int(m.sum()),
            "mean_close_pips": float(np.nanmean(yp)) if np.isfinite(yp).any() else None,
            "pct_close_up": float(np.nanmean(yp > 0)) if np.isfinite(yp).any() else None,
            "mean_mfe_up": float(np.nanmean(up)) if np.isfinite(up).any() else None,
            "mean_mfe_down": float(np.nanmean(dn)) if np.isfinite(dn).any() else None,
        }
    out["h60_by_symbol"] = {}
    for s in SYMBOLS:
        m = mask & (df["symbol"].to_numpy() == s)
        yp = df.loc[m, "y_pips_60m"].to_numpy()
        out["h60_by_symbol"][s] = {
            "n": int(m.sum()),
            "mean_close_pips": float(np.nanmean(yp)) if np.isfinite(yp).any() else None,
            "pct_close_up": float(np.nanmean(yp > 0)) if np.isfinite(yp).any() else None,
        }
    month_all = df["month"].to_numpy() if "month" in df.columns else pd.to_datetime(df["time"]).dt.to_period("M").astype(str).to_numpy()
    out["h60_by_month"] = {}
    for mo in sorted(set(month_all.tolist())):
        m = (month_all == mo) & mask
        if not m.any():
            continue
        yp = df.loc[m, "y_pips_60m"].to_numpy()
        out["h60_by_month"][mo] = {
            "n": int(m.sum()),
            "mean_close_pips": float(np.nanmean(yp)) if np.isfinite(yp).any() else None,
            "pct_close_up": float(np.nanmean(yp > 0)) if np.isfinite(yp).any() else None,
        }
    return out


def add_paths(df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sym, sub in df.groupby("symbol", sort=False):
        sub = sub.sort_values("time").reset_index(drop=True)
        close = sub["close"].to_numpy(dtype=float)
        high = sub["high"].to_numpy(dtype=float)
        low = sub["low"].to_numpy(dtype=float)
        atr = sub["atr14"].to_numpy(dtype=float)
        pip = pip_size(sym)
        cost_px = np.full(len(sub), half_spread_pips(sym) * pip)
        out = sub.copy()
        for hz in HORIZONS_MIN:
            h = hz // 5
            blk = future_path_block(close, high, low, h)
            out[f"y_pips_{hz}m"] = (blk["fwd_close"] - close) / pip
            out[f"y_atr_{hz}m"] = (blk["fwd_close"] - close) / (atr + 1e-12)
            out[f"mfe_up_{hz}m"] = (blk["fwd_high"] - close) / pip
            out[f"mfe_dn_{hz}m"] = (close - blk["fwd_low"]) / pip
            out[f"abs_exc_{hz}m"] = np.maximum(out[f"mfe_up_{hz}m"], out[f"mfe_dn_{hz}m"])
            out[f"bars_to_high_{hz}m"] = blk["bars_to_high"]
            out[f"bars_to_low_{hz}m"] = blk["bars_to_low"]
            out[f"order_cost1_{hz}m"] = path_order(close, blk["wh"], blk["wl"], cost_px)
            out[f"order_atr05_{hz}m"] = path_order(close, blk["wh"], blk["wl"], 0.5 * atr)
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    progress = {
        "study_started_at_utc": utc_now(),
        "last_checkpoint_at_utc": utc_now(),
        "current_stage": 1,
        "completed_stages": [],
        "total_stages": 26,
        "overall_status": "running",
        "stages": [],
        "definitions_frozen": True,
    }
    results: dict = {"started_at_utc": progress["study_started_at_utc"]}

    t1 = utc_now()
    print("STAGE 1", t1)
    integrity = [inspect_symbol(s) for s in SYMBOLS]
    results["stage1"] = {"symbols": integrity, "total_rows": sum(r["rows"] for r in integrity)}
    mark(progress, 1, "identity", t1, "Six CSVs match prior study ranges; gaps not repaired.")
    dump(progress, results)

    t2 = utc_now()
    print("STAGE 2-6 build", t2)
    if CACHE.exists():
        df = pd.read_pickle(CACHE)
        print("loaded cache", len(df))
    else:
        df = pd.concat([build_symbol_frame(s) for s in SYMBOLS], ignore_index=True)
        df = df.loc[df["atr14"].notna() & df["pos_in_range_24"].notna()].reset_index(drop=True)
    df["split"] = assign_split(df["time"])
    df["half_spread_pips"] = df["symbol"].map(half_spread_pips)
    print("add paths")
    df = add_paths(df)
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)
    df["month"] = pd.to_datetime(df["time"]).dt.to_period("M").astype(str)
    results["stage2"] = {
        "t50": str(SPLIT_T50),
        "t75": str(SPLIT_T75),
        "counts": df["split"].value_counts().to_dict(),
        "note": "DISCOVERY_TEST already inspected. Not a pristine final holdout.",
    }
    costs = {s: {"half_spread_pips": half_spread_pips(s), "multiples": {str(m): half_spread_pips(s) * m for m in COST_MULTS}} for s in SYMBOLS}
    results["stage3"] = {"cost_is_entry_half_spread_pips": costs, "atr_path_mults": list(ATR_PATH_MULTS)}
    # opportunity class balance (all bars)
    bal = {}
    for hz in (60, 240):
        bal[str(hz)] = {}
        for m in COST_MULTS:
            up = df[f"mfe_up_{hz}m"] >= df["half_spread_pips"] * m
            dn = df[f"mfe_dn_{hz}m"] >= df["half_spread_pips"] * m
            both = up & dn
            only_up = up & ~dn
            only_dn = dn & ~up
            neither = ~up & ~dn
            n = len(df)
            bal[str(hz)][str(m)] = {
                "only_up": float(only_up.mean()),
                "only_down": float(only_dn.mean()),
                "both": float(both.mean()),
                "neither": float(neither.mean()),
                "n": n,
            }
    amb = {str(hz): float((df[f"order_cost1_{hz}m"] == "AMBIGUOUS").mean()) for hz in HORIZONS_MIN}
    results["stage4_6"] = {
        "horizons": list(HORIZONS_MIN),
        "ambiguous_rate_cost1": amb,
        "opportunity_balance": bal,
    }
    mark(progress, 2, "splits", t2, "Frozen prior cuts. DISCOVERY_TEST is exploratory only.")
    mark(progress, 3, "cost_hurdles", t2, "Half-spread multiples 0.5/1/1.5/2/3 predeclared.")
    mark(progress, 4, "future_paths", t2, "MFE-up/down and close returns 15-480m.")
    mark(progress, 5, "path_order", t2, f"Ambiguous same-bar rates: {amb}")
    mark(progress, 6, "opportunity_balance", t2, "Class balance under predeclared cost hurdles.")
    dump(progress, results)
    print("balance 60m 1x", bal["60"]["1.0"])

    # Freeze NEW train quantiles (not pos_in_range — already frozen)
    t7 = utc_now()
    print("STAGE 7+ events", t7)
    tr = df["split"].to_numpy() == "train"
    edges = {
        "pos_in_range_24_q1": POS_RANGE_Q1,
        "pos_in_range_24_q5": POS_RANGE_Q5,
        "dist_mean24_atr": train_quantile_edges(df.loc[tr, "dist_rollmean24_atr"].to_numpy()).tolist(),
        "dist_sma20_atr": train_quantile_edges(df.loc[tr, "dist_sma20_atr"].to_numpy()).tolist(),
        "signed_body_atr": train_quantile_edges(df.loc[tr, "signed_body_atr"].to_numpy()).tolist(),
        "range_atr": train_quantile_edges(df.loc[tr, "range_atr"].to_numpy()).tolist(),
        "ret_1_abs_atr": train_quantile_edges(df.loc[tr, "ret_1_atr"].abs().to_numpy()).tolist(),
        "atr_pctile": train_quantile_edges(df.loc[tr, "atr_pctile"].to_numpy()).tolist(),
        "rv_ratio": train_quantile_edges(df.loc[tr, "rv_ratio"].to_numpy()).tolist(),
    }
    results["frozen_edges"] = edges
    dump(progress, results)  # persist definitions before event tables
    print("FROZEN EDGES", edges)

    def q1(col):
        return edges[col][1]

    def q5(col):
        return edges[col][4]

    # Range events (transition into extreme; not every persistent bar)
    g = df["symbol"].to_numpy()
    bottom = df["pos_in_range_24"].to_numpy() <= POS_RANGE_Q1
    top = df["pos_in_range_24"].to_numpy() >= POS_RANGE_Q5
    atr_p = df["atr_pctile"].to_numpy()
    prev_atr = np.r_[np.nan, atr_p[:-1]]
    prev_atr = np.where(np.r_[True, g[1:] != g[:-1]], np.nan, prev_atr)
    ev = {
        "range_bottom_enter": enter_true_grouped(bottom, g),
        "range_top_enter": enter_true_grouped(top, g),
        "extend_down_enter": enter_true_grouped(df["dist_rollmean24_atr"].to_numpy() <= q1("dist_mean24_atr"), g),
        "extend_up_enter": enter_true_grouped(df["dist_rollmean24_atr"].to_numpy() >= q5("dist_mean24_atr"), g),
        "impulse_bull_enter": enter_true_grouped(df["signed_body_atr"].to_numpy() >= q5("signed_body_atr"), g),
        "impulse_bear_enter": enter_true_grouped(df["signed_body_atr"].to_numpy() <= q1("signed_body_atr"), g),
        "vol_expand_enter": enter_true_grouped(atr_p >= q5("atr_pctile"), g),
        "vol_exit_compress": (prev_atr <= q1("atr_pctile")) & (atr_p >= edges["atr_pctile"][3]),
    }

    # Breakouts / rejections: rolling high/low exclude the current bar.
    for lb in BREAKOUT_LOOKBACKS:
        prior_high = df.groupby("symbol", sort=False)["high"].transform(
            lambda s: pd.Series(prior_rolling_extrema(s.to_numpy(), lb, "max"), index=s.index)
        )
        prior_low = df.groupby("symbol", sort=False)["low"].transform(
            lambda s: pd.Series(prior_rolling_extrema(s.to_numpy(), lb, "min"), index=s.index)
        )
        df[f"prior_high_{lb}"] = prior_high
        df[f"prior_low_{lb}"] = prior_low
        ev[f"breakout_up_{lb}"] = enter_true_grouped(df["close"].to_numpy() > prior_high.to_numpy(), g)
        ev[f"breakout_dn_{lb}"] = enter_true_grouped(df["close"].to_numpy() < prior_low.to_numpy(), g)
        ev[f"reject_upper_{lb}"] = enter_true_grouped(
            (df["high"].to_numpy() > prior_high.to_numpy()) & (df["close"].to_numpy() <= prior_high.to_numpy()),
            g,
        )
        ev[f"reject_lower_{lb}"] = enter_true_grouped(
            (df["low"].to_numpy() < prior_low.to_numpy()) & (df["close"].to_numpy() >= prior_low.to_numpy()),
            g,
        )

    # Session transitions — existing buckets only
    sess = df["session"].to_numpy()
    prev_s = np.empty(len(sess), dtype=object)
    prev_s[0] = ""
    prev_s[1:] = sess[:-1]
    prev_s = np.where(np.r_[True, g[1:] != g[:-1]], "", prev_s)
    trans = np.array([session_transition(a, b) for a, b in zip(prev_s, sess)], dtype=object)
    ev["asia_to_london"] = trans == "asia_to_london"
    ev["london_to_overlap"] = trans == "london_to_overlap"
    ev["overlap_to_late_ny"] = trans == "overlap_to_late_ny"

    print("usd panel")
    ctx = other_pairs_usd_context(df["time"], df["symbol"], df["ret_6"])
    df = df.merge(ctx, on=["time", "symbol"], how="left")
    df["usd_div"] = df["usd_own"] - df["usd_others_med"]
    tr_mask = df["split"].to_numpy() == "train"
    edges["usd_div"] = train_quantile_edges(df.loc[tr_mask, "usd_div"].to_numpy()).tolist()
    ev["usd_div_extreme_pos"] = enter_true_grouped(df["usd_div"].to_numpy() >= edges["usd_div"][4], g)
    ev["usd_div_extreme_neg"] = enter_true_grouped(df["usd_div"].to_numpy() <= edges["usd_div"][1], g)

    # Combos
    ev["range_bottom_and_lower_reject"] = ev["range_bottom_enter"] & ev["reject_lower_24"]
    ev["range_top_and_upper_reject"] = ev["range_top_enter"] & ev["reject_upper_24"]
    ev["range_bottom_and_usd_div"] = ev["range_bottom_enter"] & (
        ev["usd_div_extreme_pos"] | ev["usd_div_extreme_neg"]
    )
    ev["breakout_up_24_and_vol_expand"] = ev["breakout_up_24"] & ev["vol_expand_enter"]
    ev["impulse_bull_and_usd_agree"] = ev["impulse_bull_enter"] & (df["usd_others_agree"].to_numpy() >= 0.6)

    sides = {
        "range_bottom_enter": True,
        "range_top_enter": False,
        "extend_down_enter": True,
        "extend_up_enter": False,
        "impulse_bull_enter": None,
        "impulse_bear_enter": None,
        "vol_expand_enter": None,
        "vol_exit_compress": None,
        "breakout_up_12": True,
        "breakout_up_24": True,
        "breakout_up_48": True,
        "breakout_dn_12": False,
        "breakout_dn_24": False,
        "breakout_dn_48": False,
        "reject_upper_24": False,
        "reject_lower_24": True,
        "asia_to_london": None,
        "london_to_overlap": None,
        "overlap_to_late_ny": None,
        "usd_div_extreme_pos": None,
        "usd_div_extreme_neg": None,
        "range_bottom_and_lower_reject": True,
        "range_top_and_upper_reject": False,
        "range_bottom_and_usd_div": True,
        "breakout_up_24_and_vol_expand": True,
        "impulse_bull_and_usd_agree": True,
    }

    event_tables = {}
    for name, mask in ev.items():
        if name not in sides:
            continue
        print("event", name, int(mask.sum()))
        event_tables[name] = summarize_events(df, mask, sides[name])
        event_tables[name]["raw_true_bars"] = int(
            {
                "range_bottom_enter": bottom,
                "range_top_enter": top,
            }.get(name, mask).sum()
            if name in ("range_bottom_enter", "range_top_enter")
            else mask.sum()
        )
        if name == "range_bottom_enter":
            event_tables[name]["raw_state_bars"] = int(bottom.sum())
        if name == "range_top_enter":
            event_tables[name]["raw_state_bars"] = int(top.sum())

    # bootstrap promising candidates (predeclared: range extremes + reject + vol)
    boot = {}
    for name in ("range_bottom_enter", "range_top_enter", "vol_expand_enter", "reject_lower_24", "breakout_up_24"):
        m = ev[name]
        boot[name] = {
            "mfe_up_60": event_bootstrap_mean(df.loc[m, "mfe_up_60m"].to_numpy()),
            "mfe_dn_60": event_bootstrap_mean(df.loc[m, "mfe_dn_60m"].to_numpy()),
            "close_60": event_bootstrap_mean(df.loc[m, "y_pips_60m"].to_numpy()),
            "abs_60": event_bootstrap_mean(df.loc[m, "abs_exc_60m"].to_numpy()),
        }
    results["frozen_edges"] = edges
    results["events"] = event_tables
    results["bootstrap"] = boot
    results["n_rows"] = int(len(df))
    mark(progress, 7, "range_extreme_events", t7, "Entry into TRAIN q1/q5 pos_in_range_24.")
    mark(progress, 8, "extension_events", t7, "Enter TRAIN q1/q5 dist_rollmean24_atr.")
    mark(progress, 9, "impulse_events", t7, "Enter TRAIN q1/q5 signed_body_atr.")
    mark(progress, 10, "vol_transition", t7, "atr_pctile enter q5; exit compression.")
    mark(progress, 11, "breakouts", t7, "First close beyond prior 12/24/48 high/low.")
    mark(progress, 12, "rejections", t7, "Trade beyond prior 24 range, close back inside.")
    mark(progress, 13, "session_transitions", t7, "asia-london, london-overlap, overlap-lateNY.")
    mark(progress, 14, "usd_context", t7, "Other-pairs-only median USD-direction ret_6.")
    mark(progress, 15, "usd_divergence", t7, "Enter TRAIN extreme usd_div.")
    mark(progress, 16, "combos", t7, f"Predeclared combos: {list(COMBOS)}")
    mark(progress, 17, "independence", t7, "Event n is transition count, not persistent bars.")
    mark(progress, 18, "bootstrap", t7, "Event-level bootstrap seed=42, 200 reps.")
    dump(progress, results)
    print("FINISH compute", utc_now())


if __name__ == "__main__":
    main()
