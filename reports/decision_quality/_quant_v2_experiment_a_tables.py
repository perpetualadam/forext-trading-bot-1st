"""Print Experiment A tables from persisted JSON."""

from __future__ import annotations

import json
from pathlib import Path

d = json.loads(Path("reports/decision_quality/quant_v2_experiment_a_data.json").read_text(encoding="utf-8"))

print("=== STAGE3/4 half-spread vs modeled ===")
for s, rec in d["stage4"]["comparison"].items():
    h = rec["half_close_pips"]
    print(
        f"{s:8} n={h['n']} miss={h['missing']} zero={h['zero']} neg={h['negative']} "
        f"mean={h['mean']:.3f} med={h['median']:.3f} p10={h['p10']:.3f} p90={h['p90']:.3f} p99={h['p99']:.3f} "
        f"max={h['maximum']:.3f} modeled={rec['modeled_half_pips']:.2f} "
        f"med-model={rec['median_half_minus_modeled']:.3f} mean-model={rec['mean_half_minus_modeled']:.3f}"
    )
print("invalid", d["stage3"]["invalid_full_close"])
print("split half", d["stage3"]["by_split_half_pips"])
print("month half med", d["stage3"]["by_month_half_median"])

print("\n=== VOLUME ===")
for s, rec in d["stage5"]["by_symbol"].items():
    print(s, rec)

print("\n=== FROZEN EDGES ===")
print(d["frozen_edges"])

print("\n=== SPREAD Q TRADEABILITY 60m ===")
for q, e in d["stage8_spread_tradeability"].items():
    h = e["h60"]
    print(q, "n", e["n"], h)

print("\n=== VOL REL Q 60m ===")
for q, e in d["stage9_activity_magnitude"]["session_relative"].items():
    print(q, "n", e["n"], e["h60"])

print("\n=== RAW VOL Q 60m ===")
for q, e in d["stage9_activity_magnitude"]["raw_volume"].items():
    print(q, "n", e["n"], e["h60"])

print("\n=== 2D ===")
for k, e in d["stage14_2d"].items():
    if k == "definitions":
        continue
    print(k, "n", e["n"], e.get("h60"), "splits", e.get("h60_by_split"))

print("\n=== SPREAD EVENTS ===")
for k, e in d["stage12_spread_events"].items():
    print(k, e["n"], e["h60"], e["h60_by_split"])

print("\n=== VOL EVENTS ===")
for k, e in d["stage13_activity_events"].items():
    print(k, e["n"], e["h60"], e["h60_by_split"])

print("\n=== V1 EVENTS ===")
for k, e in d["stage15_v1_events_actual_cost"].items():
    print(k, e["n"], e["h60"])

print("\n=== RANGE BOTTOM SYMBOL ===")
print(d["stage16_range_bottom"]["h60_by_symbol"])
print("splits", d["stage16_range_bottom"]["h60_by_split"])

print("\n=== BREAKOUT ===")
print("up", d["stage17_breakouts"]["up"]["h60"], d["stage17_breakouts"]["up"]["h60_by_split"])
print("dn", d["stage17_breakouts"]["down"]["h60"])

print("\n=== TWO SIDED ===")
print("actual", d["stage18_two_sided"]["overall"])
print("modeled", d["stage18_two_sided"]["modeled_1pip_both_for_reference"])
print("by spread", d["stage18_two_sided"]["by_spread_q"])
print("amb", d["stage18_ambiguous"])

print("\n=== BOOT ===")
print(json.dumps(d["stage20_bootstrap"], indent=2)[:4000])

print("\n=== INDEP ===")
print(d["independence"])
