"""Parent-side launcher for the isolated D.13 child. Does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d13_telegram_reporting_runner.py"
UNCHANGED = {
    "forex_bot/database.py": (
        "cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e"
    ),
    "forex_bot/telegram_control.py": (
        "193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780"
    ),
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
    ),
}


def app_sha() -> str:
    return hashlib.sha256((ROOT / "forex_bot/app.py").read_bytes()).hexdigest()


def _child_env(work: Path, safety: Path) -> dict[str, str]:
    inherited = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "SYSTEMDRIVE",
            "APPDATA",
            "LOCALAPPDATA",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
        )
        if key in os.environ
    }
    return {
        **inherited,
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_CURRENT_TEST": "d13-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D13_WORK_DIR": str(work),
        "D12_WORK_DIR": str(work),
        "PAPER_TRADING": "true",
        "EXECUTION_MODE": "paper",
        "TRADING_MODE": "practice",
        "USE_OANDA_LIVE": "false",
        "TELEGRAM_COMMANDS": "1",
        "TELEGRAM_INBOUND": "0",
        "TELEGRAM_POLL_TIMEOUT_SEC": "1",
        "OANDA_ACCESS_TOKEN": "",
        "OANDA_API_KEY": "",
        "OANDA_ACCOUNT_ID": "",
        "TELEGRAM_TOKEN": "d13-synthetic-token",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "1001",
        "DISCORD_WEBHOOK_URL": "",
        "POSTGRES_HOST": "d13-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d13",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d13",
    }


def run_d13(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in UNCHANGED.items():
        path = ROOT / rel
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest
    work = tmp_path_factory.mktemp(f"d13-{mode}")
    out = work / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out), mode],
        cwd=str(work),
        env=_child_env(work, work / "safety.json"),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-2000:]
    payload["_app_sha"] = app_sha()
    return payload
