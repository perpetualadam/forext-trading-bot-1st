"""Reproduce the R.24 exec_orders lock cycle. Does not change application source."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = "127.0.0.1"
PORT = 55432
DATABASE = "r24_synthetic_orders"
USER = "r24_tester"
PASSWORD = Path(r"C:\R24_PostgreSQL_Test\secrets\tester.txt").read_text(encoding="ascii").strip()
OUT = Path(__file__).resolve().parent


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


def _connect():
    import psycopg2

    return psycopg2.connect(host=HOST, port=PORT, dbname=DATABASE, user=USER, password=PASSWORD)


def _controlled() -> dict:
    import psycopg2

    holder_error: list[str] = []
    alter_error: list[str] = []
    selected = threading.Event()
    alter_started = threading.Event()

    def hold() -> None:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM exec_orders LIMIT 1")
                cur.fetchone()
                selected.set()
                alter_started.wait(10)
                time.sleep(0.4)
                cur.execute(
                    """
                    INSERT INTO exec_orders (client_order_id, symbol, side, units, status, metadata)
                    VALUES ('cid-r28-lock-probe', 'R28_LOCK', 'BUY', 1, 'PENDING', '{}'::jsonb)
                    """
                )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            holder_error.append(f"{type(exc).__name__}: {exc}".splitlines()[0])
            conn.rollback()
        finally:
            conn.close()

    def alter() -> None:
        conn = _connect()
        try:
            selected.wait(10)
            with conn.cursor() as cur:
                alter_started.set()
                cur.execute("ALTER TABLE exec_orders ADD COLUMN IF NOT EXISTS filled_units DOUBLE PRECISION")
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            alter_error.append(f"{type(exc).__name__}: {exc}".splitlines()[0])
            conn.rollback()
        finally:
            conn.close()

    left = threading.Thread(target=hold)
    right = threading.Thread(target=alter)
    left.start()
    right.start()
    assert selected.wait(10)
    time.sleep(0.3)
    locks = []
    watch = _connect()
    watch.autocommit = True
    with watch.cursor() as cur:
        cur.execute("SELECT oid FROM pg_database WHERE datname = current_database()")
        database_oid = cur.fetchone()[0]
        cur.execute(
            """
            SELECT locktype, mode, granted, relation::text
            FROM pg_locks
            WHERE relation = 'public.exec_orders'::regclass
            ORDER BY granted DESC, mode
            """
        )
        locks = [list(row) for row in cur.fetchall()]
    watch.close()
    left.join(15)
    right.join(15)
    cleanup = _connect()
    cleanup.autocommit = True
    with cleanup.cursor() as cur:
        cur.execute("DELETE FROM exec_orders WHERE client_order_id = 'cid-r28-lock-probe'")
    cleanup.close()
    return {
        "database_oid": database_oid,
        "locks_while_alter_waited": locks,
        "holder_error": holder_error,
        "alter_error": alter_error,
        "deadlock": any("deadlock detected" in item for item in holder_error + alter_error),
    }


def _race_child(symbol: str, client_id: str) -> None:
    _barriers()
    os.environ["PERSIST_EXEC_ORDERS"] = "1"
    os.environ["POSTGRES_HOST"] = HOST
    os.environ["POSTGRES_PORT"] = str(PORT)
    os.environ["POSTGRES_DB"] = DATABASE
    os.environ["POSTGRES_USER"] = USER
    os.environ["POSTGRES_PASS"] = PASSWORD
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(OUT / "synthetic_live_safety_state.json")
    sys.path.insert(0, str(ROOT))
    notes: list[str] = []

    class _Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            notes.append(record.getMessage())

    logging.getLogger("forex_bot.database").addHandler(_Grab())
    from forex_bot.database import client_order_id_exists_in_db, insert_exec_order_pending_if_absent

    begun = insert_exec_order_pending_if_absent(
        client_order_id=client_id, symbol=symbol, side="BUY", units=1000, metadata={}
    )
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "begun": begun,
                "exists": client_order_id_exists_in_db(client_id),
                "notes": notes,
            }
        )
    )


def _race(rounds: int) -> dict:
    outcomes = []
    deadlocks = 0
    for index in range(rounds):
        symbol = f"R28S{index}"
        gate_processes = []
        for side, cid in (("a", f"cid-r28-{index}-a"), ("b", f"cid-r28-{index}-b")):
            proc = subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__)), "child", symbol, cid],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            gate_processes.append(proc)
        rows = []
        for proc in gate_processes:
            stdout, stderr = proc.communicate(timeout=60)
            payload = json.loads(stdout) if stdout.strip() else {"error": stderr[-500:]}
            payload["exit_code"] = proc.returncode
            rows.append(payload)
            if any("deadlock detected" in note for note in payload.get("notes") or []):
                deadlocks += 1
        begun = sum(1 for row in rows if row.get("begun") is True)
        exists = sum(1 for row in rows if row.get("exists") is True)
        outcomes.append({"symbol": symbol, "pids": [row.get("pid") for row in rows], "begun": begun, "exists": exists, "rows": rows})
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, count(*) FROM exec_orders WHERE symbol LIKE 'R28S%%' GROUP BY symbol ORDER BY symbol")
        stored = cur.fetchall()
        cur.execute("DELETE FROM exec_orders WHERE symbol LIKE 'R28S%%'")
    conn.close()
    return {"rounds": rounds, "deadlocks": deadlocks, "stored_before_cleanup": stored, "outcomes": outcomes}


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        _race_child(sys.argv[2], sys.argv[3])
        return 0
    report = {"controlled": _controlled(), "application_race": _race(8)}
    (OUT / "lock_cycle_before.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"deadlock": report["controlled"]["deadlock"], "race_deadlocks": report["application_race"]["deadlocks"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
