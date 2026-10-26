"""Record R.37 preflight without reading secrets or starting services."""

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
    "forex_bot/research/learning/protocol.py",
    "forex_bot/research/decision_journal.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    vote = _quant_stub_vote({"returns": 1.0})
    payload = {
        "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "strategies_inactive": all(not item.active and not item.authorised_for_live for item in strategies.values()),
        "stub_reason": vote["reason"],
        "stub_allow": vote["allow"],
        "rl_unseen": RLAgent().decide("unseen"),
        "hashes": {name: digest(ROOT / name) for name in FILES},
        "r36_evidence_present": (ROOT / "data/research/adaptive_ensemble/r36/stage_r36_report.md").is_file(),
        "production_authorised": False,
    }
    (OUT / "01_preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("branch", "head", "strategies_inactive", "stub_reason", "rl_unseen")}))


if __name__ == "__main__":
    main()
