"""PostgreSQL trade logging (lazy connection)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extensions import cursor as PGCursor

from forex_bot.config import Config

logger = logging.getLogger(__name__)

_pg_conn: PGConnection | None = None
_pg_cursor: PGCursor | None = None

CREATE_TRADES_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    time TIMESTAMP,
    symbol TEXT,
    strategy TEXT,
    direction TEXT,
    pnl DOUBLE PRECISION,
    size DOUBLE PRECISION,
    entry_price DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    trading_mode TEXT DEFAULT 'practice',
    execution_kind TEXT DEFAULT 'simulated'
);
"""

# Existing deployments created before trading_mode existed
ALTER_TRADING_MODE_SQL = "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trading_mode TEXT;"
ALTER_EXECUTION_KIND_SQL = "ALTER TABLE trades ADD COLUMN IF NOT EXISTS execution_kind TEXT;"


def get_connection() -> PGConnection | None:
    global _pg_conn, _pg_cursor
    if _pg_conn is not None and not _pg_conn.closed:
        return _pg_conn
    try:
        _pg_conn = psycopg2.connect(
            dbname=Config.POSTGRES.db,
            user=Config.POSTGRES.user,
            password=Config.POSTGRES.password,
            host=Config.POSTGRES.host,
            port=Config.POSTGRES.port,
        )
        _pg_cursor = _pg_conn.cursor()
        _pg_cursor.execute(CREATE_TRADES_SQL)
        _pg_cursor.execute(ALTER_TRADING_MODE_SQL)
        _pg_cursor.execute(ALTER_EXECUTION_KIND_SQL)
        _pg_conn.commit()
        return _pg_conn
    except Exception as exc:
        logger.warning("PostgreSQL unavailable: %s", exc)
        _pg_conn = None
        _pg_cursor = None
        return None


def log_trade_pg(
    symbol: str,
    strategy: str,
    direction: str,
    pnl: float,
    size: float,
    entry: float,
    exit_price: float,
    *,
    execution_kind: str = "simulated",
) -> None:
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return
    try:
        mode = (Config.TRADING_MODE or "practice").strip().lower()
        kind = (execution_kind or "simulated").strip().lower()
        _pg_cursor.execute(
            """
            INSERT INTO trades (
                time, symbol, strategy, direction, pnl, size, entry_price, exit_price, trading_mode, execution_kind
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                datetime.now(),
                symbol,
                strategy,
                direction,
                pnl,
                size,
                entry,
                exit_price,
                mode,
                kind,
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.error("log_trade_pg failed: %s", exc)
        conn.rollback()


def fetch_all_trades_ordered() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return []
    _pg_cursor.execute(
        """
        SELECT id, time, symbol, strategy, direction, pnl, size, entry_price, exit_price, trading_mode, execution_kind
        FROM trades ORDER BY time ASC
        """
    )
    rows = _pg_cursor.fetchall()
    cols = [
        "id",
        "time",
        "symbol",
        "strategy",
        "direction",
        "pnl",
        "size",
        "entry_price",
        "exit_price",
        "trading_mode",
        "execution_kind",
    ]
    return [dict(zip(cols, r)) for r in rows]


def fetch_strategy_analysis() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return []
    _pg_cursor.execute(
        """
        SELECT strategy, direction, AVG(pnl) AS avg_pnl, COUNT(*) AS cnt
        FROM trades
        GROUP BY strategy, direction
        """
    )
    rows = _pg_cursor.fetchall()
    return [
        {"strategy": r[0], "direction": r[1], "avg_pnl": float(r[2]) if r[2] is not None else 0.0, "count": r[3]}
        for r in rows
    ]
