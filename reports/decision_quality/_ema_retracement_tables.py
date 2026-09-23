"""Print compact tables from the EMA retracement JSON (research-only)."""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path(__file__).resolve().parent / "_ema_retracement_results.json"
HOR = ("5m", "15m", "30m", "60m", "120m", "240m")
SPLITS = ("overall", "train", "valid", "test")


def f(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x != x:
        return "n/a"
    if isinstance(x, float) and abs(x) == float("inf"):
        return "inf"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def econ_row(name, e):
    return (
        f"{name:32} {e.get('n'):6} {e.get('buy'):5} {e.get('sell'):5} "
        f"{f(e.get('win_rate'), 3):>7} {f(e.get('expectancy_r')):>9} "
        f"{f(e.get('profit_factor')):>8} {f(e.get('total_r'), 1):>10} "
        f"{f(e.get('avg_hold_min'), 1):>8}"
    )


def fwd_row(name, part):
    cells = [f"{name:32}"]
    cells.append(f"{(part or {}).get('event_n', 0):6}")
    for h in HOR:
        m = (part or {}).get(h) or {}
        cells.append(f"{f(m.get('mean'), 3):>8}")
    return " ".join(cells)


def main() -> None:
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    print("CUTS", payload.get("cuts"))
    print("SMA_PERIODS", payload.get("sma_periods"))
    print("BOOK", payload.get("book_coverage"))
    print()
    print("=== ECONOMIC overall / train / valid / test ===")
    print(
        f"{'config':32} {'n':>6} {'buy':>5} {'sell':>5} "
        f"{'wr':>7} {'expR':>9} {'pf':>8} {'totR':>10} {'holdm':>8}"
    )
    for cfg in payload["configs"]:
        e = cfg["economic"]
        print("---", cfg["name"], cfg["family"], cfg["params"])
        for split in SPLITS:
            print(econ_row(f"  {split}", e[split]))
        print(econ_row("  BUY", e["buy"]))
        print(econ_row("  SELL", e["sell"]))
        print("  symbols:")
        for sym, st in e["symbol"].items():
            print(econ_row(f"    {sym}", st))
        print()

    print("=== FORWARD mid-to-mid pips (mean) ===")
    hdr = f"{'config/split':32} {'n':>6} " + " ".join(f"{h:>8}" for h in HOR)
    print(hdr)
    for cfg in payload["configs"]:
        print("---", cfg["name"])
        ov = cfg["forward"]["overall"]
        for split in ("all", "train", "valid", "test"):
            print(fwd_row(f"  {split}", ov.get(split)))
        print("  symbols (all bars):")
        for sym, part in cfg["forward"]["symbol"].items():
            print(fwd_row(f"    {sym}", part))
        print()


if __name__ == "__main__":
    main()
