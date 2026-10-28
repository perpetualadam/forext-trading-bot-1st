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
        'be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d'
    ),
    "forex_bot/telegram_control.py": (
        '0447f31e36b63ccc586391f1a1a3b04bc4d16445d1a0bcf405ca7f3e2bb4b6fe'
    ),
    "forex_bot/live_safety.py": (
        'e4310d1cd694c3f2a8791b308666fa15ae6ba1a82bdc67a99c5788ffe70ad546'
    ),
    "forex_bot/strategy_meta.py": (
        'b45b2f7e7f684686eddd2ddf9f2d6d1c3919678ec128c38665f38c99c3ab3222'
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
        actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
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
