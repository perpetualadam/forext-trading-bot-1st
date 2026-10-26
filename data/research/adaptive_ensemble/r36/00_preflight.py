"""Record R.36 preflight flags and operational hashes. No training and no network."""

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


class _Blocked(socket.socket):
    def connect(self, *_a, **_k):
        raise OSError("R36_NETWORK_BLOCKED")


socket.socket = _Blocked
for name in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
    "GROQ_API_KEY",
    "VENICE_API_KEY",
    "QROK_API_KEY",
    "OPENAI_BASE_URL",
):
    os.environ.pop(name, None)
os.environ["ENSEMBLE_MODE"] = "hybrid"
from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.rl_agent import RLAgent
from forex_bot.strategy_meta import strategies

files = [
    "forex_bot/ai_ensemble.py",
    "forex_bot/rl_agent.py",
    "forex_bot/session_rules.py",
    "forex_bot/experiment.py",
    "forex_bot/bot_loop.py",
    "forex_bot/strategy_meta.py",
    "forex_bot/research/ml_prediction.py",
    "forex_bot/research/decision_journal.py",
    "forex_bot/research/learning/protocol.py",
    "forex_bot/research/learning/supervised.py",
    "tests/test_r36_supervised.py",
]
record = {
    "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "working_tree": "dirty_preserved",
    "strategy_flags": {
        name: {"active": bool(item.active), "authorised_for_live": bool(item.authorised_for_live)}
        for name, item in strategies.items()
    },
    "quant_stub_reason": _quant_stub_vote({}).get("reason"),
    "unverified_rl": RLAgent().decide("unseen"),
    "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
}
(OUT / "01_preflight.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({"inactive": all(not row["active"] and not row["authorised_for_live"] for row in record["strategy_flags"].values()), "rl": record["unverified_rl"], "stub": record["quant_stub_reason"]}))
