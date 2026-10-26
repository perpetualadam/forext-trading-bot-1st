"""Record R.53 preflight without importing production modules or reading secrets."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
R51_PIN = "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"
R52_PIN = "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"

socket.socket = type(
    "Blocked",
    (socket.socket,),
    {"connect": lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))},
)

EXPECTED = {
    "forex_bot/bot_loop.py": "6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "forex_bot/ai_ensemble.py": "1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa",
    "forex_bot/rl_agent.py": "2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e",
    "forex_bot/session_rules.py": "1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1",
    "forex_bot/oanda_client.py": "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a",
    "forex_bot/research/learning/regimes.py": "f3d2ffdbe77e17808e30b3d034b5b681fd631426349dbbd107c4f4c83cfdc0ea",
    "forex_bot/research/learning/timeframes.py": "a482ef747fb28a9d1a4409c8d67b67811147afaedd0b487c52f2e9730f734676",
    "forex_bot/research/learning/structure.py": "b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc",
    "forex_bot/research/learning/lifecycle.py": "4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5",
    "forex_bot/research/learning/protocol.py": "5c1038ca6e11f79820f2063f81f83fbf58cb87f617fc3d9ec2f412f32534b0fc",
    "forex_bot/research/ml_prediction.py": "97ba722204734b480ecc610cc26756a42cabafb9d4ded81070ced146580bd7bc",
    "forex_bot/research/learning/supervised.py": "164e13853c6bbc4400dec7e4346e83b4977768fc27a0adef886b033c77660347",
    "forex_bot/research/learning/diagnosis.py": "07c0acf894fa7418b1469b68cd82a680a9e3972b06f96aaafff2660105150680",
    "forex_bot/research/decision_journal.py": "793b92f35d2c2a7565ff3a6cbbe3229cbfabfcc2828250c6a3f2016eef5cd3c0",
    "tests/test_r41_structure.py": "ffd0a4c9c51da94eddbbdac64da45ada5a0448df17f7aeb24c758f69b577d6fb",
    "tests/test_r42_lifecycle.py": "8b22fdf38e6da160a7de40bae080f884f0ef0aae4c4fa302a72084496ee9db2b",
    "data/research/adaptive_ensemble/r48/readonly_transport.py": "3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844",
    "data/research/adaptive_ensemble/r49/handoff_runner.py": "5dbf4a79f4a399f2163b4e2d8d6ae7a005d6e869261372652e26a804696d0647",
    "data/research/adaptive_ensemble/r50/connector.py": "4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8",
    "data/research/adaptive_ensemble/r51/https_adapter.py": R51_PIN,
    "data/research/adaptive_ensemble/r52/session_entry.py": R52_PIN,
}
EVIDENCE = [f"data/research/adaptive_ensemble/r{number}/stage_r{number}_report.md" for number in range(25, 53)]
EVIDENCE.insert(0, "data/research/adaptive_ensemble/r24/10_recovery_repair_report.md")
FORBIDDEN = ("forex_bot", "getenv", "getpass", "urlopen", "import requests", "oandapy", "load_dotenv", "CERT_NONE", "check_hostname = False", "dotenv")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    strategy = (ROOT / "forex_bot" / "strategy_meta.py").read_text(encoding="utf-8")
    ensemble = (ROOT / "forex_bot" / "ai_ensemble.py").read_text(encoding="utf-8")
    agent = (ROOT / "forex_bot" / "rl_agent.py").read_text(encoding="utf-8")
    bot = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
    source = (OUT / "connector.py").read_text(encoding="utf-8")
    hashes = {name: digest(ROOT / name) for name in EXPECTED}
    payload = {
        "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "project_root": str(ROOT),
        "production_modules_imported": False,
        "strategies_inactive_from_source": "self._active = False" in strategy and "self.authorised_for_live: bool = False" in strategy,
        "quant_stub_source_fail_closed": 'return _unavailable("quant_stub_removed")' in ensemble,
        "rl_fail_closed_from_source": 'return "UNAVAILABLE"' in agent and "self.persisted_ok = False" in agent,
        "lifecycle_referenced_by_bot_loop": "learning.lifecycle" in bot or "apply_lifecycle" in bot,
        "lifecycle_referenced_by_ai_ensemble": "learning.lifecycle" in ensemble or "apply_lifecycle" in ensemble,
        "operational_hashes_match": hashes == EXPECTED,
        "r51_adapter_hash_matches_pin": hashes["data/research/adaptive_ensemble/r51/https_adapter.py"] == R51_PIN,
        "r52_entry_hash_matches_pin": hashes["data/research/adaptive_ensemble/r52/session_entry.py"] == R52_PIN,
        "hashes": hashes,
        "prior_evidence_present": {name: (ROOT / name).is_file() for name in EVIDENCE},
        "connector_forbidden_tokens": [token for token in FORBIDDEN if token in source],
        "credentials_read": False,
        "authenticated_request_sent": False,
        "network_execution": False,
    }
    if not payload["r51_adapter_hash_matches_pin"] or not payload["r52_entry_hash_matches_pin"]:
        raise SystemExit("R53_PRIOR_HASH_MISMATCH")
    if not all(payload["prior_evidence_present"].values()):
        raise SystemExit("R53_EVIDENCE_MISSING")
    if payload["lifecycle_referenced_by_bot_loop"] or payload["lifecycle_referenced_by_ai_ensemble"]:
        raise SystemExit("R53_RESEARCH_CONNECTED")
    if payload["connector_forbidden_tokens"]:
        raise SystemExit("R53_CONNECTOR_BOUNDARY")
    if not payload["strategies_inactive_from_source"] or not payload["quant_stub_source_fail_closed"] or not payload["rl_fail_closed_from_source"]:
        raise SystemExit("R53_SAFEGUARD")
    if not payload["operational_hashes_match"]:
        raise SystemExit("R53_HASH_DRIFT")
    (OUT / "01_preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"branch": payload["branch"], "head": payload["head"], "dirty": payload["dirty"], "r51_pin": True, "r52_pin": True, "operational_hashes_match": True, "credentials_read": False, "network_execution": False}))


if __name__ == "__main__":
    main()
