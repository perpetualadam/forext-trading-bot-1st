"""R.37 diagnosis and two pre-registered candidates. The R.36 test slice is not a training set."""

from __future__ import annotations

import hashlib
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
    def connect(self, *_a, **_k):
        raise OSError("R37_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.diagnosis import (
    DIAGNOSTIC_PROTOCOL,
    DIAGNOSTIC_PROTOCOL_SHA256,
    R36_LOGISTIC_PREDICTION_SHA256,
    R36_XGBOOST_PREDICTION_SHA256,
    assert_no_test_rows,
    eligible,
    ev_policy,
    load_logistic,
    load_xgboost,
    mistake_tally,
    outcome_reaches,
    promising,
    reconcile_populations,
    side_bins,
    stride_economics,
    table_for_horizon,
)
from forex_bot.research.learning.features import FEATURE_COLUMNS, prefix_matches, causal_features, leaky_future_return
from forex_bot.research.learning.supervised import (
    align_proba,
    apply_policy,
    brier_score,
    classification_report,
    fit_logistic,
    frequency_vector,
    log_loss,
    matrix_of,
    prediction_digest,
    prepare_market_table,
    slice_positions,
)

EUR_SHA = "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091"
PIP = {"USD_JPY": 0.01}


def _dump(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _score_labels(model, frame, train_target):
    values, target = matrix_of(frame)
    proba = align_proba(model, values)
    labels, confidence = apply_policy(proba, 0.50)
    freq = np.tile(frequency_vector(train_target), (len(target), 1))
    report = classification_report(proba, target, labels)
    report["baseline_log_loss"] = log_loss(freq, target)
    report["baseline_brier"] = brier_score(freq, target)
    return proba, labels, confidence, report


def _instrument_feasibility(history: Path, train_end: pd.Timestamp) -> dict:
    rows = []
    returns = {}
    for path in sorted(history.glob("*.csv")):
        raw = pd.read_csv(path)
        clean, quality = validate_frame(raw)
        spread = clean["ask_close"] - clean["bid_close"]
        name = path.stem.rsplit("_", 1)[0]
        pip = PIP.get(name, 0.0001)
        mid = (clean["bid_close"] + clean["ask_close"]) / 2.0
        ret = mid.pct_change()
        early = clean["time"] < train_end
        returns[name] = pd.Series(ret.to_numpy(), index=clean["time"]).loc[lambda s: s.index < train_end]
        rows.append(
            {
                "instrument": name,
                "rows": quality["rows_read"],
                "gaps": quality["gaps_longer_than_one_bar"],
                "duplicate_timestamps": quality["duplicate_timestamps"],
                "median_spread_price": float(spread.median()),
                "median_spread_pips": float(spread.median() / pip),
                "pip_size": pip,
                "sha256": file_sha256(path),
            }
        )
    aligned = pd.DataFrame(returns).dropna()
    correlation = aligned.corr().round(4).to_dict()
    return {
        "files": rows,
        "train_period_return_correlation": correlation,
        "aligned_training_rows": int(len(aligned)),
        "pooled_model_run": False,
        "reason": "The pairs share the same clock and a common market regime. Six files are not six independent samples. Pooling was not in the frozen candidate list.",
    }


def main() -> None:
    _dump("03_diagnostic_protocol.json", {"sha256": DIAGNOSTIC_PROTOCOL_SHA256, "protocol": DIAGNOSTIC_PROTOCOL})
    for spec in (
        (DIAGNOSTIC_PROTOCOL["candidates"]["B_horizon_48"]["train"], 48, 44743),
        ([20, 12000], 48, 12048),
        ([20, 20000], 48, 20048),
        ([20, 28000], 48, 28048),
        ([20, 44731], 12, 44743),
    ):
        bounds, horizon, nxt = spec
        if outcome_reaches(bounds[1] - 1, nxt, horizon):
            raise SystemExit("R37_EMBARGO_FAILED")
    source = ROOT / "data" / "historical" / "EUR_USD_M5.csv"
    if file_sha256(source) != EUR_SHA:
        raise SystemExit("R37_DATASET_HASH_MISMATCH")
    raw = pd.read_csv(source)
    clean, _quality = validate_frame(raw)
    leak = {
        "prefix_invariant": prefix_matches(causal_features, clean, 1000),
        "leaky_fixture_rejected": not prefix_matches(leaky_future_return, clean.iloc[:80].copy(), 40),
    }
    _dump("10_leakage_controls.json", leak)
    if not leak["prefix_invariant"] or not leak["leaky_fixture_rejected"]:
        raise SystemExit("R37_LEAKAGE_CHECK_FAILED")
    table = prepare_market_table(clean)
    holdout = slice_positions(table, 59657, 74560)
    logistic = load_logistic(ROOT / "data/research/adaptive_ensemble/r36/artifacts/logistic.json")
    xgboost = load_xgboost(ROOT / "data/research/adaptive_ensemble/r36/artifacts/xgboost.json")
    logistic_proba = align_proba(logistic, holdout.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float))
    xgboost_proba = align_proba(xgboost, holdout.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float))
    hashes = {
        "logistic": prediction_digest(logistic_proba),
        "xgboost": prediction_digest(xgboost_proba),
    }
    matched = hashes["logistic"] == R36_LOGISTIC_PREDICTION_SHA256 and hashes["xgboost"] == R36_XGBOOST_PREDICTION_SHA256
    _dump("02_prediction_hash_check.json", {"matched": matched, "hashes": hashes})
    if not matched:
        _dump("02_count_reconciliation.json", {"status": "unresolved", "reason": "reloaded predictions do not match the R.36 hashes"})
        raise SystemExit("R37_RECONCILIATION_UNRESOLVED")
    logistic_labels, logistic_confidence = apply_policy(logistic_proba, 0.50)
    xgboost_labels, _xgboost_confidence = apply_policy(xgboost_proba, 0.50)
    reconciliation = {
        "status": "reconciled",
        "explanation": "Mistake categories count every eligible test bar. The economic action count keeps only bars whose position is a multiple of 12 and whose next bar is evaluable.",
        "logistic": reconcile_populations(
            holdout["position"].to_numpy(),
            logistic_labels,
            holdout["next_bar_evaluable"].to_numpy(dtype=bool),
        ),
        "xgboost": reconcile_populations(
            holdout["position"].to_numpy(),
            xgboost_labels,
            holdout["next_bar_evaluable"].to_numpy(dtype=bool),
        ),
        "logistic_mistake_counts": mistake_tally(holdout, logistic_labels, logistic_confidence),
        "r36_reported_directional_calls": 83,
        "r36_reported_stride_actions": 5,
    }
    _dump("02_count_reconciliation.json", reconciliation)
    if reconciliation["logistic"]["full_directional_calls"] != 83 or reconciliation["logistic"]["stride_actions"] != 5:
        raise SystemExit("R37_REPORTED_COUNTS_NOT_REPRODUCED")
    validation = slice_positions(table, 44743, 59645)
    validation_proba = align_proba(logistic, validation.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float))
    confidence = validation_proba.max(axis=1)
    _dump(
        "06_economic_failure_diagnosis.json",
        {
            "validation_confidence_quantiles": {
                "p50": float(np.quantile(confidence, 0.50)),
                "p90": float(np.quantile(confidence, 0.90)),
                "p99": float(np.quantile(confidence, 0.99)),
                "share_at_least_0.50": float((confidence >= 0.50).mean()),
            },
            "interpretation": [
                "Predictive log loss improved slightly in R.36.",
                "The 0.50 rule abstains on almost every bar because class probabilities stay near one another.",
                "A lower probability cutoff increased turnover and lost money on the validation slice.",
                "Those are separate facts about scores, policy, and economics. None of them is a causal proof by itself.",
            ],
        },
    )
    early = slice_positions(table, 20, 15000)
    assert_no_test_rows(early["position"].to_numpy())
    early_values, early_target = matrix_of(early)
    early_model = fit_logistic(early_values, early_target)
    estimate = slice_positions(table, 15012, 25000)
    if outcome_reaches(int(early["position"].max()), int(estimate["position"].min()), 12):
        raise SystemExit("R37_EV_EMBARGO_FAILED")
    estimate_proba = align_proba(early_model, estimate.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float))
    edges = DIAGNOSTIC_PROTOCOL["candidates"]["A_expected_value_bins"]["bins"]
    buy_bins = side_bins(estimate_proba[:, 2], estimate["next_buy_return"].to_numpy(dtype=float), edges)
    sell_bins = side_bins(estimate_proba[:, 0], estimate["next_sell_return"].to_numpy(dtype=float), edges)
    candidate_a_windows = []
    for start, stop in DIAGNOSTIC_PROTOCOL["candidates"]["A_expected_value_bins"]["evaluation_folds"]:
        fold = slice_positions(table, start, stop)
        assert_no_test_rows(fold["position"].to_numpy())
        proba = align_proba(early_model, fold.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=float))
        labels = ev_policy(proba, buy_bins, sell_bins)
        candidate_a_windows.append({"start": start, "stop": stop, **stride_economics(fold, labels, 12)})
    decision_a = promising([{"recorded_bid_ask": row["recorded_bid_ask"], "plus_half_pip": row["plus_half_pip"]} for row in candidate_a_windows])
    if not any(item["tradeable"] for item in buy_bins + sell_bins):
        decision_a["qualifies"] = False
        decision_a["reason"] = "no_tradeable_probability_bin"
    _dump(
        "08_candidate_a.json",
        {
            "hypothesis": "A probability bin on an earlier fold might identify a cost-adjusted edge.",
            "buy_bins": buy_bins,
            "sell_bins": sell_bins,
            "evaluation": candidate_a_windows,
            "decision": decision_a,
            "compared_with": "always_abstain_mean_of_zero_on_the_same_stride",
        },
    )
    long = table_for_horizon(clean, 48)
    spec = DIAGNOSTIC_PROTOCOL["candidates"]["B_horizon_48"]
    train = eligible(long, *spec["train"])
    assert_no_test_rows(train["position"].to_numpy())
    if int(train["position"].max()) + 48 >= 44743:
        raise SystemExit("R37_HORIZON_EMBARGO_FAILED")
    values, target = matrix_of(train)
    model = fit_logistic(values, target)
    again = fit_logistic(values, target)
    validation_b = eligible(long, *spec["validation"])
    left = prediction_digest(align_proba(model, matrix_of(validation_b)[0]))
    right = prediction_digest(align_proba(again, matrix_of(validation_b)[0]))
    _proba, labels_b, _confidence, report_b = _score_labels(model, validation_b, target)
    economics_b = stride_economics(validation_b, labels_b, 48)
    folds = []
    for fold in spec["walk_forward"]:
        fold_train = eligible(long, *fold["train"])
        fold_eval = eligible(long, *fold["eval"])
        assert_no_test_rows(fold_train["position"].to_numpy())
        if outcome_reaches(int(fold_train["position"].max()), int(fold_eval["position"].min()), 48):
            raise SystemExit("R37_WALK_FORWARD_EMBARGO_FAILED")
        fx, fy = matrix_of(fold_train)
        fitted = fit_logistic(fx, fy)
        _p, fold_labels, _c, fold_report = _score_labels(fitted, fold_eval, fy)
        folds.append(
            {
                "train": fold["train"],
                "eval": fold["eval"],
                "log_loss": fold_report["log_loss"],
                "baseline_log_loss": fold_report["baseline_log_loss"],
                "economics": stride_economics(fold_eval, fold_labels, 48),
            }
        )
    decision_b = promising(
        [{"recorded_bid_ask": economics_b["recorded_bid_ask"], "plus_half_pip": economics_b["plus_half_pip"]}]
        + [
            {"recorded_bid_ask": row["economics"]["recorded_bid_ask"], "plus_half_pip": row["economics"]["plus_half_pip"]}
            for row in folds
        ]
    )
    log_loss_folds = sum(row["log_loss"] <= row["baseline_log_loss"] for row in folds)
    if log_loss_folds < 2:
        decision_b["qualifies"] = False
        decision_b["reason"] = "walk_forward_log_loss"
    artifact = {
        "coef": model.named_steps["clf"].coef_.tolist(),
        "intercept": model.named_steps["clf"].intercept_.tolist(),
        "classes": [int(value) for value in model.named_steps["clf"].classes_],
    }
    artifact_hash = hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    (OUT / "artifacts").mkdir(exist_ok=True)
    (OUT / "artifacts" / "candidate_b_logistic.json").write_text(json.dumps(artifact), encoding="utf-8")
    _dump(
        "09_candidate_b.json",
        {
            "hypothesis": "A 48-bar horizon might leave more room over the spread than 12 bars.",
            "log_loss_comparable_to_r36": False,
            "reproducible": left == right,
            "validation_log_loss": report_b["log_loss"],
            "validation_baseline_log_loss": report_b["baseline_log_loss"],
            "validation_brier": report_b["brier"],
            "validation_ece": report_b["ece"],
            "validation_abstention_rate": report_b["abstention_rate"],
            "validation_economics": economics_b,
            "walk_forward": folds,
            "decision": decision_b,
            "artifact_sha256": artifact_hash,
            "validation_prediction_sha256": left,
        },
    )
    history = _instrument_feasibility(ROOT / "data" / "historical", table["time"].iloc[44731])
    _dump("14_multi_instrument_feasibility.json", history)
    advancement = "NO_MODEL_QUALIFIES_FOR_ADVANCEMENT"
    if decision_a.get("qualifies") or decision_b.get("qualifies"):
        advancement = "review_required_but_not_promoted"
    _dump(
        "15_learning_history.json",
        {
            "advancement": advancement,
            "production_authorised": False,
            "records": [
                {
                    "candidate": "A_expected_value_bins",
                    "motivation": "R.36 validation showed a 0.50 cutoff almost never acts and a 0.40 cutoff lost money.",
                    "change": "Trade only inside probability bins that were positive on an earlier walk-forward fold.",
                    "result": decision_a,
                    "decision": "reject" if not decision_a.get("qualifies") else "inconclusive",
                },
                {
                    "candidate": "B_horizon_48",
                    "motivation": "The 12-bar move is often similar in size to the spread.",
                    "change": "Same logistic specification, horizon and embargo set to 48 before evaluation.",
                    "result": decision_b,
                    "decision": "reject" if not decision_b.get("qualifies") else "inconclusive",
                },
                {
                    "candidate": "C_not_run",
                    "motivation": "No specific feature defect was established on training or validation evidence.",
                    "change": "none",
                    "decision": "not_run",
                },
            ],
        },
    )
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    _dump(
        "01_run_identity.json",
        {
            "branch": branch,
            "head": head,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "advancement": advancement,
            "protocol_sha256": DIAGNOSTIC_PROTOCOL_SHA256,
        },
    )
    print(json.dumps({"advancement": advancement, "protocol": DIAGNOSTIC_PROTOCOL_SHA256, "reconciled": True, "a": decision_a.get("qualifies"), "b": decision_b.get("qualifies")}))


if __name__ == "__main__":
    main()
