"""Run R.26 reconciliation tests and the offline regressions behind a socket barrier."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R26 = ROOT / "data" / "research" / "adaptive_ensemble" / "r26"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = ""
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["PYTHONPYCACHEPREFIX"] = str(R26 / "pycache")
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R26 / "synthetic_live_safety_state.json")

PREFIX = {"r21": "R21", "r22": "R22", "r23": "R23", "r24": "R24", "r25": "R25"}.get(
    sys.argv[1] if len(sys.argv) > 1 else "r26", "R26"
)
ATTEMPTS: list[str] = []
DOTENV_CALLS: list[str] = []


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        ATTEMPTS.append("socket")
        raise RuntimeError(f"{PREFIX}_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    ATTEMPTS.append("name_lookup")
    raise RuntimeError(f"{PREFIX}_DNS_BLOCKED")


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
    R26.mkdir(parents=True, exist_ok=True)
    common = ["-p", "no:cacheprovider", "--noconftest", "-rs", "-q"]
    targets = {
        "r26": [str(ROOT / "tests" / "test_r26_broker_reconciliation.py")],
        "r25": [str(ROOT / "tests" / "test_r25_risk_limits.py")],
        "r24": [str(ROOT / "tests" / "test_r24_recovery_fail_closed.py")],
        "r20": [str(ROOT / "tests" / "test_r20_two_cycle.py")],
        "r21": [str(ROOT / "tests" / "test_r21_selector_and_order_state.py")],
        "r22": [str(ROOT / "tests" / "test_r22_restart_recovery.py")],
        "r23": [str(ROOT / "tests" / "test_r23_process_restart.py")],
        "r19": [str(ROOT / "tests" / "test_r19_adapter_boundary.py")],
        "r18": [str(ROOT / "tests" / "test_r18_entry_eligibility.py")],
        "r17": [str(ROOT / "tests" / "test_r17_hard_risk_gates.py")],
        "r16": [str(ROOT / "tests" / "test_r16_equity_sources.py")],
        "r15": [str(ROOT / "tests" / "test_r15_adapter_account.py")],
        "r14": [str(ROOT / "tests" / "test_r14_decision_path.py")],
        "r13": [str(ROOT / "tests" / "test_r13_loop_wiring.py")],
        "r12": [str(ROOT / "tests" / "test_r12_single_iteration.py")],
        "r11": [str(ROOT / "tests" / "test_r11_historical_recovery.py")],
        "r10": [str(ROOT / "tests" / "test_r10_offline_startup.py")],
        "regression": [
            str(ROOT / "tests" / "test_r4_trading_safety.py"),
            str(ROOT / "tests" / "test_r5_integration.py"),
            str(ROOT / "tests" / "test_r7_order_safety.py"),
            str(ROOT / "tests" / "test_r8_reservation_safety.py"),
            str(ROOT / "tests" / "test_r9_position_safety.py"),
        ],
    }
    extra = ["-k", "not test_h39_h40_restart_keeps_live_orders_blocked"] if mode == "regression" else []
    code = int(pytest.main(common + targets[mode] + extra))
    (R26 / f"pytest_{mode}_log.txt").write_text(
        f"exit={code}\nblocked={len(ATTEMPTS)}\ndotenv={len(DOTENV_CALLS)}\n",
        encoding="utf-8",
    )
    return code


if __name__ == "__main__":
    if len(sys.argv) == 1:
        modes = (
            "r26",
            "r25",
            "regression",
            "r10",
            "r11",
            "r12",
            "r13",
            "r14",
            "r15",
            "r16",
            "r17",
            "r18",
            "r19",
            "r20",
            "r21",
            "r22",
            "r23",
            "r24",
        )
        codes = [subprocess.call([sys.executable, "-B", str(Path(__file__).resolve()), mode], cwd=str(ROOT)) for mode in modes]
        (R26 / "pytest_isolation_log.txt").write_text(
            "".join(f"{mode}_exit={code}\n" for mode, code in zip(modes, codes)),
            encoding="utf-8",
        )
        raise SystemExit(next((code for code in codes if code), 0))
    raise SystemExit(_run(sys.argv[1]))
