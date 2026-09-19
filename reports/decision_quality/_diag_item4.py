from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact

print("ITEM4_START", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
ck = load_json(Path("reports/decision_quality/baseline_checkpoint.json"))
all_t = []
by_sym = {}
for sym in BASELINE_SYMBOLS:
    trades = load_result_artifact(Path(ck["units"][f"{sym}|baseline"]["result_path"])).trades
    by_sym[sym] = trades
    all_t.extend(trades)


def qstats(vals):
    a = np.asarray([v for v in vals if v is not None], dtype=float)
    if len(a) == 0:
        return None
    return {k: float(np.percentile(a, p)) for k, p in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))} | {
        "n": int(len(a)),
        "mean": float(a.mean()),
    }


def dump(label, trades):
    print(f"## {label} n={len(trades)}")
    for name, getter in (
        ("mfe_pips", lambda t: t.mfe_pips),
        ("mae_pips", lambda t: t.mae_pips),
        ("mfe_r", lambda t: t.mfe_r),
        ("mae_r", lambda t: t.mae_r),
        ("mfe_atr", lambda t: t.mfe_atr),
        ("mae_atr", lambda t: t.mae_atr),
        ("sl_over_atr", lambda t: t.sl_over_atr),
        ("max_tp_progress", lambda t: t.max_tp_progress),
    ):
        s = qstats([getter(t) for t in trades])
        print(name, s)


dump("ALL", all_t)
dump("WINNERS", [t for t in all_t if t.realised_r is not None and t.realised_r > 0])
dump("LOSERS", [t for t in all_t if t.realised_r is not None and t.realised_r <= 0])
for side in ("BUY", "SELL"):
    dump(side, [t for t in all_t if t.snapshot.side == side])
for sym in BASELINE_SYMBOLS:
    dump(sym, by_sym[sym])

losers = [t for t in all_t if t.realised_r is not None and t.realised_r <= 0]
winners = [t for t in all_t if t.realised_r is not None and t.realised_r > 0]
print("losers_mfe_r_ge_0.5", sum(1 for t in losers if (t.mfe_r or 0) >= 0.5), "of", len(losers))
print("losers_mfe_r_ge_1.0", sum(1 for t in losers if (t.mfe_r or 0) >= 1.0), "of", len(losers))
print("losers_mfe_pips_eq_0", sum(1 for t in losers if (t.mfe_pips or 0) == 0), "of", len(losers))
print("winners_mae_r_ge_0.5", sum(1 for t in winners if (t.mae_r or 0) >= 0.5), "of", len(winners))
print("winners_mae_r_ge_1.0", sum(1 for t in winners if (t.mae_r or 0) >= 1.0), "of", len(winners))
print("all_mae_r_ge_0.9", sum(1 for t in all_t if (t.mae_r or 0) >= 0.9), "of", len(all_t))
print("ITEM4_END", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
