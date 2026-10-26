"""Post-repair checks against the isolated R.24 cluster. Inert broker only."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 55432
DATABASE = "r24_synthetic_orders"
USER = "r24_tester"
PASSWORD = Path(r"C:\R24_PostgreSQL_Test\secrets\tester.txt").read_text(encoding="ascii").strip()
OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)


def _connect():
    import psycopg2

    return psycopg2.connect(host=HOST, port=PORT, dbname=DATABASE, user=USER, password=PASSWORD)


def _barriers() -> None:
    class _Guarded(socket.socket):
        def connect(self, address):  # noqa: ANN001
            host = str(address[0]) if isinstance(address, tuple) else ""
            port = int(address[1]) if isinstance(address, tuple) and len(address) > 1 else None
            if host != HOST or port != PORT:
                raise RuntimeError("R28_NETWORK_BLOCKED")
            return super().connect(address)

    def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R28_DNS_BLOCKED")

    socket.socket = _Guarded  # type: ignore[misc]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    socket.gethostbyname = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_a, **_k: False  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv


def _boot() -> None:
    _barriers()
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PERSIST_EXEC_ORDERS"] = "1"
    os.environ["POSTGRES_HOST"] = HOST
    os.environ["POSTGRES_PORT"] = str(PORT)
    os.environ["POSTGRES_DB"] = DATABASE
    os.environ["POSTGRES_USER"] = USER
    os.environ["POSTGRES_PASS"] = PASSWORD
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(OUT / "synthetic_live_safety_state.json")
    os.environ["FOREX_SYMBOLS"] = "EUR_USD,GBP_USD,AUD_USD,USD_CAD,NZD_USD"
    sys.path.insert(0, str(ROOT))


def _child_race(symbol: str, client_id: str, ready: str, gate: str) -> None:
    _boot()
    Path(ready).write_text("ready", encoding="ascii")
    while not Path(gate).exists():
        time.sleep(0.02)
    notes: list[str] = []

    class _Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            notes.append(record.getMessage())

    logging.getLogger("forex_bot.database").addHandler(_Grab())
    from forex_bot.database import client_order_id_exists_in_db, insert_exec_order_pending_if_absent

    begun = insert_exec_order_pending_if_absent(
        client_order_id=client_id, symbol=symbol, side="BUY", units=1000, metadata={}
    )
    print(json.dumps({"pid": os.getpid(), "begun": begun, "exists": client_order_id_exists_in_db(client_id), "notes": notes}))


def _child_fail(symbol: str, client_id: str, ready: str, release: str) -> None:
    _boot()
    from forex_bot.database import client_order_id_exists_in_db, insert_exec_order_pending_if_absent

    begun = insert_exec_order_pending_if_absent(
        client_order_id=client_id, symbol=symbol, side="BUY", units=1000, metadata={}
    )
    Path(ready).write_text("ready", encoding="ascii")
    while not Path(release).exists():
        time.sleep(0.05)
    print(json.dumps({"pid": os.getpid(), "begun": begun, "exists": client_order_id_exists_in_db(client_id)}))


def _child_insert(symbol: str, client_id: str) -> None:
    _boot()
    from forex_bot.database import client_order_id_exists_in_db, insert_exec_order_pending_if_absent

    begun = insert_exec_order_pending_if_absent(
        client_order_id=client_id, symbol=symbol, side="BUY", units=1000, metadata={}
    )
    print(json.dumps({"pid": os.getpid(), "begun": begun, "exists": client_order_id_exists_in_db(client_id)}))


def _child_recover() -> None:
    _boot()
    import importlib.util

    from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration
    from forex_bot.database import exposure_entry_block_reason
    from forex_bot.orders import load_open_orders_from_db_into_memory

    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    load_open_orders_from_db_into_memory()
    results = []
    for symbol in ("EUR_USD", "GBP_USD", "AUD_USD", "USD_CAD"):
        broker = module.FakeBroker("filled")
        result = evaluate_one_instrument_iteration(
            symbol,
            IterationDependencies(
                candles=[
                    {
                        "open": 1.1,
                        "high": 1.1002,
                        "low": 1.0998,
                        "close": 1.1,
                        "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
                    }
                    for index in range(50)
                ],
                balance=10000.0,
                account_present=True,
                account_context="isolated_test",
                simulation=True,
                now=OPEN,
                quote_as_of=OPEN,
                account_as_of=OPEN,
                unrealised=0.0,
                price=1.1,
                bid=1.09995,
                ask=1.10005,
                stop_distance=0.001,
                stop_loss=1.099,
                take_profit=1.102,
                broker=broker,
                strategy_name="scalp",
                strategy_known=True,
                strategy_active=True,
                strategy_authorised=True,
                safety_initialised=True,
                vote={"allow": True, "direction": "BUY", "confidence": 0.8},
                account_payload={"id": "101-004-1435156-001"},
                expected_account_id="101-004-1435156-001",
            ),
        )
        results.append(
            {
                "symbol": symbol,
                "blocked_by": result.get("blocked_by"),
                "broker_requests": broker.request_count,
                "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
                "production_eligible": result.get("production_eligible"),
                "exposure": exposure_entry_block_reason(symbol),
            }
        )
    print(json.dumps({"pid": os.getpid(), "results": results}))


def _child_risk(state: str) -> None:
    _boot()
    import importlib.util

    os.environ["RISK_STATE_PATH"] = state
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
    os.environ["RISK_ACCOUNT_ID"] = "101-004-1435156-001"
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration

    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    broker = module.FakeBroker("filled")
    summary = {
        "observed_at": OPEN.isoformat(),
        "account": {
            "id": "101-004-1435156-001",
            "currency": "USD",
            "balance": "10000.0000",
            "unrealizedPL": "0.0000",
            "positions": [],
            "orders": [],
        },
    }
    result = evaluate_one_instrument_iteration(
        "NZD_USD",
        IterationDependencies(
            candles=[
                {
                    "open": 1.1,
                    "high": 1.1002,
                    "low": 1.0998,
                    "close": 1.1,
                    "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
                }
                for index in range(50)
            ],
            balance=10000.0,
            account_present=True,
            account_context="isolated_test",
            simulation=True,
            now=OPEN,
            quote_as_of=OPEN,
            account_as_of=OPEN,
            unrealised=0.0,
            price=1.1,
            bid=1.09995,
            ask=1.10005,
            stop_distance=0.001,
            stop_loss=1.099,
            take_profit=1.102,
            broker=broker,
            strategy_name="scalp",
            strategy_known=True,
            strategy_active=True,
            strategy_authorised=True,
            safety_initialised=True,
            vote={"allow": True, "direction": "BUY", "confidence": 0.8},
            account_payload={"id": "101-004-1435156-001"},
            expected_account_id="101-004-1435156-001",
            expected_account_currency="USD",
            oanda_summary=summary,
            oanda_transactions={"lastTransactionID": "0", "transactions": []},
        ),
    )
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "blocked_by": result.get("blocked_by"),
                "broker_requests": broker.request_count,
                "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
                "production_eligible": result.get("production_eligible"),
                "phases": list(result.get("phases") or []),
            }
        )
    )


def _run(role: str, *args: str) -> dict:
    proc = subprocess.Popen(
        [sys.executable, "-B", str(Path(__file__)), role, *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(timeout=90)
    if proc.returncode != 0 or not stdout.strip():
        raise RuntimeError(stderr or stdout)
    payload = json.loads(stdout)
    payload["exit_code"] = proc.returncode
    return payload


def _column_present(name: str) -> bool:
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'exec_orders' AND column_name = %s
            """,
            (name,),
        )
        found = cur.fetchone() is not None
    conn.close()
    return found


