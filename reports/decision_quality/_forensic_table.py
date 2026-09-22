import json
from pathlib import Path

s = json.loads(Path(__file__).with_name("_forensic_summary.json").read_text(encoding="utf-8"))
lines = [
    "| trade | pair | side | entry UTC | exit UTC | hold s | fill | SL | TP | fillR | PL | OANDA | class | build |",
    "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|",
]
for tr in s["completed_trades"]:
    et = (tr.get("entry_time") or "")[:19]
    xt = (tr.get("exit_time") or "")[:19]
    hold = tr.get("hold_sec")
    hold_s = f"{hold:.0f}" if hold is not None else ""
    fr = tr.get("fill_r")
    fr_s = f"{fr:.2f}" if fr is not None else ""
    pl = tr.get("realized_pl")
    pl_s = f"{pl:.4f}" if pl is not None else ""
    sl = tr.get("submitted_sl")
    tp = tr.get("submitted_tp")
    lines.append(
        f"| {tr.get('trade_id')} | {tr.get('symbol')} | {tr.get('side')} | {et} | {xt} | {hold_s} | "
        f"{tr.get('entry_price')} | {sl} | {tp} | {fr_s} | {pl_s} | {tr.get('oanda_reason')} | "
        f"{tr.get('class')} | {tr.get('build')} |"
    )
Path(__file__).with_name("_forensic_close_table.md").write_text("\n".join(lines), encoding="utf-8")
print("rows", len(s["completed_trades"]))
