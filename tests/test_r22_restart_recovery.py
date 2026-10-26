"""Offline restart recovery through the existing startup contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R22 = ROOT / "data" / "research" / "adaptive_ensemble" / "r22"
R22.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R22 / "synthetic_live_safety_state.json")
os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
os.environ.pop("HYBRID_EUR_USD", None)
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    evaluate,
    production_execution_adapter,
    rl_decision_state,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    reset_order_intent_gate_for_tests,
)
from forex_bot.orders import orders_by_client_id, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

_startup_spec = importlib.util.spec_from_file_location("r10_fakes", ROOT / "tests" / "r10_fakes.py")
_startup_mod = importlib.util.module_from_spec(_startup_spec)
assert _startup_spec is not None and _startup_spec.loader is not None
_startup_spec.loader.exec_module(_startup_mod)
OfflineServices = _startup_mod.OfflineServices

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
SYMBOL = "EUR_USD"
NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")


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


def _agent(bars: list[dict[str, float | str]]) -> RLAgent:
    import pandas as pd

    from forex_bot.indicators import compute_indicators

    key = rl_decision_state(compute_indicators(pd.DataFrame(bars)))
    agent = RLAgent(epsilon=0.0)
    agent.q[key] = {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}
    agent.persisted_ok = True
    return agent


def _deps(broker: object, when: datetime, **extra: object) -> IterationDependencies:
    bars = _bars()
    values: dict[str, object] = {
        "candles": bars,
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": when,
        "quote_as_of": when,
        "bid": 1.09995,
        "ask": 1.10005,
        "price": 1.1,
        "stop_distance": 0.001,
        "stop_loss": 1.09895,
        "take_profit": 1.10205,
        "broker": broker,
        "strategy_name": "trend",
        "strategy_active_map": {"scalp": True},
        "invoke_selector": True,
        "invoke_vote": True,
        "invoke_rl": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "rl_agent": _agent(bars),
    }
    values.update(extra)
    if "unrealised" not in extra:
        values["unrealised"] = 0.0
    if "account_as_of" not in extra:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _drive(coro: object) -> dict:
    try:
        while True:
            coro.send(None)  # type: ignore[attr-defined]
    except StopIteration as stop:
        return dict(stop.value)


def _cycle(broker: object, when: datetime, **extra: object) -> dict:
    return _drive(evaluate(SYMBOL, _deps(broker, when, **extra)))


def _wipe() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    positions.clear()


def _memory_counts() -> dict[str, int]:
    return {
        "orders": len(orders_by_client_id),
        "positions": len(positions),
        "exposure": len(database._process_exposure),
        "blocking": len(database._process_blocking),
        "unresolved": len(database._process_unresolved),
    }


def _store(name: str) -> Path:
    path = R22 / "stores" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    return path


def _recover(path: Path):
    database.arm_offline_exec_order_store(path, context="isolated_offline_test")
    services = OfflineServices()
    services.use_provider = True

    def recover_orders() -> list[dict]:
        services.calls.append("read_offline_exec_orders")
        return database.read_offline_exec_orders()

    services.recover_orders = recover_orders  # type: ignore[method-assign]
    from forex_bot.app import initialise_application

    coro = initialise_application(services.ports())
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        report = stop.value
        error = None
    except Exception as exc:
        report = getattr(exc, "startup_report", None)
        error = exc
    return report, error, services


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R22)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R22 / "synthetic_live_safety_state.json")
    os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
    database.disarm_offline_exec_order_store()
    os.environ.pop("HYBRID_EUR_USD", None)
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    _wipe()


def _restart_case(kind: str) -> dict:
    path = _store(f"{kind}.json")
    broker_a = FakeBroker(kind if kind != "filled" else "filled")
    if kind == "ambiguous":
        broker_a = FakeBroker("ambiguous")
    first = _cycle(broker_a, OPEN)
    order = orders_by_client_id[first["client_order_id"]]
    before = {
        "client_order_id": order.client_order_id,
        "status": order.status.value,
        "object_id": id(order),
    }
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    persisted = json.loads(path.read_text(encoding="utf-8"))
    _wipe()
    empty = _memory_counts()
    survived = hashlib.sha256(path.read_bytes()).hexdigest()
    report, error, services = _recover(path)
    recovered = orders_by_client_id[before["client_order_id"]]
    broker_b = FakeBroker("filled")
    second = _cycle(broker_b, OPEN + timedelta(minutes=1))
    return {
        "kind": kind,
        "instance_a": {
            "functions": ["evaluate", "dispatch_production_iteration", "evaluate_one_instrument_iteration"],
            "inert_dispatches": broker_a.request_count,
            "order_status": before["status"],
            "client_order_id": before["client_order_id"],
            "production_eligible": first["production_eligible"],
            "selected_strategy": first["details"]["selected_strategy"],
        },
        "store": {
            "path": str(path),
            "sha256": digest,
            "sha256_after_wipe": survived,
            "record": next(row for row in persisted["orders"] if row["client_order_id"] == before["client_order_id"]),
        },
        "restart": {
            "maps_after_wipe": empty,
            "file_unchanged": digest == survived,
            "startup_function": "initialise_application",
            "recovery_functions": ["read_offline_exec_orders", "select_rows_for_recovery", "ingest_recovery_snapshot"],
            "provider_calls": services.calls,
            "startup_ok": error is None and report is not None and report.ok is True,
            "recovered_source": recovered.source,
            "recovered_status": recovered.status.value,
            "recovered_object_is_new": id(recovered) != before["object_id"],
            "exposure": exposure_entry_block_reason(SYMBOL),
        },
        "instance_b": {
            "functions": ["evaluate", "dispatch_production_iteration", "evaluate_one_instrument_iteration"],
            "blocked_by": second["blocked_by"],
            "exposure_read": second["details"].get("exposure_read"),
            "reservation_attempted": second["details"].get("reservation_attempted"),
            "inert_dispatches": broker_b.request_count,
            "production_eligible": second.get("production_eligible"),
        },
    }


def test_filled_restart_blocks_on_recovered_exposure() -> None:
    trace = _restart_case("filled")
    (R22 / "filled_restart_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    assert trace["instance_a"]["inert_dispatches"] == 1
    assert trace["instance_a"]["order_status"] == "FILLED"
    assert trace["instance_a"]["selected_strategy"] == "scalp"
    assert trace["instance_a"]["production_eligible"] is False
    assert trace["store"]["record"]["status"] == "FILLED"
    assert trace["store"]["record"]["metadata"]["exposure_safety"] == "UNCONFIRMED"
    assert "CONFIRMED_FLAT" not in json.dumps(trace["store"]["record"])
    assert trace["restart"]["maps_after_wipe"] == {"orders": 0, "positions": 0, "exposure": 0, "blocking": 0, "unresolved": 0}
    assert trace["restart"]["file_unchanged"] is True
    assert trace["restart"]["startup_ok"] is True
    assert trace["restart"]["recovered_source"] == "db_recovery"
    assert trace["restart"]["recovered_status"] == "FILLED"
    assert trace["restart"]["recovered_object_is_new"] is True
    assert trace["restart"]["exposure"] == "exposure_unconfirmed"
    assert trace["instance_b"]["blocked_by"] == "exposure_unconfirmed"
    assert trace["instance_b"]["reservation_attempted"] is False
    assert trace["instance_b"]["inert_dispatches"] == 0
    assert database._pg_conn is None


def test_unresolved_restart_blocks_without_retry() -> None:
    trace = _restart_case("ambiguous")
    (R22 / "unresolved_restart_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    assert trace["instance_a"]["inert_dispatches"] == 1
    assert trace["instance_a"]["order_status"] == "UNRESOLVED"
    assert trace["store"]["record"]["status"] == "UNRESOLVED"
    assert trace["restart"]["maps_after_wipe"]["orders"] == 0
    assert trace["restart"]["recovered_status"] == "UNRESOLVED"
    assert trace["restart"]["recovered_object_is_new"] is True
    assert trace["restart"]["exposure"] == "exposure_unconfirmed"
    assert trace["instance_b"]["blocked_by"] == "exposure_unconfirmed"
    assert trace["instance_b"]["inert_dispatches"] == 0
    assert trace["instance_b"]["reservation_attempted"] is False


def _plant(name: str, orders: object) -> Path:
    path = _store(name)
    path.write_text(
        json.dumps({"schema": "exec_orders_offline_v1", "orders": orders}, indent=2),
        encoding="utf-8",
    )
    return path


def _row(status: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_order_id": "legacy-1",
        "symbol": SYMBOL,
        "side": "BUY",
        "units": 1.0,
        "status": status,
        "reservation_status": status,
        "metadata": {"exposure_safety": "UNCONFIRMED"},
    }
    payload.update(extra)
    return payload


@pytest.mark.parametrize(
    ("name", "orders", "reason"),
    [
        ("pending", [_row("PENDING", metadata={})], "active_reservation"),
        ("partial", [_row("PARTIAL")], "exposure_unconfirmed"),
        ("filled_open", [_row("FILLED", metadata={})], "exposure_unconfirmed"),
        ("unresolved", [_row("UNRESOLVED")], "exposure_unconfirmed"),
        ("legacy_missing_metadata", [_row("FILLED", metadata=None)], "exposure_unconfirmed"),
    ],
)
def test_recovered_legacy_rows_block(name: str, orders: list[dict], reason: str) -> None:
    path = _plant(f"legacy-{name}.json", orders)
    _wipe()
    report, error, _services = _recover(path)
    assert error is None and report is not None and report.ok is True
    broker = FakeBroker("filled")
    result = _cycle(broker, OPEN)
    assert result["blocked_by"] == reason
    assert broker.request_count == 0
    assert "reservation" not in result["phases"]


def test_unknown_exposure_marker_fails_closed() -> None:
    path = _plant("unknown-marker.json", [_row("FILLED", metadata={"exposure_safety": "MAYBE_FLAT"})])
    _wipe()
    _report, error, _services = _recover(path)
    assert error is not None
    result = _cycle(FakeBroker("filled"), OPEN)
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["broker_requests"] == 0


@pytest.mark.parametrize(
    ("name", "writer"),
    [
        ("missing", None),
        ("corrupt", lambda path: path.write_text("{", encoding="utf-8")),
        ("truncated", lambda path: path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [{"client_order_id": "x"}]}), encoding="utf-8")),
        ("missing_client_id", lambda path: path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [{"client_order_id": "", "symbol": "EUR_USD", "status": "PENDING"}]}), encoding="utf-8")),
        ("duplicate", lambda path: path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [_row("PENDING"), _row("PENDING", client_order_id="legacy-1")]}), encoding="utf-8")),
        ("inconsistent", lambda path: path.write_text(json.dumps({"schema": "exec_orders_offline_v1", "orders": [_row("PENDING", reservation_status="FILLED")]}), encoding="utf-8")),
    ],
)
def test_damaged_store_fails_closed(name: str, writer) -> None:
    path = R22 / "stores" / f"damaged-{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    if writer is not None:
        writer(path)
    _wipe()
    _report, error, _services = _recover(path)
    assert error is not None
    result = _cycle(FakeBroker("filled"), OPEN)
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["broker_requests"] == 0


def test_write_failure_prevents_dispatch() -> None:
    blocked = R22 / "stores" / "not-a-directory"
    blocked.write_text("file", encoding="utf-8")
    database.arm_offline_exec_order_store(blocked / "orders.json", context="isolated_offline_test")
    broker = FakeBroker("filled")
    result = _cycle(broker, OPEN)
    assert result["blocked_by"] == "reservation_refused"
    assert broker.request_count == 0


def test_empty_store_is_not_an_unreadable_store() -> None:
    path = _plant("empty.json", [])
    _wipe()
    report, error, _services = _recover(path)
    assert error is None and report is not None and report.ok is True
    assert exposure_entry_block_reason(SYMBOL) is None
    assert database._process_fail_closed is False


def test_caller_flat_marker_does_not_release() -> None:
    path = _store("flat.json")
    _cycle(FakeBroker("filled"), OPEN)
    _wipe()
    _recover(path)
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT", verified=True) is False
    follow = _cycle(FakeBroker("filled"), OPEN + timedelta(minutes=1))
    assert follow["blocked_by"] == "exposure_unconfirmed"
    assert follow["broker_requests"] == 0


def test_null_selector_still_blocks() -> None:
    _store("null-selector.json")
    broker = FakeBroker("filled")
    result = _cycle(broker, OPEN, strategy_active_map={}, strategy_name="scalp")
    assert result["blocked_by"] == "NO_STRATEGY_SELECTED"
    assert broker.request_count == 0
    assert not (R22 / "stores" / "null-selector.json").exists()


def test_production_adapter_stays_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {"unexpected": True}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    _store("adapter.json")
    decision = _cycle(FakeBroker("filled"), OPEN)["details"]["risk_decision"]
    forged = dict(decision)
    forged["production_eligible"] = True
    forged["context"] = "production"
    outcome = _drive(
        production_execution_adapter(
            SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2,
            execution_kind="production", entry_quote=None, risk_decision=forged,
        )
    )
    assert decision["production_eligible"] is False
    assert outcome["broker_called"] is False
    assert calls == []
    assert database._pg_conn is None


def test_no_network_database_or_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    _restart_case("filled")
    with pytest.raises(RuntimeError, match="R22_NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="R22_DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)
    assert calls == []
    assert database._pg_conn is None
    assert all(strategies[name].active is False for name in NAMES)
