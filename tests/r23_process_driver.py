"""One offline create or recover process. Barriers are installed before imports."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import sys
import traceback
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _install_barriers() -> None:
    class _BlockedSocket(socket.socket):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("R23_NETWORK_BLOCKED")

    def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R23_DNS_BLOCKED")

    socket.socket = _BlockedSocket  # type: ignore[misc]
    socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
    socket.gethostbyname = _blocked_name  # type: ignore[assignment]
    socket.create_connection = _blocked_name  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return False

    dotenv.load_dotenv = load_dotenv  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv


def main() -> int:
    _install_barriers()
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("create", "recover"))
    parser.add_argument("--kind", choices=("filled", "ambiguous"), required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    store = Path(args.store)
    result_path = Path(args.result)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(root / "data" / "research" / "adaptive_ensemble" / "r23" / "synthetic_live_safety_state.json")
    os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
    sys.path.insert(0, str(root))
    payload: dict[str, object] = {"pid": os.getpid(), "role": args.role, "kind": args.kind, "ok": False}
    try:
        payload.update(_run(root, args.role, args.kind, store))
        payload["ok"] = True
        code = 0
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        payload["traceback"] = traceback.format_exc()
        code = 1
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return code


def _run(root: Path, role: str, kind: str, store: Path) -> dict[str, object]:
    from forex_bot import database
    from forex_bot.bot_loop import IterationDependencies, evaluate, rl_decision_state
    from forex_bot.database import exposure_entry_block_reason
    from forex_bot.indicators import compute_indicators
    from forex_bot.orders import orders_by_client_id
    from forex_bot.rl_agent import RLAgent

    database.disarm_offline_exec_order_store()
    database.arm_offline_exec_order_store(store, context="isolated_offline_test")
    if role == "create":
        return _create(kind, store, compute_indicators, IterationDependencies, evaluate, rl_decision_state, RLAgent, orders_by_client_id, database)
    return _recover(root, kind, store, compute_indicators, IterationDependencies, evaluate, rl_decision_state, RLAgent, orders_by_client_id, database, exposure_entry_block_reason)


def _bars() -> list[dict[str, float | str]]:
    price = 1.1
    return [
        {
            "open": price,
            "high": price + 0.0002,
            "low": price - 0.0002,
            "close": price,
            "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
        }
        for index in range(50)
    ]


def _deps(bars, broker, when, compute_indicators, IterationDependencies, rl_decision_state, RLAgent):
    import pandas as pd

    key = rl_decision_state(compute_indicators(pd.DataFrame(bars)))
    agent = RLAgent(epsilon=0.0)
    agent.q[key] = {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}
    agent.persisted_ok = True
    return IterationDependencies(
        candles=bars,
        balance=10000.0,
        account_present=True,
        account_context="isolated_test",
        simulation=True,
        now=when,
        quote_as_of=when,
        bid=1.09995,
        ask=1.10005,
        price=1.1,
        stop_distance=0.001,
        stop_loss=1.09895,
        take_profit=1.10205,
        broker=broker,
        strategy_name="trend",
        strategy_active_map={"scalp": True},
        invoke_selector=True,
        invoke_vote=True,
        invoke_rl=True,
        vote={"allow": True, "direction": "BUY", "confidence": 0.8},
        rl_agent=agent,
        unrealised=0.0,
        account_as_of=when,
    )


def _drive(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def _fake_broker(root: Path, kind: str):
    spec = importlib.util.spec_from_file_location("r12_fakes", root / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker(kind)


def _create(kind, store, compute_indicators, IterationDependencies, evaluate, rl_decision_state, RLAgent, orders, database) -> dict[str, object]:
    opened = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
    broker = _fake_broker(Path(__file__).resolve().parents[1], "ambiguous" if kind == "ambiguous" else "filled")
    result = _drive(evaluate("EUR_USD", _deps(_bars(), broker, opened, compute_indicators, IterationDependencies, rl_decision_state, RLAgent)))
    order = orders[result["client_order_id"]]
    if broker.request_count != 1:
        raise RuntimeError(f"create dispatch {broker.request_count}")
    expected = "UNRESOLVED" if kind == "ambiguous" else "FILLED"
    if order.status.value != expected:
        raise RuntimeError(f"create status {order.status.value}")
    if database._pg_conn is not None:
        raise RuntimeError("postgres connection")
    return {
        "evaluate": True,
        "functions": ["evaluate", "dispatch_production_iteration", "evaluate_one_instrument_iteration"],
        "inert_dispatches": broker.request_count,
        "client_order_id": order.client_order_id,
        "order_status": order.status.value,
        "production_eligible": result["production_eligible"],
        "selected_strategy": result["details"]["selected_strategy"],
        "store_sha256": hashlib.sha256(store.read_bytes()).hexdigest(),
        "postgresql_connection": database._pg_conn is not None,
    }


def _recover(root, kind, store, compute_indicators, IterationDependencies, evaluate, rl_decision_state, RLAgent, orders, database, exposure_entry_block_reason) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("r10_fakes", root / "tests" / "r10_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    services = module.OfflineServices()
    services.use_provider = True
    called: list[str] = []

    def recover_orders():
        called.append("read_offline_exec_orders")
        return database.read_offline_exec_orders()

    services.recover_orders = recover_orders
    from forex_bot.app import initialise_application

    report = _drive(initialise_application(services.ports()))
    if report is None or report.ok is not True:
        raise RuntimeError("startup recovery failed")
    recovered = list(orders.values())
    if len(recovered) != 1:
        raise RuntimeError(f"recovered orders {len(recovered)}")
    order = recovered[0]
    expected = "UNRESOLVED" if kind == "ambiguous" else "FILLED"
    if order.status.value != expected or order.source != "db_recovery":
        raise RuntimeError(f"recovered {order.status.value} {order.source}")
    opened = datetime(2026, 1, 7, 12, 1, tzinfo=timezone.utc)
    broker = _fake_broker(root, "filled")
    result = _drive(evaluate("EUR_USD", _deps(_bars(), broker, opened, compute_indicators, IterationDependencies, rl_decision_state, RLAgent)))
    if broker.request_count != 0 or result["details"].get("reservation_attempted"):
        raise RuntimeError("process B dispatched")
    if result["blocked_by"] != "exposure_unconfirmed":
        raise RuntimeError(result["blocked_by"])
    if database._pg_conn is not None:
        raise RuntimeError("postgres connection")
    return {
        "evaluate": True,
        "functions": ["initialise_application", "evaluate", "dispatch_production_iteration", "evaluate_one_instrument_iteration"],
        "recovery_functions": called + ["select_rows_for_recovery", "ingest_recovery_snapshot"],
        "startup_ok": True,
        "recovered_client_order_id": order.client_order_id,
        "recovered_status": order.status.value,
        "recovered_source": order.source,
        "exposure": exposure_entry_block_reason("EUR_USD"),
        "blocked_by": result["blocked_by"],
        "exposure_read": result["details"].get("exposure_read"),
        "reservation_attempted": bool(result["details"].get("reservation_attempted")),
        "inert_dispatches": broker.request_count,
        "production_eligible": result.get("production_eligible"),
        "postgresql_connection": database._pg_conn is not None,
        "duplicate_order": len(orders) != 1,
    }


if __name__ == "__main__":
    raise SystemExit(main())
