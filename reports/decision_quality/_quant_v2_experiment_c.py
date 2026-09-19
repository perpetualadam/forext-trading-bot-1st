"""Quant V2 Experiment C: M1 path-order of frozen M5 events. Research-only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.cross_pair import instrument_to_usd, synchronized_panel
from forex_bot.decision_quality.event_discovery import (
    BOOT_REPS,
    BOOT_SEED,
    assign_split,
    event_bootstrap_mean,
    future_path_block,
    path_order,
)
from forex_bot.decision_quality.feature_discovery import RANGE_SHORT, SYMBOLS, utc_now
from forex_bot.decision_quality.history_cache import (
    classify_gap,
    default_historical_dir,
    default_m1_historical_dir,
)
from forex_bot.decision_quality.m1_path import (
    EVENT_FAMILIES,
    HORIZONS_MIN,
    HURDLE_MULTS,
    PCA_BETAS,
    PCA_MEANS,
    PCA_WEIGHTS,
    apply_frozen_pca_factor,
    breakout24_events,
    first_eligible_m1_time,
    first_touch_labels,
    instrument_reversal_side,
    last_m1_time_for_horizon,
    range_events,
    residual_events,
    residual_from_frozen,
    summarize_labels,
)
from forex_bot.decision_quality.spread_volume import half_close_spread
from forex_bot.session_rules import fx_market_open_at

OUT = Path("reports/decision_quality/quant_v2_experiment_c_data.json")
PROGRESS = Path("reports/decision_quality/quant_v2_experiment_c_progress.json")
META = Path("reports/decision_quality/quant_v2_experiment_c_m1_identity.json")
M5_DIR = default_historical_dir()
M1_DIR = default_m1_historical_dir()
PRIMARY = "60m_1x"


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


def verify_m1() -> dict:
    rec = {}
    needed = [
        "time", "open", "high", "low", "close", "volume", "complete",
        "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close",
    ]
    for s in SYMBOLS:
        path = M1_DIR / f"{s}_M1.csv"
        raw = pd.read_csv(path)
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
        raw = raw.sort_values("time")
        deltas = raw["time"].diff().dt.total_seconds() / 60.0
        gap_n = int((deltas.iloc[1:] > 1).sum())
        exp_w = unexp = 0
        gap_idx = np.flatnonzero(deltas.iloc[1:].to_numpy() > 1) + 1
        for i in gap_idx[:5000]:
            kind = classify_gap(raw["time"].iloc[i - 1].to_pydatetime(), raw["time"].iloc[i].to_pydatetime(), bar_minutes=1)
            if kind == "expected_weekend":
                exp_w += 1
            elif kind == "unexpected":
                unexp += 1
        _ = gap_n
        rec[s] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": int(len(raw)),
            "first": str(raw["time"].iloc[0]) if len(raw) else None,
            "last": str(raw["time"].iloc[-1]) if len(raw) else None,
            "monotonic": bool(raw["time"].is_monotonic_increasing),
            "duplicates": int(raw["time"].duplicated().sum()),
            "complete_true": int(raw["complete"].astype(str).str.lower().isin(("true", "1")).sum()) if "complete" in raw.columns else int(len(raw)),
            "columns_present": all(c in raw.columns for c in needed),
            "mid_ok": bool(raw[["open", "high", "low", "close"]].notna().all().all()),
            "bid_ok": bool(raw[["bid_open", "bid_high", "bid_low", "bid_close"]].notna().all().all()),
            "ask_ok": bool(raw[["ask_open", "ask_high", "ask_low", "ask_close"]].notna().all().all()),
            "volume_ok": bool(raw["volume"].notna().all()) if "volume" in raw.columns else False,
            "expected_weekend_gaps": exp_w,
            "unexpected_gaps": unexp,
        }
    return rec


def load_m5(symbol: str) -> pd.DataFrame:
    raw = pd.read_csv(M5_DIR / f"{symbol}_M5.csv")
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw["symbol"] = symbol
    close = raw["close"].astype(float)
    high = raw["high"].astype(float)
    low = raw["low"].astype(float)
    raw["pos_in_range_24"] = (close - low.rolling(RANGE_SHORT).min()) / (
        high.rolling(RANGE_SHORT).max() - low.rolling(RANGE_SHORT).min() + 1e-12
    )
    raw["usd_ret_6"] = instrument_to_usd(symbol, close.pct_change(6).to_numpy())
    raw["half_spread_price"] = half_close_spread(raw["ask_close"], raw["bid_close"])
    raw["split"] = assign_split(raw["time"])
    raw["month"] = raw["time"].dt.to_period("M").astype(str)
    return raw


def load_m1(symbol: str) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(M1_DIR / f"{symbol}_M1.csv", usecols=["time", "high", "low", "close", "ask_close", "bid_close"])
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw = raw.sort_values("time").reset_index(drop=True)
    index = {pd.Timestamp(t): i for i, t in enumerate(raw["time"])}
    return raw, index


def m5_blocks(df: pd.DataFrame) -> dict:
    c = df["close"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    return {hz: future_path_block(c, h, lo, hz // 5) for hz in HORIZONS_MIN}


def m5_label_at(blocks: dict, i: int, close: float, hz: int, cost: float) -> str:
    blk = blocks[hz]
    lab = path_order(np.array([close]), blk["wh"][i][None, :], blk["wl"][i][None, :], np.array([cost]))[0]
    return "M5_AMBIGUOUS" if lab == "AMBIGUOUS" else str(lab)


def slice_expected(open_idx: pd.DatetimeIndex, first: pd.Timestamp, horizon=480):
    last = last_m1_time_for_horizon(first, horizon)
    i0 = int(open_idx.searchsorted(first))
    i1 = int(open_idx.searchsorted(last, side="right"))
    return open_idx[i0:i1]


def classify_event_row(row, m1_df, m1_index, open_idx) -> dict:
    first = first_eligible_m1_time(row.time)
    expected = slice_expected(open_idx, first)
    return first_touch_labels(
        m1_df["time"].to_numpy(),
        m1_df["high"].to_numpy(),
        m1_df["low"].to_numpy(),
        first_eligible=first,
        entry_close=float(row.close),
        cost_price=float(row.half_spread_price),
        expected_times=expected,
        m1_index=m1_index,
    )


def hyp_side(family: str, symbol: str, resid: float) -> str:
    if family == "resid_pos":
        return instrument_reversal_side(symbol, resid if np.isfinite(resid) else 0.01)
    if family == "resid_neg":
        return instrument_reversal_side(symbol, resid if np.isfinite(resid) else -0.01)
    return EVENT_FAMILIES[family]["hypothesis"]


def pack_family(df: pd.DataFrame, key: str) -> dict:
    rec = {"event_n": int(len(df)), "by_split": {}, "by_symbol": {}, "keys": {}}
    if df.empty:
        return rec
    for sp in ("train", "valid", "discovery_test"):
        rec["by_split"][sp] = int((df["split"] == sp).sum())
    for s in SYMBOLS:
        rec["by_symbol"][s] = int((df["symbol"] == s).sum())
    for col in [c for c in df.columns if c.startswith("m1_")]:
        rec["keys"][col] = summarize_labels(df[col].tolist(), "UP")
    return rec


def fav_table(df: pd.DataFrame, key: str, hyp_col: str) -> dict:
    out = {}
    if df.empty:
        return out
    for col in [c for c in df.columns if c.startswith("m1_")]:
        labels = df[col].to_numpy()
        hyps = df[hyp_col].to_numpy()
        fav = ((labels == "UP_FIRST") & (hyps == "UP")) | ((labels == "DOWN_FIRST") & (hyps == "DOWN"))
        adv = ((labels == "UP_FIRST") & (hyps == "DOWN")) | ((labels == "DOWN_FIRST") & (hyps == "UP"))
        n = len(df)
        out[col] = {
            "n": n,
            "favorable_first": int(fav.sum()),
            "adverse_first": int(adv.sum()),
            "neither": int((labels == "NEITHER").sum()),
            "m1_ambiguous": int((labels == "M1_AMBIGUOUS").sum()),
            "insufficient": int((labels == "INSUFFICIENT_DATA").sum()),
            "fav_rate": float(fav.mean()),
            "adv_rate": float(adv.mean()),
            "fav_minus_adv": float(fav.mean() - adv.mean()),
            "by_split": {},
            "by_symbol": {},
        }
        for sp in ("train", "valid", "discovery_test"):
            m = df["split"].to_numpy() == sp
            if not m.any():
                continue
            f = fav[m]
            a = adv[m]
            out[col]["by_split"][sp] = {
                "n": int(m.sum()),
                "fav_rate": float(f.mean()),
                "adv_rate": float(a.mean()),
                "fav_minus_adv": float(f.mean() - a.mean()),
            }
        for s in SYMBOLS:
            m = df["symbol"].to_numpy() == s
            if not m.any():
                continue
            f = fav[m]
            a = adv[m]
            out[col]["by_symbol"][s] = {
                "n": int(m.sum()),
                "fav_rate": float(f.mean()),
                "adv_rate": float(a.mean()),
                "fav_minus_adv": float(f.mean() - a.mean()),
            }
    return out


def main() -> None:
    progress = {
        "study_started_at_utc": utc_now(),
        "last_checkpoint_at_utc": utc_now(),
        "current_stage": 1,
        "completed_stages": [],
        "total_stages": 19,
        "overall_status": "running",
        "no_train": True,
        "no_production_change": True,
        "m1_only_authorized_download": True,
        "stages": [],
    }
    results = {"started_at_utc": progress["study_started_at_utc"]}
    t1 = utc_now()
    results["stage1"] = {
        "frozen_spec": "reports/decision_quality/quant_v2_experiment_c_frozen_spec.json",
        "families": EVENT_FAMILIES,
        "note": "Definitions frozen before M1 outcome inspection.",
    }
    mark(progress, 1, "freeze_definitions", t1, "Frozen V1 range/breakout and B residual events.")
    dump(progress, results)

    t2 = utc_now()
    results["stage2"] = {
        "oanda_time": "candle time is bar start",
        "m5_bar": "[t, t+5m)",
        "knowable_at": "t+5m",
        "first_eligible_m1": "t+5m",
        "excluded_forming_m1": "t, t+1, t+2, t+3, t+4",
    }
    mark(progress, 2, "decision_timestamp", t2, "M1 path starts at t+5m only.")
    dump(progress, results)

    print("VERIFY M1", utc_now(), flush=True)
    identity = verify_m1()
    META.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    m5_sha = {s: hashlib.sha256((M5_DIR / f"{s}_M5.csv").read_bytes()).hexdigest()[:16] for s in SYMBOLS}
    results["m1_identity"] = {s: {k: identity[s][k] for k in ("rows", "first", "last", "duplicates", "unexpected_gaps", "sha256")} for s in SYMBOLS}
    results["m5_sha16"] = m5_sha
    print("M1 rows", {s: identity[s]["rows"] for s in SYMBOLS})

    print("LOAD M5", utc_now())
    frames = {s: load_m5(s) for s in SYMBOLS}
    usd_panel = synchronized_panel(frames, "usd_ret_6")[list(SYMBOLS)]
    mu = np.array([PCA_MEANS[s] for s in SYMBOLS], dtype=float)
    w = np.array([PCA_WEIGHTS[s] for s in SYMBOLS], dtype=float)
    factor = pd.Series((usd_panel.to_numpy(dtype=float) - mu) @ w, index=usd_panel.index)
    long_parts = []
    for s, df in frames.items():
        ev_r = range_events(df["pos_in_range_24"].to_numpy(), df["symbol"].to_numpy())
        ev_b = breakout24_events(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), df["symbol"].to_numpy())
        mapped = df["time"].map(factor).to_numpy(dtype=float)
        resid = df["usd_ret_6"].to_numpy(dtype=float) - float(PCA_BETAS[s]) * mapped
        ev_x = residual_events(resid, df["symbol"].to_numpy())
        part = df.copy()
        part["resid_pca6"] = resid
        part["orig_i"] = np.arange(len(part))
        for k, v in {**ev_r, **ev_b, **ev_x}.items():
            part[k] = v
        long_parts.append(part)
    blocks = {s: m5_blocks(frames[s]) for s in SYMBOLS}
    long = pd.concat(long_parts, ignore_index=True)
    results["event_n"] = {k: int(long[k].sum()) for k in EVENT_FAMILIES}
    print("EVENT N", results["event_n"])

    print("LOAD M1", utc_now())
    m1s = {}
    idxs = {}
    for s in SYMBOLS:
        m1s[s], idxs[s] = load_m1(s)
        print(" loaded", s, len(m1s[s]), flush=True)

    start = min(m1s[s]["time"].min() for s in SYMBOLS)
    end = max(m1s[s]["time"].max() for s in SYMBOLS)
    print("OPEN INDEX", start, end, flush=True)
    open_times = []
    cur = pd.Timestamp(start)
    last = pd.Timestamp(end) + pd.Timedelta(minutes=480)
    while cur <= last:
        if fx_market_open_at(cur.to_pydatetime()):
            open_times.append(cur)
        cur += pd.Timedelta(minutes=1)
    open_idx = pd.DatetimeIndex(open_times)
    print("open minutes", len(open_idx))

    t3 = utc_now()
    print("CLASSIFY EVENTS", t3)
    event_frames = {}
    for fam in EVENT_FAMILIES:
        sub = long.loc[long[fam]].copy()
        recs = []
        for row in sub.itertuples(index=False):
            m1_rec = classify_event_row(row, m1s[row.symbol], idxs[row.symbol], open_idx)
            item = {
                "symbol": row.symbol,
                "time": str(row.time),
                "split": row.split,
                "month": row.month,
                "close": float(row.close),
                "cost": float(row.half_spread_price),
                "hyp": hyp_side(fam, row.symbol, getattr(row, "resid_pca6", np.nan)),
            }
            for k, v in m1_rec.items():
                item[f"m1_{k}"] = v["label"]
                item[f"m1bars_{k}"] = v["bars_to_touch"]
            for hz in HORIZONS_MIN:
                item[f"m5_{hz}m_1x"] = m5_label_at(
                    blocks[row.symbol], int(row.orig_i), float(row.close), hz, float(row.half_spread_price)
                )
            recs.append(item)
        event_frames[fam] = pd.DataFrame(recs)
        print(" classified", fam, len(recs), flush=True)

    results["stage3"] = {
        "alignment": "M1 from first_eligible=t+5m through last=t+5m+horizon-1; missing open minutes = INSUFFICIENT_DATA",
        "event_n": results["event_n"],
    }
    mark(progress, 3, "m1_m5_alignment", t3, "Aligned frozen events to subsequent M1; gaps not filled.")
    results["stage4"] = {"cost": "M5 contemporaneous half-spread price at event time (Experiment A)."}
    mark(progress, 4, "event_cost", t3, "Primary hurdle is event-time M5 half-spread.")
    results["stage5"] = {"hurdles": list(HURDLE_MULTS), "horizons": list(HORIZONS_MIN)}
    mark(progress, 5, "hurdles", t3, "Predeclared 1/1.5/2/3x and 15-480m.")
    dump(progress, results)

    # Ambiguity reduction at primary 60m 1x
    t6 = utc_now()
    amb = {}
    for fam, df in event_frames.items():
        if df.empty:
            continue
        m5a = df["m5_60m_1x"] == "M5_AMBIGUOUS"
        resolved = df.loc[m5a, "m1_60m_1x"].value_counts().to_dict()
        amb[fam] = {
            "event_n": int(len(df)),
            "m5_ambiguous_n": int(m5a.sum()),
            "m5_ambiguous_rate": float(m5a.mean()),
            "of_ambiguous": resolved,
            "m1_all": df["m1_60m_1x"].value_counts().to_dict(),
        }
    pooled_m5 = []
    pooled_m1_from_m5a = []
    for df in event_frames.values():
        if df.empty:
            continue
        pooled_m5.extend(df["m5_60m_1x"].tolist())
        pooled_m1_from_m5a.extend(df.loc[df["m5_60m_1x"] == "M5_AMBIGUOUS", "m1_60m_1x"].tolist())
    results["stage6"] = {
        "by_family": amb,
        "pooled_m5_60m_1x": pd.Series(pooled_m5).value_counts().to_dict() if pooled_m5 else {},
        "m5_ambiguous_rate_pooled": float(np.mean([x == "M5_AMBIGUOUS" for x in pooled_m5])) if pooled_m5 else None,
        "m1_resolution_of_m5_ambiguous": pd.Series(pooled_m1_from_m5a).value_counts().to_dict() if pooled_m1_from_m5a else {},
    }
    mark(progress, 6, "ambiguity_reduction", t6, "M1 labels of previously M5_AMBIGUOUS 60m 1x paths.")
    dump(progress, results)

    t7 = utc_now()
    results["stage7"] = {
        "family": "range_bottom",
        "hypothesis": "UP",
        "fav": fav_table(event_frames["range_bottom"], "range_bottom", "hyp"),
        "counts_60m_1x": event_frames["range_bottom"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["range_bottom"].empty else {},
    }
    mark(progress, 7, "range_bottom", t7, "Range-bottom first-touch.")
    results["stage8"] = {
        "family": "range_top",
        "hypothesis": "DOWN",
        "fav": fav_table(event_frames["range_top"], "range_top", "hyp"),
        "counts_60m_1x": event_frames["range_top"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["range_top"].empty else {},
    }
    mark(progress, 8, "range_top", t7, "Range-top first-touch.")
    results["stage9"] = {
        "breakout_up_24": {
            "hypothesis": "DOWN",
            "fav": fav_table(event_frames["breakout_up_24"], "breakout_up_24", "hyp"),
            "counts_60m_1x": event_frames["breakout_up_24"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["breakout_up_24"].empty else {},
        },
        "breakout_dn_24": {
            "hypothesis": "UP",
            "fav": fav_table(event_frames["breakout_dn_24"], "breakout_dn_24", "hyp"),
            "counts_60m_1x": event_frames["breakout_dn_24"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["breakout_dn_24"].empty else {},
        },
    }
    mark(progress, 9, "breakout_failure", t7, "24-bar breakout failure first-touch.")
    results["stage10"] = {
        "resid_pos": {
            "hypothesis": "REVERSAL",
            "fav": fav_table(event_frames["resid_pos"], "resid_pos", "hyp"),
            "counts_60m_1x": event_frames["resid_pos"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["resid_pos"].empty else {},
        },
        "resid_neg": {
            "hypothesis": "REVERSAL",
            "fav": fav_table(event_frames["resid_neg"], "resid_neg", "hyp"),
            "counts_60m_1x": event_frames["resid_neg"]["m1_60m_1x"].value_counts().to_dict() if not event_frames["resid_neg"].empty else {},
        },
    }
    mark(progress, 10, "residual_extreme", t7, "B residual-extreme reversal first-touch.")
    dump(progress, results)

    print("BASE RATE", utc_now(), flush=True)
    t11 = utc_now()
    # Predeclared control: all M5 bars with valid cost, 60m 1x (primary) plus 15m/240m 1x.
    base_labels = {k: [] for k in ("15m_1x", "60m_1x", "240m_1x")}
    # All eligible M5 timestamps with valid cost. 15/60/240m 1x only (same first-touch walk, max 240m).
    for s in SYMBOLS:
        df = frames[s]
        print(" base", s, len(df), flush=True)
        for row in df.itertuples(index=False):
            if not np.isfinite(row.half_spread_price) or row.half_spread_price <= 0:
                continue
            first = first_eligible_m1_time(row.time)
            expected = slice_expected(open_idx, first, horizon=240)
            rec = first_touch_labels(
                m1s[s]["time"].to_numpy(),
                m1s[s]["high"].to_numpy(),
                m1s[s]["low"].to_numpy(),
                first_eligible=first,
                entry_close=float(row.close),
                cost_price=float(row.half_spread_price),
                expected_times=expected,
                m1_index=idxs[s],
                max_horizon_min=240,
            )
            for k in base_labels:
                base_labels[k].append(rec[k]["label"])
    results["stage11"] = {
        "control": "all eligible M5 timestamps with valid contemporaneous half-spread; 15/60/240m at 1x",
        "n": {k: len(v) for k, v in base_labels.items()},
        "rates": {k: pd.Series(v).value_counts(normalize=True).to_dict() for k, v in base_labels.items()},
        "up_minus_down_60m_1x": None,
    }
    b60 = base_labels["60m_1x"]
    if b60:
        results["stage11"]["up_rate"] = float(np.mean([x == "UP_FIRST" for x in b60]))
        results["stage11"]["down_rate"] = float(np.mean([x == "DOWN_FIRST" for x in b60]))
        results["stage11"]["up_minus_down_60m_1x"] = results["stage11"]["up_rate"] - results["stage11"]["down_rate"]
        results["stage11"]["neither_rate"] = float(np.mean([x == "NEITHER" for x in b60]))
        results["stage11"]["amb_rate"] = float(np.mean([x == "M1_AMBIGUOUS" for x in b60]))
        results["stage11"]["insuff_rate"] = float(np.mean([x == "INSUFFICIENT_DATA" for x in b60]))
    mark(progress, 11, "base_rate", t11, "Unconditional M1 first-touch base rates.")
    dump(progress, results)

    t12 = utc_now()
    adj = {}
    base_up = results["stage11"].get("up_rate") or 0.0
    base_dn = results["stage11"].get("down_rate") or 0.0
    stage_for = {
        "range_bottom": results["stage7"]["fav"],
        "range_top": results["stage8"]["fav"],
        "breakout_up_24": results["stage9"]["breakout_up_24"]["fav"],
        "breakout_dn_24": results["stage9"]["breakout_dn_24"]["fav"],
        "resid_pos": results["stage10"]["resid_pos"]["fav"],
        "resid_neg": results["stage10"]["resid_neg"]["fav"],
    }
    for fam in EVENT_FAMILIES:
        tab = stage_for[fam].get("m1_60m_1x", {})
        hyp = EVENT_FAMILIES[fam]["hypothesis"]
        if fam.startswith("resid"):
            # mixed per-row hyp; use fav_rate directly vs (base matching mix is not simple)
            base_fav = None
            incr = None
        else:
            base_fav = base_up if hyp == "UP" else base_dn
            incr = (tab.get("fav_rate") or 0) - base_fav if tab else None
        adj[fam] = {"primary": tab, "base_fav": base_fav, "incremental_fav": incr}
    results["stage12"] = adj
    mark(progress, 12, "unique_directional", t12, "Favorable-first minus adverse-first and vs base.")
    dump(progress, results)

    t14 = utc_now()
    boot = {}
    for fam in EVENT_FAMILIES:
        df = event_frames[fam]
        if df.empty or len(df) < 20:
            continue
        hyps = df["hyp"].to_numpy()
        labels = df["m1_60m_1x"].to_numpy()
        fav = ((labels == "UP_FIRST") & (hyps == "UP")) | ((labels == "DOWN_FIRST") & (hyps == "DOWN"))
        adv = ((labels == "UP_FIRST") & (hyps == "DOWN")) | ((labels == "DOWN_FIRST") & (hyps == "UP"))
        boot[fam] = {
            "fav": event_bootstrap_mean(fav.astype(float), BOOT_SEED, BOOT_REPS),
            "adv": event_bootstrap_mean(adv.astype(float), BOOT_SEED, BOOT_REPS),
            "diff": event_bootstrap_mean((fav.astype(float) - adv.astype(float)), BOOT_SEED, BOOT_REPS),
        }
    results["stage14"] = boot
    mark(progress, 14, "bootstrap", t14, "Event-level bootstrap seed=42 on 60m 1x.")
    dump(progress, results)

    t15 = utc_now()
    monthly = {}
    for fam, df in event_frames.items():
        if df.empty:
            continue
        monthly[fam] = {}
        for month, g in df.groupby("month"):
            lab = g["m1_60m_1x"].to_numpy()
            hyps = g["hyp"].to_numpy()
            fav = ((lab == "UP_FIRST") & (hyps == "UP")) | ((lab == "DOWN_FIRST") & (hyps == "DOWN"))
            adv = ((lab == "UP_FIRST") & (hyps == "DOWN")) | ((lab == "DOWN_FIRST") & (hyps == "UP"))
            monthly[fam][month] = {"n": int(len(g)), "fav_minus_adv": float(fav.mean() - adv.mean())}
    results["stage15"] = monthly
    mark(progress, 15, "time_stability", t15, "Monthly fav-adv at 60m 1x.")
    results["stage16"] = {fam: stage_for[fam].get("m1_60m_1x", {}).get("by_symbol") for fam in EVENT_FAMILIES}
    mark(progress, 16, "symbol_stability", t15, "Per-symbol fav-adv at 60m 1x.")
    dump(progress, results)

    results["n_long"] = int(len(long))
    results["finished_at_utc"] = utc_now()
    dump(progress, results)
    print("DONE", utc_now(), flush=True)


if __name__ == "__main__":
    main()
