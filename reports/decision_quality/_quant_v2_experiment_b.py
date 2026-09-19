"""Quant V2 Experiment B: cross-pair factor / residual / dispersion. Research-only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.cross_pair import (
    LAGS,
    PRIMARY_BARS,
    RETURN_BARS,
    apply_pca1,
    cross_section_iqr,
    cross_section_std,
    instrument_to_usd,
    leave_one_out_median,
    residual,
    reversal_instrument_side,
    synchronized_panel,
    train_betas,
    train_pca1,
    usd_ranks,
)
from forex_bot.decision_quality.event_discovery import (
    BOOT_REPS,
    BOOT_SEED,
    HORIZONS_MIN,
    assign_split,
    enter_true_grouped,
    event_bootstrap_mean,
    future_path_block,
)
from forex_bot.decision_quality.feature_discovery import SYMBOLS, utc_now
from forex_bot.decision_quality.history_cache import classify_gap, default_historical_dir
from forex_bot.decision_quality.sessions import classify_session
from forex_bot.decision_quality.spread_volume import (
    apply_frozen_edges,
    half_close_spread,
    train_quantile_edges,
)
from forex_bot.indicators import _true_range
from forex_bot.profit_protection import pip_size

# Frozen Experiment A session-relative activity edges (do not retune).
VOL_SESS_REL_EDGES = np.array(
    [0.005102040816326505, 0.6428571428571387, 0.879106438896188, 1.1380753138075266, 1.5610972568578514, 89.38255033556928]
)

OUT = Path("reports/decision_quality/quant_v2_experiment_b_data.json")
PROGRESS = Path("reports/decision_quality/quant_v2_experiment_b_progress.json")
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


def _nanmean(x):
    x = np.asarray(x, dtype=float)
    return float(np.nanmean(x)) if np.isfinite(x).any() else None


def dist_stats(x):
    v = np.asarray(x, dtype=float)
    fin = v[np.isfinite(v)]
    if len(fin) == 0:
        return {"n": 0}
    qs = np.quantile(fin, [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99])
    return {
        "n": int(len(fin)),
        "mean": float(np.mean(fin)),
        "std": float(np.std(fin)),
        "p01": float(qs[0]),
        "p10": float(qs[1]),
        "p25": float(qs[2]),
        "median": float(qs[3]),
        "p75": float(qs[4]),
        "p90": float(qs[5]),
        "p99": float(qs[6]),
    }


def load_symbol(symbol: str) -> pd.DataFrame:
    raw = pd.read_csv(HIST / f"{symbol}_M5.csv")
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw["symbol"] = symbol
    pip = pip_size(symbol)
    close = raw["close"].astype(float)
    atr = _true_range(raw["high"], raw["low"], close).rolling(14).mean()
    raw["atr14"] = atr
    raw["half_close_spread_pips"] = half_close_spread(raw["ask_close"], raw["bid_close"]) / pip
    raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
    raw["session"] = [classify_session(x.to_pydatetime()) for x in raw["time"]]
    raw["split"] = assign_split(raw["time"])
    raw["month"] = raw["time"].dt.to_period("M").astype(str)
    for b in RETURN_BARS:
        instr = close.pct_change(b)
        raw[f"instr_ret_{b}"] = instr
        raw[f"usd_ret_{b}"] = instrument_to_usd(symbol, instr.to_numpy())
        raw[f"usd_ret_{b}_atr"] = instrument_to_usd(symbol, ((close - close.shift(b)) / (atr + 1e-12)).to_numpy())
    c = close.to_numpy(dtype=float)
    h = raw["high"].to_numpy(dtype=float)
    lo = raw["low"].to_numpy(dtype=float)
    for hz in HORIZONS_MIN:
        blk = future_path_block(c, h, lo, hz // 5)
        raw[f"y_instr_pips_{hz}m"] = (blk["fwd_close"] - c) / pip
        raw[f"y_usd_{hz}m"] = instrument_to_usd(symbol, (blk["fwd_close"] - c) / (c + 1e-12))
        raw[f"mfe_up_{hz}m"] = (blk["fwd_high"] - c) / pip
        raw[f"mfe_dn_{hz}m"] = (c - blk["fwd_low"]) / pip
    return raw


def event_metrics(df: pd.DataFrame, mask: np.ndarray, hyp: str) -> dict:
    """hyp: reversal | continuation | catchup. Signed in USD space; economic in instrument side."""
    sub = df.loc[mask].copy()
    rec = {"event_n": int(mask.sum()), "by_split": {}, "by_symbol": {}, "horizons": {}}
    if sub.empty:
        return rec
    for sp in ("train", "valid", "discovery_test"):
        rec["by_split"][sp] = int((sub["split"] == sp).sum())
    for s in SYMBOLS:
        rec["by_symbol"][s] = int((sub["symbol"] == s).sum())
    resid = sub["resid_pca6"].to_numpy()
    factor = sub["factor_pca"].to_numpy()
    cost = sub["half_close_spread_pips"].to_numpy()
    if hyp == "reversal":
        usd_sign = -np.sign(resid)
    elif hyp == "continuation":
        usd_sign = np.sign(resid)
    else:
        usd_sign = np.sign(factor)
    for hz in HORIZONS_MIN:
        yu = sub[f"y_usd_{hz}m"].to_numpy()
        yp = sub[f"y_instr_pips_{hz}m"].to_numpy()
        signed_usd = usd_sign * yu
        # hypothesized instrument side from residual (reversal/continuation) or factor (catchup)
        fav, adv = [], []
        close_signed = []
        for i, row in enumerate(sub.itertuples(index=False)):
            if hyp == "catchup":
                # instrument side that is USD in the factor direction
                side = reversal_instrument_side(row.symbol, -row.factor_pca if np.isfinite(row.factor_pca) else 0.0)
            elif hyp == "reversal":
                side = reversal_instrument_side(row.symbol, row.resid_pca6)
            else:
                side = reversal_instrument_side(row.symbol, -row.resid_pca6)
            up = getattr(row, f"mfe_up_{hz}m")
            dn = getattr(row, f"mfe_dn_{hz}m")
            if side == "BUY":
                fav.append(up)
                adv.append(dn)
                close_signed.append(getattr(row, f"y_instr_pips_{hz}m"))
            elif side == "SELL":
                fav.append(dn)
                adv.append(up)
                close_signed.append(-getattr(row, f"y_instr_pips_{hz}m"))
            else:
                fav.append(np.nan)
                adv.append(np.nan)
                close_signed.append(np.nan)
        fav = np.asarray(fav, dtype=float)
        adv = np.asarray(adv, dtype=float)
        cs = np.asarray(close_signed, dtype=float)
        rec["horizons"][str(hz)] = {
            "n": int(np.isfinite(signed_usd).sum()),
            "mean_signed_usd": _nanmean(signed_usd),
            "hit_usd": _nanmean(signed_usd > 0),
            "mean_signed_instr_pips": _nanmean(cs),
            "mean_mfe_hyp": _nanmean(fav),
            "mean_mae": _nanmean(adv),
            "close_over_cost": _nanmean(cs / cost),
            "mfe_over_cost": _nanmean(fav / cost),
            "frac_close_1x": _nanmean(cs >= cost),
            "frac_close_1_5x": _nanmean(cs >= 1.5 * cost),
            "frac_close_2x": _nanmean(cs >= 2.0 * cost),
            "frac_mfe_1x": _nanmean(fav >= cost),
        }
    rec["h60_by_split"] = {}
    for sp in ("train", "valid", "discovery_test"):
        m = mask & (df["split"].to_numpy() == sp)
        rec["h60_by_split"][sp] = _signed60(df, m, hyp)
    rec["h60_by_symbol"] = {s: _signed60(df, mask & (df["symbol"].to_numpy() == s), hyp) for s in SYMBOLS}
    return rec


def _signed60(df, mask, hyp):
    sub = df.loc[mask]
    if sub.empty:
        return {"n": 0}
    resid = sub["resid_pca6"].to_numpy()
    factor = sub["factor_pca"].to_numpy()
    if hyp == "reversal":
        signed = -np.sign(resid) * sub["y_usd_60m"].to_numpy()
    elif hyp == "continuation":
        signed = np.sign(resid) * sub["y_usd_60m"].to_numpy()
    else:
        signed = np.sign(factor) * sub["y_usd_60m"].to_numpy()
    yp = sub["y_instr_pips_60m"].to_numpy()
    return {
        "n": int(len(sub)),
        "mean_signed_usd": _nanmean(signed),
        "hit_usd": _nanmean(signed > 0),
        "mean_instr_pips": _nanmean(yp),
    }


def main() -> None:
    progress = {
        "study_started_at_utc": utc_now(),
        "last_checkpoint_at_utc": utc_now(),
        "current_stage": 1,
        "completed_stages": [],
        "total_stages": 22,
        "overall_status": "running",
        "no_download": True,
        "no_train": True,
        "stages": [],
    }
    results = {"started_at_utc": progress["study_started_at_utc"]}

    t1 = utc_now()
    print("STAGE 1 load", t1)
    frames = {s: load_symbol(s) for s in SYMBOLS}
    per_n = {s: int(len(frames[s])) for s in SYMBOLS}
    times = {s: set(frames[s]["time"]) for s in SYMBOLS}
    all_times = set.union(*times.values())
    sync_times = set.intersection(*times.values())
    results["stage1"] = {
        "alignment": "inner join on timestamp; no forward-fill",
        "rows_per_symbol": per_n,
        "union_timestamps": int(len(all_times)),
        "fully_synchronized": int(len(sync_times)),
        "missing_on_at_least_one": int(len(all_times) - len(sync_times)),
        "sha256": {s: hashlib.sha256((HIST / f"{s}_M5.csv").read_bytes()).hexdigest()[:16] for s in SYMBOLS},
    }
    mark(progress, 1, "sync_panel", t1, f"Inner-join sync {len(sync_times)} / union {len(all_times)}.")
    dump(progress, results)

    t2 = utc_now()
    print("STAGE 2-5 panel", t2)
    usd_panels = {b: synchronized_panel(frames, f"usd_ret_{b}") for b in RETURN_BARS}
    instr_panels = {b: synchronized_panel(frames, f"instr_ret_{b}") for b in RETURN_BARS}
    wide = usd_panels[PRIMARY_BARS]
    split_by_time = pd.Series(assign_split(pd.Series(wide.index)), index=wide.index)
    train_mask = split_by_time.to_numpy() == "train"
    results["stage2"] = {
        "return_bars": list(RETURN_BARS),
        "primary_factor_return": "usd_ret_6 (30m, USD-oriented)",
        "instrument_return": "positive = quoted price up",
        "usd_oriented": "positive = USD strengthens",
        "sync_rows_primary": int(len(wide)),
    }

    loo = leave_one_out_median(wide)
    train_x = wide.loc[train_mask].to_numpy()
    pca_fit = train_pca1(train_x)
    factor_all = pd.Series(apply_pca1(wide.to_numpy(), pca_fit), index=wide.index, name="factor_pca")
    loo_med_all = wide.median(axis=1)  # includes self — reference only, not used for residuals
    results["stage3"] = {
        "simple_factor": "leave-one-out median of other five USD-oriented ret_6",
        "not_novel_vs_v1": True,
    }
    results["stage4"] = {
        "method": "PCA-1 on TRAIN synchronized usd_ret_6, 6 columns",
        "train_n": int(train_mask.sum()),
        "weights": {s: float(w) for s, w in zip(wide.columns, pca_fit["weights"])},
        "train_means": {s: float(m) for s, m in zip(wide.columns, pca_fit["mean"])},
        "sign": "flipped if needed so factor positively correlates with cross-sectional mean",
        "corr_pca_vs_median": float(factor_all.corr(wide.median(axis=1))),
        "corr_pca_vs_loo_eur": float(factor_all.corr(loo["EUR_USD"])),
    }
    betas = {}
    for s in SYMBOLS:
        betas[s] = train_betas(wide.loc[train_mask, s].to_numpy(), factor_all.loc[train_mask].to_numpy())
    results["stage4"]["train_betas"] = betas
    resid_pca = pd.DataFrame({s: residual(wide[s].to_numpy(), factor_all.to_numpy(), betas[s]) for s in SYMBOLS}, index=wide.index)
    resid_loo = wide - loo
    results["stage5"] = {
        "resid_pca": "usd_ret_6 - beta_TRAIN * PCA1_factor (USD-oriented units)",
        "resid_loo": "usd_ret_6 - LOO_median (V1-like divergence, USD-oriented)",
    }
    results["frozen"] = {
        "pca_weights": results["stage4"]["weights"],
        "pca_means": results["stage4"]["train_means"],
        "betas": betas,
    }
    mark(progress, 2, "returns", t2, "Predeclared 1/3/6/12 bar instrument and USD returns.")
    mark(progress, 3, "simple_usd_factor", t2, "LOO median reference. Not claimed novel vs V1.")
    mark(progress, 4, "train_pca", t2, "PCA-1 TRAIN-only, frozen weights/means/betas.")
    mark(progress, 5, "residuals", t2, "PCA residual and LOO residual in USD-oriented units.")
    dump(progress, results)
    print("PCA weights", results["stage4"]["weights"], "betas", betas)

    # long frame on sync timestamps
    parts = []
    for s, df in frames.items():
        sub = df.loc[df["time"].isin(wide.index)].copy()
        sub = sub.merge(
            pd.DataFrame(
                {
                    "time": wide.index,
                    "factor_pca": factor_all.to_numpy(),
                    "factor_loo": loo[s].to_numpy(),
                    "resid_pca6": resid_pca[s].to_numpy(),
                    "resid_loo6": resid_loo[s].to_numpy(),
                    "usd_ret6_panel": wide[s].to_numpy(),
                    "disp_std": cross_section_std(wide).to_numpy(),
                    "disp_iqr": cross_section_iqr(wide).to_numpy(),
                    "usd_rank": usd_ranks(wide)[s].to_numpy(),
                }
            ),
            on="time",
            how="inner",
        )
        parts.append(sub)
    long = pd.concat(parts, ignore_index=True).sort_values(["symbol", "time"]).reset_index(drop=True)
    g = long["symbol"].to_numpy()
    tr = long["split"].to_numpy() == "train"

    t6 = utc_now()
    print("STAGE 6-7", t6)
    results["stage6"] = {
        "resid_pca_overall": dist_stats(long["resid_pca6"]),
        "by_symbol": {s: dist_stats(long.loc[long["symbol"] == s, "resid_pca6"]) for s in SYMBOLS},
        "by_split": {sp: dist_stats(long.loc[long["split"] == sp, "resid_pca6"]) for sp in ("train", "valid", "discovery_test")},
        "resid_loo_overall": dist_stats(long["resid_loo6"]),
    }
    edges = {
        "resid_pca6": train_quantile_edges(long.loc[tr, "resid_pca6"].to_numpy()).tolist(),
        "resid_loo6": train_quantile_edges(long.loc[tr, "resid_loo6"].to_numpy()).tolist(),
        "disp_std": train_quantile_edges(long.loc[tr, "disp_std"].to_numpy()).tolist(),
        "disp_iqr": train_quantile_edges(long.loc[tr, "disp_iqr"].to_numpy()).tolist(),
    }
    results["frozen"]["edges"] = edges
    dump(progress, results)
    print("FROZEN EDGES", edges)

    long["q_resid"] = apply_frozen_edges(long["resid_pca6"].to_numpy(), np.array(edges["resid_pca6"]))
    long["q_disp"] = apply_frozen_edges(long["disp_std"].to_numpy(), np.array(edges["disp_std"]))
    ev_pos = enter_true_grouped(long["q_resid"].to_numpy() == 5, g)
    ev_neg = enter_true_grouped(long["q_resid"].to_numpy() == 1, g)
    ev_any = ev_pos | ev_neg
    results["stage7"] = {
        "enter_pos_n": int(ev_pos.sum()),
        "enter_neg_n": int(ev_neg.sum()),
        "q5_state_bars": int((long["q_resid"] == 5).sum()),
        "q1_state_bars": int((long["q_resid"] == 1).sum()),
        "edges": edges["resid_pca6"],
    }
    mark(progress, 6, "residual_distributions", t6, "PCA residual distributions by symbol/split.")
    mark(progress, 7, "residual_events", t6, "TRAIN quintile enter q1/q5 transitions.")
    dump(progress, results)

    t8 = utc_now()
    print("STAGE 8-12", t8)
    results["stage8"] = {
        "reversal_pos": event_metrics(long, ev_pos, "reversal"),
        "reversal_neg": event_metrics(long, ev_neg, "reversal"),
        "reversal_any": event_metrics(long, ev_any, "reversal"),
        "continuation_any": event_metrics(long, ev_any, "continuation"),
        "catchup_any": event_metrics(long, ev_any, "catchup"),
        "definitions": {
            "reversal": "signed_usd = -sign(resid)*future_usd; instrument side fades idiosyncratic USD residual",
            "continuation": "opposite of reversal",
            "catchup": "signed_usd = sign(factor)*future_usd; target follows common USD after residual event",
        },
    }
    results["stage9"] = {
        "reversal_any_60": results["stage8"]["reversal_any"]["horizons"]["60"],
        "continuation_any_60": results["stage8"]["continuation_any"]["horizons"]["60"],
        "catchup_any_60": results["stage8"]["catchup_any"]["horizons"]["60"],
        "cost": "contemporaneous historical half-spread pips (Experiment A semantics)",
    }

    # dispersion
    # unique times only for transitions (same event would repeat 6 times in long)
    time_lvl = pd.DataFrame(
        {
            "time": wide.index,
            "disp_std": cross_section_std(wide).to_numpy(),
            "split": split_by_time.to_numpy(),
        }
    )
    time_lvl["q_disp"] = apply_frozen_edges(time_lvl["disp_std"].to_numpy(), np.array(edges["disp_std"]))
    tg = np.array(["PANEL"] * len(time_lvl))
    disp_enter_high = enter_true_grouped(time_lvl["q_disp"].to_numpy() == 5, tg)
    prev_q = np.r_[0, time_lvl["q_disp"].to_numpy()[:-1]]
    disp_high_to_norm = (prev_q == 5) & (time_lvl["q_disp"].to_numpy() != 5) & (time_lvl["q_disp"].to_numpy() != 0)
    # map time events onto long (all 6 pairs at that stamp)
    high_times = set(time_lvl.loc[disp_enter_high, "time"])
    exit_times = set(time_lvl.loc[disp_high_to_norm, "time"])
    m_disp_hi = long["time"].isin(high_times)
    m_disp_exit = long["time"].isin(exit_times)

    def mag_summary(mask):
        rec = {"n_rows": int(mask.sum()), "n_times": int(long.loc[mask, "time"].nunique())}
        for hz in (60, 240):
            rec[f"h{hz}_abs_instr"] = _nanmean(np.abs(long.loc[mask, f"y_instr_pips_{hz}m"]))
            rec[f"h{hz}_abs_usd"] = _nanmean(np.abs(long.loc[mask, f"y_usd_{hz}m"]))
        rec["by_split_abs60"] = {}
        for sp in ("train", "valid", "discovery_test"):
            m = mask & (long["split"].to_numpy() == sp)
            rec["by_split_abs60"][sp] = {
                "n": int(m.sum()),
                "mean_abs_pips": _nanmean(np.abs(long.loc[m, "y_instr_pips_60m"])),
            }
        rec["by_symbol_abs60"] = {
            s: _nanmean(np.abs(long.loc[mask & (long["symbol"].to_numpy() == s), "y_instr_pips_60m"])) for s in SYMBOLS
        }
        # future dispersion change at +12 bars (~60m) on panel
        return rec

    results["stage10"] = {
        "dispersion": "cross-sectional std of synchronized usd_ret_6",
        "also": "IQR computed, std is primary",
        "level_q1": mag_summary(long["q_disp"].to_numpy() == 1),
        "level_q5": mag_summary(long["q_disp"].to_numpy() == 5),
        "edges": edges["disp_std"],
    }
    results["stage11"] = {
        "normal_to_high": mag_summary(m_disp_hi),
        "high_to_normal": mag_summary(m_disp_exit),
        "event_times_enter": int(disp_enter_high.sum()),
        "event_times_exit": int(disp_high_to_norm.sum()),
        "high_state_times": int((time_lvl["q_disp"] == 5).sum()),
    }

    strongest = long["usd_rank"].to_numpy() == 1
    weakest = long["usd_rank"].to_numpy() == 6
    # rank is a state every bar — use every sync bar (not transition) but report n; also enter rank-1
    enter_strong = enter_true_grouped(strongest, g)
    enter_weak = enter_true_grouped(weakest, g)
    results["stage12"] = {
        "strongest_enter": event_metrics(long, enter_strong, "continuation"),
        "weakest_enter": event_metrics(long, enter_weak, "continuation"),
        "note": "continuation here = future_usd * sign(current usd_ret6) via resid sign proxy; also raw hit of rank persistence",
        "strongest_raw_future_usd_60": _nanmean(long.loc[enter_strong, "y_usd_60m"]),
        "weakest_raw_future_usd_60": _nanmean(long.loc[enter_weak, "y_usd_60m"]),
        "by_symbol_strong_future_usd": {
            s: _nanmean(long.loc[enter_strong & (long["symbol"].to_numpy() == s), "y_usd_60m"]) for s in SYMBOLS
        },
    }
    mark(progress, 8, "catchup_reversal_continuation", t8, "Three predeclared signed hypotheses on residual events.")
    mark(progress, 9, "economic_cost", t8, "Close and MFE vs contemporaneous half-spread.")
    mark(progress, 10, "dispersion", t8, "TRAIN quintiles of cross-sectional USD std.")
    mark(progress, 11, "dispersion_events", t8, "NORMAL->HIGH and HIGH->NORMAL time events.")
    mark(progress, 12, "relative_rank", t8, "Enter strongest/weakest USD rank.")
    dump(progress, results)

    t13 = utc_now()
    print("STAGE 13-17", t13)
    lag_tab = {}
    for k in LAGS:
        feat = factor_all.shift(k)
        # future 60m usd by symbol from long
        row = {}
        for s in SYMBOLS:
            sub = long.loc[long["symbol"] == s, ["time", "y_usd_60m", "split"]].copy()
            sub["feat"] = sub["time"].map(feat)
            for sp in ("train", "valid", "discovery_test", "all"):
                sl = sub if sp == "all" else sub.loc[sub["split"] == sp]
                x = sl["feat"].to_numpy(dtype=float)
                y = sl["y_usd_60m"].to_numpy(dtype=float)
                m = np.isfinite(x) & np.isfinite(y)
                if m.sum() < 30:
                    row[f"{s}_{sp}"] = None
                    continue
                row[f"{s}_{sp}_corr"] = float(np.corrcoef(x[m], y[m])[0, 1])
                row[f"{s}_{sp}_mean_y_if_feat_pos"] = float(np.mean(y[m & (x > 0)])) if (m & (x > 0)).any() else None
                row[f"{s}_{sp}_mean_y_if_feat_neg"] = float(np.mean(y[m & (x < 0)])) if (m & (x < 0)).any() else None
        lag_tab[str(k)] = row
    results["stage13"] = {
        "definition": "feature=PCA factor at t-k; label=target USD-oriented 60m return AFTER t",
        "lags": lag_tab,
    }

    # leave-one-pair-out PCA robustness on TRAIN
    loo_w = {}
    for drop in SYMBOLS:
        cols = [c for c in SYMBOLS if c != drop]
        fit = train_pca1(wide.loc[train_mask, cols].to_numpy())
        loo_w[drop] = {c: float(w) for c, w in zip(cols, fit["weights"])}
    results["stage14"] = {"pca_weights_excluding": loo_w}

    results["stage15"] = {
        "reversal_by_symbol": results["stage8"]["reversal_any"]["h60_by_symbol"],
        "catchup_by_symbol": results["stage8"]["catchup_any"]["h60_by_symbol"],
        "disp_q5_by_symbol": results["stage10"]["level_q5"]["by_symbol_abs60"],
    }
    results["stage16"] = {
        "reversal_splits": results["stage8"]["reversal_any"]["h60_by_split"],
        "catchup_splits": results["stage8"]["catchup_any"]["h60_by_split"],
        "disp_q5_splits": results["stage10"]["level_q5"]["by_split_abs60"],
        "disp_q1_splits": results["stage10"]["level_q1"]["by_split_abs60"],
    }
    boot = {
        "reversal_signed_usd_60": event_bootstrap_mean(
            (-np.sign(long.loc[ev_any, "resid_pca6"]) * long.loc[ev_any, "y_usd_60m"]).to_numpy(),
            BOOT_SEED,
            BOOT_REPS,
        ),
        "reversal_signed_instr_60": event_bootstrap_mean(
            np.array(
                [
                    long.loc[i, "y_instr_pips_60m"]
                    * (1 if reversal_instrument_side(long.loc[i, "symbol"], long.loc[i, "resid_pca6"]) == "BUY" else -1)
                    for i in long.index[ev_any]
                ],
                dtype=float,
            ),
            BOOT_SEED,
            BOOT_REPS,
        ),
        "disp_high_abs_60": event_bootstrap_mean(
            np.abs(long.loc[long["q_disp"] == 5, "y_instr_pips_60m"]).to_numpy(),
            BOOT_SEED,
            BOOT_REPS,
        ),
        "disp_low_abs_60": event_bootstrap_mean(
            np.abs(long.loc[long["q_disp"] == 1, "y_instr_pips_60m"]).to_numpy(),
            BOOT_SEED,
            BOOT_REPS,
        ),
    }
    results["stage17"] = boot
    mark(progress, 13, "lead_lag", t13, "Predeclared lags 1/2/3 of PCA factor vs future 60m USD return.")
    mark(progress, 14, "loo_robustness", t13, "PCA-1 refit excluding each pair on TRAIN.")
    mark(progress, 15, "pair_structure", t13, "Per-symbol reversal/catchup/dispersion.")
    mark(progress, 16, "time_stability", t13, "TRAIN/VALID/DISCOVERY_TEST for major effects.")
    mark(progress, 17, "bootstrap", t13, "Event-level bootstrap seed=42.")
    dump(progress, results)

    t18 = utc_now()
    print("STAGE 18-19", t18)
    # V1-like LOO residual events
    long["q_loo"] = apply_frozen_edges(long["resid_loo6"].to_numpy(), np.array(edges["resid_loo6"]))
    ev_loo = enter_true_grouped(long["q_loo"].to_numpy() == 5, g) | enter_true_grouped(long["q_loo"].to_numpy() == 1, g)
    # reuse reversal metric but swap resid
    tmp = long.copy()
    tmp["resid_pca6"] = tmp["resid_loo6"]
    results["stage18"] = {
        "v1_was": "other-pairs median USD ret_6 and TRAIN-extreme usd_own - median",
        "new_here": [
            "TRAIN-fit PCA-1 common factor with frozen betas",
            "explicit residual vs fitted factor (not raw divergence only)",
            "dispersion std/IQR and transitions",
            "relative rank",
            "predeclared 1/2/3 bar lags",
        ],
        "loo_residual_event_reversal": event_metrics(tmp, ev_loo, "reversal")["horizons"]["60"],
        "pca_residual_event_reversal": results["stage8"]["reversal_any"]["horizons"]["60"],
        "corr_resid_pca_vs_loo": float(long["resid_pca6"].corr(long["resid_loo6"])),
    }

    # activity context — TRAIN session medians like Experiment A
    sess_med = (
        long.loc[long["split"] == "train"].groupby(["symbol", "session"], sort=False)["volume"].median().rename("train_sess_vol_med")
    )
    long = long.merge(sess_med, left_on=["symbol", "session"], right_index=True, how="left")
    long["vol_sess_rel"] = long["volume"] / (long["train_sess_vol_med"] + 1e-12)
    long["q_vol"] = apply_frozen_edges(long["vol_sess_rel"].to_numpy(), VOL_SESS_REL_EDGES)
    # realign ev_any after merge (order preserved)
    ev_any = enter_true_grouped(long["q_resid"].to_numpy() == 5, long["symbol"].to_numpy()) | enter_true_grouped(
        long["q_resid"].to_numpy() == 1, long["symbol"].to_numpy()
    )
    act_ctx = {}
    for lab, qm in (("low", 1), ("normal", 3), ("high", 5)):
        m = ev_any & (long["q_vol"].to_numpy() == qm)
        act_ctx[lab] = {
            "n": int(m.sum()),
            "reversal_60": event_metrics(long, m, "reversal")["horizons"].get("60"),
        }
    results["stage19"] = {
        "note": "Descriptive only. Frozen Experiment A vol_sess_rel quintiles. No optimized combo.",
        "residual_events_by_activity": act_ctx,
    }
    mark(progress, 18, "compare_v1_usd", t18, "PCA residual vs LOO residual; list what is new.")
    mark(progress, 19, "activity_context", t18, "Residual events sliced by frozen A activity. Explanatory only.")
    dump(progress, results)

    results["n_sync_times"] = int(len(wide))
    results["n_long"] = int(len(long))
    results["finished_at_utc"] = utc_now()
    dump(progress, results)
    print("DONE", utc_now(), "sync", len(wide), "long", len(long))


if __name__ == "__main__":
    main()
