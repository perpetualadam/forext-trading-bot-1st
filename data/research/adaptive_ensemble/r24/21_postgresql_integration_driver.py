"""Isolated PostgreSQL 18.6 integration driver. Does not change application source."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import traceback
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BIN = Path(r"C:\R24_PostgreSQL_Test\tools\pgsql\bin")
PGDATA = Path(r"C:\R24_PostgreSQL_Test\pgdata")
SECRETS = Path(r"C:\R24_PostgreSQL_Test\secrets")
R24 = ROOT / "data" / "research" / "adaptive_ensemble" / "r24"
TRACES = R24 / "pg_traces"
HOST = "127.0.0.1"
PORT = 55432
DATABASE = "r24_synthetic_orders"
APP_ROLE = "r24_tester"
BOOTSTRAP = "r24_bootstrap"
APPROVED = (HOST, PORT, DATABASE, APP_ROLE)


def _password(name: str) -> str:
    return (SECRETS / name).read_text(encoding="ascii").strip()


def _clean_env() -> dict[str, str]:
    keep = (
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "SYSTEMDRIVE",
        "COMPUTERNAME",
        "USERNAME",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
    )
    env = {key: os.environ[key] for key in keep if os.environ.get(key)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PERSIST_EXEC_ORDERS"] = "1"
    env["LIVE_SAFETY_STATE_PATH"] = str(R24 / "synthetic_live_safety_state.json")
    env["POSTGRES_HOST"] = HOST
    env["POSTGRES_PORT"] = str(PORT)
    env["POSTGRES_DB"] = DATABASE
    env["POSTGRES_USER"] = APP_ROLE
    return env


def _install_barriers() -> dict[str, list]:
    counts: dict[str, list] = {"socket": [], "dns": [], "dotenv": [], "route": [], "broker": []}

    class _GuardedSocket(socket.socket):
        def __init__(self, family=-1, type=-1, proto=-1, fileno=None):  # noqa: A002
            super().__init__(family, type, proto, fileno)

        def connect(self, address):  # noqa: ANN001
            host = ""
            port = None
            if isinstance(address, tuple):
                host = str(address[0])
                port = int(address[1]) if len(address) > 1 else None
            if host != HOST or port != PORT:
                counts["socket"].append(f"{host}:{port}")
                raise RuntimeError("R24_NETWORK_BLOCKED")
            return super().connect(address)

    def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
        counts["dns"].append("lookup")
        raise RuntimeError("R24_DNS_BLOCKED")

    socket.socket = _GuardedSocket  # type: ignore[misc]
    socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
    socket.gethostbyname = _blocked_name  # type: ignore[assignment]
    socket.create_connection = _blocked_name  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*_args, **_kwargs):  # noqa: ANN002, ANN003
        counts["dotenv"].append("load_dotenv")
        return False

    dotenv.load_dotenv = load_dotenv  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv
    return counts


def _guard_connect(counts: dict[str, list]):
    import psycopg2

    real = psycopg2.connect

    def connect(*args, **kwargs):  # noqa: ANN002, ANN003
        host = str(kwargs.get("host") or "")
        port = int(kwargs.get("port") or 0)
        dbname = str(kwargs.get("dbname") or "")
        user = str(kwargs.get("user") or "")
        if (host, port, dbname, user) != APPROVED:
            counts["route"].append(f"{user}@{host}:{port}/{dbname}")
            raise RuntimeError("R24_ROUTE_REFUSED")
        return real(*args, **kwargs)

    psycopg2.connect = connect  # type: ignore[assignment]
    return real


def _bootstrap_connect(dbname: str):
    import psycopg2

    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=dbname,
        user=BOOTSTRAP,
        password=_password("bootstrap.txt"),
    )


def bootstrap() -> dict[str, object]:
    import psycopg2
    from psycopg2 import sql

    admin = _bootstrap_connect("postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD %s"
                ).format(sql.Identifier(APP_ROLE)),
                (_password("tester.txt"),),
            )
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASE), sql.Identifier(BOOTSTRAP)
                )
            )
        for database in ("postgres", "template1", DATABASE):
            cur.execute(
                sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
            )
        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(DATABASE), sql.Identifier(APP_ROLE)
            )
        )
        cur.execute(
            """
            SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin
            FROM pg_roles WHERE rolname = %s
            """,
            (APP_ROLE,),
        )
        flags = cur.fetchone()
    admin.close()
    refused = False
    try:
        bad = psycopg2.connect(
            host=HOST,
            port=PORT,
            dbname="postgres",
            user=APP_ROLE,
            password=_password("tester.txt"),
            connect_timeout=5,
        )
        bad.close()
    except psycopg2.OperationalError:
        refused = True
    db = _bootstrap_connect(DATABASE)
    db.autocommit = True
    with db.cursor() as cur:
        cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        cur.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE))
        )
        cur.execute("SHOW password_encryption")
        encryption = cur.fetchone()[0]
        cur.execute(
            """
            SELECT substring(rolpassword from 1 for 13)
            FROM pg_authid WHERE rolname = %s
            """,
            (APP_ROLE,),
        )
        prefix_row = cur.fetchone()
        prefix = prefix_row[0] if prefix_row and prefix_row[0] else ""
    db.close()
    return {
        "database": DATABASE,
        "role": APP_ROLE,
        "rolsuper": flags[0],
        "rolcreatedb": flags[1],
        "rolcreaterole": flags[2],
        "rolreplication": flags[3],
        "rolbypassrls": flags[4],
        "rolcanlogin": flags[5],
        "postgres_database_refused": refused,
        "password_encryption": encryption,
        "password_prefix": prefix,
        "schema_create_granted": True,
    }


def _prepare_application(counts: dict[str, list]):
    os.environ.update(_clean_env())
    os.environ["POSTGRES_PASS"] = _password("tester.txt")
    os.environ.pop("EXEC_ORDER_OFFLINE_STORE", None)
    os.environ.pop("PGPASSWORD", None)
    os.environ.pop("PGHOST", None)
    os.environ.pop("PGPORT", None)
    os.environ.pop("PGDATABASE", None)
    os.environ.pop("PGUSER", None)
    sys.path.insert(0, str(ROOT))
    _guard_connect(counts)
    from forex_bot import database
    from forex_bot.config import Config
    from forex_bot.oanda_exec import execute_oanda_market_open

    if (
        Config.POSTGRES.host,
        int(Config.POSTGRES.port),
        Config.POSTGRES.db,
        Config.POSTGRES.user,
    ) != APPROVED:
        raise RuntimeError("R24_CONFIG_NOT_EXPLICIT")
    database.disarm_offline_exec_order_store()

    def _broker(*_args, **_kwargs):  # noqa: ANN002, ANN003
        counts["broker"].append("execute_oanda_market_open")
        raise RuntimeError("R24_BROKER_BLOCKED")

    import forex_bot.oanda_exec as oanda

    oanda.execute_oanda_market_open = _broker  # type: ignore[assignment]
    _ = execute_oanda_market_open
    return database


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


def _deps(symbol_unused: str, broker, when):
    import pandas as pd

    from forex_bot.bot_loop import IterationDependencies, rl_decision_state
    from forex_bot.indicators import compute_indicators
    from forex_bot.rl_agent import RLAgent

    _ = symbol_unused
    key = rl_decision_state(compute_indicators(pd.DataFrame(_bars())))
    agent = RLAgent(epsilon=0.0)
    agent.q[key] = {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}
    return IterationDependencies(
        candles=_bars(),
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
    )


def _drive(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def _broker(kind: str):
    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker(kind)


def _evaluate(symbol: str, kind: str, when: datetime):
    from forex_bot.bot_loop import evaluate

    broker = _broker(kind)
    result = _drive(evaluate(symbol, _deps(symbol, broker, when)))
    return result, broker.request_count


def _startup_recover(symbol: str) -> dict[str, object]:
    from forex_bot.app import _PRODUCTION_RECOVERY, initialise_application
    from forex_bot.database import get_connection
    from forex_bot.orders import load_open_orders_from_db_into_memory, orders_by_client_id
    from forex_bot.reconciliation import load_reconcile_state_from_db

    spec = importlib.util.spec_from_file_location("r10_fakes", ROOT / "tests" / "r10_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    services = module.OfflineServices()
    services.symbols = [symbol]
    called: list[str] = []

    def init_persistence() -> None:
        called.append("get_connection")
        if get_connection() is None:
            raise RuntimeError("R24 persistence connection unavailable")

    def recover_orders() -> None:
        called.append("load_open_orders_from_db_into_memory")
        load_open_orders_from_db_into_memory()
        called.append("load_reconcile_state_from_db")
        load_reconcile_state_from_db()

    ports = services.ports()
    ports.recovery_rows = _PRODUCTION_RECOVERY
    ports.init_persistence = init_persistence
    ports.recover_orders = recover_orders
    report = _drive(initialise_application(ports))
    return {
        "startup_ok": bool(report and report.ok),
        "trading_ready": bool(report.trading_ready) if report else None,
        "trading_loop_started": bool(report.trading_loop_started) if report else None,
        "recovery_functions": called,
        "orders": [
            {
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "status": order.status.value,
                "source": order.source,
            }
            for order in orders_by_client_id.values()
            if order.symbol == symbol
        ],
    }


def child(role: str, result_path: Path, extra: list[str]) -> int:
    counts = _install_barriers()
    payload: dict[str, object] = {"pid": os.getpid(), "role": role, "ok": False}
    try:
        database = _prepare_application(counts)
        payload.update(_child_body(role, extra, database))
        payload["ok"] = True
        code = 0
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        payload["traceback"] = traceback.format_exc()
        code = 1
    payload["route_refusals"] = list(counts["route"])
    payload["socket_blocks"] = list(counts["socket"])
    payload["dns_blocks"] = len(counts["dns"])
    payload["dotenv_stubs"] = len(counts["dotenv"])
    payload["real_broker_calls"] = len(counts["broker"])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return code


def _child_body(role: str, extra: list[str], database) -> dict[str, object]:
    from forex_bot.database import (
        _symbol_reservation_lock_key,
        client_order_id_exists_in_db,
        confirm_exposure_flat,
        exposure_entry_block_reason,
        fetch_exec_orders_open_for_recovery,
        insert_exec_order_pending_if_absent,
        read_durable_recovery,
    )
    from forex_bot.database import update_exec_order_row
    from forex_bot.orders import (
        OrderStatus,
        finalize_order_fill,
        ingest_recovery_snapshot,
        try_begin_order_submission,
        update_order,
    )
    opened = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
    if role == "schema":
        conn = database.get_connection()
        if conn is None:
            raise RuntimeError("schema connection failed")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
        return {"tables": tables, "fail_closed": database._process_fail_closed}
    if role == "empty":
        rows, readable = read_durable_recovery()
        result, dispatches = _evaluate_blocked(opened)
        return {
            "rows": len(rows),
            "readable": readable,
            "fail_closed": database._process_fail_closed,
            "blocked_by": result.get("blocked_by"),
            "inert_dispatches": dispatches,
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
        }
    if role == "persist":
        symbol = extra[0]
        cid = extra[1]
        begun = try_begin_order_submission(
            client_order_id=cid, symbol=symbol, direction="BUY", units=1000, metadata={}
        )
        duplicate = try_begin_order_submission(
            client_order_id=cid, symbol=symbol, direction="BUY", units=1000, metadata={}
        )
        wrote = update_exec_order_row(
            client_order_id=cid,
            status="FILLED",
            fill_price=1.1,
            broker_order_id="SIMULATED",
            metadata={"exposure_safety": "UNCONFIRMED"},
            filled_units=1000,
        )
        update_order(cid, status=OrderStatus.FILLED, units_filled=1000, avg_fill_price=1.1)
        exists = client_order_id_exists_in_db(cid)
        recovered = fetch_exec_orders_open_for_recovery()
        mine = [row for row in recovered if row["client_order_id"] == cid]
        return {
            "begun": begun,
            "duplicate_reported_success": duplicate,
            "wrote": wrote,
            "exists": exists,
            "stored_status": mine[0]["status"] if mine else None,
            "stored_symbol": mine[0]["symbol"] if mine else None,
        }
    if role == "insert":
        symbol, cid = extra
        begun = insert_exec_order_pending_if_absent(
            client_order_id=cid, symbol=symbol, side="BUY", units=1000, metadata={}
        )
        return {
            "begun": begun,
            "exists": client_order_id_exists_in_db(cid),
            "fail_closed": database._process_fail_closed,
            "block": exposure_entry_block_reason(symbol),
        }
    if role == "race":
        gate = Path(extra[0])
        symbol, cid = extra[1], extra[2]
        while not gate.exists():
            time.sleep(0.02)
        begun = insert_exec_order_pending_if_absent(
            client_order_id=cid, symbol=symbol, side="BUY", units=1000, metadata={}
        )
        return {"begun": begun, "exists": client_order_id_exists_in_db(cid)}
    if role == "lock_hold":
        ready = Path(extra[0])
        release = Path(extra[1])
        symbol = extra[2]
        conn = database.get_connection()
        if conn is None:
            raise RuntimeError("lock connection unavailable")
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_symbol_reservation_lock_key(symbol),))
        ready.write_text("ready", encoding="ascii")
        while not release.exists():
            time.sleep(0.05)
        conn.rollback()
        return {"rolled_back": True}
    if role == "fail_insert":
        symbol, cid = extra
        begun = insert_exec_order_pending_if_absent(
            client_order_id=cid, symbol=symbol, side="BUY", units=1000, metadata={}
        )
        result, dispatches = _evaluate_blocked(opened, symbol)
        return {
            "begun": begun,
            "exists": client_order_id_exists_in_db(cid),
            "fail_closed": database._process_fail_closed,
            "blocked_by": result.get("blocked_by"),
            "inert_dispatches": dispatches,
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
        }
    if role == "create_state":
        kind, symbol, cid = extra
        if kind == "filled":
            result, dispatches = _evaluate(symbol, "filled", opened)
            return {
                "client_order_id": result.get("client_order_id"),
                "blocked_by": result.get("blocked_by"),
                "inert_dispatches": dispatches,
                "production_eligible": result.get("production_eligible"),
            }
        begun = try_begin_order_submission(
            client_order_id=cid, symbol=symbol, direction="BUY", units=1000, metadata={}
        )
        if kind == "pending":
            return {"begun": begun, "client_order_id": cid, "inert_dispatches": 0}
        if kind == "partial":
            finalize_order_fill(
                cid,
                broker_order_id="SIMULATED",
                fill_price=1.1,
                units_filled=400,
                status=OrderStatus.PARTIAL,
            )
            return {"begun": begun, "client_order_id": cid, "inert_dispatches": 0}
        wrote = update_exec_order_row(
            client_order_id=cid,
            status="UNRESOLVED",
            metadata={"reason": "ambiguous_broker_outcome", "exposure_safety": "UNCONFIRMED"},
        )
        update_order(cid, status=OrderStatus.UNRESOLVED)
        return {"begun": begun, "wrote": wrote, "client_order_id": cid, "inert_dispatches": 0}
    if role == "recover":
        symbol = extra[0]
        started = _startup_recover(symbol)
        result, dispatches = _evaluate(symbol, "filled", opened.replace(minute=1))
        from forex_bot.database import confirm_exposure_flat as flat

        return {
            **started,
            "blocked_by": result.get("blocked_by"),
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
            "inert_dispatches": dispatches,
            "production_eligible": result.get("production_eligible"),
            "exposure": exposure_entry_block_reason(symbol),
            "flat_cleared": flat(symbol, evidence="CONFIRMED_FLAT"),
            "exposure_after_flat": exposure_entry_block_reason(symbol),
            "second_blocked_by": _evaluate(symbol, "filled", opened.replace(minute=2))[0].get("blocked_by"),
        }
    if role == "conn_fail":
        rows, readable = read_durable_recovery()
        result, dispatches = _evaluate_blocked(opened)
        return {
            "rows": rows,
            "readable": readable,
            "fail_closed": database._process_fail_closed,
            "blocked_by": result.get("blocked_by"),
            "inert_dispatches": dispatches,
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
        }
    if role == "query_fail":
        try:
            fetch_exec_orders_open_for_recovery()
            raised = ""
        except database.OrderRecoveryUnreadable as exc:
            raised = str(exc)
        result, dispatches = _evaluate_blocked(opened)
        return {
            "raised": raised,
            "fail_closed": database._process_fail_closed,
            "blocked_by": result.get("blocked_by"),
            "inert_dispatches": dispatches,
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
        }
    if role == "explicit_false":
        try:
            ingest_recovery_snapshot([], False)
            raised = ""
        except database.OrderRecoveryUnreadable as exc:
            raised = type(exc).__name__
        result, dispatches = _evaluate_blocked(opened)
        return {
            "raised": raised,
            "fail_closed": database._process_fail_closed,
            "blocked_by": result.get("blocked_by"),
            "inert_dispatches": dispatches,
            "flat_cleared": confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT"),
            "blocked_after_flat": _evaluate_blocked(opened.replace(minute=2))[0].get("blocked_by"),
        }
    if role == "negative":
        import psycopg2

        try:
            psycopg2.connect(host="localhost", port=5432, dbname="trading", user="postgres", password="password")
            refused = False
        except RuntimeError as exc:
            refused = str(exc) == "R24_ROUTE_REFUSED"
        return {"refused": refused, "route_recorded": True}
    raise RuntimeError(f"unknown role {role}")


def _evaluate_blocked(when: datetime, symbol: str = "EUR_USD"):
    from forex_bot.bot_loop import IterationDependencies, evaluate

    broker = _broker("filled")
    deps = IterationDependencies(
        candles=_bars(),
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
        strategy_name="scalp",
        strategy_active_map={"scalp": True},
        invoke_selector=False,
        invoke_vote=True,
        invoke_rl=False,
        vote=None,
    )
    return _drive(evaluate(symbol, deps)), broker.request_count


def _spawn(role: str, name: str, args: list[str]) -> subprocess.Popen:
    TRACES.mkdir(parents=True, exist_ok=True)
    result = TRACES / f"{name}.json"
    if result.exists():
        result.unlink()
    proc = subprocess.Popen(
        [sys.executable, "-B", str(Path(__file__)), "child", role, str(result), *args],
        cwd=str(ROOT),
        env=_clean_env(),
    )
    return proc


def _finish(proc: subprocess.Popen, name: str, timeout: float = 90) -> dict:
    proc.wait(timeout=timeout)
    path = TRACES / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["exit_code"] = proc.returncode
    data["pid"] = proc.pid
    return data


def _admin_sql(statements: list[str]) -> None:
    conn = _bootstrap_connect(DATABASE)
    conn.autocommit = True
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.close()


def run_all() -> dict[str, object]:
    TRACES.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"bootstrap": bootstrap()}
    schema = _finish(_spawn("schema", "schema", []), "schema")
    report["schema"] = schema
    if not schema.get("ok"):
        return report
    report["empty"] = _finish(_spawn("empty", "empty", []), "empty")
    _admin_sql(["ALTER TABLE exec_orders DROP COLUMN client_order_id"])
    try:
        report["query_fail"] = _finish(_spawn("query_fail", "query_fail", []), "query_fail")
    finally:
        _admin_sql(
            [
                "ALTER TABLE exec_orders ADD COLUMN client_order_id TEXT",
                "ALTER TABLE exec_orders ALTER COLUMN client_order_id SET NOT NULL",
                "ALTER TABLE exec_orders ADD CONSTRAINT exec_orders_client_order_id_key UNIQUE (client_order_id)",
            ]
        )
    _admin_sql([f"REVOKE CONNECT ON DATABASE {DATABASE} FROM {APP_ROLE}"])
    try:
        report["conn_fail"] = _finish(_spawn("conn_fail", "conn_fail", []), "conn_fail")
    finally:
        _admin_sql([f"GRANT CONNECT ON DATABASE {DATABASE} TO {APP_ROLE}"])
    report["explicit_false"] = _finish(_spawn("explicit_false", "explicit_false", []), "explicit_false")
    report["persist"] = _finish(
        _spawn("persist", "persist", ["USD_CHF", "cid-r24-persist"]),
        "persist",
    )
    _admin_sql(
        [
            """
            CREATE OR REPLACE FUNCTION r24_reject_insert() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'r24_insert_rejected';
            END;
            $$
            """,
            """
            CREATE TRIGGER r24_reject_insert
            BEFORE INSERT ON exec_orders
            FOR EACH ROW EXECUTE FUNCTION r24_reject_insert()
            """,
        ]
    )
    try:
        report["fail_insert"] = _finish(
            _spawn("fail_insert", "fail_insert", ["EUR_GBP", "cid-r24-fail"]),
            "fail_insert",
        )
    finally:
        _admin_sql(
            [
                "DROP TRIGGER IF EXISTS r24_reject_insert ON exec_orders",
                "DROP FUNCTION IF EXISTS r24_reject_insert()",
            ]
        )
    report["insert_after_rollback"] = _finish(
        _spawn("insert", "insert_after", ["EUR_GBP", "cid-r24-after"]),
        "insert_after",
    )
    gate = TRACES / "race.gate"
    if gate.exists():
        gate.unlink()
    first = _spawn("race", "race_a", [str(gate), "NZD_USD", "cid-r24-race-a"])
    second = _spawn("race", "race_b", [str(gate), "NZD_USD", "cid-r24-race-b"])
    time.sleep(0.8)
    gate.write_text("go", encoding="ascii")
    report["race"] = {
        "a": _finish(first, "race_a"),
        "b": _finish(second, "race_b"),
    }
    ready = TRACES / "lock.ready"
    release = TRACES / "lock.release"
    for path in (ready, release):
        if path.exists():
            path.unlink()
    holder = _spawn("lock_hold", "lock_hold", [str(ready), str(release), "EUR_AUD"])
    deadline = time.time() + 20
    while not ready.exists():
        if holder.poll() is not None or time.time() > deadline:
            break
        time.sleep(0.05)
    waiter = _spawn("insert", "lock_waiter", ["EUR_AUD", "cid-r24-lock"])
    time.sleep(1.0)
    release.write_text("release", encoding="ascii")
    report["lock"] = {
        "holder": _finish(holder, "lock_hold"),
        "waiter": _finish(waiter, "lock_waiter", timeout=30),
    }
    scenarios = [
        ("filled", "EUR_USD", "cid-r24-filled"),
        ("unresolved", "GBP_USD", "cid-r24-unresolved"),
        ("pending", "AUD_USD", "cid-r24-pending"),
        ("partial", "USD_CAD", "cid-r24-partial"),
    ]
    recovery = []
    for kind, symbol, cid in scenarios:
        created_proc = _spawn("create_state", f"create_{kind}", [kind, symbol, cid])
        created = _finish(created_proc, f"create_{kind}")
        if created_proc.returncode != 0 or created_proc.poll() is None:
            recovery.append({"kind": kind, "create": created, "recover": None})
            continue
        recovered = _finish(_spawn("recover", f"recover_{kind}", [symbol]), f"recover_{kind}")
        recovery.append(
            {
                "kind": kind,
                "symbol": symbol,
                "create_pid": created["pid"],
                "create_exit": created["exit_code"],
                "recover_pid": recovered["pid"],
                "recover_exit": recovered["exit_code"],
                "create": created,
                "recover": recovered,
                "a_exited_before_b": created["exit_code"] == 0 and recovered["pid"] != created["pid"],
            }
        )
    report["recovery"] = recovery
    report["negative"] = _finish(_spawn("negative", "negative", []), "negative")
    return report


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(2)
    if sys.argv[1] == "child":
        return child(sys.argv[2], Path(sys.argv[3]), sys.argv[4:])
    if sys.argv[1] == "run":
        try:
            report = run_all()
            ok = True
        except Exception as exc:
            report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
            ok = False
        (TRACES / "integration_raw.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0 if ok else 1
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
