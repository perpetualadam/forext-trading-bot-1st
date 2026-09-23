"""Dump remaining configs to a text file."""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path(__file__).resolve().parent / "_ema_retracement_results.json"
OUT = Path(__file__).resolve().parent / "_ema_retracement_tables.txt"
HOR = ("5m", "15m", "30m", "60m", "120m", "240m")
WANT = (
    "baseline_sma_first_qual",
    "ema50_100_pull_resume",
    "ema50_200_pull_resume",
    "ema50_200_pull_only",
    "ema50_200_swing50_resume",
    "mean_reversion_ema50_z2",
)


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    lines: list[str] = []
    for cfg in d["configs"]:
        if cfg["name"] not in WANT:
            continue
        lines.append("=" * 80)
        lines.append(cfg["name"])
        e = cfg["economic"]
        for k in ("overall", "train", "valid", "test", "buy", "sell"):
            s = e[k]
            lines.append(
                f"  {k:8} n={s['n']} buy={s['buy']} sell={s['sell']} "
                f"wr={fmt(s['win_rate'], 3)} expR={fmt(s['expectancy_r'])} "
                f"pf={fmt(s['profit_factor'])} totR={fmt(s['total_r'], 1)} "
                f"holdm={fmt(s['avg_hold_min'], 1)}"
            )
        for sym, s in e["symbol"].items():
            lines.append(
                f"    {sym:8} n={s['n']} buy={s['buy']} sell={s['sell']} "
                f"wr={fmt(s['win_rate'], 3)} expR={fmt(s['expectancy_r'])} "
                f"pf={fmt(s['profit_factor'])} totR={fmt(s['total_r'], 1)} "
                f"holdm={fmt(s['avg_hold_min'], 1)}"
            )
        ov = cfg["forward"]["overall"]
        for split in ("all", "train", "valid", "test"):
            part = ov[split]
            cells = " ".join(f"{h}={fmt((part.get(h) or {}).get('mean'), 3)}" for h in HOR)
            lines.append(
                f"  FWD {split:6} n={part.get('event_n')} buy={part.get('buy')} "
                f"sell={part.get('sell')} {cells}"
            )
        lines.append("  FWD symbols:")
        for sym, part in cfg["forward"]["symbol"].items():
            cells = " ".join(f"{h}={fmt((part.get(h) or {}).get('mean'), 3)}" for h in HOR)
            lines.append(f"    {sym:8} n={part.get('event_n')} {cells}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
