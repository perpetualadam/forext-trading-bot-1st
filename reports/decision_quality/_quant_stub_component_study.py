"""Read-only SMA-state / momentum-sign study. No trade replay, no production changes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.csv_ohlcv import load_ohlcv_csv
from forex_bot.decision_quality.stub_components import (
    HORIZONS_MIN,
    build_component_frame,
    chrono_masks,
    summarize_group,
    vote_matches_row,
)

SYMBOLS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
DATA_DIR = Path("data/historical")
OUT_JSON = Path("reports/decision_quality/quant_stub_component_study_data.json")
PRIMARY_LOOKBACK = {"USD_JPY": 50}
DEFAULT_LOOKBACK = 100
SWING_LOOKBACK = 200
AGE_NAMES = ("0", "1", "2-3", "4-6", "7-12", "13-24", "25+")
PARTS = ("train", "valid", "test")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_symbol(symbol: str) -> pd.DataFrame:
    return load_ohlcv_csv(DATA_DIR / f"{symbol}_M5.csv")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def add_split(frame: pd.DataFrame, cuts) -> pd.DataFrame:
    t = pd.to_datetime(frame["time"])
    t50, t75 = cuts
    part = np.where(t <= t50, "train", np.where(t <= t75, "valid", "test"))
    out = frame.copy()
    out["part"] = part
    return out


def dump_summary(label: str, frame: pd.DataFrame, mask: np.ndarray) -> dict:
    body = summarize_group(frame, mask)
    body["label"] = label
    return body


def per_symbol_parts(frame: pd.DataFrame, mask: np.ndarray) -> dict:
    out = {}
    for sym in SYMBOLS:
        sm = mask & (frame["symbol"].to_numpy() == sym)
        out[sym] = summarize_group(frame, sm)
    for part in PARTS:
        pm = mask & (frame["part"].to_numpy() == part)
        out[part] = summarize_group(frame, pm)
        out[f"{part}_by_symbol"] = {}
        for sym in SYMBOLS:
            out[f"{part}_by_symbol"][sym] = summarize_group(
                frame, pm & (frame["symbol"].to_numpy() == sym)
            )
    return out


def main() -> None:
    started = utc_now()
    print("START", started)
    frames = []
    swing_frames = []
    for symbol in SYMBOLS:
        df = load_symbol(symbol)
        lb = PRIMARY_LOOKBACK.get(symbol, DEFAULT_LOOKBACK)
        print(f"build {symbol} lookback={lb} bars={len(df)}")
        frames.append(build_component_frame(df, symbol, lb))
        if symbol != "USD_JPY":
            swing_frames.append(build_component_frame(df, symbol, SWING_LOOKBACK))
    all_df = pd.concat(frames, ignore_index=True)
    warmup = (
        all_df["ma_fast"].notna()
        & all_df["ma_slow"].notna()
        & all_df["atr"].notna()
        & all_df["ret_1"].notna()
    )
    all_df = all_df.loc[warmup].reset_index(drop=True)

    # Global chronological cuts from pooled timestamps
    cuts_raw = chrono_masks(all_df["time"])
    t50, t75 = cuts_raw["cut_50"], cuts_raw["cut_75"]
    all_df = add_split(all_df, (t50, t75))
    print("cuts", t50, t75, "rows", len(all_df))

    # Production stub parity sample
    sample = all_df.sample(n=min(400, len(all_df)), random_state=42)
    mismatches = int(sum(not vote_matches_row(row) for _, row in sample.iterrows()))
    print("stub_parity_mismatches", mismatches, "of", len(sample))

    state_on = all_df["state"].to_numpy() != 0
    stub = all_df["stub_allow"].to_numpy()
    cross = all_df["is_cross"].to_numpy()
    first_q = all_df["first_qual"].to_numpy()
    repeat_q = all_df["repeat_qual"].to_numpy()
    agree = all_df["agree"].to_numpy()
    disagree = all_df["disagree"].to_numpy()
    buy = all_df["state"].to_numpy() > 0
    sell = all_df["state"].to_numpy() < 0
    mom_pos = all_df["mom_sign"].to_numpy() > 0
    mom_neg = all_df["mom_sign"].to_numpy() < 0
    mag = all_df["mag_ok"].to_numpy()

    groups = {
        "A_sma_state": state_on,
        "B_first_crossover": cross,
        "H_first_qual_after_cross": first_q,
        "I_every_qualifying_in_state": stub,
        "I_repeat_qualifying": repeat_q,
        "J_current_exact_stub": stub,
        "F_agree_sma_and_mom_sign": agree,
        "G_disagree_sma_and_mom_sign": disagree,
        "F_agree_and_stub_allow": agree & stub,
        "G_disagree_and_stub_allow": disagree & stub,
        "buy_mom_pos": buy & mom_pos,
        "buy_mom_neg": buy & mom_neg,
        "sell_mom_neg": sell & mom_neg,
        "sell_mom_pos": sell & mom_pos,
        "buy_mom_pos_stub": buy & mom_pos & stub,
        "buy_mom_neg_stub": buy & mom_neg & stub,
        "sell_mom_neg_stub": sell & mom_neg & stub,
        "sell_mom_pos_stub": sell & mom_pos & stub,
        "D_mag_ok_state": state_on & mag,
        "D_mag_fail_state": state_on & ~mag,
        "E_mom_pos_state": state_on & mom_pos,
        "E_mom_neg_state": state_on & mom_neg,
    }

    result = {
        "started_at_utc": started,
        "cuts": {"t50": t50.isoformat(), "t75": t75.isoformat()},
        "primary_lookback": {s: PRIMARY_LOOKBACK.get(s, DEFAULT_LOOKBACK) for s in SYMBOLS},
        "n_rows_after_warmup": int(len(all_df)),
        "stub_parity_mismatches": mismatches,
        "stub_parity_sample": int(len(sample)),
        "state_frac": float(state_on.mean()),
        "stub_allow_frac": float(stub.mean()),
        "cross_n": int(cross.sum()),
        "episode_n": int(all_df.loc[all_df["episode_key"].astype(str).str.len() > 0, "episode_key"].nunique()),
        "groups": {},
        "age": {},
        "age_stub": {},
        "inverse_J": {},
        "swing200": {},
    }

    for name, mask in groups.items():
        summary = dump_summary(name, all_df, mask)
        summary.update(per_symbol_parts(all_df, mask))
        result["groups"][name] = summary
        print(
            f"{name}: raw={summary['raw_bar_n']} episodes={summary['event_state_n']} "
            f"60m_mean={summary['60m']['mean']} 60m_pct={summary['60m']['pct_pos']}"
        )

    # Inverse of current stub = same allow bars, opposite signed forwards
    inv = {"raw_bar_n": int(stub.sum()), "event_state_n": result["groups"]["J_current_exact_stub"]["event_state_n"]}
    sub = all_df.loc[stub]
    for minutes in HORIZONS_MIN:
        x = sub[f"inv_{minutes}m_pips"].to_numpy()
        from forex_bot.decision_quality.stub_components import fwd_summary

        inv[f"{minutes}m"] = fwd_summary(x)
    result["inverse_J"] = inv
    print("K_inverse_stub 60m_mean", inv["60m"]["mean"], "pct", inv["60m"]["pct_pos"])

    for bucket in AGE_NAMES:
        bm = all_df["age_bucket"].to_numpy() == bucket
        result["age"][bucket] = dump_summary(bucket, all_df, bm)
        result["age"][bucket].update(per_symbol_parts(all_df, bm))
        result["age_stub"][bucket] = dump_summary(bucket + "_stub", all_df, bm & stub)
        result["age_stub"][bucket].update(per_symbol_parts(all_df, bm & stub))
        a = result["age"][bucket]
        print(
            f"AGE {bucket}: raw={a['raw_bar_n']} ep={a['event_state_n']} "
            f"60m_mean={a['60m']['mean']} pct={a['60m']['pct_pos']}"
        )

    # Episode-level (one row per episode at age 0 and at first qualifying)
    ep0 = all_df["is_cross"].to_numpy()
    result["episode_level"] = {
        "age0_one_per_episode": dump_summary("ep_age0", all_df, ep0),
        "first_qual_one_per_episode": dump_summary("ep_first_q", all_df, first_q),
    }
    result["episode_level"]["age0_one_per_episode"].update(per_symbol_parts(all_df, ep0))
    result["episode_level"]["first_qual_one_per_episode"].update(per_symbol_parts(all_df, first_q))

    if swing_frames:
        sw = pd.concat(swing_frames, ignore_index=True)
        sw = sw.loc[sw["ma_fast"].notna() & sw["ma_slow"].notna() & sw["ret_1"].notna()].reset_index(drop=True)
        sw = add_split(sw, (t50, t75))
        sw_state = sw["state"].to_numpy() != 0
        sw_stub = sw["stub_allow"].to_numpy()
        sw_cross = sw["is_cross"].to_numpy()
        result["swing200"] = {
            "note": "Predeclared secondary SMA windows (lookback 200 → 20/100). Not optimized.",
            "A_sma_state": dump_summary("swA", sw, sw_state),
            "B_cross": dump_summary("swB", sw, sw_cross),
            "J_stub": dump_summary("swJ", sw, sw_stub),
        }

    result["finished_at_utc"] = utc_now()
    OUT_JSON.write_text(json.dumps(_jsonable(result), indent=2), encoding="utf-8")
    print("WROTE", OUT_JSON)
    print("FINISH", result["finished_at_utc"])


if __name__ == "__main__":
    main()