def _count(symbol: str) -> int:
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM exec_orders WHERE symbol = %s", (symbol,))
        count = int(cur.fetchone()[0])
    conn.close()
    return count


def _cleanup() -> None:
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM exec_orders
            WHERE symbol LIKE 'R28%%'
               OR client_order_id LIKE 'cid-r28%%'
               OR symbol IN ('EUR_USD', 'GBP_USD', 'AUD_USD', 'USD_CAD', 'NZD_USD')
            """
        )
        cur.execute("DROP TRIGGER IF EXISTS r28_reject_insert ON exec_orders")
        cur.execute("DROP FUNCTION IF EXISTS r28_reject_insert()")
        if not _column_present("filled_units"):
            cur.execute("ALTER TABLE exec_orders ADD COLUMN filled_units DOUBLE PRECISION")
    conn.close()


def main() -> int:
    role = sys.argv[1] if len(sys.argv) > 1 else "parent"
    if role == "race":
        _child_race(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return 0
    if role == "fail":
        _child_fail(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return 0
    if role == "insert":
        _child_insert(sys.argv[2], sys.argv[3])
        return 0
    if role == "recover":
        _child_recover()
        return 0
    if role == "risk":
        _child_risk(sys.argv[2])
        return 0
    report: dict[str, object] = {}
    try:
        parallel = []
        deadlocks = 0
        for index in range(12):
            symbol = f"R28P{index}"
            gate = OUT / f"race-{index}.gate"
            ready_paths = [OUT / f"race-{index}-{side}.ready" for side in ("a", "b")]
            for path in (gate, *ready_paths):
                if path.exists():
                    path.unlink()
            procs = [
                subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        str(Path(__file__)),
                        "race",
                        symbol,
                        f"cid-r28-p-{index}-{side}",
                        str(ready),
                        str(gate),
                    ],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for side, ready in zip(("a", "b"), ready_paths)
            ]
            deadline = time.time() + 40
            while not all(path.exists() for path in ready_paths):
                if any(proc.poll() is not None for proc in procs) or time.time() > deadline:
                    break
                time.sleep(0.05)
            gate.write_text("go", encoding="ascii")
            rows = []
            for proc in procs:
                stdout, stderr = proc.communicate(timeout=60)
                payload = json.loads(stdout) if stdout.strip() else {"error": stderr[-400:]}
                rows.append(payload)
                if any("deadlock detected" in note for note in payload.get("notes") or []):
                    deadlocks += 1
            parallel.append(
                {
                    "symbol": symbol,
                    "pids": [row.get("pid") for row in rows],
                    "begun": sum(1 for row in rows if row.get("begun") is True),
                    "exists": sum(1 for row in rows if row.get("exists") is True),
                    "stored": _count(symbol),
                }
            )
        report["parallel"] = {"deadlocks": deadlocks, "rounds": parallel}
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION r28_reject_insert() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'r28_insert_rejected';
                END;
                $$
                """
            )
            cur.execute(
                """
                CREATE TRIGGER r28_reject_insert
                BEFORE INSERT ON exec_orders
                FOR EACH ROW EXECUTE FUNCTION r28_reject_insert()
                """
            )
        conn.close()
        ready = OUT / "fail.ready"
        release = OUT / "fail.release"
        for path in (ready, release):
            if path.exists():
                path.unlink()
        holder = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__)), "fail", "R28FAIL", "cid-r28-fail", str(ready), str(release)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 30
        while not ready.exists():
            if holder.poll() is not None or time.time() > deadline:
                break
            time.sleep(0.05)
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DROP TRIGGER IF EXISTS r28_reject_insert ON exec_orders")
            cur.execute("DROP FUNCTION IF EXISTS r28_reject_insert()")
        conn.close()
        follower = _run("insert", "R28FAIL", "cid-r28-after-fail")
        release.write_text("go", encoding="ascii")
        stdout, stderr = holder.communicate(timeout=30)
        failed = json.loads(stdout) if stdout.strip() else {"error": stderr[-400:]}
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DROP TRIGGER IF EXISTS r28_reject_insert ON exec_orders")
            cur.execute("DROP FUNCTION IF EXISTS r28_reject_insert()")
        conn.close()
        report["forced_failure"] = {
            "holder_pid": failed.get("pid"),
            "holder_begun": failed.get("begun"),
            "holder_exists": failed.get("exists"),
            "follower": follower,
            "rows": _count("R28FAIL"),
        }
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE exec_orders DROP COLUMN filled_units")
        conn.close()
        missing = _run("insert", "R28SCHEMA", "cid-r28-schema")
        still_missing = not _column_present("filled_units")
        conn = _connect()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE exec_orders ADD COLUMN filled_units DOUBLE PRECISION")
        conn.close()
        report["invalid_schema"] = {
            "insert": missing,
            "column_remained_absent": still_missing,
            "column_restored": _column_present("filled_units"),
            "rows": _count("R28SCHEMA"),
        }
        for symbol, cid, status in (
            ("EUR_USD", "cid-r28-pending", "PENDING"),
            ("GBP_USD", "cid-r28-filled", "FILLED"),
            ("AUD_USD", "cid-r28-partial", "PARTIAL"),
            ("USD_CAD", "cid-r28-unresolved", "UNRESOLVED"),
        ):
            _run("insert", symbol, cid)
            if status != "PENDING":
                conn = _connect()
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("UPDATE exec_orders SET status = %s WHERE client_order_id = %s", (status, cid))
                conn.close()
        report["recovery"] = _run("recover")
        state = OUT / "risk_state.json"
        state.write_text("{}", encoding="utf-8")
        report["risk"] = _run("risk", str(state))
        report["risk_rows"] = _count("NZD_USD")
    finally:
        _cleanup()
    (OUT / "post_repair_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "deadlocks": report["parallel"]["deadlocks"],
                "parallel_ok": all(item["begun"] == 1 and item["stored"] == 1 for item in report["parallel"]["rounds"]),
                "failure_ok": report["forced_failure"]["holder_begun"] is False and report["forced_failure"]["follower"]["begun"] is True,
                "schema_ok": report["invalid_schema"]["column_remained_absent"] is True and report["invalid_schema"]["insert"]["begun"] is False,
                "recovery_blocks": [item["blocked_by"] for item in report["recovery"]["results"]],
                "risk_block": report["risk"]["blocked_by"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
