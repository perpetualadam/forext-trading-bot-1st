"""Run the offline R.8–R.39 regressions. Logs stay under r39."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R36 = ROOT / "data" / "research" / "adaptive_ensemble" / "r39"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = ""
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["PYTHONPYCACHEPREFIX"] = str(R36 / "pycache")
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R36 / "synthetic_live_safety_state.json")

PREFIX = {
    "r21": "R21",
    "r22": "R22",
    "r23": "R23",
    "r24": "R24",
    "r25": "R25",
    "r26": "R26",
    "r27": "R27",
    "r29": "R29",
    "r30": "R30",
    "r31": "R31",
    "r32": "R32",
    "r33": "R33",
    "r34": "R34",
    "r35": "R35",
    "r36": "R37",
    "r37": "R38",
    "r38": "R39",
    "r39": "R39",
    "legacy": "R39",
}.get(sys.argv[1] if len(sys.argv) > 1 else "r36", "R36")
ATTEMPTS: list[str] = []
DOTENV_CALLS: list[str] = []


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        ATTEMPTS.append("socket")
        raise RuntimeError(f"{PREFIX}_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    ATTEMPTS.append("name_lookup")
    raise RuntimeError(f"{PREFIX}_DNS_BLOCKED")


if (sys.argv[1] if len(sys.argv) > 1 else "") != "legacy":
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
    R36.mkdir(parents=True, exist_ok=True)
    common = ["-p", "no:cacheprovider", "--noconftest", "-rs", "-q"]
    targets = {
        "r39": [str(ROOT / "tests" / "test_r39_regimes.py")],
        "r38": [str(ROOT / "tests" / "test_r38_feature_discovery.py")],
        "r37": [str(ROOT / "tests" / "test_r37_learning.py")],
        "r36": [str(ROOT / "tests" / "test_r36_supervised.py")],
        "r35": [str(ROOT / "tests" / "test_r35_learning_foundation.py")],
        "legacy": [
            str(ROOT / "tests" / "test_silent_skip_observability.py"),
            str(ROOT / "tests" / "test_v2_shadow.py"),
            str(ROOT / "tests" / "test_momentum_m5_dedup_research.py"),
            str(ROOT / "tests" / "test_decision_quality_engine.py"),
            str(ROOT / "tests" / "test_quant_stub_mapping.py"),
        ],
        "r34": [str(ROOT / "tests" / "test_r34_stub_removal.py")],
        "r33": [str(ROOT / "tests" / "test_r33_ai_rl_audit.py")],
        "r32": [str(ROOT / "tests" / "test_r32_signal_diagnostics.py")],
        "r31": [str(ROOT / "tests" / "test_r31_strategy_screening.py")],
        "r30": [str(ROOT / "tests" / "test_r30_scalp_lifecycle.py")],
        "r29": [str(ROOT / "tests" / "test_r29_scalp_readiness.py")],
        "r27": [str(ROOT / "tests" / "test_r27_oanda_account_contract.py")],
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
    (R36 / f"pytest_{mode}_log.txt").write_text(
        f"exit={code}\nblocked={len(ATTEMPTS)}\ndotenv={len(DOTENV_CALLS)}\n",
        encoding="utf-8",
    )
    return code


if __name__ == "__main__":
    if len(sys.argv) == 1:
        modes = (
            "r39",
            "r38",
            "r37",
            "r36",
            "r35",
            "legacy",
            "r34",
            "r33",
            "r32",
            "r31",
            "r30",
            "r29",
            "r27",
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
        codes = [
            subprocess.call([sys.executable, "-B", str(Path(__file__).resolve()), mode], cwd=str(ROOT))
            for mode in modes
        ]
        (R36 / "pytest_isolation_log.txt").write_text(
            "".join(f"{mode}_exit={code}\n" for mode, code in zip(modes, codes)),
            encoding="utf-8",
        )
        raise SystemExit(next((code for code in codes if code), 0))
    raise SystemExit(_run(sys.argv[1]))
