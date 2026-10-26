"""Record R.40 preflight without reading secrets or starting services."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["DOTENV_PATH"] = str(OUT / "missing.env")
import dotenv

dotenv.load_dotenv = lambda *a, **k: False
socket.socket = type("Blocked", (socket.socket,), {"connect": lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))})

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.rl_agent import RLAgent
from forex_bot.strategy_meta import strategies

FILES = [
    "forex_bot/ai_ensemble.py",
    "forex_bot/rl_agent.py",
    "forex_bot/session_rules.py",
    "forex_bot/bot_loop.py",
    "forex_bot/strategy_meta.py",
    "forex_bot/research/ml_prediction.py",
    "forex_bot/research/learning/supervised.py",
    "forex_bot/research/learning/diagnosis.py",
    "forex_bot/research/learning/regimes.py",
    "forex_bot/research/learning/timeframes.py",
    "forex_bot/research/learning/protocol.py",
    "forex_bot/research/decision_journal.py",
    "tests/test_r40_timeframes.py",
]
EVIDENCE = [
    "data/research/adaptive_ensemble/r24/10_recovery_repair_report.md",
    "data/research/adaptive_ensemble/r25/stage_r25_report.md",
    "data/research/adaptive_ensemble/r26/stage_r26_report.md",
    "data/research/adaptive_ensemble/r27/stage_r27_report.md",
    "data/research/adaptive_ensemble/r28/stage_r28_report.md",
    "data/research/adaptive_ensemble/r29/stage_r29_report.md",
    "data/research/adaptive_ensemble/r30/stage_r30_report.md",
    "data/research/adaptive_ensemble/r31/stage_r31_report.md",
    "data/research/adaptive_ensemble/r32/stage_r32_report.md",
    "data/research/adaptive_ensemble/r33/stage_r33_report.md",
    "data/research/adaptive_ensemble/r34/stage_r34_report.md",
    "data/research/adaptive_ensemble/r35/stage_r35_report.md",
    "data/research/adaptive_ensemble/r36/stage_r36_report.md",
    "data/research/adaptive_ensemble/r37/stage_r37_report.md",
    "data/research/adaptive_ensemble/r38/stage_r38_report.md",
    "data/research/adaptive_ensemble/r39/stage_r39_report.md",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    vote = _quant_stub_vote({"returns": 1.0})
    bot = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
    ensemble = (ROOT / "forex_bot" / "ai_ensemble.py").read_text(encoding="utf-8")
    payload = {
        "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "project_root": str(ROOT),
        "strategies_inactive": all(not item.active and not item.authorised_for_live for item in strategies.values()),
        "strategy_names": sorted(item.name for item in strategies.values()),
        "stub_reason": vote["reason"],
        "stub_allow": vote["allow"],
        "rl_unseen": RLAgent().decide("unseen"),
        "timeframes_imported_by_bot_loop": "timeframes" in bot,
        "timeframes_imported_by_ai_ensemble": "timeframes" in ensemble,
        "hashes": {name: digest(ROOT / name) for name in FILES},
        "prior_evidence_present": {name: (ROOT / name).is_file() for name in EVIDENCE},
        "production_authorised": False,
        "trading_backtest_run": False,
        "external_video_accessed": False,
    }
    (OUT / "01_preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("branch", "head", "dirty", "strategies_inactive", "stub_reason", "rl_unseen")}))


if __name__ == "__main__":
    main()
