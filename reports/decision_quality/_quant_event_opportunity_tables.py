"""Print compact event-study tables from the persisted JSON."""

from __future__ import annotations

import json
from pathlib import Path

P = Path("reports/decision_quality/quant_event_opportunity_data.json")
d = json.loads(P.read_text(encoding="utf-8"))
ev = d["events"]

print("=== SPLITS ===")
print(d["stage2"])
print("=== COST ===")
print(d["stage3"]["cost_is_entry_half_spread_pips"])
print("=== AMBIGUOUS ===")
print(d["stage4_6"]["ambiguous_rate_cost1"])
print("=== OPP BALANCE ===")
print(json.dumps(d["stage4_6"]["opportunity_balance"], indent=2))

print("\n=== EVENT 60m SUMMARY ===")
print(f"{'event':40} {'n':>7} {'tr':>6} {'va':>6} {'te':>6} {'cls':>8} {'up%':>6} {'mfeU':>7} {'mfeD':>7} {'h1':>5} {'h2':>5}")
for name, e in ev.items():
    h = e["horizons"].get("60", {})
    sp = e["by_split"]
    print(
        f"{name:40} {e['event_n']:7d} {sp.get('train',0):6d} {sp.get('valid',0):6d} {sp.get('discovery_test',0):6d} "
        f"{(h.get('mean_close_pips') or 0):+8.3f} {(h.get('pct_close_up') or 0)*100:5.1f} "
        f"{(h.get('mean_mfe_up') or 0):7.2f} {(h.get('mean_mfe_down') or 0):7.2f} "
        f"{(h.get('hurdle',{}).get('1.0') or 0)*100:5.1f} {(h.get('hurdle',{}).get('2.0') or 0)*100:5.1f}"
    )

print("\n=== PATH ORDER 60m cost1 ===")
for name, e in ev.items():
    po = e["horizons"].get("60", {}).get("order_cost1_60m", {})
    print(f"{name:40} {po}")

print("\n=== SPLIT 60m close ===")
for name in (
    "range_bottom_enter",
    "range_top_enter",
    "extend_down_enter",
    "extend_up_enter",
    "impulse_bull_enter",
    "impulse_bear_enter",
    "vol_expand_enter",
    "breakout_up_24",
    "breakout_dn_24",
    "reject_upper_24",
    "reject_lower_24",
    "asia_to_london",
    "london_to_overlap",
    "overlap_to_late_ny",
    "usd_div_extreme_pos",
    "usd_div_extreme_neg",
    "range_bottom_and_lower_reject",
    "breakout_up_24_and_vol_expand",
):
    e = ev[name]
    print(name, e["h60_by_split"])

print("\n=== SYMBOL 60m ===")
for name in (
    "range_bottom_enter",
    "range_top_enter",
    "breakout_up_24",
    "vol_expand_enter",
    "impulse_bull_enter",
    "reject_lower_24",
    "usd_div_extreme_pos",
):
    print(name, ev[name]["h60_by_symbol"])

print("\n=== HORIZONS range_bottom ===")
for hz, h in ev["range_bottom_enter"]["horizons"].items():
    print(hz, {k: h[k] for k in ("n", "mean_close_pips", "pct_close_up", "mean_mfe_up", "mean_mfe_down")})

print("\n=== HORIZONS vol_expand ===")
for hz, h in ev["vol_expand_enter"]["horizons"].items():
    print(hz, {k: h[k] for k in ("n", "mean_close_pips", "pct_close_up", "mean_abs_exc", "mean_mfe_up", "mean_mfe_down")})

print("\n=== BOOT ===")
print(json.dumps(d["bootstrap"], indent=2))

print("\n=== MONTH range_bottom ===")
print(ev["range_bottom_enter"]["h60_by_month"])
print("=== MONTH breakout_up_24 ===")
print(ev["breakout_up_24"]["h60_by_month"])
print("=== MONTH vol_expand ===")
print(ev["vol_expand_enter"]["h60_by_month"])
