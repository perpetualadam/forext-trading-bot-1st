"""Confirm the isolated listener before any reservation test. Prints no secrets."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg2

HOST = "127.0.0.1"
PORT = 55432
DATABASE = "r24_synthetic_orders"
USER = "r24_tester"
PASSWORD = Path(r"C:\R24_PostgreSQL_Test\secrets\tester.txt").read_text(encoding="ascii").strip()

conn = psycopg2.connect(host=HOST, port=PORT, dbname=DATABASE, user=USER, password=PASSWORD)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(
        """
        SELECT inet_server_addr()::text, inet_server_port(), current_database(),
               current_user, pg_postmaster_start_time()::text
        """
    )
    identity = cur.fetchone()
    cur.execute(
        """
        SELECT c.oid, n.nspname, c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.oid
        """
    )
    relations = cur.fetchall()
    cur.execute(
        """
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'public.exec_orders'::regclass
        ORDER BY conname
        """
    )
    constraints = cur.fetchall()
conn.close()
print(
    json.dumps(
        {
            "identity": identity,
            "relations": relations,
            "constraints": constraints,
        },
        default=str,
    )
)
