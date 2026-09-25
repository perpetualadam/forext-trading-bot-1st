"""Append compact per-trade table to the diagnosis report. Research-only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
a = json.loads((ROOT / "_live_trade_failure_analysis.json").read_text(encoding="utf-8"))
trades = sorted(a["trades"], key=lambda t: (t["entry_ts"], t["id"] or 0))
lines = [
    "",
    "| id | symbol | side | strategy | entry UTC | exit UTC | class | hold min | SL pips | init R | MFE_R | MAE_R | exit R | bucket | USD |",
    "|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
]


def short(ts: str) -> str:
    return (ts or "")[:19].replace("T", " ")


for t in trades:
    hold = ""
    if t.get("hold_sec") is not None:
        hold = f"{t['hold_sec'] / 60:.1f}"
    sl = f"{t['sl_pips']:.2f}" if t.get("sl_pips") is not None else ""
    ir = f"{t['initial_r']:.1f}" if t.get("initial_r") is not None else ""
    mfe = f"{t['mfe_r']:.2f}" if t.get("mfe_r") is not None else ""
    mae = f"{t['mae_r']:.2f}" if t.get("mae_r") is not None else ""
    rr = f"{t['realised_r']:.2f}" if t.get("realised_r") is not None else ""
    buck = (t.get("mfe_bucket") or "")[:1] if t["exit_class"] == "BROKER_STOP_LOSS" else ""
    lines.append(
        f"| {t['id']} | {t['symbol']} | {t['side']} | {t['strategy']} | "
        f"{short(t['entry_ts'])} | {short(t['exit_ts'])} | {t['exit_class']} | "
        f"{hold} | {sl} | {ir} | {mfe} | {mae} | {rr} | {buck} | {t['usd_dir']} |"
    )

path = ROOT / "live_trade_failure_diagnosis.md"
with path.open("a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("appended", len(trades), "rows")
