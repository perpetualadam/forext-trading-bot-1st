"""Print markdown tables from the component-study JSON."""

from __future__ import annotations

import json
from pathlib import Path

P = Path("reports/decision_quality/quant_stub_component_study_data.json")
d = json.loads(P.read_text(encoding="utf-8"))
HS = ("5m", "15m", "30m", "60m", "120m", "240m")
PARTS = ("train", "valid", "test")
SYMS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")


def cell(h):
    if not h or h.get("n", 0) == 0:
        return "n=0"
    return f"n={h['n']} mean={h['mean']:.4f} med={h['median']:.4f} %pos={100*h['pct_pos']:.2f}"


def row(name, g):
    bits = [name, str(g.get("raw_bar_n")), str(g.get("event_state_n"))]
    for hz in HS:
        h = g.get(hz) or {}
        bits.append(cell(h))
    print(" | ".join(bits))


print("CUTS", d["cuts"], "N", d["n_rows_after_warmup"], "episodes", d["episode_n"])
print("state_frac", d["state_frac"], "stub_frac", d["stub_allow_frac"], "parity", d["stub_parity_mismatches"])
print()
print("=== GROUPS overall ===")
for name, g in d["groups"].items():
    row(name, g)

print()
print("=== INVERSE ===")
row("K_inverse", d["inverse_J"])

print()
print("=== AGE all-state ===")
for b, g in d["age"].items():
    row(b, g)

print()
print("=== AGE stub-allow ===")
for b, g in d["age_stub"].items():
    row(b, g)

print()
print("=== EPISODE LEVEL ===")
for name, g in d["episode_level"].items():
    row(name, g)

print()
print("=== KEY GROUPS by part 60m ===")
for name in (
    "A_sma_state",
    "B_first_crossover",
    "H_first_qual_after_cross",
    "J_current_exact_stub",
    "I_repeat_qualifying",
    "F_agree_and_stub_allow",
    "G_disagree_and_stub_allow",
):
    g = d["groups"][name]
    print(name)
    for part in PARTS:
        h = g[part]["60m"]
        print(f"  {part}: raw={g[part]['raw_bar_n']} ep={g[part]['event_state_n']} {cell(h)}")

print()
print("=== AGE 60m by part ===")
for b, g in d["age"].items():
    print(b, "overall", cell(g["60m"]))
    for part in PARTS:
        print(f"  {part}: raw={g[part]['raw_bar_n']} ep={g[part]['event_state_n']} {cell(g[part]['60m'])}")

print()
print("=== AGE stub 60m by part ===")
for b, g in d["age_stub"].items():
    print(b, cell(g["60m"]))
    for part in PARTS:
        print(f"  {part}: raw={g[part]['raw_bar_n']} ep={g[part]['event_state_n']} {cell(g[part]['60m'])}")

print()
print("=== AGREE/DISAGREE stub by symbol 60m ===")
for name in ("F_agree_and_stub_allow", "G_disagree_and_stub_allow", "J_current_exact_stub", "B_first_crossover"):
    print(name)
    g = d["groups"][name]
    for sym in SYMS:
        print(f"  {sym}: raw={g[sym]['raw_bar_n']} ep={g[sym]['event_state_n']} {cell(g[sym]['60m'])}")

print()
print("=== four-way stub 60m by part ===")
for name in ("buy_mom_pos_stub", "buy_mom_neg_stub", "sell_mom_neg_stub", "sell_mom_pos_stub"):
    g = d["groups"][name]
    print(name, "all", cell(g["60m"]))
    for part in PARTS:
        print(f"  {part}: raw={g[part]['raw_bar_n']} ep={g[part]['event_state_n']} {cell(g[part]['60m'])}")

print()
print("=== swing200 ===")
print(d.get("swing200"))
