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

CREATE_RECONCILE_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS reconcile_metadata (
    singleton SMALLINT PRIMARY KEY CHECK (singleton = 1),
    last_run_utc TIMESTAMPTZ,
    last_success BOOLEAN,
    last_error TEXT,
    mismatch_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0
);
"""

CREATE_OPERATIONAL_EVENT_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS operational_event_log (
    id BIGSERIAL PRIMARY KEY,
    ts_utc TIMESTAMPTZ NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    detail TEXT
);
"""

CREATE_OPERATIONAL_EVENT_LOG_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_operational_event_log_id_desc ON operational_event_log (id DESC);"
)


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
        _pg_cursor.execute(CREATE_RECONCILE_METADATA_SQL)
        _pg_cursor.execute(CREATE_OPERATIONAL_EVENT_LOG_TABLE_SQL)
        _pg_cursor.execute(CREATE_OPERATIONAL_EVENT_LOG_INDEX_SQL)
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


def fetch_reconcile_metadata() -> dict[str, Any] | None:
    """Last persisted reconcile row (singleton), or None if missing / DB unavailable."""
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return None
    try:
        _pg_cursor.execute(
            """
            SELECT last_run_utc, last_success, last_error, mismatch_count, critical_count, warning_count
            FROM reconcile_metadata WHERE singleton = 1
            """
        )
        row = _pg_cursor.fetchone()
        if row is None:
            return None
        ts = row[0]
        last_run = ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else None
        return {
            "last_run_utc": last_run,
            "last_success": row[1],
            "last_error": row[2],
            "mismatch_count": row[3] if row[3] is not None else 0,
            "critical_count": row[4] if row[4] is not None else 0,
            "warning_count": row[5] if row[5] is not None else 0,
        }
    except Exception as exc:
        logger.debug("fetch_reconcile_metadata: %s", exc)
        return None


def upsert_reconcile_metadata(
    *,
    last_run_utc: str | None,
    last_success: bool | None,
    last_error: str | None,
    mismatch_count: int,
    critical_count: int,
    warning_count: int,
) -> None:
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return
    try:
        _pg_cursor.execute(
            """
            INSERT INTO reconcile_metadata (
                singleton, last_run_utc, last_success, last_error,
                mismatch_count, critical_count, warning_count
            ) VALUES (1, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (singleton) DO UPDATE SET
                last_run_utc = EXCLUDED.last_run_utc,
                last_success = EXCLUDED.last_success,
                last_error = EXCLUDED.last_error,
                mismatch_count = EXCLUDED.mismatch_count,
                critical_count = EXCLUDED.critical_count,
                warning_count = EXCLUDED.warning_count
            """,
            (
                last_run_utc,
                last_success,
                last_error,
                mismatch_count,
                critical_count,
                warning_count,
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("upsert_reconcile_metadata failed: %s", exc)
        conn.rollback()


def append_operational_event_log(
    *,
    ts_utc_iso: str,
    from_state: str | None,
    to_state: str,
    detail: str,
) -> None:
    """Append-only row; mirrors in-memory operational event deque."""
    conn = get_connection()
    if conn is None or _pg_cursor is None:
        return
    try:
        _pg_cursor.execute(
            """
            INSERT INTO operational_event_log (ts_utc, from_state, to_state, detail)
            VALUES (%s, %s, %s, %s)
            """,
            (
                ts_utc_iso,
                from_state,
                to_state,
                detail,
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("append_operational_event_log failed: %s", exc)
        conn.rollback()


def fetch_recent_operational_event_logs(limit: int) -> list[dict[str, Any]]:
    """Last ``limit`` rows by id, returned oldest-first (chronological)."""
    conn = get_connection()
    if conn is None or _pg_cursor is None or limit <= 0:
        return []
    try:
        _pg_cursor.execute(
            """
            SELECT id, ts_utc, from_state, to_state, detail
            FROM (
                SELECT id, ts_utc, from_state, to_state, detail
                FROM operational_event_log
                ORDER BY id DESC
                LIMIT %s
            ) t
            ORDER BY id ASC
            """,
            (limit,),
        )
        rows = _pg_cursor.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            ts = r[1]
            ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else ""
            out.append(
                {
                    "id": r[0],
                    "ts_utc": ts_iso,
                    "from_state": r[2],
                    "to_state": r[3],
                    "detail": r[4] or "",
                }
            )
        return out
    except Exception as exc:
        logger.debug("fetch_recent_operational_event_logs: %s", exc)
        return []
