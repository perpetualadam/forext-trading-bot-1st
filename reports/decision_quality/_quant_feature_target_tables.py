"""Extract discovery findings without dumping the whole JSON."""

from __future__ import annotations

import json
from pathlib import Path

d = json.loads(Path("reports/decision_quality/quant_feature_target_discovery_data.json").read_text(encoding="utf-8"))

print("N", d.get("n_rows"), "splits", d["stage2"])
print("integrity total", d["stage1"]["total_rows"])
for s in d["stage1"]["symbols"]:
    print(s["symbol"], s["rows"], s["earliest"], s["latest"], "dups", s["duplicates"], "gaps", s["gaps"], "inc", s["incomplete_flagged"])

print("\nNEAR CONST", d["stage6"]["near_constant"])
print("REDUNDANT DROP", d["stage7"]["redundant_drop_suggestions"])
print("REDUNDANT PAIRS", len(d["stage7"]["pairs_ge_0_90"]))
for p in d["stage7"]["pairs_ge_0_90"][:20]:
    print(" ", p)

print("\n=== SIGN HIT 60m ===")
for col, body in d["stage9"].items():
    tr = body["train"].get("sign_hit_60m")
    va = body["valid"].get("sign_hit_60m")
    te = body["discovery_test"].get("sign_hit_60m")
    print(col, "train", tr, "valid", va, "test", te, "sym", body["by_symbol"])

print("\n=== QUINTILES 60m train/valid/test for key feats ===")
for col in ("ret_1", "ret_6", "ret_12", "sma5_20_diff_atr", "sma_state", "dist_sma20_atr", "pos_in_range_24", "h1_ret", "atr_pctile", "rv_ratio"):
    print(col)
    for split in ("train", "valid", "discovery_test"):
        qs = []
        for q in ("q1", "q2", "q3", "q4", "q5"):
            h = d["stage8"][col]["splits"][split][q]["60"]
            qs.append(f"{q}:{h['n']}/{h['mean']:.3f}/{100*h['pct_pos']:.1f}%")
        print(" ", split, " | ".join(qs))

print("\n=== QUOTE VS BASE ===")
print(d["stage10_12"]["quote_vs_base"])

print("\n=== MONTHLY ret_1 / sma ===")
for col in ("ret_1", "sma5_20_diff_atr", "sma_state"):
    print(col)
    for k, v in d["stage10_12"]["monthly"][col].items():
        print(" ", k, v["n"], v["sign_hit_60m"])

print("\n=== DEP ===")
print(json.dumps(d["stage13"], indent=2)[:4000])

print("\n=== BASELINES ===")
for name, splits in d["stage14"]["baselines"].items():
    print(name)
    for sp, sc in splits.items():
        print(" ", sp, sc)

print("\n=== LOGREG ===")
print({k: v for k, v in d["stage14"]["logreg"].items() if k != "features"})

print("\n=== ABLATION ===")
print(d["stage15"])

print("\n=== COST ===")
print(d["stage16"])
