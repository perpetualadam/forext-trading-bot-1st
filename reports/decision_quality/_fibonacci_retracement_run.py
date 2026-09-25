"""Run the research-only Fibonacci vs control experiment. No OANDA, no production edits."""

from __future__ import annotations

import json
from pathlib import Path

from forex_bot.decision_quality.ema_retracement import _jsonable
from forex_bot.decision_quality.fibonacci_retracement import run_experiment

OUT = Path(__file__).resolve().parent / "_fibonacci_retracement_results.json"


def main() -> None:
    payload = _jsonable(run_experiment())
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("cuts", payload["cuts"])
    print("conclusion", payload["conclusion_code"], payload["conclusion"])


if __name__ == "__main__":
    main()
