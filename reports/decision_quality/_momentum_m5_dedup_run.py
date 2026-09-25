"""Run the frozen momentum x one-M5 2x2. Research only. No OANDA. No production writes."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.history_cache import last_completed_bar_start
from forex_bot.decision_quality.momentum_m5_dedup import (
    MOM_THR,
    TRAIN_LE,
    VALID_LE,
    aligned_stub_allow,
    candle_key,
    last_completed_m5_key,
    run_experiment,
)
from forex_bot.decision_quality.stub_components import current_stub_allow

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "decision_quality" / "_momentum_m5_dedup_results.json"
LIVE = ROOT / "reports" / "decision_quality" / "_live_trade_failure_analysis.json"
SHADOW = ROOT / "data" / "research" / "v2_shadow" / "observations.jsonl"


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        x = float(obj)
        return None if not math.isfinite(x) else round(x, 6)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if obj is None:
        return None
    return obj


def live_cross_check() -> dict:
    if not LIVE.exists():
        return {"available": False}
    payload = json.loads(LIVE.read_text(encoding="utf-8"))
    trades = [
        t
        for t in payload.get("trades") or []
        if t.get("exit_class") in ("BROKER_STOP_LOSS", "BROKER_TAKE_PROFIT", "BOT_PROFIT_PROTECTION")
    ]
    a0 = []
    a1 = []
    keys: dict[tuple[str, str], list[int]] = {}
    for t in trades:
        pre5 = (t.get("pre_move_pips") or {}).get("5")
        try:
            pre5 = float(pre5) if pre5 is not None else None
        except (TypeError, ValueError):
            pre5 = None
        # Descriptive A1: last-M5 move in trade direction (same proxy as first-5m audit).
        aligned = pre5 is not None and pre5 > 0
        t = dict(t)
        t["live_aligned"] = aligned
        a0.append(t)
        if aligned:
            a1.append(t)
        entry = t.get("entry_ts")
        if entry:
            key = last_completed_m5_key(str(t.get("symbol")), entry)
            keys.setdefault((key[0], str(key[1])), []).append(int(t["id"]))

    suppressed = []
    for key, ids in keys.items():
        if len(ids) > 1:
            for extra in ids[1:]:
                suppressed.append({"key": key, "id": extra, "first_id": ids[0]})

    def block(rows: list[dict]) -> dict:
        rs = [float(r["realised_r"]) for r in rows if r.get("realised_r") is not None]
        if not rs:
            return {"n": len(rows)}
        wins = [x for x in rs if x > 0]
        losses = [x for x in rs if x < 0]
        gl = abs(sum(losses))
        hits = []
        for r in rows:
            dc = (r.get("dir_correct") or {}).get("5")
            if dc is not None:
                hits.append(1.0 if dc else 0.0)
        return {
            "n": len(rows),
            "win_rate": len(wins) / len(rs),
            "mean_r": sum(rs) / len(rs),
            "profit_factor": (sum(wins) / gl) if gl else None,
            "sum_r": sum(rs),
            "fwd5_hit": (sum(hits) / len(hits)) if hits else None,
        }

    b1_kept = [t for t in trades if t["id"] not in {s["id"] for s in suppressed}]
    return {
        "label": "LIVE DESCRIPTIVE CROSS-CHECK — NOT TRAINING DATA",
        "available": True,
        "note": "A1 uses signed pre-entry 5m executable move > 0 as the live proxy; ret_1 is not stored on live rows. Exact 0.0001 threshold cannot be applied to live.",
        "A0": block(a0),
        "A1": block(a1),
        "B1_suppressed_same_candle": suppressed,
        "B1_counterfactual_kept": block(b1_kept),
        "A1B1_kept": block([t for t in a1 if t["id"] not in {s["id"] for s in suppressed}]),
    }


def v2_forward() -> dict:
    if not SHADOW.exists():
        return {"status": "INSUFFICIENT DATA", "n": 0}
    n = 0
    a0 = 0
    a1 = 0
    first = None
    last = None
    with SHADOW.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n += 1
            ts = rec.get("timestamp_utc")
            if first is None:
                first = ts
            last = ts
            inputs = rec.get("inputs") or {}
            side = str((inputs.get("production_stub_side") or {}).get("value") or "").upper()
            ret = (inputs.get("ret_1") or {}).get("value")
            atr = (inputs.get("atr") or {}).get("value")
            try:
                ret_f = float(ret) if ret is not None else float("nan")
                atr_f = float(atr) if atr is not None else float("nan")
            except (TypeError, ValueError):
                continue
            state = 1 if side == "BUY" else (-1 if side == "SELL" else 0)
            if current_stub_allow(np.array([state]), np.array([ret_f]), np.array([atr_f]))[0]:
                a0 += 1
            if aligned_stub_allow(np.array([state]), np.array([ret_f]), np.array([atr_f]))[0]:
                a1 += 1
    if n < 50:
        return {"status": "INSUFFICIENT DATA", "n": n}
    return {
        "status": "OBSERVATION ONLY — no fills / no economic outcomes",
        "n": n,
        "first": first,
        "last": last,
        "a0_eligible": a0,
        "a1_eligible": a1,
        "a1_retention_vs_a0": (a1 / a0) if a0 else None,
        "note": "V2 proposed_action is SKIP; not combined with historical results.",
    }


def main() -> None:
    result = run_experiment()
    result["live_cross_check"] = live_cross_check() if not result.get("stop") else {"skipped": True}
    result["v2_forward"] = v2_forward()
    result["momentum_threshold"] = MOM_THR
    OUT.write_text(json.dumps(_jsonable(result), indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("baseline", result.get("baseline_reproduction"), result.get("baseline"))
    if result.get("stop"):
        print("STOPPED — baseline reproduction failed")
        return
    for name in ("A0B0", "A1B0", "A0B1", "A1B1"):
        ov = result["cells"][name]["overall"]
        print(
            name,
            "n",
            ov.get("n"),
            "wr",
            ov.get("win_rate"),
            "exp",
            ov.get("expectancy_r"),
            "pf",
            ov.get("profit_factor"),
        )
    print("class", result.get("classification"))
    print("retention events", result.get("candidate_events"))
    print("reentry", result.get("same_candle_reentry"))


if __name__ == "__main__":
    main()
