"""Record R.48 preflight without importing the broker client or reading secrets."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
os.environ["DOTENV_PATH"] = str(OUT / "missing.env")
sys.path.insert(0, str(ROOT))

socket.socket = type(
    "Blocked",
    (socket.socket,),
    {"connect": lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))},
)

FILES = [
    "forex_bot/ai_ensemble.py",
    "forex_bot/rl_agent.py",
    "forex_bot/session_rules.py",
    "forex_bot/bot_loop.py",
    "forex_bot/strategy_meta.py",
    "forex_bot/oanda_client.py",
    "forex_bot/research/learning/structure.py",
    "forex_bot/research/learning/lifecycle.py",
    "tests/test_r42_lifecycle.py",
    "tests/test_r48_readonly_transport.py",
]
EVIDENCE = [f"data/research/adaptive_ensemble/r{number}/stage_r{number}_report.md" for number in range(25, 48)]
EVIDENCE.insert(0, "data/research/adaptive_ensemble/r24/10_recovery_repair_report.md")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    strategy_meta = importlib.import_module("forex_bot.strategy_meta")
    rl_agent = importlib.import_module("forex_bot.rl_agent")
    bot = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
    ensemble = (ROOT / "forex_bot" / "ai_ensemble.py").read_text(encoding="utf-8")
    client = (ROOT / "forex_bot" / "oanda_client.py").read_text(encoding="utf-8")
    payload = {
        "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "project_root": str(ROOT),
        "strategies_inactive": all(
            not item.active and not item.authorised_for_live for item in strategy_meta.strategies.values()
        ),
        "strategy_count": len(strategy_meta.strategies),
        "rl_unseen": rl_agent.RLAgent().decide("unseen"),
        "quant_stub_source_fail_closed": 'return _unavailable("quant_stub_removed")' in ensemble,
        "config_imported": "forex_bot.config" in sys.modules,
        "oanda_client_imported": "forex_bot.oanda_client" in sys.modules,
        "lifecycle_imported_by_bot_loop": "learning.lifecycle" in bot or "apply_lifecycle" in bot,
        "lifecycle_imported_by_ai_ensemble": "learning.lifecycle" in ensemble or "apply_lifecycle" in ensemble,
        "live_host_named_in_source": "https://api-fxtrade.oanda.com" in client,
        "hashes": {name: digest(ROOT / name) for name in FILES},
        "prior_evidence_present": {name: (ROOT / name).is_file() for name in EVIDENCE},
        "authenticated_request_sent": False,
        "credentials_read": False,
        "screenshot_stored": False,
        "account_identifiers_recorded": False,
    }
    if payload["config_imported"] or payload["oanda_client_imported"] or payload["credentials_read"]:
        raise SystemExit("R48_CREDENTIAL_BOUNDARY")
    if payload["lifecycle_imported_by_bot_loop"] or payload["lifecycle_imported_by_ai_ensemble"]:
        raise SystemExit("R48_RESEARCH_CONNECTED")
    if (
        not payload["strategies_inactive"]
        or payload["strategy_count"] != 6
        or payload["rl_unseen"] != "UNAVAILABLE"
        or not payload["quant_stub_source_fail_closed"]
    ):
        raise SystemExit("R48_SAFEGUARD")
    (OUT / "01_preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "branch",
                    "head",
                    "dirty",
                    "strategies_inactive",
                    "rl_unseen",
                    "config_imported",
                    "authenticated_request_sent",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
