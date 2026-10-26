"""R.38 cost-aware feature discovery. The protocol is written before the comparisons."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["DOTENV_PATH"] = str(OUT / "missing.env")
import dotenv

dotenv.load_dotenv = lambda *a, **k: False


class _Blocked(socket.socket):
    def connect(self, *_args, **_kwargs):
        raise OSError("R38_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.feature_discovery import (
    CATEGORICAL_FEATURES,
    DATASET_SHA256,
    NUMERIC_FEATURES,
    PIP_SIZE,
    PRIMARY_HORIZON,
    PRIMARY_INSTRUMENT,
    PROTOCOL,
    PROTOCOL_SHA256,
    SENSITIVITY_HORIZON,
    apply_candidate,
    association_interval,
    classify_feature,
    fit_magnitude,
    period_mask,
    promotion_allowed,
    quantile_edges,
    research_frame,
    same_sign,
    spearman,
    stride_mean,
)
from forex_bot.research.learning.features import causal_features, leaky_future_return, prefix_matches

TRAIN_END = pd.Timestamp(PROTOCOL["train_end_exclusive"])
CONFIRM_START = pd.Timestamp(PROTOCOL["confirmation_start"])
FOLD_STARTS = [pd.Timestamp(value) for value in PROTOCOL["walk_forward_eval_starts"]]


def _dump(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _column(frame: pd.DataFrame, name: str) -> np.ndarray:
    return frame[name].to_numpy(dtype=float)


def _screen(frame: pd.DataFrame, horizon: int) -> list[dict]:
    rows = []
    target = _column(frame, "midpoint_return")
    block = max(20, horizon)
    for name in NUMERIC_FEATURES:
        item = association_interval(_column(frame, name), target, block)
        item["feature"] = name
        item["unadjusted_excludes_zero"] = bool(item["low"] is not None and (item["low"] > 0.0 or item["high"] < 0.0))
        rows.append(item)
    return rows


def _walk_forward(frame: pd.DataFrame, horizon: int) -> list[dict]:
    ends = FOLD_STARTS[1:] + [TRAIN_END]
    folds = []
    for start, end in zip(FOLD_STARTS, ends):
        train = frame.loc[period_mask(frame, None, start, horizon)]
        eval_rows = frame.loc[period_mask(frame, start, end, horizon)]
        if train.empty or eval_rows.empty:
            raise SystemExit("R38_EMPTY_FOLD")
        if train["outcome_timestamp"].max() >= eval_rows["time"].min():
            raise SystemExit("R38_EMBARGO_FAILED")
        signs = {}
        target = _column(eval_rows, "midpoint_return")
        for name in NUMERIC_FEATURES:
            values = _column(eval_rows, name)
            paired = np.isfinite(values) & np.isfinite(target)
            signs[name] = spearman(values[paired], target[paired])
        folds.append({"eval_start": str(start), "eval_end": str(end), "n": int(len(eval_rows)), "rho": signs})
    return folds


def main() -> None:
    _dump("03_protocol.json", {"sha256": PROTOCOL_SHA256, "protocol": PROTOCOL})
    history = ROOT / "data" / "historical"
    hashes = {}
    for name, expected in DATASET_SHA256.items():
        digest = file_sha256(history / f"{name}_M5.csv")
        hashes[name] = digest
        if digest != expected:
            raise SystemExit("R38_DATASET_HASH_MISMATCH")
    _dump("02_dataset_hashes.json", hashes)
    if promotion_allowed():
        raise SystemExit("R38_PROMOTION_BLOCKED")
    clean = {}
    for name in DATASET_SHA256:
        raw = pd.read_csv(history / f"{name}_M5.csv")
        frame, quality = validate_frame(raw)
        if quality["duplicate_timestamps"] or quality["out_of_order_steps"] or quality["negative_spread_rows"]:
            raise SystemExit(f"R38_DATA_QUALITY_{name}")
        clean[name] = frame
    eur = clean[PRIMARY_INSTRUMENT]
    leak = {
        "prefix_invariant": prefix_matches(causal_features, eur, 1000),
        "leaky_fixture_rejected": not prefix_matches(leaky_future_return, eur.iloc[:80].copy(), 40),
    }
    _dump("06_leakage_controls.json", leak)
    if not leak["prefix_invariant"] or not leak["leaky_fixture_rejected"]:
        raise SystemExit("R38_LEAKAGE_CHECK_FAILED")
    primary = research_frame(eur, PRIMARY_HORIZON)
    train = primary.loc[period_mask(primary, None, TRAIN_END, PRIMARY_HORIZON)]
    confirm = primary.loc[period_mask(primary, CONFIRM_START, None, PRIMARY_HORIZON)]
    if train["outcome_timestamp"].max() >= CONFIRM_START or confirm["time"].min() < CONFIRM_START:
        raise SystemExit("R38_SPLIT_FAILED")
    training_screen = _screen(train, PRIMARY_HORIZON)
    eligible = [row for row in training_screen if row["unadjusted_excludes_zero"]]
    selected = None
    if eligible:
        selected = sorted(eligible, key=lambda row: (-abs(row["rho"]), NUMERIC_FEATURES.index(row["feature"])))[0]
    confirmation = _screen(confirm, PRIMARY_HORIZON)
    folds = _walk_forward(primary, PRIMARY_HORIZON)
    by_name = {row["feature"]: row for row in confirmation}
    train_by_name = {row["feature"]: row for row in training_screen}
    candidate_result = {"constructed": False, "reason": "no_training_interval_excluded_zero"}
    passing_feature = None
    if selected is not None:
        low, high = quantile_edges(_column(train, selected["feature"]))
        positive = selected["rho"] > 0.0
        labels = apply_candidate(_column(confirm, selected["feature"]), low, high, positive)
        economics = stride_mean(confirm, labels, PRIMARY_HORIZON, PIP_SIZE[PRIMARY_INSTRUMENT])
        abstain = stride_mean(confirm, np.full(len(confirm), "NO_TRADE", dtype=object), PRIMARY_HORIZON, PIP_SIZE[PRIMARY_INSTRUMENT])
        always_buy = stride_mean(confirm, np.full(len(confirm), "BUY", dtype=object), PRIMARY_HORIZON, PIP_SIZE[PRIMARY_INSTRUMENT])
        passes = (
            economics["recorded"]["n_actions"] >= PROTOCOL["minimum_actions"]
            and economics["recorded"]["mean"] is not None
            and economics["recorded"]["mean"] > 0.0
            and economics["recorded"]["bootstrap_low"] is not None
            and economics["recorded"]["bootstrap_low"] > 0.0
            and economics["half_pip"]["mean"] is not None
            and economics["half_pip"]["mean"] > 0.0
        )
        if passes:
            passing_feature = selected["feature"]
        candidate_result = {
            "constructed": True,
            "feature": selected["feature"],
            "training_rho": selected["rho"],
            "positive_association": positive,
            "thresholds": {"low": low, "high": high},
            "economics": economics,
            "always_abstain_mean": abstain["recorded"]["mean"],
            "always_buy_mean": always_buy["recorded"]["mean"],
            "passes": passes,
            "production_authorised": False,
        }
    classifications = []
    for name in NUMERIC_FEATURES:
        later = by_name[name]
        earlier = train_by_name[name]
        fold_signs = [same_sign(earlier["rho"], fold["rho"][name]) for fold in folds]
        stable = all(fold_signs) and same_sign(earlier["rho"], later["rho"])
        classifications.append(
            {
                "feature": name,
                "classification": classify_feature(later["n"], later["excludes_zero"], stable, name == passing_feature),
                "confirmation_rho": later["rho"],
                "adjusted_low": later["adjusted_low"],
                "adjusted_high": later["adjusted_high"],
                "training_rho": earlier["rho"],
                "sign_stable": stable,
                "n": later["n"],
            }
        )
    for name in CATEGORICAL_FEATURES:
        classifications.append({"feature": name, "classification": "INCONCLUSIVE", "reason": "categorical_summary_is_descriptive"})
    sessions = (
        confirm.groupby("session_code")
        .agg(n=("midpoint_return", "size"), mean_signed=("midpoint_return", "mean"), mean_absolute=("absolute_midpoint_return", "mean"))
        .reset_index()
        .to_dict(orient="records")
    )
    hindsight = confirm["hindsight_best_side"].to_numpy(dtype=float)
    hindsight = hindsight[np.isfinite(hindsight)]
    _dump(
        "07_feature_comparisons.json",
        {
            "training_screen": training_screen,
            "confirmation": confirmation,
            "walk_forward": folds,
            "classifications": classifications,
            "session_means_descriptive": sessions,
            "hindsight_upper_bound": {
                "label": "better_of_buy_and_sell_after_the_outcome_is_known",
                "n": int(len(hindsight)),
                "mean": float(hindsight.mean()),
                "share_positive": float((hindsight > 0.0).mean()),
            },
        },
    )
    magnitude = {}
    for horizon in (PRIMARY_HORIZON, SENSITIVITY_HORIZON):
        framed = primary if horizon == PRIMARY_HORIZON else research_frame(eur, horizon)
        early = framed.loc[period_mask(framed, None, TRAIN_END, horizon)]
        later = framed.loc[period_mask(framed, CONFIRM_START, None, horizon)]
        magnitude[str(horizon)] = fit_magnitude(
            early.loc[:, list(NUMERIC_FEATURES)].to_numpy(dtype=float),
            _column(early, "absolute_midpoint_return"),
            later.loc[:, list(NUMERIC_FEATURES)].to_numpy(dtype=float),
            _column(later, "absolute_midpoint_return"),
        )
        point = []
        target = _column(later, "absolute_midpoint_return")
        for name in NUMERIC_FEATURES:
            values = _column(later, name)
            paired = np.isfinite(values) & np.isfinite(target)
            point.append({"feature": name, "rho_with_absolute_return": spearman(values[paired], target[paired]), "n": int(paired.sum())})
        magnitude[str(horizon)]["exploratory_absolute_correlations"] = point
    _dump("08_magnitude.json", magnitude)
    _dump("16_candidate.json", candidate_result)
    replication = []
    eur_sign = {row["feature"]: row["rho"] for row in confirmation}
    for name, frame in clean.items():
        if name == PRIMARY_INSTRUMENT:
            continue
        other = research_frame(frame, PRIMARY_HORIZON)
        later = other.loc[period_mask(other, CONFIRM_START, None, PRIMARY_HORIZON)]
        target = _column(later, "midpoint_return")
        rows = []
        for feature in NUMERIC_FEATURES:
            values = _column(later, feature)
            paired = np.isfinite(values) & np.isfinite(target)
            rho = spearman(values[paired], target[paired])
            rows.append({"feature": feature, "rho": rho, "same_sign_as_eur": same_sign(rho, eur_sign[feature])})
        spread = (later["spread"] / PIP_SIZE[name]).median()
        replication.append({"instrument": name, "n": int(len(later)), "median_spread_pips": float(spread), "features": rows, "independent_confirmation": False})
    _dump("14_multi_instrument.json", {"primary": PRIMARY_INSTRUMENT, "replication": replication, "pooled_model": False})
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    _dump(
        "01_run_identity.json",
        {
            "branch": branch,
            "head": head,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": PROTOCOL_SHA256,
            "candidate_passes": bool(candidate_result.get("passes")),
            "production_authorised": False,
        },
    )
    print(json.dumps({"protocol": PROTOCOL_SHA256, "candidate": candidate_result.get("feature"), "passes": candidate_result.get("passes", False)}))


if __name__ == "__main__":
    main()
