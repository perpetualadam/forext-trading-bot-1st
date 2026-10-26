"""Run the R.12 iteration tests behind a socket and DNS barrier."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R12 = ROOT / "data" / "research" / "adaptive_ensemble" / "r12"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = ""
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R12 / "synthetic_live_safety_state.json")

ATTEMPTS: list[str] = []
DOTENV_CALLS: list[str] = []


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        ATTEMPTS.append(str(args[0]) if args else "")
        raise RuntimeError("R12_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    ATTEMPTS.append("name_lookup")
    raise RuntimeError("R12_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]

dotenv = types.ModuleType("dotenv")


def load_dotenv(*_args, **_kwargs):  # noqa: ANN002, ANN003
    DOTENV_CALLS.append("load_dotenv")
    return False


dotenv.load_dotenv = load_dotenv  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


def _run(mode: str) -> int:
    R12.mkdir(parents=True, exist_ok=True)
    common = ["-p", "no:cacheprovider", "--noconftest", "-rs", "-q"]
    if mode == "r12":
        targets = [str(ROOT / "tests" / "test_r12_single_iteration.py")]
        extra: list[str] = []
    elif mode == "regression":
        targets = [
            str(ROOT / "tests" / "test_r4_trading_safety.py"),
            str(ROOT / "tests" / "test_r5_integration.py"),
            str(ROOT / "tests" / "test_r7_order_safety.py"),
            str(ROOT / "tests" / "test_r8_reservation_safety.py"),
            str(ROOT / "tests" / "test_r9_position_safety.py"),
        ]
        extra = ["-k", "not test_h39_h40_restart_keeps_live_orders_blocked"]
    elif mode == "r10":
        targets = [str(ROOT / "tests" / "test_r10_offline_startup.py")]
        extra = []
    elif mode == "r11":
        targets = [str(ROOT / "tests" / "test_r11_historical_recovery.py")]
        extra = []
    else:
        raise SystemExit(f"unknown mode {mode}")
    code = int(pytest.main(common + targets + extra))
    (R12 / f"pytest_{mode}_log.txt").write_text(
        "exit={0}\nblocked={1}\ndotenv={2}\n".format(code, len(ATTEMPTS), len(DOTENV_CALLS)),
        encoding="utf-8",
    )
    return code


if __name__ == "__main__":
    if len(sys.argv) == 1:
        codes = [
            subprocess.call([sys.executable, "-B", str(Path(__file__).resolve()), mode])
            for mode in ("r12", "regression", "r10", "r11")
        ]
        (R12 / "pytest_isolation_log.txt").write_text(
            "r12_exit={0}\nregression_exit={1}\nr10_exit={2}\nr11_exit={3}\n".format(*codes),
            encoding="utf-8",
        )
        raise SystemExit(codes[0] or codes[1] or codes[2] or codes[3])
    raise SystemExit(_run(sys.argv[1]))
