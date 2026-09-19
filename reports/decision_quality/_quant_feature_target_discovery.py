"""Vectorized feature/target discovery. No trade engine. No production changes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.feature_discovery import (
    ALL_FEATURES,
    FEATURE_FAMILIES,
    HORIZONS_MIN,
    SIGNED_FEATURES,
    SYMBOLS,
    apply_bins,
    assign_split,
    block_bootstrap_mean,
    build_symbol_frame,
    classification_scores,
    file_sha256,
    fit_logreg,
    freeze_splits,
    inspect_symbol,
    predict_logreg,
    summarize_numeric,
    train_quintile_edges,
    utc_now,
)
from forex_bot.decision_quality.stub_components import current_stub_allow

OUT_DIR = Path("data/research/quant_features")
REPORT_JSON = Path("reports/decision_quality/quant_feature_target_discovery_data.json")
PROGRESS = Path("reports/decision_quality/quant_feature_target_progress.json")
CACHE = OUT_DIR / "six_pair_features.pkl"
SEED = 42
USD_QUOTE = ("EUR_USD", "GBP_USD", "AUD_USD")
USD_BASE = ("USD_JPY", "USD_CAD", "USD_CHF")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def write_progress(payload: dict) -> None:
    PROGRESS.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")


def write_data(payload: dict) -> None:
    REPORT_JSON.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")


def fwd_stats(pips: np.ndarray, atrn: np.ndarray | None = None) -> dict:
    x = np.asarray(pips, dtype=float)
    m = np.isfinite(x)
    x = x[m]
    out = {
        "n": int(len(x)),
        "mean": float(np.mean(x)) if len(x) else None,
        "median": float(np.median(x)) if len(x) else None,
        "pct_pos": float(np.mean(x > 0)) if len(x) else None,
    }
    if atrn is not None:
        a = np.asarray(atrn, dtype=float)[m]
        a = a[np.isfinite(a)]
        out["mean_atr"] = float(np.mean(a)) if len(a) else None
    return out


def main() -> None:
    progress = {
        "study_started_at_utc": utc_now(),
        "last_checkpoint_at_utc": utc_now(),
        "current_stage": 1,
        "completed_stages": [],
        "total_stages": 20,
        "overall_status": "running",
        "stages": [],
    }
    results: dict = {"started_at_utc": progress["study_started_at_utc"]}

    # ---- Stage 1 ----
    t0 = utc_now()
    print("STAGE 1", t0)
    integrity = [inspect_symbol(s) for s in SYMBOLS]
    results["stage1"] = {"symbols": integrity, "total_rows": sum(r["rows"] for r in integrity)}
    print("rows", results["stage1"]["total_rows"])
    progress["stages"].append(
        {
            "stage": 1,
            "stage_name": "dataset_integrity",
            "status": "completed",
            "started_at_utc": t0,
            "finished_at_utc": utc_now(),
            "input_rows": results["stage1"]["total_rows"],
            "output_rows": results["stage1"]["total_rows"],
            "findings": "Six CSVs loaded. Gaps classified, not repaired.",
        }
    )
    progress["completed_stages"] = [1]
    progress["last_checkpoint_at_utc"] = utc_now()
    write_progress(progress)
    write_data(results)

    # ---- Stage 2-4 build ----
    t2 = utc_now()
    print("STAGE 2-4 build", t2)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = [build_symbol_frame(s) for s in SYMBOLS]
    all_df = pd.concat(frames, ignore_index=True)
    t50, t75 = freeze_splits(all_df["time"])
    all_df["split"] = assign_split(all_df["time"], t50, t75)
    warmup = all_df["sma20_50_diff_atr"].notna() & all_df["ret_24"].notna() & all_df["atr14"].notna()
    all_df = all_df.loc[warmup].reset_index(drop=True)
    all_df.to_pickle(CACHE)
    results["stage2"] = {
        "t50": t50.isoformat(),
        "t75": t75.isoformat(),
        "note": "DISCOVERY_TEST is inspected in this study and is NOT a future pristine holdout.",
        "counts": all_df["split"].value_counts().to_dict(),
    }
    print("splits", results["stage2"])
    results["stage3"] = {
        "horizons_min": list(HORIZONS_MIN),
        "alignment": "features at completed M5 t; target is mid close[t+h] - close[t]",
        "labels": "UP if y_px>0 else DOWN if y_px<0; zeros remain 0",
    }
    results["stage4"] = {"features": list(ALL_FEATURES), "families": {k: list(v) for k, v in FEATURE_FAMILIES.items()}}
    results["n_rows"] = int(len(all_df))
    progress["stages"].append(
        {
            "stage": 2,
            "stage_name": "freeze_splits",
            "status": "completed",
            "started_at_utc": t2,
            "finished_at_utc": utc_now(),
            "output_rows": int(len(all_df)),
            "findings": f"Cuts {t50} / {t75}. Test labeled DISCOVERY_TEST.",
        }
    )
    progress["stages"].append(
        {
            "stage": 3,
            "stage_name": "freeze_targets",
            "status": "completed",
            "started_at_utc": t2,
            "finished_at_utc": utc_now(),
            "output_rows": int(len(all_df)),
            "findings": "Six mid-return horizons created.",
        }
    )
    progress["stages"].append(
        {
            "stage": 4,
            "stage_name": "build_features",
            "status": "completed",
            "started_at_utc": t2,
            "finished_at_utc": utc_now(),
            "output_rows": int(len(all_df)),
            "findings": f"{len(ALL_FEATURES)} features in 9 families. Cached {CACHE}.",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4]
    progress["last_checkpoint_at_utc"] = utc_now()
    write_progress(progress)
    write_data(results)

    train = all_df["split"].to_numpy() == "train"
    valid = all_df["split"].to_numpy() == "valid"
    test = all_df["split"].to_numpy() == "discovery_test"

    # ---- Stage 6 distributions ----
    t6 = utc_now()
    print("STAGE 6", t6)
    dist = {}
    for col in ALL_FEATURES:
        dist[col] = summarize_numeric(all_df[col])
        by_sym = {}
        for s in SYMBOLS:
            by_sym[s] = summarize_numeric(all_df.loc[all_df["symbol"] == s, col])
        dist[col]["by_symbol"] = by_sym
    constants = [c for c, d in dist.items() if (d["std"] is not None and d["std"] < 1e-15) or d["count"] == 0]
    results["stage6"] = {"distributions": dist, "near_constant": constants}
    progress["stages"].append(
        {
            "stage": 6,
            "stage_name": "distributions",
            "status": "completed",
            "started_at_utc": t6,
            "finished_at_utc": utc_now(),
            "findings": f"near_constant={constants}",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4, 6]
    write_progress(progress)
    write_data(results)

    # ---- Stage 7 redundancy TRAIN ----
    t7 = utc_now()
    print("STAGE 7", t7)
    Xtr = all_df.loc[train, list(ALL_FEATURES)].apply(pd.to_numeric, errors="coerce")
    corr = Xtr.corr().abs()
    redundant = []
    seen = set()
    cols = list(ALL_FEATURES)
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            v = corr.loc[a, b]
            if pd.notna(v) and v >= 0.90:
                redundant.append({"a": a, "b": b, "abs_corr": float(v)})
                seen.add(b)
    keep = [c for c in cols if c not in seen]
    results["stage7"] = {"pairs_ge_0_90": redundant, "candidate_keep": keep, "redundant_drop_suggestions": sorted(seen)}
    print("redundant", len(redundant), "drop_sugg", sorted(seen))
    progress["stages"].append(
        {
            "stage": 7,
            "stage_name": "redundancy",
            "status": "completed",
            "started_at_utc": t7,
            "finished_at_utc": utc_now(),
            "findings": f"{len(redundant)} pairs |corr|>=0.90 on TRAIN.",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4, 6, 7]
    write_progress(progress)
    write_data(results)

    # ---- Stage 8 univariate quintiles ----
    t8 = utc_now()
    print("STAGE 8", t8)
    uni = {}
    for col in ALL_FEATURES:
        edges = train_quintile_edges(all_df.loc[train, col].to_numpy())
        bins = apply_bins(all_df[col].to_numpy(), edges)
        uni[col] = {"edges": [None if not np.isfinite(e) else float(e) for e in edges], "splits": {}}
        for split_name, mask in (("train", train), ("valid", valid), ("discovery_test", test)):
            uni[col]["splits"][split_name] = {}
            for q in range(5):
                m = mask & (bins == q) & np.isfinite(all_df[col].to_numpy())
                uni[col]["splits"][split_name][f"q{q+1}"] = {
                    hz: fwd_stats(
                        all_df.loc[m, f"y_pips_{hz}m"].to_numpy(),
                        all_df.loc[m, f"y_atr_{hz}m"].to_numpy(),
                    )
                    for hz in HORIZONS_MIN
                }
    results["stage8"] = uni
    progress["stages"].append(
        {
            "stage": 8,
            "stage_name": "univariate_quintiles",
            "status": "completed",
            "started_at_utc": t8,
            "finished_at_utc": utc_now(),
            "findings": "Train-only quintile edges applied to valid and DISCOVERY_TEST.",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4, 6, 7, 8]
    write_progress(progress)
    write_data(results)

    # ---- Stage 9 signed features ----
    t9 = utc_now()
    print("STAGE 9", t9)
    signed = {}
    for col in SIGNED_FEATURES:
        signed[col] = {}
        feat = all_df[col].to_numpy(dtype=float)
        for split_name, mask in (("train", train), ("valid", valid), ("discovery_test", test)):
            signed[col][split_name] = {}
            for name, extra in (("pos", feat > 0), ("neg", feat < 0)):
                m = mask & extra & np.isfinite(feat)
                signed[col][split_name][name] = {
                    hz: fwd_stats(all_df.loc[m, f"y_pips_{hz}m"].to_numpy(), all_df.loc[m, f"y_atr_{hz}m"].to_numpy())
                    for hz in HORIZONS_MIN
                }
            # sign hit: feature sign == future sign
            for hz in HORIZONS_MIN:
                y = all_df[f"y_dir_{hz}m"].to_numpy()
                m = mask & np.isfinite(feat) & (feat != 0) & np.isfinite(y) & (y != 0)
                hit = float(np.mean(np.sign(feat[m]) == y[m])) if m.any() else None
                signed[col][split_name][f"sign_hit_{hz}m"] = {"n": int(m.sum()), "hit": hit}
        signed[col]["by_symbol"] = {}
        for s in SYMBOLS:
            sm = (all_df["symbol"].to_numpy() == s) & np.isfinite(feat) & (feat != 0)
            y = all_df["y_dir_60m"].to_numpy()
            m = sm & np.isfinite(y) & (y != 0)
            signed[col]["by_symbol"][s] = {
                "n": int(m.sum()),
                "sign_hit_60m": float(np.mean(np.sign(feat[m]) == y[m])) if m.any() else None,
            }
    results["stage9"] = signed
    progress["stages"].append(
        {
            "stage": 9,
            "stage_name": "directional_features",
            "status": "completed",
            "started_at_utc": t9,
            "finished_at_utc": utc_now(),
            "findings": "Signed-feature UP/DOWN and sign-hit rates.",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4, 6, 7, 8, 9]
    write_progress(progress)
    write_data(results)

    # ---- Stage 10-12 extracted from 8/9 plus monthly ----
    t10 = utc_now()
    print("STAGE 10-12", t10)
    monthly = {}
    all_df["month"] = pd.to_datetime(all_df["time"]).dt.to_period("M").astype(str)
    key_feats = ("ret_1", "ret_6", "ret_12", "sma5_20_diff_atr", "sma_state", "dist_sma20_atr", "h1_ret", "pos_in_range_24")
    for col in key_feats:
        feat = all_df[col].to_numpy(dtype=float)
        monthly[col] = {}
        for month, sub in all_df.groupby("month"):
            f = sub[col].to_numpy(dtype=float)
            y = sub["y_dir_60m"].to_numpy()
            m = np.isfinite(f) & (f != 0) & np.isfinite(y) & (y != 0)
            monthly[col][str(month)] = {
                "n": int(m.sum()),
                "sign_hit_60m": float(np.mean(np.sign(f[m]) == y[m])) if m.any() else None,
                "mean_pips_60m_when_pos": fwd_stats(sub.loc[f > 0, "y_pips_60m"].to_numpy()) if (f > 0).any() else None,
            }
    quote_vs_base = {}
    for col in key_feats:
        quote_vs_base[col] = {}
        for group, names in (("usd_quote", USD_QUOTE), ("usd_base", USD_BASE)):
            m = all_df["symbol"].isin(names).to_numpy()
            f = all_df[col].to_numpy(dtype=float)
            y = all_df["y_dir_60m"].to_numpy()
            ok = m & np.isfinite(f) & (f != 0) & np.isfinite(y) & (y != 0)
            quote_vs_base[col][group] = {
                "n": int(ok.sum()),
                "sign_hit_60m": float(np.mean(np.sign(f[ok]) == y[ok])) if ok.any() else None,
            }
    results["stage10_12"] = {"monthly": monthly, "quote_vs_base": quote_vs_base}
    progress["stages"].append(
        {
            "stage": 10,
            "stage_name": "horizon_structure",
            "status": "completed",
            "started_at_utc": t10,
            "finished_at_utc": utc_now(),
            "findings": "Horizon tables live in stage8/9.",
        }
    )
    progress["stages"].append(
        {
            "stage": 11,
            "stage_name": "cross_symbol",
            "status": "completed",
            "started_at_utc": t10,
            "finished_at_utc": utc_now(),
            "findings": "USD-quote vs USD-base sign-hit at 60m.",
        }
    )
    progress["stages"].append(
        {
            "stage": 12,
            "stage_name": "temporal_stability",
            "status": "completed",
            "started_at_utc": t10,
            "finished_at_utc": utc_now(),
            "findings": "Monthly sign-hit for key features.",
        }
    )
    progress["completed_stages"] = [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12]
    write_progress(progress)
    write_data(results)

    # ---- Stage 13 dependence ----
    t13 = utc_now()
    print("STAGE 13", t13)
    dep = {}
    for col in ("ret_1", "ret_6", "sma5_20_diff_atr", "dist_sma20_atr"):
        feat = all_df[col].to_numpy(dtype=float)
        y = all_df["y_pips_60m"].to_numpy()
        # condition: feature positive vs all
        mpos = np.isfinite(feat) & (feat > 0) & np.isfinite(y)
        dep[col] = {
            "overlapping_pos": fwd_stats(y[mpos]),
            "block_bootstrap_pos": block_bootstrap_mean(y[mpos], block=12, n_boot=200, seed=SEED),
        }
        # non-overlapping: one bar per 12-step block per symbol
        non = []
        for s in SYMBOLS:
            sub = all_df.loc[all_df["symbol"] == s]
            f = sub[col].to_numpy(dtype=float)
            yy = sub["y_pips_60m"].to_numpy()
            idx = np.arange(len(sub))
            take = (idx % 12 == 0) & np.isfinite(f) & (f > 0) & np.isfinite(yy)
            non.append(yy[take])
        dep[col]["nonoverlap_pos"] = fwd_stats(np.concatenate(non) if non else np.array([]))
    results["stage13"] = dep
    progress["stages"].append(
        {
            "stage": 13,
            "stage_name": "dependence_aware",
            "status": "completed",
            "started_at_utc": t13,
            "finished_at_utc": utc_now(),
            "findings": "Block bootstrap (block=12, seed=42, 200) and non-overlap every 12th bar.",
        }
    )
    progress["completed_stages"].append(13)
    write_progress(progress)
    write_data(results)

    # ---- Stage 14-15 simple model + ablation ----
    t14 = utc_now()
    print("STAGE 14-15", t14)
    model_feats = [
        "ret_1",
        "ret_6",
        "ret_12",
        "sma5_20_diff_atr",
        "sma5_slope_atr",
        "dist_sma20_atr",
        "pos_in_range_24",
        "signed_body_atr",
        "rv_ratio",
        "atr_pctile",
        "h1_ret",
        "h1_state",
        "hour_sin",
        "hour_cos",
    ]
    y60 = all_df["y_dir_60m"].to_numpy()
    usable = np.isfinite(y60) & (y60 != 0)
    ybin = (y60 > 0).astype(float)

    def pack(mask, feats):
        X = all_df.loc[mask & usable, feats].apply(pd.to_numeric, errors="coerce")
        y = ybin[mask & usable]
        ok = np.isfinite(X.to_numpy()).all(axis=1)
        return X.to_numpy()[ok], y[ok], ok

    def standardize_fit(X):
        mu = np.nanmean(X, axis=0)
        sd = np.nanstd(X, axis=0)
        sd = np.where(sd < 1e-12, 1.0, sd)
        return mu, sd, (X - mu) / sd

    baselines = {}
    # always up / down
    for split_name, mask in (("train", train), ("valid", valid), ("discovery_test", test)):
        y = ybin[mask & usable]
        baselines.setdefault("always_up", {})[split_name] = classification_scores(y, np.ones_like(y))
        baselines.setdefault("always_down", {})[split_name] = classification_scores(y, np.zeros_like(y))
        # recent return sign
        r1 = all_df["ret_1"].to_numpy()
        p = np.where(r1[mask & usable] > 0, 1.0, 0.0)
        baselines.setdefault("ret1_sign", {})[split_name] = classification_scores(y, p)
        st = all_df["sma_state"].to_numpy()
        p = np.where(st[mask & usable] > 0, 1.0, 0.0)
        baselines.setdefault("sma_state", {})[split_name] = classification_scores(y, p)
        # current stub: allow bars only, predict SMA side
        atr = all_df["atr14"].to_numpy()
        allow = current_stub_allow(st, r1, atr)
        m = mask & usable & allow
        if m.any():
            baselines.setdefault("current_stub", {})[split_name] = classification_scores(
                ybin[m], np.where(st[m] > 0, 1.0, 0.0)
            )

    Xtr, ytr, _ = pack(train, model_feats)
    mu, sd, Ztr = standardize_fit(Xtr)
    w = fit_logreg(Ztr, ytr, l2=1.0, steps=250, lr=0.15)
    model_scores = {"features": model_feats}
    for split_name, mask in (("train", train), ("valid", valid), ("discovery_test", test)):
        X, y, _ = pack(mask, model_feats)
        Z = (X - mu) / sd
        p = predict_logreg(Z, w)
        model_scores[split_name] = classification_scores(y, p)
        # signed future pips when predicted UP vs DOWN
        pred = p >= 0.5
        yp = all_df.loc[mask & usable, "y_pips_60m"].to_numpy()
        # align with pack ok
        Xfull = all_df.loc[mask & usable, model_feats].apply(pd.to_numeric, errors="coerce")
        ok = np.isfinite(Xfull.to_numpy()).all(axis=1)
        yp = yp[ok]
        model_scores[split_name]["mean_pips_pred_up"] = fwd_stats(yp[pred])
        model_scores[split_name]["mean_pips_pred_down"] = fwd_stats(yp[~pred])

    ablation = {}
    family_feats = {
        "price_action": ["ret_1", "ret_6", "ret_12"],
        "trend": ["sma5_20_diff_atr", "sma5_slope_atr"],
        "extension": ["dist_sma20_atr", "pos_in_range_24"],
        "candle": ["signed_body_atr"],
        "volatility": ["rv_ratio", "atr_pctile"],
        "htf": ["h1_ret", "h1_state"],
        "session_regime": ["hour_sin", "hour_cos"],
    }
    for fam, drop in family_feats.items():
        feats = [f for f in model_feats if f not in drop]
        Xa, ya, _ = pack(train, feats)
        mua, sda, Za = standardize_fit(Xa)
        wa = fit_logreg(Za, ya, l2=1.0, steps=250, lr=0.15)
        ablation[fam] = {}
        for split_name, mask in (("valid", valid), ("discovery_test", test)):
            Xb, yb, _ = pack(mask, feats)
            pb = predict_logreg((Xb - mua) / sda, wa)
            ablation[fam][split_name] = classification_scores(yb, pb)

    results["stage14"] = {"baselines": baselines, "logreg": model_scores, "l2": 1.0, "seed": SEED}
    results["stage15"] = {"ablation_drop_family": ablation}
    print("logreg valid", model_scores["valid"])
    print("logreg test", model_scores["discovery_test"])
    progress["stages"].append(
        {
            "stage": 14,
            "stage_name": "simple_multivariate",
            "status": "completed",
            "started_at_utc": t14,
            "finished_at_utc": utc_now(),
            "findings": "Fixed L2 logreg on TRAIN; valid/DISCOVERY_TEST exploratory.",
        }
    )
    progress["stages"].append(
        {
            "stage": 15,
            "stage_name": "ablation",
            "status": "completed",
            "started_at_utc": t14,
            "finished_at_utc": utc_now(),
            "findings": "Dropped one family at a time.",
        }
    )
    progress["completed_stages"].extend([14, 15])
    write_progress(progress)
    write_data(results)

    # ---- Stage 16 cost hurdle ----
    t16 = utc_now()
    print("STAGE 16", t16)
    cost = {}
    for col in ("ret_1", "ret_6", "dist_sma20_atr"):
        feat = all_df[col].to_numpy(dtype=float)
        yp = all_df["y_pips_60m"].to_numpy()
        spr = all_df["half_spread_pips"].to_numpy()
        m = np.isfinite(feat) & (feat != 0) & np.isfinite(yp)
        signed = np.sign(feat[m]) * yp[m]
        cost[col] = {
            "mean_signed_60m_pips": float(np.mean(signed)) if len(signed) else None,
            "median_signed_60m_pips": float(np.median(signed)) if len(signed) else None,
            "mean_half_spread_pips": float(np.mean(spr[m])) if m.any() else None,
            "ratio_mean_to_half_spread": None,
        }
        if cost[col]["mean_half_spread_pips"]:
            cost[col]["ratio_mean_to_half_spread"] = cost[col]["mean_signed_60m_pips"] / cost[col]["mean_half_spread_pips"]
    results["stage16"] = cost
    progress["stages"].append(
        {
            "stage": 16,
            "stage_name": "cost_hurdle",
            "status": "completed",
            "started_at_utc": t16,
            "finished_at_utc": utc_now(),
            "findings": "Signed 60m pips vs production half-spread.",
        }
    )
    progress["completed_stages"].append(16)
    progress["last_checkpoint_at_utc"] = utc_now()
    write_progress(progress)
    write_data(results)
    print("FINISH", utc_now(), "rows", len(all_df))


if __name__ == "__main__":
    main()
