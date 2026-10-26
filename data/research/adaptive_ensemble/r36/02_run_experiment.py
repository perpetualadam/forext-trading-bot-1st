"""Train offline R.36 models. The held-out test slice is scored only after selection is saved."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from collections import Counter
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
        raise OSError("R36_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.decision_journal import validate_journal_record
from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.features import prefix_matches, causal_features, leaky_future_return
from forex_bot.research.learning.journal import research_decision_id
from forex_bot.research.learning.mistakes import classify_mistake
from forex_bot.research.learning.supervised import (
    FEATURE_SCHEMA_SHA256,
    FROZEN_PROTOCOL,
    FROZEN_PROTOCOL_SHA256,
    INDEX_TO_CLASS,
    align_proba,
    apply_policy,
    brier_score,
    classification_report,
    economic_report,
    fit_logistic,
    fit_xgboost,
    frequency_vector,
    json_bytes,
    library_status,
    log_loss,
    matrix_of,
    momentum_baseline,
    outcome_reaches_next_period,
    prediction_digest,
    prepare_market_table,
    qualify,
    sha256_bytes,
    slice_positions,
)

EUR_SHA = "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091"
FEATURE_SHA = "7d15b98d9bfe99136f2de5e05522d9cef623539b38f7ab61e9ea722a24889946"
EVAL_SHA = "bab4a868f1b789b795c5c124f86f7975d0b6ca9a5c0848b3323f743c2d8f81e9"


def _dump(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _check_boundaries() -> None:
    splits = FROZEN_PROTOCOL["splits"]
    pairs = (
        (splits["train"][1], splits["validation"][0]),
        (splits["validation"][1], splits["test"][0]),
    )
    for stop, start in pairs:
        if outcome_reaches_next_period(stop - 1, start):
            raise RuntimeError("main_split_embargo_failed")
    for fold in FROZEN_PROTOCOL["walk_forward"]:
        if outcome_reaches_next_period(fold["train"][1] - 1, fold["eval"][0]):
            raise RuntimeError(f"{fold['name']}_embargo_failed")
        if fold["eval"][1] > splits["train"][1]:
            raise RuntimeError("walk_forward_enters_validation")


def _fit_pair(kind: str, values: np.ndarray, target: np.ndarray):
    if kind == "logistic":
        return fit_logistic(values, target)
    if kind == "xgboost":
        return fit_xgboost(values, target)
    raise RuntimeError("unknown_model")


def _score(model, frame: pd.DataFrame, train_target: np.ndarray, threshold: float) -> dict:
    values, target = matrix_of(frame)
    proba = align_proba(model, values)
    labels, _confidence = apply_policy(proba, threshold)
    freq = frequency_vector(train_target)
    baseline = np.tile(freq, (len(target), 1))
    report = classification_report(proba, target, labels)
    report["baseline_log_loss"] = log_loss(baseline, target)
    report["baseline_brier"] = brier_score(baseline, target)
    report["baseline_ece"] = None
    report["probabilities"] = proba
    report["labels"] = labels
    report["target"] = target
    return report


def _selection_view(score: dict, frame: pd.DataFrame, reproducible: bool) -> dict:
    econ = economic_report(frame, score["labels"], "next")
    interval = econ["recorded_bid_ask"]["block_interval"] or {}
    return {
        "log_loss": score["log_loss"],
        "baseline_log_loss": score["baseline_log_loss"],
        "brier": score["brier"],
        "baseline_brier": score["baseline_brier"],
        "ece": score["ece"],
        "n_actions": econ["recorded_bid_ask"]["n_actions"],
        "mean_return": econ["recorded_bid_ask"]["mean_including_abstentions"],
        "bootstrap_low": interval.get("low"),
        "half_pip_mean": econ["plus_half_pip"]["mean_including_abstentions"],
        "reproducible": reproducible,
    }


def _choose_threshold(model, frame: pd.DataFrame, train_target: np.ndarray) -> dict:
    values, _target = matrix_of(frame)
    proba = align_proba(model, values)
    chosen = {"threshold": 0.50, "reason": "default_no_candidate_with_30_actions"}
    best_mean = None
    considered = []
    for threshold in FROZEN_PROTOCOL["policy"]["validation_threshold_grid"]:
        labels, _confidence = apply_policy(proba, threshold)
        econ = economic_report(frame, labels, "next")["recorded_bid_ask"]
        considered.append({"threshold": threshold, "n_actions": econ["n_actions"], "mean": econ["mean_including_abstentions"]})
        if econ["n_actions"] < 30 or econ["mean_including_abstentions"] is None:
            continue
        mean = econ["mean_including_abstentions"]
        better = best_mean is None or mean > best_mean + 1e-15 or (abs(mean - best_mean) <= 1e-15 and threshold > chosen["threshold"])
        if better:
            best_mean = mean
            chosen = {"threshold": threshold, "reason": "validation_stride12_mean", "mean": mean, "n_actions": econ["n_actions"]}
    chosen["considered"] = considered
    return chosen


def _artifact(kind: str, model, path: Path) -> str:
    if kind == "logistic":
        clf = model.named_steps["clf"]
        payload = {
            "coef": clf.coef_.tolist(),
            "intercept": clf.intercept_.tolist(),
            "classes": [int(value) for value in clf.classes_],
            "scaler_mean": model.named_steps["scaler"].mean_.tolist(),
            "scaler_scale": model.named_steps["scaler"].scale_.tolist(),
            "imputer_statistics": model.named_steps["imputer"].statistics_.tolist(),
            "n_iter": [int(value) for value in np.atleast_1d(clf.n_iter_)],
        }
        raw = json_bytes(payload)
        path.write_bytes(raw)
        return sha256_bytes(raw)
    model.save_model(str(path))
    return sha256_bytes(path.read_bytes())


def _public_score(score: dict, frame: pd.DataFrame) -> dict:
    econ_next = economic_report(frame, score["labels"], "next")
    econ_close = economic_report(frame, score["labels"], "close")
    midpoint = frame["directional_outcome"].astype(str).to_numpy()
    labels = score["labels"]
    directional = labels != "NO_TRADE"
    midpoint_hits = ((labels == "BUY") & (midpoint == "up")) | ((labels == "SELL") & (midpoint == "down"))
    spread = frame["spread"].to_numpy(dtype=float)
    return {
        "log_loss": score["log_loss"],
        "brier": score["brier"],
        "ece": score["ece"],
        "accuracy": score["accuracy"],
        "abstention_rate": score["abstention_rate"],
        "baseline_log_loss": score["baseline_log_loss"],
        "baseline_brier": score["baseline_brier"],
        "confusion_truth_rows_predicted_columns": score["confusion_truth_rows_predicted_columns"],
        "per_class": score["per_class"],
        "class_balance": score["class_balance"],
        "prediction_sha256": prediction_digest(score["probabilities"]),
        "next_bar": econ_next,
        "close_to_close": econ_close,
        "midpoint_hit_rate_among_actions": None if not np.any(directional) else float(midpoint_hits[directional].mean()),
        "spread_price_quantiles": {
            "p10": float(np.quantile(spread, 0.10)),
            "p50": float(np.quantile(spread, 0.50)),
            "p90": float(np.quantile(spread, 0.90)),
        },
    }


def _baseline_economics(frame: pd.DataFrame, train_target: np.ndarray) -> dict:
    majority = INDEX_TO_CLASS[int(np.argmax(frequency_vector(train_target)))]
    majority_labels = np.full(len(frame), majority, dtype=object)
    momentum = momentum_baseline(frame)
    return {
        "majority_class": majority,
        "majority_next_bar": economic_report(frame, majority_labels, "next"),
        "momentum_next_bar": economic_report(frame, momentum, "next"),
        "always_abstain_mean": 0.0,
    }


def _mistakes(frame: pd.DataFrame, labels: np.ndarray, confidence: np.ndarray, train: pd.DataFrame) -> dict:
    vol_edges = np.quantile(train["rolling_vol_20"].to_numpy(dtype=float), [1.0 / 3.0, 2.0 / 3.0])
    spread_edges = np.quantile(train["spread"].to_numpy(dtype=float), [1.0 / 3.0, 2.0 / 3.0])

    def _bucket(value: float, edges: np.ndarray) -> str:
        if value <= edges[0]:
            return "low"
        if value <= edges[1]:
            return "mid"
        return "high"

    counts: Counter[str] = Counter()
    by_session: dict[str, Counter] = {}
    by_vol: dict[str, Counter] = {}
    by_spread: dict[str, Counter] = {}
    for index, label in enumerate(labels):
        evaluable = bool(frame["next_bar_evaluable"].iloc[index])
        buy = float(frame["next_buy_return"].iloc[index]) if evaluable else None
        sell = float(frame["next_sell_return"].iloc[index]) if evaluable else None
        row = {
            "prediction_status": "abstain" if label == "NO_TRADE" else "directional",
            "outcome_evaluable": evaluable,
            "direction": None if label == "NO_TRADE" else str(label),
            "directional_outcome": None if not evaluable else frame["directional_outcome"].iloc[index],
            "cost_adjusted_return": None if label == "NO_TRADE" or not evaluable else (buy if label == "BUY" else sell),
            "confidence": float(confidence[index]),
            "best_hypothetical_cost_return": None if not evaluable else max(buy, sell),
        }
        kind = classify_mistake(row)
        counts[kind] += 1
        session = str(int(frame["session_code"].iloc[index]))
        vol_name = _bucket(float(frame["rolling_vol_20"].iloc[index]), vol_edges)
        spread_name = _bucket(float(frame["spread"].iloc[index]), spread_edges)
        by_session.setdefault(session, Counter())[kind] += 1
        by_vol.setdefault(vol_name, Counter())[kind] += 1
        by_spread.setdefault(spread_name, Counter())[kind] += 1
    return {
        "counts": dict(counts),
        "by_session_code": {key: dict(value) for key, value in by_session.items()},
        "by_volatility_tercile_from_training": {key: dict(value) for key, value in by_vol.items()},
        "by_spread_tercile_from_training": {key: dict(value) for key, value in by_spread.items()},
        "cost_convention": "next_bar_open_entry",
        "individual_losses_are_not_systematic_proof": True,
    }


def _sample_journal(frame: pd.DataFrame, labels: np.ndarray, proba: np.ndarray, dataset_sha: str, artifact: str, model_id: str) -> list[dict]:
    samples = []
    for index, label in enumerate(labels):
        if len(samples) >= 3:
            break
        if index not in (0, len(labels) // 2, len(labels) - 1):
            continue
        stamp = pd.Timestamp(frame["time"].iloc[index]).to_pydatetime()
        evaluable = bool(frame["outcome_evaluable"].iloc[index])
        decision = "abstained" if label == "NO_TRADE" else "accepted"
        direction = None if label == "NO_TRADE" else str(label)
        move = frame["directional_outcome"].iloc[index]
        matched = (direction == "BUY" and move == "up") or (direction == "SELL" and move == "down")
        record = validate_journal_record(
            {
                "decision_at": stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=timezone.utc),
                "instrument": "EUR_USD",
                "timeframe": "M5",
                "feature_schema_version": "r35.features.v1",
                "model_id": model_id,
                "model_version": "r36",
                "artifact_sha256": artifact,
                "prediction_direction": direction,
                "probabilities": {INDEX_TO_CLASS[column]: float(proba[index, column]) for column in range(3)},
                "decision": decision,
                "spread": float(frame["spread"].iloc[index]),
                "market_condition": "research_exposed",
                "risk_rejection_reason": "" if decision == "accepted" else "research_abstain_policy",
                "outcome_return": float(frame["midpoint_return"].iloc[index]) if evaluable else None,
                "prediction_error": None if not evaluable else (0.0 if matched or direction is None else 1.0),
                "outcome_evaluable": evaluable,
                "adverse_outcome": None if not evaluable else False,
                "data_provenance": dataset_sha,
                "model_provenance": "r36_research_exposed_not_for_production",
                "prediction_status": "recorded",
            }
        )
        samples.append(
            {
                "research_decision_id": research_decision_id(dataset_sha, "EUR_USD", "M5", record.decision_at),
                "decision": record.decision,
                "prediction_direction": record.prediction_direction,
                "validation_status": "unvalidated",
            }
        )
    return samples


def main() -> None:
    _check_boundaries()
    if FEATURE_SCHEMA_SHA256 != FEATURE_SHA or FROZEN_PROTOCOL["evaluation_protocol_sha256"] != EVAL_SHA:
        raise SystemExit("R36_PROTOCOL_HASH_MISMATCH")
    libraries = library_status()
    _dump("02_dependencies.json", {"libraries": libraries, "proposed_install_not_executed": ["python -m pip install lightgbm"] if libraries.get("lightgbm") is None else []})
    _dump("03_frozen_protocol.json", {"sha256": FROZEN_PROTOCOL_SHA256, "protocol": FROZEN_PROTOCOL})
    source = ROOT / "data" / "historical" / "EUR_USD_M5.csv"
    dataset_sha = file_sha256(source)
    if dataset_sha != EUR_SHA:
        raise SystemExit("R36_DATASET_HASH_MISMATCH")
    raw = pd.read_csv(source)
    clean, quality = validate_frame(raw)
    leak_frame = clean.iloc[:80].copy()
    leakage = {
        "prefix_invariant_at_1000": prefix_matches(causal_features, clean, 1000),
        "leaky_fixture_detected": not prefix_matches(leaky_future_return, leak_frame, 40),
        "nominal_embargo_holds": True,
    }
    _dump("05_leakage_controls.json", leakage)
    if not leakage["prefix_invariant_at_1000"] or not leakage["leaky_fixture_detected"]:
        raise SystemExit("R36_LEAKAGE_CHECK_FAILED")
    table = prepare_market_table(clean)
    splits = FROZEN_PROTOCOL["splits"]
    train = slice_positions(table, *splits["train"])
    validation = slice_positions(table, *splits["validation"])
    holdout = slice_positions(table, *splits["test"])
    removed = {
        "rows_read": quality["rows_read"],
        "rows_kept": quality["rows_kept"],
        "feature_invalid": int((~table["feature_valid"]).sum()),
        "label_unevaluable": int((~table["outcome_evaluable"]).sum()),
        "eligible": int(train.shape[0] + validation.shape[0] + holdout.shape[0]),
        "train_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "test_rows": int(len(holdout)),
        "embargo_positions": 24,
        "warmup_bars": 20,
        "gaps_longer_than_one_bar": quality["gaps_longer_than_one_bar"],
    }
    _dump("04_split_boundaries.json", {"removed": removed, "splits": splits, "research_exposed": True})
    x_train, y_train = matrix_of(train)
    balance = {INDEX_TO_CLASS[index]: int((y_train == index).sum()) for index in range(3)}
    _dump("04b_training_class_balance.json", balance)
    kinds = ["logistic"]
    if libraries.get("xgboost"):
        kinds.append("xgboost")
    models = {}
    reproducible = {}
    artifacts = {}
    for kind in kinds:
        model = _fit_pair(kind, x_train, y_train)
        again = _fit_pair(kind, x_train, y_train)
        left = prediction_digest(align_proba(model, matrix_of(validation)[0]))
        right = prediction_digest(align_proba(again, matrix_of(validation)[0]))
        reproducible[kind] = left == right
        suffix = "json"
        path = OUT / "artifacts" / f"{kind}.{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        artifacts[kind] = _artifact(kind, model, path)
        models[kind] = model
    validation_scores = {kind: _score(models[kind], validation, y_train, 0.50) for kind in kinds}
    thresholds = {kind: _choose_threshold(models[kind], validation, y_train) for kind in kinds}
    walk = []
    for kind in kinds:
        for fold in FROZEN_PROTOCOL["walk_forward"]:
            fold_train = slice_positions(table, *fold["train"])
            fold_eval = slice_positions(table, *fold["eval"])
            if outcome_reaches_next_period(int(fold_train["position"].max()), int(fold_eval["position"].min())):
                raise RuntimeError("filtered_embargo_failed")
            fx, fy = matrix_of(fold_train)
            if set(fy.tolist()) != {0, 1, 2}:
                walk.append({"model": kind, "fold": fold["name"], "status": "missing_class"})
                continue
            fitted = _fit_pair(kind, fx, fy)
            scored = _score(fitted, fold_eval, fy, 0.50)
            walk.append(
                {
                    "model": kind,
                    "fold": fold["name"],
                    "status": "ok",
                    "train_end_position": fold["train"][1],
                    "eval_start_position": fold["eval"][0],
                    "log_loss": scored["log_loss"],
                    "baseline_log_loss": scored["baseline_log_loss"],
                    "brier": scored["brier"],
                    "n": int(len(fold_eval)),
                    "prediction_sha256": prediction_digest(scored["probabilities"]),
                }
            )
    decisions = {}
    for kind in kinds:
        view = _selection_view(validation_scores[kind], validation, reproducible[kind])
        fold_rows = [row for row in walk if row["model"] == kind]
        decisions[kind] = qualify(view, fold_rows)
        decisions[kind]["validation_threshold_choice"] = {key: value for key, value in thresholds[kind].items() if key != "considered"}
        decisions[kind]["threshold_grid"] = thresholds[kind]["considered"]
    qualified = [kind for kind, row in decisions.items() if row["qualifies"]]
    advancement = qualified[0] if len(qualified) == 1 else ("NO_MODEL_QUALIFIES_FOR_ADVANCEMENT" if not qualified else min(qualified, key=lambda name: validation_scores[name]["log_loss"]))
    if len(qualified) > 1:
        advancement_reason = "lowest_validation_log_loss_among_qualifying_models"
    else:
        advancement_reason = "frozen_rule"
    selection = {
        "advancement": advancement if qualified else "NO_MODEL_QUALIFIES_FOR_ADVANCEMENT",
        "advancement_reason": advancement_reason,
        "test_metrics_used": False,
        "validation_status": "unvalidated",
        "production_authorised": False,
        "models": decisions,
        "training_class_balance": balance,
        "lightgbm": "unavailable",
    }
    if not qualified:
        selection["advancement"] = "NO_MODEL_QUALIFIES_FOR_ADVANCEMENT"
    _dump("06_selection_decision.json", selection)
    selection_hash = hashlib.sha256((OUT / "06_selection_decision.json").read_bytes()).hexdigest()
    holdout_public = {}
    mistake_report = {}
    journals = {}
    for kind in kinds:
        score = _score(models[kind], holdout, y_train, 0.50)
        holdout_public[kind] = _public_score(score, holdout)
        chosen = thresholds[kind]["threshold"]
        tuned = _score(models[kind], holdout, y_train, chosen)
        holdout_public[kind]["validation_chosen_threshold"] = chosen
        holdout_public[kind]["at_validation_chosen_threshold"] = {
            "log_loss": tuned["log_loss"],
            "abstention_rate": tuned["abstention_rate"],
            "next_bar": economic_report(holdout, tuned["labels"], "next"),
        }
        _confidence = tuned["probabilities"].max(axis=1)
        # Mistake analysis uses the a priori 0.50 policy, not the tuned threshold.
        mistake_report[kind] = _mistakes(holdout, score["labels"], score["probabilities"].max(axis=1), train)
        journals[kind] = _sample_journal(holdout, score["labels"], score["probabilities"], dataset_sha, artifacts[kind], kind)
    if hashlib.sha256((OUT / "06_selection_decision.json").read_bytes()).hexdigest() != selection_hash:
        raise SystemExit("R36_SELECTION_CHANGED_AFTER_TEST")
    validation_public = {kind: _public_score(validation_scores[kind], validation) for kind in kinds}
    for kind in kinds:
        validation_public[kind].pop("prediction_sha256", None)
        validation_public[kind]["prediction_sha256"] = prediction_digest(validation_scores[kind]["probabilities"])
        validation_public[kind]["baselines"] = _baseline_economics(validation, y_train)
        holdout_public[kind]["baselines"] = _baseline_economics(holdout, y_train)
    _dump("08_validation_metrics.json", validation_public)
    _dump("09_test_metrics.json", holdout_public)
    _dump("10_walk_forward.json", {"folds": walk})
    _dump("11_mistakes.json", mistake_report)
    _dump(
        "07_artifacts.json",
        {
            "models": {
                kind: {
                    "artifact_sha256": artifacts[kind],
                    "prediction_sha256": holdout_public[kind]["prediction_sha256"],
                    "reproducible": reproducible[kind],
                    "library": libraries.get("sklearn" if kind == "logistic" else "xgboost"),
                    "validation_status": "unvalidated",
                }
                for kind in kinds
            },
            "journal_samples": journals,
            "dataset_sha256": dataset_sha,
            "frozen_protocol_sha256": FROZEN_PROTOCOL_SHA256,
        },
    )
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    _dump("01_run_identity.json", {"branch": branch, "head": head, "finished_utc": datetime.now(timezone.utc).isoformat(), "advancement": selection["advancement"]})
    print(json.dumps({"advancement": selection["advancement"], "models": kinds, "train_rows": len(train), "reproducible": reproducible}))


if __name__ == "__main__":
    main()
