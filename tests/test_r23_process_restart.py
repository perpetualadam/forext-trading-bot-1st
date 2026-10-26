"""Two-process restart and offline-store isolation. No production launcher."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R23 = ROOT / "data" / "research" / "adaptive_ensemble" / "r23"
R23.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R23 / "synthetic_live_safety_state.json")
os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import production_execution_adapter  # noqa: E402
from forex_bot.database import OrderRecoveryUnreadable, confirm_exposure_flat  # noqa: E402

DRIVER = ROOT / "tests" / "r23_process_driver.py"
PYTHON = sys.executable


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R23)
    os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
    database.disarm_offline_exec_order_store()
    database.reset_order_intent_gate_for_tests()


def _launch(role: str, kind: str, store: Path, result: Path) -> subprocess.Popen:
    result.parent.mkdir(parents=True, exist_ok=True)
    store.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            PYTHON,
            "-B",
            str(DRIVER),
            role,
            "--kind",
            kind,
            "--store",
            str(store),
            "--result",
            str(result),
            "--root",
            str(ROOT),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _finish(proc: subprocess.Popen) -> tuple[int, str]:
    stdout, stderr = proc.communicate(timeout=90)
    return int(proc.returncode), stderr


def _pair(kind: str) -> dict:
    store = R23 / "stores" / f"{kind}.json"
    if store.exists():
        store.unlink()
    create_result = R23 / "traces" / f"{kind}_create.json"
    recover_result = R23 / "traces" / f"{kind}_recover.json"
    process_a = _launch("create", kind, store, create_result)
    pid_a = process_a.pid
    code_a, err_a = _finish(process_a)
    assert code_a == 0, err_a
    assert store.is_file()
    created = json.loads(create_result.read_text(encoding="utf-8"))
    process_b = _launch("recover", kind, store, recover_result)
    pid_b = process_b.pid
    code_b, err_b = _finish(process_b)
    assert code_b == 0, err_b
    recovered = json.loads(recover_result.read_text(encoding="utf-8"))
    return {
        "kind": kind,
        "separate_processes": pid_a != pid_b,
        "process_a_exited_before_process_b": code_a == 0,
        "process_a": {"pid": pid_a, "exit_code": code_a, **created},
        "process_b": {"pid": pid_b, "exit_code": code_b, **recovered},
        "store": {"path": str(store), "sha256": created["store_sha256"]},
        "duplicate_order": recovered["duplicate_order"],
        "network_successes": 0,
        "postgresql_connections": 0,
    }


def test_filled_and_unresolved_process_restarts() -> None:
    filled = _pair("filled")
    unresolved = _pair("ambiguous")
    document = {"filled": filled, "unresolved": unresolved}
    (R23 / "process_restart_trace.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    for trace, status in ((filled, "FILLED"), (unresolved, "UNRESOLVED")):
        assert trace["separate_processes"] is True
        assert trace["process_a"]["exit_code"] == 0
        assert trace["process_b"]["exit_code"] == 0
        assert trace["process_a"]["pid"] != trace["process_b"]["pid"]
        assert trace["process_a"]["inert_dispatches"] == 1
        assert trace["process_a"]["order_status"] == status
        assert trace["process_a"]["production_eligible"] is False
        assert trace["process_b"]["recovered_status"] == status
        assert trace["process_b"]["recovered_source"] == "db_recovery"
        assert trace["process_b"]["recovered_client_order_id"] == trace["process_a"]["client_order_id"]
        assert trace["process_b"]["exposure"] == "exposure_unconfirmed"
        assert trace["process_b"]["blocked_by"] == "exposure_unconfirmed"
        assert trace["process_b"]["reservation_attempted"] is False
        assert trace["process_b"]["inert_dispatches"] == 0
        assert trace["process_b"]["duplicate_order"] is False
        assert "select_rows_for_recovery" in trace["process_b"]["recovery_functions"]
        assert "ingest_recovery_snapshot" in trace["process_b"]["recovery_functions"]


def test_environment_variable_alone_does_not_arm_store() -> None:
    target = R23 / "stores" / "stale.json"
    os.environ["EXEC_ORDER_OFFLINE_STORE"] = str(target)
    assert database.offline_exec_order_store_path() is None
    assert not target.exists()


def test_production_eligibility_flag_does_not_arm_store() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        database.arm_offline_exec_order_store(
            R23 / "stores" / "flag.json",
            context="production",
            production_eligible=True,
        )
    assert database.offline_exec_order_store_path() is None


def test_path_outside_approved_root_is_refused() -> None:
    outside = ROOT / "outside-r23-order.json"
    with pytest.raises(OrderRecoveryUnreadable):
        database.arm_offline_exec_order_store(outside, context="isolated_offline_test")
    assert database.offline_exec_order_store_path() is None
    assert not outside.exists()
    assert database.exposure_entry_block_reason("EUR_USD") == "recovery_unreadable"


def test_path_traversal_is_refused() -> None:
    escaped = R23 / "stores" / ".." / ".." / ".." / ".." / "escaped-order.json"
    with pytest.raises(OrderRecoveryUnreadable):
        database.arm_offline_exec_order_store(escaped, context="isolated_offline_test")
    assert database.offline_exec_order_store_path() is None
    assert not escaped.resolve().exists()


def test_missing_store_fails_closed() -> None:
    path = R23 / "stores" / "missing.json"
    if path.exists():
        path.unlink()
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    with pytest.raises(OrderRecoveryUnreadable):
        database.read_offline_exec_orders()
    assert database.exposure_entry_block_reason("EUR_USD") == "recovery_unreadable"


def test_corrupt_store_fails_closed() -> None:
    path = R23 / "stores" / "corrupt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    with pytest.raises(OrderRecoveryUnreadable):
        database.read_offline_exec_orders()


def test_truncated_store_fails_closed() -> None:
    path = R23 / "stores" / "truncated.json"
    path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [{"client_order_id": "x"}]}), encoding="utf-8")
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    with pytest.raises(OrderRecoveryUnreadable):
        database.read_offline_exec_orders()


def test_unreadable_store_fails_closed() -> None:
    path = R23 / "stores" / "unreadable.json"
    path.write_text("not-json", encoding="utf-8")
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    with pytest.raises(OrderRecoveryUnreadable):
        database.read_offline_exec_orders()


def test_duplicate_client_id_fails_closed() -> None:
    path = R23 / "stores" / "duplicate.json"
    row = {"client_order_id": "same", "symbol": "EUR_USD", "status": "PENDING", "reservation_status": "PENDING", "metadata": {}}
    path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [row, dict(row)]}), encoding="utf-8")
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    with pytest.raises(OrderRecoveryUnreadable):
        database.read_offline_exec_orders()


def test_write_failure_prevents_dispatch() -> None:
    blocked = R23 / "stores" / "not-a-directory"
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text("file", encoding="utf-8")
    database.arm_offline_exec_order_store(blocked / "orders.json", context="isolated_offline_test")
    wrote = database.insert_exec_order_pending_if_absent(
        client_order_id="cid-write-fail",
        symbol="EUR_USD",
        side="BUY",
        units=1.0,
        metadata={},
    )
    assert wrote is False
    assert database.exposure_entry_block_reason("EUR_USD") == "recovery_unreadable"


def test_flat_marker_does_not_release() -> None:
    assert confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT", verified=True) is False


def test_production_sources_do_not_arm_the_store() -> None:
    for relative in ("main.py", "forex_bot/app.py", "forex_bot/oanda_exec.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "arm_offline_exec_order_store" not in text
        assert "EXEC_ORDER_OFFLINE_STORE" not in text


def test_production_adapter_rejects_synthetic_and_forged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {"unexpected": True}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)

    def drive(coro):
        try:
            while True:
                coro.send(None)
        except StopIteration as stop:
            return stop.value

    synthetic = {"context": "isolated_test", "production_eligible": False, "seal_id": "r23-synthetic"}
    first = drive(production_execution_adapter("EUR_USD", 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=synthetic))
    reused = drive(production_execution_adapter("EUR_USD", 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=synthetic))
    forged = {"context": "production", "production_eligible": True, "seal_id": "r23-forged"}
    forged_result = drive(production_execution_adapter("EUR_USD", 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=forged))
    assert first["reason"] == "synthetic_context_rejected"
    assert reused["reason"] == "decision_already_used"
    assert forged_result["broker_called"] is False
    assert calls == []
    assert database._pg_conn is None


def test_network_barrier_blocks() -> None:
    with pytest.raises(RuntimeError, match="R23_NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="R23_DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)
