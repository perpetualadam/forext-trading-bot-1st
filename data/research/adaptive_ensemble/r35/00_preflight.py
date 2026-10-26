"""Record R.35 preflight hashes and strategy flags. No network and no orders."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class _Blocked(socket.socket):
    def connect(self, *_a, **_k):
        raise OSError("R35_NETWORK_BLOCKED")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    os.environ["DOTENV_PATH"] = str(OUT / "missing.env")
    import dotenv

    dotenv.load_dotenv = lambda *a, **k: False
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
    from forex_bot.ai_ensemble import _build_default_ensemble, _quant_stub_vote
    from forex_bot.rl_agent import RLAgent
    from forex_bot.strategy_meta import strategies

    flags = {
        name: {"active": bool(item.active), "authorised_for_live": bool(item.authorised_for_live)}
        for name, item in strategies.items()
    }
    vote = _quant_stub_vote({"ma_fast": 2.0, "ma_slow": 1.0, "returns": 0.01, "atr": 0.01})
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = [
        "forex_bot/ai_ensemble.py",
        "forex_bot/rl_agent.py",
        "forex_bot/session_rules.py",
        "forex_bot/experiment.py",
        "forex_bot/bot_loop.py",
        "forex_bot/strategy_meta.py",
        "forex_bot/research/ml_prediction.py",
        "forex_bot/research/decision_journal.py",
        "forex_bot/decision_quality/live_path.py",
        "forex_bot/decision_quality/reports.py",
        "forex_bot/shadow/fidelity.py",
        "tests/test_silent_skip_observability.py",
        "tests/test_v2_shadow.py",
        "tests/test_momentum_m5_dedup_research.py",
        "tests/test_decision_quality_engine.py",
        "tests/test_quant_stub_mapping.py",
    ]
    evidence = [path.name for path in sorted((ROOT / "data/research/adaptive_ensemble").glob("r*")) if path.is_dir()]
    record = {
        "project_root": str(ROOT),
        "branch": branch,
        "head": head,
        "working_tree": "dirty_preserved",
        "strategy_flags": flags,
        "all_strategies_inactive": all(not item["active"] and not item["authorised_for_live"] for item in flags.values()),
        "quant_stub_vote": {key: vote[key] for key in ("allow", "direction", "status", "reason")},
        "default_builder_registers_local_llm": "LocalLLM(" in inspect.getsource(_build_default_ensemble),
        "unverified_rl": RLAgent().decide("unseen"),
        "source_hashes_before_r35": {name: _sha(ROOT / name) for name in files},
        "evidence_directories": evidence,
    }
    (OUT / "01_preflight.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("branch", "head", "all_strategies_inactive", "quant_stub_vote", "unverified_rl", "default_builder_registers_local_llm")}))


if __name__ == "__main__":
    main()
