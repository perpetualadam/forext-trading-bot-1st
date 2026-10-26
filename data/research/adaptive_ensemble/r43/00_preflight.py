"""Record R.43 preflight without reading secrets or starting services."""

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
    "forex_bot/research/learning/structure.py",
    "forex_bot/research/learning/lifecycle.py",
    "forex_bot/research/learning/protocol.py",
    "forex_bot/research/decision_journal.py",
    "tests/test_r42_lifecycle.py",
]
EVIDENCE = [f"data/research/adaptive_ensemble/r{number}/stage_r{number}_report.md" for number in range(25, 43)]
EVIDENCE.insert(0, "data/research/adaptive_ensemble/r24/10_recovery_repair_report.md")


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
        "stub_reason": vote["reason"],
        "stub_allow": vote["allow"],
        "rl_unseen": RLAgent().decide("unseen"),
        "lifecycle_imported_by_bot_loop": "learning.lifecycle" in bot or "apply_lifecycle" in bot,
        "lifecycle_imported_by_ai_ensemble": "learning.lifecycle" in ensemble or "apply_lifecycle" in ensemble,
        "hashes": {name: digest(ROOT / name) for name in FILES},
        "prior_evidence_present": {name: (ROOT / name).is_file() for name in EVIDENCE},
        "acquisition_implemented": (ROOT / "forex_bot" / "research" / "learning" / "acquire_market_data.py").is_file(),
        "broker_contacted": False,
        "market_data_downloaded": False,
        "production_authorised": False,
        "trading_backtest_run": False,
    }
    if payload["lifecycle_imported_by_bot_loop"] or payload["lifecycle_imported_by_ai_ensemble"]:
        raise SystemExit("R43_RESEARCH_CONNECTED")
    if payload["acquisition_implemented"] or not payload["strategies_inactive"] or payload["stub_allow"] or payload["rl_unseen"] != "UNAVAILABLE":
        raise SystemExit("R43_SAFEGUARD")
    (OUT / "01_preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("branch", "head", "dirty", "strategies_inactive", "stub_reason", "rl_unseen", "acquisition_implemented")}))


if __name__ == "__main__":
    main()
