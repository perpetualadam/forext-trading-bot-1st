"""Read-only dump of live trades / exec_orders / ledger. No writes."""
from __future__ import annotations

import json
import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor


def _ser(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _ser(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_ser(x) for x in v]
    return v


def main() -> None:
    conn = psycopg2.connect(
        dbname=os.environ.get("POSTGRES_DB", "trading"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASS", "password"),
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        connect_timeout=8,
    )
    conn.set_session(readonly=True, autocommit=True)
    out: dict = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, time, symbol, strategy, direction, pnl, size, entry_price, exit_price,
                   trading_mode, execution_kind, diagnostics
            FROM trades
            ORDER BY time ASC
            """
        )
        out["trades"] = [_ser(dict(r)) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT client_order_id, symbol, side, units, status, created_at, filled_at,
                   fill_price, filled_units, broker_order_id, metadata
            FROM exec_orders
            ORDER BY created_at ASC
            """
        )
        out["exec_orders"] = [_ser(dict(r)) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT closing_transaction_id, broker_trade_id, symbol, booked_at
            FROM broker_exit_ledger
            ORDER BY booked_at ASC
            """
        )
        out["broker_exit_ledger"] = [_ser(dict(r)) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) AS n FROM trades")
        out["trade_count"] = cur.fetchone()["n"]
    conn.close()
    dest = "/tmp/live_trade_dump.json"
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("trades", len(out["trades"]), "orders", len(out["exec_orders"]), "ledger", len(out["broker_exit_ledger"]))


if __name__ == "__main__":
    main()
