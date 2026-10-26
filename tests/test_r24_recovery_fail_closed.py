"""Offline startup recovery must fail closed. No PostgreSQL server is used."""

from __future__ import annotations

import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R24 = ROOT / "data" / "research" / "adaptive_ensemble" / "r24"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "1"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R24 / "synthetic_live_safety_state.json")
os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402
import pytest  # noqa: E402

CONNECT_CALLS: list[str] = []


def _refuse_connect(*_args, **_kwargs):  # noqa: ANN002, ANN003
    CONNECT_CALLS.append("psycopg2.connect")
    raise RuntimeError("R24_POSTGRES_BLOCKED")


psycopg2.connect = _refuse_connect  # type: ignore[assignment]

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import IterationDependencies, evaluate  # noqa: E402
from forex_bot.database import OrderRecoveryUnreadable, confirm_exposure_flat  # noqa: E402
from forex_bot.orders import (  # noqa: E402
    ingest_recovery_snapshot,
    load_open_orders_from_db_into_memory,
    reset_orders_for_tests,
)

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, rows=None, error: BaseException | None = None) -> None:
        self.rows = rows or []
        self.error = error

    def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        if self.error is not None:
            raise self.error

    def fetchall(self):
        return list(self.rows)


class _Conn:
    closed = False

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _Broker:
    def __init__(self) -> None:
        self.request_count = 0

    def market_open(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        self.request_count += 1
        return {"filled": True}


def setup_function() -> None:
    CONNECT_CALLS.clear()
    database.disarm_offline_exec_order_store()
    database.reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    database._pg_conn = None
    database._pg_cursor = None
    _connection_unavailable()


def _connection_unavailable() -> None:
    def get_connection():
        database._pg_conn = None
        database._pg_cursor = None
        return None

    database.get_connection = get_connection  # type: ignore[method-assign]


def _cursor(rows=None, error: BaseException | None = None) -> None:
    cursor = _Cursor(rows=rows, error=error)

    def get_connection():
        database._pg_conn = _Conn()
        database._pg_cursor = cursor
        return database._pg_conn

    database.get_connection = get_connection  # type: ignore[method-assign]


def _bars() -> list[dict[str, float | str]]:
    return [
        {"open": 1.1, "high": 1.1002, "low": 1.0998, "close": 1.1, "time": "2026-01-07T11:58:00+00:00"}
        for _ in range(50)
    ]


def _drive(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def _evaluate() -> dict:
    broker = _Broker()
    result = _drive(
        evaluate(
            "EUR_USD",
            IterationDependencies(
                candles=_bars(),
                balance=10000.0,
                account_present=True,
                account_context="isolated_test",
                simulation=True,
                now=OPEN,
                quote_as_of=OPEN,
                bid=1.09995,
                ask=1.10005,
                price=1.1,
                stop_distance=0.001,
                stop_loss=1.09895,
                take_profit=1.10205,
                broker=broker,
                strategy_name="scalp",
                strategy_active=True,
                invoke_selector=False,
            ),
        )
    )
    return {
        "blocked_by": result.get("blocked_by"),
        "reservation": bool((result.get("details") or {}).get("reservation_attempted")),
        "broker_requests": broker.request_count,
        "production_eligible": result.get("production_eligible") is True,
        "fail_closed": database.current_intent_book()["fail_closed"],
    }


def _fetch_row(status: str, *, meta: dict | None = None, cid: str = "cid-r24") -> tuple:
    return (
        cid,
        "EUR_USD",
        "BUY",
        1.0,
        status,
        OPEN,
        1.1,
        "SIMULATED",
        {} if meta is None else meta,
        1.0,
    )


def _snapshot(status: str, *, meta: dict | None = None, cid: str = "cid-r24") -> dict:
    return {
        "client_order_id": cid,
        "symbol": "EUR_USD",
        "side": "BUY",
        "units": 1.0,
        "status": status,
        "fill_price": 1.1,
        "broker_order_id": "SIMULATED",
        "metadata": {} if meta is None else meta,
        "filled_units": 1.0,
    }


def test_connection_unavailable_blocks_evaluate() -> None:
    assert load_open_orders_from_db_into_memory() == 0
    result = _evaluate()
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["reservation"] is False
    assert result["broker_requests"] == 0
    assert CONNECT_CALLS == []


def test_read_connection_failure_is_not_an_empty_book() -> None:
    rows, readable = database.read_durable_recovery()
    assert rows == [] and readable is False
    result = _evaluate()
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["reservation"] is False
    assert result["broker_requests"] == 0


def test_recovery_query_failure_blocks_evaluate() -> None:
    _cursor(error=RuntimeError("query failed"))
    with pytest.raises(OrderRecoveryUnreadable):
        database.fetch_exec_orders_open_for_recovery()
    result = _evaluate()
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["broker_requests"] == 0


def test_read_query_failure_is_an_explicit_failure() -> None:
    _cursor(error=RuntimeError("query failed"))
    rows, readable = database.read_durable_recovery()
    assert rows == [] and readable is False
    result = _evaluate()
    assert result["blocked_by"] == "recovery_unreadable"
    assert result["reservation"] is False


def test_explicit_failure_result_blocks_without_a_preset_flag() -> None:
    rows, readable = database.read_durable_recovery()
    assert readable is False
    assert database.current_intent_book()["fail_closed"] is True
    result = _evaluate()
    assert result["blocked_by"] == "recovery_unreadable"


def test_empty_success_is_not_a_recovery_failure() -> None:
    _cursor(rows=[])
    rows, readable = database.read_durable_recovery()
    assert rows == [] and readable is True
    assert database.current_intent_book()["fail_closed"] is False
    result = _evaluate()
    assert result["blocked_by"] != "recovery_unreadable"
    assert result["fail_closed"] is False


def test_empty_success_clears_only_the_failure_flag() -> None:
    database.read_durable_recovery()
    assert database.current_intent_book()["fail_closed"] is True
    _cursor(rows=[])
    rows, readable = database.read_durable_recovery()
    assert rows == [] and readable is True
    assert database.current_intent_book()["fail_closed"] is False
    assert database.current_intent_book()["exposure"] == {}
    result = _evaluate()
    assert result["blocked_by"] != "recovery_unreadable"


def test_filled_recovery_blocks_on_exposure() -> None:
    _cursor(rows=[_fetch_row("FILLED", meta={"exposure_safety": "UNCONFIRMED"})])
    assert load_open_orders_from_db_into_memory() == 1
    result = _evaluate()
    assert result["blocked_by"] == "exposure_unconfirmed"
    assert result["fail_closed"] is False
    assert result["broker_requests"] == 0
    assert result["production_eligible"] is False


def test_unresolved_recovery_blocks_on_exposure() -> None:
    _cursor(rows=[_fetch_row("UNRESOLVED", meta={"exposure_safety": "UNCONFIRMED", "reason": "ambiguous_broker_outcome"})])
    load_open_orders_from_db_into_memory()
    result = _evaluate()
    assert result["blocked_by"] == "exposure_unconfirmed"
    assert result["broker_requests"] == 0
    assert result["reservation"] is False


def test_pending_and_partial_recovery_block() -> None:
    _cursor(rows=[_fetch_row("PENDING", cid="cid-pending")])
    load_open_orders_from_db_into_memory()
    pending = _evaluate()
    assert pending["blocked_by"] == "active_reservation"
    assert pending["broker_requests"] == 0
    reset_orders_for_tests()
    database.reset_order_intent_gate_for_tests()
    _cursor(rows=[_fetch_row("PARTIAL", cid="cid-partial")])
    load_open_orders_from_db_into_memory()
    partial = _evaluate()
    assert partial["blocked_by"] == "active_reservation"
    assert partial["broker_requests"] == 0


def test_failure_persists_across_repeated_evaluations() -> None:
    database.read_durable_recovery()
    first = _evaluate()
    second = _evaluate()
    assert first["blocked_by"] == "recovery_unreadable"
    assert second["blocked_by"] == "recovery_unreadable"
    assert first["broker_requests"] == 0
    assert second["broker_requests"] == 0
    assert second["reservation"] is False


def test_caller_cannot_release_the_failure() -> None:
    database.read_durable_recovery()
    assert confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT", verified=True) is False
    assert database.current_intent_book()["fail_closed"] is True
    assert _evaluate()["blocked_by"] == "recovery_unreadable"


def test_successful_recovery_clears_failure_and_keeps_exposure() -> None:
    ingest_recovery_snapshot([_snapshot("FILLED", meta={"exposure_safety": "UNCONFIRMED"})], True)
    database.read_durable_recovery()
    assert database.current_intent_book()["fail_closed"] is True
    assert "EUR_USD" in database.current_intent_book()["exposure"]
    _cursor(rows=[_fetch_row("FILLED", meta={"exposure_safety": "UNCONFIRMED"})])
    load_open_orders_from_db_into_memory()
    assert database.current_intent_book()["fail_closed"] is False
    assert "EUR_USD" in database.current_intent_book()["exposure"]
    result = _evaluate()
    assert result["blocked_by"] == "exposure_unconfirmed"
    assert result["broker_requests"] == 0
    assert result["production_eligible"] is False


def test_network_and_postgres_stay_closed() -> None:
    with pytest.raises(RuntimeError, match="R24_NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="R24_DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)
    with pytest.raises(RuntimeError, match="R24_POSTGRES_BLOCKED"):
        psycopg2.connect(dbname="trading", host="localhost", port=5432)
    assert CONNECT_CALLS == ["psycopg2.connect"]
