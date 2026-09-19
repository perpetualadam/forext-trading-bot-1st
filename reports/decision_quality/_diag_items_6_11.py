"""Items 6-11 from persisted trades only. No signal replay."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact
from forex_bot.decision_quality.outcomes import summarize_closed
from forex_bot.decision_quality.walk_forward import chronological_splits
from forex_bot.trading import simulated_half_spread
from forex_bot.profit_protection import pip_size

print("START", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
ck = load_json(Path("reports/decision_quality/baseline_checkpoint.json"))
all_t = []
by_sym = {}
for sym in BASELINE_SYMBOLS:
    trades = load_result_artifact(Path(ck["units"][f"{sym}|baseline"]["result_path"])).trades
    by_sym[sym] = trades
    all_t.extend(trades)
splits = chronological_splits(all_t)


def med(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else float(np.median(xs))


def row(label, trades):
    s = summarize_closed(trades)
    fwd60 = [t.forward.get("60m_pips") for t in trades if t.forward.get("60m_pips") is not None]
    print(
        f"{label}\tn={s['trade_count']}\texp={s['expectancy_r']}\tpf={s['profit_factor']}\t"
        f"wr={s['win_rate']}\ttot={s['total_r']}\t"
        f"buy={sum(1 for t in trades if t.snapshot.side=='BUY')}\t"
        f"sell={sum(1 for t in trades if t.snapshot.side=='SELL')}\t"
        f"medMFE={med([t.mfe_r for t in trades])}\tmedMAE={med([t.mae_r for t in trades])}\t"
        f"fwd60_mean={float(np.mean(fwd60)) if fwd60 else None}\t"
        f"fwd60_pctpos={float(np.mean([x>0 for x in fwd60])) if fwd60 else None}"
    )


print("=== ITEM6 pre_move_atr ===")
pm = [t.snapshot.pre_move_atr for t in all_t if t.snapshot.pre_move_atr is not None]
print("pre_move n", len(pm), "missing", sum(1 for t in all_t if t.snapshot.pre_move_atr is None))
a = np.asarray(pm, dtype=float)
print("pre_move p10/p25/med/p75/p90", np.percentile(a, [10, 25, 50, 75, 90]), "mean", a.mean())


def bucket_pre(t):
    x = t.snapshot.pre_move_atr
    if x is None:
        return "unknown"
    if x < 0.5:
        return "small_<0.5"
    if x < 1.5:
        return "moderate_0.5_1.5"
    return "large_>=1.5"  # existing possible_late_entry threshold


for b in ("small_<0.5", "moderate_0.5_1.5", "large_>=1.5", "unknown"):
    row(f"PRE {b}", [t for t in all_t if bucket_pre(t) == b])
for part in ("train", "valid", "test"):
    for b in ("small_<0.5", "moderate_0.5_1.5", "large_>=1.5"):
        row(f"{part} PRE {b}", [t for t in splits[part] if bucket_pre(t) == b])

losers = [t for t in all_t if t.realised_r is not None and t.realised_r <= 0]
print("loser_pre_med", med([t.snapshot.pre_move_atr for t in losers]))
print("winner_pre_med", med([t.snapshot.pre_move_atr for t in all_t if t.realised_r and t.realised_r > 0]))

print("=== ITEM7 strategy ===")
labels = sorted({t.snapshot.strategy or "unknown" for t in all_t})
for lab in labels:
    row(f"STRAT {lab}", [t for t in all_t if (t.snapshot.strategy or "unknown") == lab])
for lab in labels:
    for part in ("train", "valid", "test"):
        row(f"{part} STRAT {lab}", [t for t in splits[part] if (t.snapshot.strategy or "unknown") == lab])
for lab in labels:
    for sym in BASELINE_SYMBOLS:
        row(f"{sym} STRAT {lab}", [t for t in by_sym[sym] if (t.snapshot.strategy or "unknown") == lab])

print("=== ITEM8 HTF ===")


def h1_class(t):
    a = t.snapshot.htf_agreement or ""
    if "aligned_h1" in a:
        return "h1_aligned"
    if "against_h1" in a:
        return "h1_against"
    return "h1_uncertain"


def h4_class(t):
    a = t.snapshot.htf_agreement or ""
    if "aligned_h4" in a:
        return "h4_aligned"
    if "against_h4" in a:
        return "h4_against"
    return "h4_uncertain"


for fn, name in ((h1_class, "H1"), (h4_class, "H4")):
    for g in sorted({fn(t) for t in all_t}):
        row(f"{name} {g}", [t for t in all_t if fn(t) == g])
    for part in ("train", "valid", "test"):
        for g in sorted({fn(t) for t in all_t}):
            row(f"{part} {name} {g}", [t for t in splits[part] if fn(t) == g])

print("=== ITEM9 regime ===")
regs = sorted({t.snapshot.regime or "unknown" for t in all_t})
for r in regs:
    row(f"REG {r}", [t for t in all_t if (t.snapshot.regime or "unknown") == r])
for r in regs:
    for part in ("train", "valid", "test"):
        row(f"{part} REG {r}", [t for t in splits[part] if (t.snapshot.regime or "unknown") == r])
for r in regs:
    for sym in BASELINE_SYMBOLS:
        row(f"{sym} REG {r}", [t for t in by_sym[sym] if (t.snapshot.regime or "unknown") == r])

print("=== ITEM10 session / hour ===")
sess = sorted({t.snapshot.session or "unknown" for t in all_t})
for sname in sess:
    row(f"SES {sname}", [t for t in all_t if (t.snapshot.session or "unknown") == sname])
for sname in sess:
    for part in ("train", "valid", "test"):
        row(f"{part} SES {sname}", [t for t in splits[part] if (t.snapshot.session or "unknown") == sname])
print("hour_utc (descriptive, not optimized)")
for h in range(24):
    subset = [t for t in all_t if t.snapshot.hour_utc == h]
    if subset:
        row(f"HOUR_UTC {h:02d}", subset)

print("=== ITEM11 cost ===")
spreads_pips = [t.snapshot.spread_pips for t in all_t if t.snapshot.spread_pips is not None]
spreads_r = []
for t in all_t:
    if t.snapshot.spread_pips is not None and t.sl_distance_pips:
        spreads_r.append(t.snapshot.spread_pips / t.sl_distance_pips)
print("spread_pips n", len(spreads_pips), "mean", float(np.mean(spreads_pips)), "med", float(np.median(spreads_pips)))
print("entry_half_spread_as_R n", len(spreads_r), "mean", float(np.mean(spreads_r)), "med", float(np.median(spreads_r)))
print("total_entry_spread_R", float(np.sum(spreads_r)))
# reconstruct mid from entry: BUY entry = mid+half, SELL entry = mid-half
# realized from mid would add back the half-spread in price
gross_r = []
for t in all_t:
    if t.realised_r is None or t.sl_distance_pips <= 0:
        continue
    # entry paid half-spread; exit is SL/TP/mid close — no exit spread in baseline
    if t.snapshot.spread_pips is None:
        continue
    gross_r.append(t.realised_r + (t.snapshot.spread_pips / t.sl_distance_pips))
print("after_cost_exp", summarize_closed(all_t)["expectancy_r"])
print("before_entry_cost_approx_exp", float(np.mean(gross_r)) if gross_r else None, "n", len(gross_r))
print("half_spread_functions")
for sym in BASELINE_SYMBOLS:
    half = simulated_half_spread(sym)
    print(sym, "half_price", half, "half_pips", half / pip_size(sym))
print("END", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
