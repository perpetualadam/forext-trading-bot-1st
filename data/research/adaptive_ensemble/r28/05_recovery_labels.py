"""Print recovery labels for the four statuses, then restore the R.24 race row."""

from __future__ import annotations

import json
import os
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST, PORT, DATABASE, USER = "127.0.0.1", 55432, "r24_synthetic_orders", "r24_tester"
PASSWORD = Path(r"C:\R24_PostgreSQL_Test\secrets\tester.txt").read_text(encoding="ascii").strip()


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
os.environ["PERSIST_EXEC_ORDERS"] = "1"
os.environ["POSTGRES_HOST"] = HOST
os.environ["POSTGRES_PORT"] = str(PORT)
os.environ["POSTGRES_DB"] = DATABASE
os.environ["POSTGRES_USER"] = USER
os.environ["POSTGRES_PASS"] = PASSWORD
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402
from forex_bot.database import (  # noqa: E402
    client_order_id_exists_in_db,
    exposure_entry_block_reason,
    insert_exec_order_pending_if_absent,
)
from forex_bot.orders import load_open_orders_from_db_into_memory  # noqa: E402

conn = psycopg2.connect(host=HOST, port=PORT, dbname=DATABASE, user=USER, password=PASSWORD)
conn.autocommit = True
rows = [
    ("EUR_USD", "cid-r28-label-pending", "PENDING"),
    ("GBP_USD", "cid-r28-label-filled", "FILLED"),
    ("AUD_USD", "cid-r28-label-partial", "PARTIAL"),
    ("USD_CAD", "cid-r28-label-unresolved", "UNRESOLVED"),
]
with conn.cursor() as cur:
    for symbol, cid, status in rows:
        cur.execute(
            """
            INSERT INTO exec_orders (client_order_id, symbol, side, units, status, metadata)
            VALUES (%s, %s, 'BUY', 1, %s, '{}'::jsonb)
            """,
            (cid, symbol, status),
        )
    cur.execute(
        "SELECT symbol, client_order_id, status FROM exec_orders WHERE client_order_id LIKE 'cid-r28-label%%' ORDER BY symbol"
    )
    stored = cur.fetchall()
load_open_orders_from_db_into_memory()
labels = {symbol: exposure_entry_block_reason(symbol) for symbol, _cid, _status in rows}
first = insert_exec_order_pending_if_absent(
    client_order_id="cid-r28-dup", symbol="R28DUP", side="BUY", units=1, metadata={}
)
second = insert_exec_order_pending_if_absent(
    client_order_id="cid-r28-dup", symbol="R28DUP2", side="BUY", units=1, metadata={}
)
with conn.cursor() as cur:
    cur.execute("DELETE FROM exec_orders WHERE client_order_id LIKE 'cid-r28-label%%' OR client_order_id = 'cid-r28-dup'")
    cur.execute("SELECT 1 FROM exec_orders WHERE symbol = 'NZD_USD'")
    missing_race = cur.fetchone() is None
    if missing_race:
        cur.execute(
            """
            INSERT INTO exec_orders (client_order_id, symbol, side, units, status, metadata)
            VALUES ('cid-r24-race-b', 'NZD_USD', 'BUY', 1000, 'PENDING', '{}'::jsonb)
            """
        )
print(json.dumps({"stored": stored, "labels": labels, "duplicate_first": first, "duplicate_second": second, "duplicate_exists": client_order_id_exists_in_db("cid-r28-dup"), "restored_nzd": missing_race}))
conn.close()
