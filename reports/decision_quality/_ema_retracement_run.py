"""Run the research-only EMA retracement experiment. No OANDA, no production edits."""

from __future__ import annotations

import json
from pathlib import Path

from forex_bot.decision_quality.ema_retracement import _jsonable, run_experiment

OUT = Path(__file__).resolve().parent / "_ema_retracement_results.json"


def main() -> None:
    payload = _jsonable(run_experiment())
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT.name} configs={len(payload.get('configs') or [])}")
    print("cuts", payload.get("cuts"))
    for cfg in payload.get("configs") or []:
        e = cfg.get("economic") or {}
        ov = e.get("overall") or {}
        te = e.get("test") or {}
        fw = ((cfg.get("forward") or {}).get("overall") or {}).get("test") or {}
        h60 = (fw.get("60m") or {}).get("mean")
        print(
            f"{cfg['name']}: trades={ov.get('n')} expR={ov.get('expectancy_r')} "
            f"test_n={te.get('n')} test_expR={te.get('expectancy_r')} test_60m={h60}"
        )


if __name__ == "__main__":
    main()
