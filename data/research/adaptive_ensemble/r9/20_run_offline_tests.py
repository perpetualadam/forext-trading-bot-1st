"""Run the R.9 synthetic tests behind a socket and DNS barrier."""

from __future__ import annotations

import os
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R9 = ROOT / "data" / "research" / "adaptive_ensemble" / "r9"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = ""
os.environ["PERSIST_EXEC_ORDERS"] = "0"

ATTEMPTS: list[str] = []
DOTENV_CALLS: list[str] = []


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        ATTEMPTS.append(str(args[0]) if args else "")
        raise RuntimeError("R9_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    ATTEMPTS.append("name_lookup")
    raise RuntimeError("R9_DNS_BLOCKED")


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


if __name__ == "__main__":
    code = pytest.main(
        [
            "-p",
            "no:cacheprovider",
            "--noconftest",
            "-rs",
            str(ROOT / "tests" / "test_r4_trading_safety.py"),
            str(ROOT / "tests" / "test_r5_integration.py"),
            str(ROOT / "tests" / "test_r7_order_safety.py"),
            str(ROOT / "tests" / "test_r8_reservation_safety.py"),
            str(ROOT / "tests" / "test_r9_position_safety.py"),
            "-k",
            "not test_h39_h40_restart_keeps_live_orders_blocked",
            "-q",
        ]
    )
    (R9 / "pytest_isolation_log.txt").write_text(
        "exit={0}\nblocked={1}\ndotenv={2}\n".format(code, len(ATTEMPTS), len(DOTENV_CALLS)),
        encoding="utf-8",
    )
    raise SystemExit(code)
