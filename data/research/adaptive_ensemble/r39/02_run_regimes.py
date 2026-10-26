"""R.39 regime research. The protocol is written before strategy outcomes are scored."""

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
    def connect(self, *_args, **_kwargs):
        raise OSError("R39_NETWORK_BLOCKED")


socket.socket = _Blocked

from forex_bot.research.learning.data_validation import file_sha256, validate_frame
from forex_bot.research.learning.features import causal_features, leaky_future_return, prefix_matches
from forex_bot.research.learning.regimes import (
    DATASET_SHA256,
    HOLD_BARS,
    LOOKBACK,
    PIP_SIZE,
    PROTOCOL,
    PROTOCOL_SHA256,
    classify_regimes,
    merits,
    promotion_allowed,
    select_signals,
    simulate,
    strategy_signals,
    summarise,
)

TRAIN_END = pd.Timestamp(PROTOCOL["train_end_exclusive"])
CONFIRM_START = pd.Timestamp(PROTOCOL["confirmation_start"])
STREAMS = ("range", "trend", "breakout", "selector")


def _dump(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _market(clean: pd.DataFrame) -> dict:
    bid_close = clean["bid_close"].to_numpy(dtype=float)
    ask_close = clean["ask_close"].to_numpy(dtype=float)
    bid_open = clean["bid_open"].to_numpy(dtype=float)
    ask_open = clean["ask_open"].to_numpy(dtype=float)
    high = ((clean["bid_high"] + clean["ask_high"]) / 2.0).to_numpy(dtype=float)
    low = ((clean["bid_low"] + clean["ask_low"]) / 2.0).to_numpy(dtype=float)
    mid = (bid_close + ask_close) / 2.0
    opened = (bid_open + ask_open) / 2.0
    spread = ask_close - bid_close
    time_ns = clean["time"].astype("int64").to_numpy()
    signals = strategy_signals(mid, opened, high, low, spread)
    regimes = classify_regimes(mid, high, low, spread, time_ns)
    signals["selector"] = select_signals(regimes, signals)
    kind = np.full(len(mid), "trend", dtype=object)
    kind[regimes == "RANGE"] = "range"
    kind[regimes == "BREAKOUT"] = "breakout"
    return {
        "time": clean["time"],
        "time_ns": time_ns,
        "mid": mid,
        "high": high,
        "low": low,
        "spread": spread,
        "bid_open": bid_open,
        "ask_open": ask_open,
        "bid_high": clean["bid_high"].to_numpy(dtype=float),
        "bid_low": clean["bid_low"].to_numpy(dtype=float),
        "ask_high": clean["ask_high"].to_numpy(dtype=float),
        "ask_low": clean["ask_low"].to_numpy(dtype=float),
        "bid_close": bid_close,
        "ask_close": ask_close,
        "regimes": regimes,
        "signals": signals,
        "kind": kind,
    }


def _run(market: dict, name: str, pip: float, allowed: np.ndarray, extra: float) -> dict:
    kind = market["kind"] if name == "selector" else name
    direction = market["signals"]["selector"] if name == "selector" else market["signals"][name]
    result = simulate(
        direction,
        kind,
        time_ns=market["time_ns"],
        bid_open=market["bid_open"],
        ask_open=market["ask_open"],
        bid_high=market["bid_high"],
        bid_low=market["bid_low"],
        ask_high=market["ask_high"],
        ask_low=market["ask_low"],
        bid_close=market["bid_close"],
        ask_close=market["ask_close"],
        spread=market["spread"],
        atr=market["signals"]["atr"],
        support=market["signals"]["prior_low"],
        resistance=market["signals"]["prior_high"],
        pip=pip,
        extra_pips_per_side=extra,
        allowed=allowed,
    )
    summary = summarise(result["returns"], ambiguous=result["ambiguous"])
    summary["rejected"] = result["rejected"]
    summary["outcomes"] = result["outcomes"]
    summary["excluded"] = result["excluded"]
    return summary


def _mask(times: pd.Series, start: pd.Timestamp | None, end: pd.Timestamp | None) -> np.ndarray:
    ok = np.ones(len(times), dtype=bool)
    if start is not None:
        ok &= times >= start
    if end is not None:
        horizon = pd.Timedelta(seconds=(HOLD_BARS + 1) * 300)
        ok &= (times < end) & (times + horizon < end)
    return ok


def _regime_summary(labels: np.ndarray) -> dict:
    counts = {name: int((labels == name).sum()) for name in ("TREND", "RANGE", "BREAKOUT", "UNCERTAIN")}
    runs = {name: 0 for name in counts}
    if len(labels):
        current = labels[0]
        length = 1
        lengths = {name: [] for name in counts}
        for label in labels[1:]:
            if label == current:
                length += 1
            else:
                lengths[current].append(length)
                runs[current] += 1
                current = label
                length = 1
        lengths[current].append(length)
        runs[current] += 1
        average = {name: None if not values else float(np.mean(values)) for name, values in lengths.items()}
    else:
        average = {name: None for name in counts}
    return {"counts": counts, "runs": runs, "average_run_bars": average, "changes": int(sum(runs.values()) - (1 if len(labels) else 0))}


def main() -> None:
    _dump("03_protocol.json", {"sha256": PROTOCOL_SHA256, "protocol": PROTOCOL})
    if promotion_allowed():
        raise SystemExit("R39_PROMOTION_BLOCKED")
    history = ROOT / "data" / "historical"
    hashes = {}
    clean = {}
    for name, expected in DATASET_SHA256.items():
        digest = file_sha256(history / f"{name}_M5.csv")
        hashes[name] = digest
        if digest != expected:
            raise SystemExit("R39_DATASET_HASH_MISMATCH")
        frame, quality = validate_frame(pd.read_csv(history / f"{name}_M5.csv"))
        if quality["duplicate_timestamps"] or quality["out_of_order_steps"] or quality["negative_spread_rows"]:
            raise SystemExit(f"R39_DATA_QUALITY_{name}")
        clean[name] = frame
    _dump("02_dataset_hashes.json", hashes)
    eur = clean["EUR_USD"]
    leak = {
        "prefix_invariant": prefix_matches(causal_features, eur, 1000),
        "leaky_fixture_rejected": not prefix_matches(leaky_future_return, eur.iloc[:80].copy(), 40),
    }
    _dump("07_leakage_controls.json", leak)
    if not leak["prefix_invariant"] or not leak["leaky_fixture_rejected"]:
        raise SystemExit("R39_LEAKAGE_CHECK_FAILED")
    comparison = {}
    confirmation_means = {name: {} for name in STREAMS}
    regime_rows = {}
    for instrument, frame in clean.items():
        market = _market(frame)
        pip = PIP_SIZE[instrument]
        design = _mask(market["time"], None, TRAIN_END)
        confirm = _mask(market["time"], CONFIRM_START, None)
        regime_rows[instrument] = _regime_summary(market["regimes"][confirm])
        comparison[instrument] = {}
        for stream in STREAMS:
            comparison[instrument][stream] = {
                "design": _run(market, stream, pip, design, 0.0),
                "confirmation": _run(market, stream, pip, confirm, 0.0),
                "confirmation_half_pip": _run(market, stream, pip, confirm, 0.5),
                "confirmation_one_pip": _run(market, stream, pip, confirm, 1.0),
            }
            confirmation_means[stream][instrument] = comparison[instrument][stream]["confirmation"]["mean"]
    decisions = {}
    for stream in STREAMS:
        eur_row = comparison["EUR_USD"][stream]
        others = [confirmation_means[stream][name] for name in DATASET_SHA256 if name != "EUR_USD" and confirmation_means[stream][name] is not None]
        passed = merits(eur_row["confirmation"], eur_row["confirmation_half_pip"], others)
        decisions[stream] = {"merits_further_validation": passed, "production_authorised": False}
    _dump("10_strategy_comparison.json", {"instruments": comparison, "decisions": decisions, "always_abstain_mean": 0.0})
    _dump("09_regime_distribution.json", regime_rows)
    labels = _market(clean["EUR_USD"])["regimes"]
    _dump(
        "16_journal.json",
        {
            "provenance_sha256": hashlib.sha256("|".join(labels.tolist()).encode("utf-8")).hexdigest(),
            "note": "A losing trade is recorded as a stop, timeout, or ambiguous bar. It is not recorded as proof that the regime label was false.",
            "eur_confirmation_outcomes": {stream: comparison["EUR_USD"][stream]["confirmation"]["outcomes"] for stream in STREAMS},
            "eur_confirmation_rejections": {stream: comparison["EUR_USD"][stream]["confirmation"]["rejected"] for stream in STREAMS},
            "eur_confirmation_excluded": {stream: comparison["EUR_USD"][stream]["confirmation"]["excluded"] for stream in STREAMS},
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
            "protocol_sha256": PROTOCOL_SHA256,
            "any_strategy_merits_validation": any(row["merits_further_validation"] for row in decisions.values()),
            "production_authorised": False,
        },
    )
    print(json.dumps({"protocol": PROTOCOL_SHA256, "merits": {key: value["merits_further_validation"] for key, value in decisions.items()}}))


if __name__ == "__main__":
    main()
