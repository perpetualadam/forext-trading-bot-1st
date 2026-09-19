from datetime import datetime, timezone
from pathlib import Path
import statistics as st

from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact
from forex_bot.decision_quality.outcomes import summarize_closed
from forex_bot.decision_quality.walk_forward import chronological_splits

print("ITEM2_START", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
ck = load_json(Path("reports/decision_quality/baseline_checkpoint.json"))
all_t = []
by_sym = {}
for sym in BASELINE_SYMBOLS:
    r = load_result_artifact(Path(ck["units"][f"{sym}|baseline"]["result_path"]))
    by_sym[sym] = r.trades
    all_t.extend(r.trades)


def med(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else float(st.median(xs))


def row(label, trades):
    s = summarize_closed(trades)
    print(
        label,
        s["trade_count"],
        s["win_rate"],
        s["expectancy_r"],
        s["profit_factor"],
        s["total_r"],
        s["median_r"],
        med([t.mfe_r for t in trades]),
        med([t.mae_r for t in trades]),
        sep="\t",
    )


print("=== OVERALL SIDE ===")
for side in ("BUY", "SELL"):
    row(side, [t for t in all_t if t.snapshot.side == side])
print("=== PER SYMBOL SIDE ===")
for sym in BASELINE_SYMBOLS:
    for side in ("BUY", "SELL"):
        row(f"{sym} {side}", [t for t in by_sym[sym] if t.snapshot.side == side])
print("=== CHRONO SIDE ===")
splits = chronological_splits(all_t)
for part in ("train", "valid", "test"):
    for side in ("BUY", "SELL"):
        row(f"{part} {side}", [t for t in splits[part] if t.snapshot.side == side])
print("ITEM2_END", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
