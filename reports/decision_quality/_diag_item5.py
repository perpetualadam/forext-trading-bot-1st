from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact
from forex_bot.decision_quality.walk_forward import chronological_splits

print("ITEM5_START", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
ck = load_json(Path("reports/decision_quality/baseline_checkpoint.json"))
all_t = []
by_sym = {}
for sym in BASELINE_SYMBOLS:
    trades = load_result_artifact(Path(ck["units"][f"{sym}|baseline"]["result_path"])).trades
    by_sym[sym] = trades
    all_t.extend(trades)

STOPPED = {"sl", "ambiguous_sl_tp"}


def report(label, trades):
    stopped = [t for t in trades if t.exit_reason in STOPPED]
    n = len(stopped)
    if n == 0:
        print(label, "n=0")
        return
    def pct(key):
        return sum(1 for t in stopped if t.post_stop.get(key)) / n
    mins = [t.post_stop.get("minutes_to_original_tp") for t in stopped if t.post_stop.get("reached_original_tp") and t.post_stop.get("minutes_to_original_tp") is not None]
    print(
        label,
        "n", n,
        "pct_0.5R", pct("plus_0_5r"),
        "pct_1R", pct("plus_1r"),
        "pct_2R_or_TP", pct("plus_2r"),
        "pct_orig_TP", pct("reached_original_tp"),
        "pct_moved_dir", pct("moved_original_direction"),
    )
    if mins:
        a = np.asarray(mins, dtype=float)
        print(
            "  time_to_TP_min n", len(a),
            "p25", float(np.percentile(a, 25)),
            "med", float(np.median(a)),
            "p75", float(np.percentile(a, 75)),
            "p90", float(np.percentile(a, 90)),
        )
    for minutes in (5, 15, 30, 60):
        vals = [t.post_stop.get(f"{minutes}m_pips") for t in stopped]
        vals = [float(v) for v in vals if v is not None]
        if vals:
            a = np.asarray(vals)
            print(f"  post{minutes}m n={len(a)} mean={a.mean():.3f} med={np.median(a):.3f} pct_pos={(a>0).mean():.3f}")


report("OVERALL", all_t)
for side in ("BUY", "SELL"):
    report(side, [t for t in all_t if t.snapshot.side == side])
for sym in BASELINE_SYMBOLS:
    report(sym, by_sym[sym])
splits = chronological_splits(all_t)
for part in ("train", "valid", "test"):
    report(part, splits[part])
print("all_exit_reasons")
from collections import Counter
print(Counter(t.exit_reason for t in all_t))
print("ITEM5_END", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
