"""PostgreSQL trade logging (lazy connection)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json
from psycopg2.extensions import connection as PGConnection
from psycopg2.extensions import cursor as PGCursor

from forex_bot.config import Config

logger = logging.getLogger(__name__)

_pg_conn: PGConnection | None = None
_pg_cursor: PGCursor | None = None
_pg_lock = threading.RLock()
_partial_cleanup_notes: list[str] = []

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
ALTER_TRADES_DIAGNOSTICS_SQL = "ALTER TABLE trades ADD COLUMN IF NOT EXISTS diagnostics JSONB;"

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

CREATE_EXEC_ORDERS_SQL = """
CREATE TABLE IF NOT EXISTS exec_orders (
    id SERIAL PRIMARY KEY,
    client_order_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    units DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    fill_price DOUBLE PRECISION,
    broker_order_id TEXT,
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS idx_exec_orders_status ON exec_orders (status);
CREATE INDEX IF NOT EXISTS idx_exec_orders_created ON exec_orders (created_at DESC);
"""

ALTER_EXEC_ORDERS_FILLED_UNITS_SQL = (
    "ALTER TABLE exec_orders ADD COLUMN IF NOT EXISTS filled_units DOUBLE PRECISION;"
)

CREATE_BROKER_EXIT_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS broker_exit_ledger (
    closing_transaction_id TEXT NOT NULL,
    broker_trade_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    booked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (closing_transaction_id, broker_trade_id)
);
"""

CREATE_BROKER_EXIT_PENDING_SQL = """
CREATE TABLE IF NOT EXISTS broker_exit_pending (
    symbol TEXT PRIMARY KEY,
    broker_trade_id TEXT NOT NULL,
    first_seen_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_attempt_utc TIMESTAMPTZ,
    last_error TEXT,
    snapshot JSONB
);
"""

# Read-only. Connection setup must not CREATE or ALTER: those statements take
# AccessExclusiveLock on exec_orders and deadlock an overlapping reservation INSERT.
_SCHEMA_READY_SQL = """
SELECT
    to_regclass('public.trades') IS NOT NULL
    AND to_regclass('public.reconcile_metadata') IS NOT NULL
    AND to_regclass('public.operational_event_log') IS NOT NULL
    AND to_regclass('public.exec_orders') IS NOT NULL
    AND to_regclass('public.broker_exit_ledger') IS NOT NULL
    AND to_regclass('public.broker_exit_pending') IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('public.exec_orders')
          AND attname = 'filled_units'
          AND NOT attisdropped
    )
    AND EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('public.trades')
          AND attname = 'trading_mode'
          AND NOT attisdropped
    )
    AND EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('public.trades')
          AND attname = 'execution_kind'
          AND NOT attisdropped
    )
    AND EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('public.trades')
          AND attname = 'diagnostics'
          AND NOT attisdropped
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.exec_orders')
          AND contype = 'u'
          AND conkey = ARRAY[
              (SELECT attnum FROM pg_attribute
               WHERE attrelid = to_regclass('public.exec_orders')
                 AND attname = 'client_order_id')
          ]::smallint[]
    )
"""


def partial_initialization_cleanup_errors() -> tuple[str, ...]:
    """Exception type names from the latest failed connection initialization."""
    return tuple(_partial_cleanup_notes)


def _note_partial_cleanup(exc: BaseException) -> None:
    name = type(exc).__name__
    _partial_cleanup_notes.append(name)
    logger.warning("PostgreSQL partial initialization cleanup failed: %s", name)


def _discard_partial_connection(conn: Any, cursor: Any) -> None:
    """Roll back and close a connection this attempt created and did not publish."""
    if cursor is not None and not getattr(cursor, "closed", False):
        try:
            cursor.close()
        except Exception as exc:  # noqa: BLE001
            _note_partial_cleanup(exc)
    if conn is None or getattr(conn, "closed", True):
        return
    try:
        conn.rollback()
    except Exception as exc:  # noqa: BLE001
        _note_partial_cleanup(exc)
    if getattr(conn, "closed", True):
        return
    try:
        conn.close()
    except Exception as exc:  # noqa: BLE001
        _note_partial_cleanup(exc)


def release_connection_after_failed_startup() -> tuple[str, ...]:
    """Close the connection this module published. Does not open another one.

    Idempotent. Globals are cleared only while they still refer to the
    objects being released. The caller must already have stopped tasks
    that borrow the connection.
    """
    global _pg_conn, _pg_cursor
    notes: list[str] = []
    with _pg_lock:
        conn = _pg_conn
        cursor = _pg_cursor
        if _pg_conn is conn:
            _pg_conn = None
        if _pg_cursor is cursor:
            _pg_cursor = None
    if cursor is not None and not getattr(cursor, "closed", False):
        try:
            cursor.close()
        except Exception as exc:  # noqa: BLE001
            notes.append(type(exc).__name__)
            logger.warning(
                "PostgreSQL startup release cleanup failed: %s",
                type(exc).__name__,
            )
    if conn is not None and not getattr(conn, "closed", True):
        try:
            conn.close()
        except Exception as exc:  # noqa: BLE001
            notes.append(type(exc).__name__)
            logger.warning(
                "PostgreSQL startup release cleanup failed: %s",
                type(exc).__name__,
            )
    return tuple(notes)


def get_connection() -> PGConnection | None:
    """Return the shared PostgreSQL connection.

    ``_pg_lock`` is held across the reuse check, initialization, and
    publication. Callers must still hold ``_pg_lock`` around later cursor
    use. The lock is reentrant, so a helper that already holds it can call
    this function.
    """
    global _pg_conn, _pg_cursor
    with _pg_lock:
        if _pg_conn is not None and not _pg_conn.closed:
            return _pg_conn
        _partial_cleanup_notes.clear()
        new_conn = None
        new_cursor = None
        try:
            new_conn = psycopg2.connect(
                dbname=Config.POSTGRES.db,
                user=Config.POSTGRES.user,
                password=Config.POSTGRES.password,
                host=Config.POSTGRES.host,
                port=Config.POSTGRES.port,
            )
            new_cursor = new_conn.cursor()
            new_cursor.execute(_SCHEMA_READY_SQL)
            ready = bool(new_cursor.fetchone()[0])
            new_conn.commit()
            if not ready:
                logger.warning("PostgreSQL schema is not ready; reservation will fail closed")
                _discard_partial_connection(new_conn, new_cursor)
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("PostgreSQL unavailable: %s", exc)
            _discard_partial_connection(new_conn, new_cursor)
            return None
        _pg_conn = new_conn
        _pg_cursor = new_cursor
        return new_conn


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
    diagnostics: dict[str, Any] | None = None,
    closed_at: datetime | None = None,
) -> None:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return
        try:
            mode = (Config.TRADING_MODE or "practice").strip().lower()
            kind = (execution_kind or "simulated").strip().lower()
            _pg_cursor.execute(
                """
                INSERT INTO trades (
                    time, symbol, strategy, direction, pnl, size, entry_price, exit_price,
                    trading_mode, execution_kind, diagnostics
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    closed_at if closed_at is not None else datetime.now(),
                    symbol,
                    strategy,
                    direction,
                    pnl,
                    size,
                    entry,
                    exit_price,
                    mode,
                    kind,
                    Json(diagnostics) if diagnostics else None,
                ),
            )
            conn.commit()
        except Exception as exc:
            logger.error("log_trade_pg failed: %s", exc)
            conn.rollback()


def fetch_all_trades_ordered() -> list[dict[str, Any]]:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return []
        _pg_cursor.execute(
            """
            SELECT id, time, symbol, strategy, direction, pnl, size, entry_price, exit_price,
                   trading_mode, execution_kind, diagnostics
            FROM trades ORDER BY time DESC
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
            "diagnostics",
        ]
        return [dict(zip(cols, r)) for r in rows]


def fetch_strategy_analysis() -> list[dict[str, Any]]:
    with _pg_lock:
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
            {
                "strategy": r[0],
                "direction": r[1],
                "avg_pnl": float(r[2]) if r[2] is not None else 0.0,
                "count": r[3],
            }
            for r in rows
        ]


def fetch_reconcile_metadata() -> dict[str, Any] | None:
    """Last persisted reconcile row (singleton), or None if missing / DB unavailable."""
    with _pg_lock:
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
    with _pg_lock:
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
    with _pg_lock:
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
    with _pg_lock:
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


def persist_exec_orders_enabled() -> bool:
    return (os.getenv("PERSIST_EXEC_ORDERS") or "1").strip().lower() not in ("0", "false", "no", "off")


OFFLINE_EXEC_ORDER_SCHEMA = "exec_orders_offline_v1"
OFFLINE_EXEC_ORDER_CONTEXT = "isolated_offline_test"
_OFFLINE_STORE_ARMED: Path | None = None


def _approved_offline_store_roots() -> tuple[Path, ...]:
    project = Path(__file__).resolve().parents[1]
    base = project / "data" / "research" / "adaptive_ensemble"
    return (base / "r22", base / "r23")


def _offline_store_path_approved(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in _approved_offline_store_roots():
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        else:
            return True
    return False


def disarm_offline_exec_order_store() -> None:
    """Drop an armed test store. Does not open a database connection."""
    global _OFFLINE_STORE_ARMED
    _OFFLINE_STORE_ARMED = None


def arm_offline_exec_order_store(
    path: Path | str,
    *,
    context: str,
    production_eligible: bool = False,
) -> Path:
    """Arm the JSON store for this process.

    ``EXEC_ORDER_OFFLINE_STORE`` is not read. A production-eligibility flag
    is ignored. The path must sit under an approved offline research root.
    """
    global _OFFLINE_STORE_ARMED
    _ = production_eligible
    candidate = Path(path)
    if context != OFFLINE_EXEC_ORDER_CONTEXT or not _offline_store_path_approved(candidate):
        _OFFLINE_STORE_ARMED = None
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline store arm refused")
    resolved = candidate.resolve()
    _OFFLINE_STORE_ARMED = resolved
    return resolved


def offline_exec_order_store_path() -> Path | None:
    """Return the armed test store.

    An environment variable, including a stale ``EXEC_ORDER_OFFLINE_STORE``,
    does not select this store. Production code does not arm it.
    """
    return _OFFLINE_STORE_ARMED


def _offline_row_blocks(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").strip().upper()
    if status in {"CANCELLED", "REJECTED"}:
        return False
    if status == "FILLED":
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        return str(meta.get("exposure_safety") or "").strip().upper() != "CONFIRMED_FLAT"
    return True


def _write_offline_exec_orders(path: Path, orders: list[dict[str, Any]]) -> bool:
    payload = {"schema": OFFLINE_EXEC_ORDER_SCHEMA, "orders": orders}
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
        return True
    except Exception as exc:
        logger.warning("offline exec order store write failed: %s", type(exc).__name__)
        return False


def _blank_offline_document() -> dict[str, Any]:
    return {"schema": OFFLINE_EXEC_ORDER_SCHEMA, "orders": []}


def read_offline_exec_orders() -> list[dict[str, Any]]:
    """Read the isolated store. A missing or damaged file is unreadable, not empty."""
    path = offline_exec_order_store_path()
    if path is None:
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline order store not configured")
    if not path.is_file():
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline order store missing")
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline order store unreadable")
    if not isinstance(blob, dict) or blob.get("schema") != OFFLINE_EXEC_ORDER_SCHEMA:
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline order store schema invalid")
    orders = blob.get("orders")
    if not isinstance(orders, list):
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("offline order store truncated")
    seen: set[str] = set()
    for row in orders:
        if not isinstance(row, dict):
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("offline order store truncated")
        cid = str(row.get("client_order_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        status = str(row.get("status") or "").strip()
        if not cid:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("offline order store missing client id")
        if not symbol or not status:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("offline order store truncated")
        if cid in seen:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("offline order store duplicate client id")
        seen.add(cid)
        reservation = row.get("reservation_status")
        if reservation is not None and str(reservation).strip().upper() != status.upper():
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("offline order store reservation mismatch")
    return [dict(row) for row in orders]


def _load_offline_for_write(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return _blank_offline_document()
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(blob, dict) or blob.get("schema") != OFFLINE_EXEC_ORDER_SCHEMA:
        return None
    if not isinstance(blob.get("orders"), list):
        return None
    return blob


def _insert_offline_pending(
    path: Path,
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    units: float,
    metadata: dict[str, Any] | None,
) -> bool:
    document = _load_offline_for_write(path)
    if document is None:
        refuse_reservation_after_database_fault()
        return False
    orders = list(document["orders"])
    for row in orders:
        if str(row.get("client_order_id") or "") == client_order_id:
            return False
        if str(row.get("symbol") or "").upper() == symbol and _offline_row_blocks(row):
            return False
    orders.append(
        {
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side.upper(),
            "units": float(units),
            "status": "PENDING",
            "reservation_status": "PENDING",
            "metadata": dict(metadata or {}),
            "fill_price": None,
            "broker_order_id": "",
            "filled_units": None,
        }
    )
    if not _write_offline_exec_orders(path, orders):
        refuse_reservation_after_database_fault()
        return False
    _process_blocking[symbol] = str(client_order_id)
    return True


def _update_offline_exec_order(
    path: Path,
    *,
    client_order_id: str,
    status: str,
    fill_price: float | None,
    broker_order_id: str | None,
    metadata: dict[str, Any] | None,
    filled_units: float | None,
) -> bool:
    document = _load_offline_for_write(path)
    if document is None:
        refuse_reservation_after_database_fault()
        return False
    found = False
    updated: list[dict[str, Any]] = []
    for row in document["orders"]:
        if str(row.get("client_order_id") or "") != client_order_id:
            updated.append(row)
            continue
        found = True
        current = dict(row)
        if str(current.get("status") or "").upper() == "UNRESOLVED" and status.upper() == "CANCELLED":
            updated.append(current)
            continue
        meta = dict(current.get("metadata") or {}) if isinstance(current.get("metadata"), dict) else {}
        meta.update(dict(metadata or {}))
        current["status"] = status.upper()
        current["reservation_status"] = status.upper()
        current["metadata"] = meta
        if fill_price is not None:
            current["fill_price"] = fill_price
        if broker_order_id:
            current["broker_order_id"] = broker_order_id
        if filled_units is not None:
            current["filled_units"] = filled_units
        updated.append(current)
    if not found:
        refuse_reservation_after_database_fault()
        return False
    if not _write_offline_exec_orders(path, updated):
        refuse_reservation_after_database_fault()
        return False
    return True


class OrderRecoveryUnreadable(RuntimeError):
    """Recovery could not be read. Callers must fail closed."""


UNRESOLVED_ORDER_STATUS = "UNRESOLVED"
_BLOCKING_RESERVATION_STATUSES = frozenset({"PENDING", "PARTIAL", UNRESOLVED_ORDER_STATUS})
_TERMINAL_RELEASE_STATUSES = frozenset({"FILLED", "REJECTED", "CANCELLED"})
_KNOWN_ORDER_STATUSES = _TERMINAL_RELEASE_STATUSES | _BLOCKING_RESERVATION_STATUSES
EXPOSURE_UNCONFIRMED = "UNCONFIRMED"
EXPOSURE_CONFIRMED_FLAT = "CONFIRMED_FLAT"
_EXPOSURE_MARKERS = frozenset({EXPOSURE_UNCONFIRMED, EXPOSURE_CONFIRMED_FLAT})
_RECOVERY_ACTIVE_STATUSES = frozenset({"PENDING", "PARTIAL", "UNRESOLVED"})
_RECOVERY_TERMINAL_STATUSES = frozenset({"CANCELLED", "REJECTED"})
RECOVERY_FETCH_LIMIT = 2000
RECOVERY_SELECTION_SQL = (
    "status IN ('PENDING', 'PARTIAL', 'UNRESOLVED') "
    "OR (status = 'FILLED' AND COALESCE(metadata->>'exposure_safety', '') <> 'CONFIRMED_FLAT')"
)
RESERVATION_BLOCK_SQL = (
    "status NOT IN ('CANCELLED', 'REJECTED') "
    "AND NOT (status = 'FILLED' AND COALESCE(metadata->>'exposure_safety', '') = 'CONFIRMED_FLAT')"
)
_process_unresolved: dict[str, str] = {}
_process_blocking: dict[str, str] = {}
_process_exposure: dict[str, str] = {}
_process_fail_closed = False


def order_status_proves_exposure_closed(status: object) -> bool:
    """An order word never proves the position is flat."""
    _ = status
    return False


def _metadata_marker(metadata: object) -> str:
    """Return a marker. None and an empty object are missing, not flat."""
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("exposure_safety") or "").strip().upper()


def select_rows_for_recovery(rows: object) -> list[dict[str, Any]]:
    """Apply the recovery selection rule to an in-memory row set.

    This is the same rule as ``RECOVERY_SELECTION_SQL``. It does not execute
    SQL and does not prove that PostgreSQL would return the same rows.
    ``CONFIRMED_FLAT`` is an internal token, not broker evidence. A FILLED
    row without that exact token stays selected. Cancelled and rejected rows
    are not exposure evidence. Any other status fails closed.
    """
    if not isinstance(rows, list):
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("order recovery result incomplete")
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery row corrupt")
        status = str(row.get("status") or "").strip().upper()
        if status in _RECOVERY_TERMINAL_STATUSES:
            continue
        if status == "FILLED":
            metadata = row.get("metadata", None)
            if isinstance(metadata, dict) and _metadata_marker(metadata) == EXPOSURE_CONFIRMED_FLAT:
                continue
            selected.append(row)
            continue
        if status in _RECOVERY_ACTIVE_STATUSES:
            selected.append(row)
            continue
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("order recovery status unrecognised")
    return selected


def exposure_marker_block_reason(row: object) -> str | None:
    """Return a block when a row does not prove exposure is closed.

    FILLED without an explicit flat marker stays blocked. NULL metadata is
    not flat. A stale, malformed, or unknown marker fails closed. This does
    not contact a broker.
    """
    if not isinstance(row, dict):
        return "recovery_corrupt"
    if row.get("snapshot_stale") is True:
        return "stale_position_snapshot"
    raw_meta = row.get("metadata", None)
    if raw_meta is not None and not isinstance(raw_meta, dict):
        return "recovery_corrupt"
    meta = raw_meta if isinstance(raw_meta, dict) else {}
    marker = _metadata_marker(meta)
    if marker and marker not in _EXPOSURE_MARKERS:
        return "unknown_position_status"
    status = str(row.get("status") or "").strip().upper()
    if marker == EXPOSURE_UNCONFIRMED or (status == "FILLED" and marker != EXPOSURE_CONFIRMED_FLAT):
        return "exposure_unconfirmed"
    if status == "PARTIAL" and marker != EXPOSURE_CONFIRMED_FLAT:
        return "exposure_unconfirmed"
    return None


def note_unconfirmed_exposure(symbol: str, client_order_id: str) -> None:
    """Remember that a fill is not proof the exposure is closed."""
    sym = symbol.upper().strip()
    with _pg_lock:
        _process_exposure.setdefault(sym, str(client_order_id))
        _process_blocking.setdefault(sym, str(client_order_id))


def exposure_entry_block_reason(symbol: str) -> str | None:
    """Block a new entry while exposure or recovery is uncertain."""
    sym = symbol.upper().strip()
    with _pg_lock:
        if _process_fail_closed:
            return "recovery_unreadable"
        if sym in _process_exposure:
            return "exposure_unconfirmed"
        if sym in _process_unresolved:
            return "unresolved_intent"
        if sym in _process_blocking:
            return "active_reservation"
    return None


def confirm_exposure_flat(symbol: str, evidence: object = "", **caller_supplied: object) -> bool:
    """Refuse every caller-supplied release.

    A string, including ``CONFIRMED_FLAT``, a boolean, or a dictionary is
    not broker-flat evidence. This function does not query a broker and
    does not clear the in-memory hold. No offline caller can manufacture
    an authorised release.
    """
    _ = (symbol, evidence, caller_supplied)
    return False


def interpret_close_evidence(symbol: str, evidence: str) -> str | None:
    """A close attempt keeps the hold. Caller-supplied evidence cannot clear it."""
    if confirm_exposure_flat(symbol, evidence=evidence):
        return None
    return exposure_entry_block_reason(symbol) or "exposure_unconfirmed"


def reservation_status_block_reason(status: object) -> str | None:
    """Block a new reservation while an order is still active or unreadable.

    FILLED, CANCELLED, and REJECTED do not block here. FILLED does not prove
    the position is closed; the position book is a separate gate.
    """
    text = str(status or "").strip().upper()
    if text == UNRESOLVED_ORDER_STATUS:
        return "unresolved_intent"
    if text in {"PENDING", "PARTIAL"}:
        return "active_reservation"
    if text in {"FILLED", "CANCELLED", "REJECTED"}:
        return None
    return "unknown_status"


def reset_order_intent_gate_for_tests() -> None:
    """Clear process-local intent state. Does not open a database connection."""
    global _process_fail_closed
    _process_unresolved.clear()
    _process_blocking.clear()
    _process_exposure.clear()
    _process_fail_closed = False


def fresh_intent_book() -> dict[str, Any]:
    return {
        "unresolved": {},
        "blocking": {},
        "exposure": {},
        "fail_closed": False,
        "retries": 0,
        "replacements": [],
    }


def _copy_intent_book(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "unresolved": {str(k): str(v) for k, v in dict(book.get("unresolved") or {}).items()},
        "blocking": {str(k): str(v) for k, v in dict(book.get("blocking") or {}).items()},
        "exposure": {str(k): str(v) for k, v in dict(book.get("exposure") or {}).items()},
        "fail_closed": bool(book.get("fail_closed")),
        "retries": int(book.get("retries") or 0),
        "replacements": list(book.get("replacements") or []),
    }


def book_on_ambiguous(book: dict[str, Any], symbol: str, client_order_id: str) -> dict[str, Any]:
    """Keep the first client id for an unresolved intent. Never retries."""
    out = _copy_intent_book(book)
    sym = symbol.upper().strip()
    out["unresolved"].setdefault(sym, str(client_order_id))
    out["blocking"].setdefault(sym, str(client_order_id))
    return out


def book_on_terminal(book: dict[str, Any], symbol: str, status: str) -> dict[str, Any]:
    """Clear an intent only for an explicit fill, rejection, or cancellation."""
    out = _copy_intent_book(book)
    if str(status).upper() not in _TERMINAL_RELEASE_STATUSES:
        return out
    sym = symbol.upper().strip()
    out["unresolved"].pop(sym, None)
    out["blocking"].pop(sym, None)
    return out


def book_on_reconciliation(book: dict[str, Any], symbol: str, result: str) -> dict[str, Any]:
    """Interpret a simulated reconciliation result. Does not contact a broker.

    CONFIRMED_ABSENT releases the intent and does not create a replacement id.
    CONFIRMED_FILL clears the unresolved intent and does not create a replacement id.
    Any other result, including an unavailable reconciliation, leaves the intent blocked.
    """
    out = _copy_intent_book(book)
    sym = symbol.upper().strip()
    if result == "CONFIRMED_ABSENT":
        out["unresolved"].pop(sym, None)
        out["blocking"].pop(sym, None)
        out["last_reconciliation"] = "CONFIRMED_ABSENT"
        return out
    if result == "CONFIRMED_FILL":
        out["unresolved"].pop(sym, None)
        out["blocking"].pop(sym, None)
        out["last_reconciliation"] = "CONFIRMED_FILL"
        return out
    out["last_reconciliation"] = "UNAVAILABLE"
    return out


def new_intent_block_reason(
    book: dict[str, Any],
    symbol: str,
    recovery_rows: object,
    recovery_readable: bool,
) -> str | None:
    """Return a block reason, or None when a new broker intent may be reserved."""
    if book.get("fail_closed") or not recovery_readable:
        return "recovery_unreadable"
    if not isinstance(recovery_rows, list):
        return "recovery_corrupt"
    sym = symbol.upper().strip()
    unresolved = book.get("unresolved") or {}
    blocking = book.get("blocking") or {}
    exposure = book.get("exposure") or {}
    if sym in unresolved:
        return "unresolved_intent"
    if sym in blocking:
        return "active_reservation"
    if sym in exposure:
        return "exposure_unconfirmed"
    for row in recovery_rows:
        if not isinstance(row, dict) or "status" not in row or "symbol" not in row:
            return "recovery_corrupt"
        status = str(row.get("status") or "").upper()
        if status not in _KNOWN_ORDER_STATUSES:
            return "recovery_corrupt"
        if str(row.get("symbol") or "").upper() != sym:
            continue
        reason = reservation_status_block_reason(status)
        if reason:
            return reason
        exposure_reason = exposure_marker_block_reason(row)
        if exposure_reason:
            return exposure_reason
    return None


def current_intent_book() -> dict[str, Any]:
    return {
        "unresolved": dict(_process_unresolved),
        "blocking": dict(_process_blocking),
        "exposure": dict(_process_exposure),
        "fail_closed": _process_fail_closed,
        "retries": 0,
        "replacements": [],
    }


def force_order_recovery_fail_closed() -> None:
    """Block new broker reservations after recovery cannot be trusted."""
    global _process_fail_closed
    with _pg_lock:
        _process_fail_closed = True


def note_order_recovery_readable() -> None:
    """Clear only the recovery-failure latch after a completed readable recovery.

    Exposure, unresolved, and reservation holds are left in place. A caller
    flat marker is not a recovery result and cannot call this.
    """
    global _process_fail_closed
    with _pg_lock:
        _process_fail_closed = False


def restore_unresolved_intent(symbol: str, client_order_id: str) -> None:
    """Reload a durable unresolved intent without writing to the database."""
    note_blocking_reservation(symbol, client_order_id)
    sym = symbol.upper().strip()
    with _pg_lock:
        _process_unresolved.setdefault(sym, str(client_order_id))


def note_blocking_reservation(symbol: str, client_order_id: str) -> None:
    """Remember an active reservation. Does not open a database connection."""
    sym = symbol.upper().strip()
    with _pg_lock:
        _process_blocking.setdefault(sym, str(client_order_id))


def release_reservation_hold(symbol: str) -> None:
    """Drop the in-flight reservation hold for one symbol.

    This does not prove the position is flat. FILLED is not evidence that
    exposure is closed; the position book is a separate gate.
    """
    sym = symbol.upper().strip()
    with _pg_lock:
        _process_unresolved.pop(sym, None)
        held = _process_blocking.get(sym)
        if held is not None:
            _process_blocking.pop(sym, None)


def refuse_reservation_after_database_fault() -> None:
    """A failed or ambiguous reservation write blocks further broker entries."""
    global _process_fail_closed
    with _pg_lock:
        _process_fail_closed = True


def client_order_is_unresolved(client_order_id: str) -> bool:
    cid = str(client_order_id)
    with _pg_lock:
        return any(value == cid for value in _process_unresolved.values())


def _symbol_reservation_lock_key(symbol: str) -> int:
    import zlib

    return zlib.crc32(symbol.encode("utf-8")) & 0x7FFFFFFF


def remember_ambiguous_outcome(symbol: str, client_order_id: str) -> bool:
    """Hold the original client id. A failed durable write fail-closes new broker intents."""
    global _process_fail_closed
    sym = symbol.upper().strip()
    with _pg_lock:
        _process_unresolved.setdefault(sym, str(client_order_id))
        _process_blocking.setdefault(sym, str(client_order_id))
    persisted = persist_unresolved_order(client_order_id)
    if not persisted:
        with _pg_lock:
            _process_fail_closed = True
    return persisted


def release_resolved_intent(symbol: str) -> None:
    """Drop a process-local hold after an explicit cancel or rejection."""
    release_reservation_hold(symbol)


def read_durable_recovery() -> tuple[list[dict[str, Any]], bool]:
    """Load rows that still block a new reservation.

    An unavailable store is unreadable, not empty-and-clear.
    """
    if offline_exec_order_store_path() is not None:
        try:
            rows = select_rows_for_recovery(read_offline_exec_orders())
        except OrderRecoveryUnreadable:
            return [], False
        note_order_recovery_readable()
        return rows, True
    if not persist_exec_orders_enabled():
        return [], False
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            force_order_recovery_fail_closed()
            return [], False
        try:
            _pg_cursor.execute(
                """
                SELECT client_order_id, symbol, status, metadata
                FROM exec_orders
                WHERE """
                + RECOVERY_SELECTION_SQL
                + """
                """
            )
            rows = [
                {
                    "client_order_id": r[0],
                    "symbol": r[1],
                    "status": r[2],
                    "metadata": r[3],
                }
                for r in _pg_cursor.fetchall()
            ]
        except Exception as exc:
            logger.warning("exec_orders: unresolved recovery unreadable: %s", exc)
            force_order_recovery_fail_closed()
            return [], False
        note_order_recovery_readable()
        return rows, True


def persist_unresolved_order(client_order_id: str) -> bool:
    """Store UNRESOLVED. Returns False when the row cannot be made durable."""
    if offline_exec_order_store_path() is not None:
        return update_exec_order_row(
            client_order_id=client_order_id,
            status=UNRESOLVED_ORDER_STATUS,
            metadata={"reason": "ambiguous_broker_outcome", "exposure_safety": "UNCONFIRMED"},
        )
    if not persist_exec_orders_enabled():
        return False
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return False
        try:
            _pg_cursor.execute(
                """
                UPDATE exec_orders SET
                    status = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE client_order_id = %s
                """,
                (
                    UNRESOLVED_ORDER_STATUS,
                    Json({"reason": "ambiguous_broker_outcome"}),
                    client_order_id,
                ),
            )
            conn.commit()
            return _pg_cursor.rowcount > 0
        except Exception as exc:
            logger.warning("exec_orders: could not persist unresolved outcome: %s", exc)
            conn.rollback()
            return False


def insert_exec_order_pending_if_absent(
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    units: float,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Insert one PENDING reservation for a symbol.

    The advisory lock, the blocking-status check, and the insert commit
    together. PENDING, PARTIAL, UNRESOLVED, and any other non-terminal
    status already stored for the symbol refuse a second client id.
    A database fault fail-closes later reservations. This function does
    not contact a broker and does not prove PostgreSQL locking.
    """
    sym = symbol.upper().strip()
    with _pg_lock:
        if _process_fail_closed or sym in _process_unresolved or sym in _process_blocking or sym in _process_exposure:
            logger.info("exec_orders: active reservation blocks a new client id for %s", sym)
            return False
        store = offline_exec_order_store_path()
        if store is not None:
            return _insert_offline_pending(
                store,
                client_order_id=client_order_id,
                symbol=sym,
                side=side,
                units=units,
                metadata=metadata,
            )
        if not persist_exec_orders_enabled():
            _process_blocking[sym] = str(client_order_id)
            return True
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            logger.warning("exec_orders: persist enabled but PostgreSQL unavailable — blocking new order reservation")
            refuse_reservation_after_database_fault()
            return False
        try:
            _pg_cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_symbol_reservation_lock_key(sym),),
            )
            _pg_cursor.execute(
                """
                SELECT status FROM exec_orders
                WHERE symbol = %s
                  AND (
                    """
                + RESERVATION_BLOCK_SQL
                + """
                  )
                LIMIT 1
                """,
                (sym,),
            )
            if _pg_cursor.fetchone() is not None:
                logger.info("exec_orders: durable active reservation blocks %s", sym)
                conn.rollback()
                _process_blocking.setdefault(sym, str(client_order_id))
                return False
            _pg_cursor.execute(
                """
                INSERT INTO exec_orders (client_order_id, symbol, side, units, status, metadata)
                VALUES (%s, %s, %s, %s, 'PENDING', %s)
                ON CONFLICT (client_order_id) DO NOTHING
                """,
                (
                    client_order_id,
                    symbol.upper().strip(),
                    side.upper().strip(),
                    float(units),
                    Json(metadata or {}),
                ),
            )
            conn.commit()
            inserted = _pg_cursor.rowcount > 0
            if not inserted:
                logger.info("exec_orders: duplicate client_order_id (idempotent skip) %s", client_order_id)
                return False
            _process_blocking[sym] = str(client_order_id)
            return True
        except Exception as exc:
            logger.warning("insert_exec_order_pending_if_absent failed: %s", exc)
            try:
                conn.rollback()
            except Exception:
                logger.warning("exec_orders: reservation rollback also failed for %s", sym)
            _process_blocking[sym] = str(client_order_id)
            refuse_reservation_after_database_fault()
            return False


def update_exec_order_row(
    *,
    client_order_id: str,
    status: str,
    fill_price: float | None = None,
    broker_order_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    filled_units: float | None = None,
) -> bool:
    with _pg_lock:
        store = offline_exec_order_store_path()
        if store is not None:
            return _update_offline_exec_order(
                store,
                client_order_id=client_order_id,
                status=status,
                fill_price=fill_price,
                broker_order_id=broker_order_id,
                metadata=metadata,
                filled_units=filled_units,
            )
        if not persist_exec_orders_enabled():
            return True
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return False
        st = status.upper()
        try:
            if st in ("FILLED", "PARTIAL"):
                _pg_cursor.execute(
                    """
                    UPDATE exec_orders SET
                        status = %s,
                        fill_price = COALESCE(%s, fill_price),
                        broker_order_id = COALESCE(%s, broker_order_id),
                        filled_units = COALESCE(%s, filled_units),
                        filled_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || COALESCE(%s::jsonb, '{}'::jsonb)
                    WHERE client_order_id = %s
                    """,
                    (st, fill_price, broker_order_id, filled_units, Json(metadata or {}), client_order_id),
                )
            elif st == "CANCELLED":
                _pg_cursor.execute(
                    """
                    UPDATE exec_orders SET
                        status = 'CANCELLED',
                        metadata = COALESCE(metadata, '{}'::jsonb) || COALESCE(%s::jsonb, '{}'::jsonb)
                    WHERE client_order_id = %s
                      AND status IS DISTINCT FROM 'UNRESOLVED'
                    """,
                    (Json(metadata or {}), client_order_id),
                )
            else:
                _pg_cursor.execute(
                    """
                    UPDATE exec_orders SET
                        status = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || COALESCE(%s::jsonb, '{}'::jsonb)
                    WHERE client_order_id = %s
                    """,
                    (st, Json(metadata or {}), client_order_id),
                )
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("update_exec_order_row failed: %s", exc)
            try:
                conn.rollback()
            except Exception:
                logger.warning("exec_orders: order update rollback failed")
            return False


def fetch_exec_orders_open_for_recovery() -> list[dict[str, Any]]:
    """Load active orders and FILLED rows whose exposure is not explicitly flat.

    A full page is treated as truncated and fails closed. This function does
    not prove the SQL against a PostgreSQL server.
    """
    with _pg_lock:
        if offline_exec_order_store_path() is not None:
            rows = read_offline_exec_orders()
            selected = select_rows_for_recovery(rows)
            note_order_recovery_readable()
            return selected
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery connection unavailable")
        try:
            _pg_cursor.execute(
                """
                SELECT client_order_id, symbol, side, units, status, created_at, fill_price, broker_order_id, metadata,
                       filled_units
                FROM exec_orders
                WHERE """
                + RECOVERY_SELECTION_SQL
                + """
                ORDER BY created_at DESC
                LIMIT """
                + str(RECOVERY_FETCH_LIMIT + 1)
            )
            rows = _pg_cursor.fetchall()
            if len(rows) > RECOVERY_FETCH_LIMIT:
                force_order_recovery_fail_closed()
                raise OrderRecoveryUnreadable("order recovery result truncated")
            out: list[dict[str, Any]] = []
            for r in rows:
                ts = r[5]
                ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else ""
                fu = r[9]
                metadata = r[8]
                out.append(
                    {
                        "client_order_id": r[0],
                        "symbol": r[1],
                        "side": r[2],
                        "units": float(r[3]) if r[3] is not None else 0.0,
                        "status": r[4],
                        "created_at": ts_iso,
                        "fill_price": r[6],
                        "broker_order_id": r[7],
                        "metadata": metadata,
                        "filled_units": float(fu) if fu is not None else None,
                    }
                )
            note_order_recovery_readable()
            return out
        except OrderRecoveryUnreadable:
            raise
        except Exception as exc:
            logger.warning("fetch_exec_orders_open_for_recovery: %s", exc)
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery query failed") from exc


def client_order_id_exists_in_db(client_order_id: str) -> bool:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return False
        try:
            _pg_cursor.execute(
                "SELECT 1 FROM exec_orders WHERE client_order_id = %s LIMIT 1",
                (client_order_id,),
            )
            return _pg_cursor.fetchone() is not None
        except Exception:
            return False


def broker_exit_ledger_exists(closing_transaction_id: str, broker_trade_id: str) -> bool:
    xid = str(closing_transaction_id or "").strip()
    tid = str(broker_trade_id or "").strip()
    if not xid or not tid:
        return False
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return False
        try:
            _pg_cursor.execute(
                """
                SELECT 1 FROM broker_exit_ledger
                WHERE closing_transaction_id = %s AND broker_trade_id = %s
                LIMIT 1
                """,
                (xid, tid),
            )
            return _pg_cursor.fetchone() is not None
        except Exception:
            return False


def insert_broker_exit_ledger(closing_transaction_id: str, broker_trade_id: str, symbol: str) -> bool:
    """Insert booked-exit key. True if inserted, False if already present or DB down (caller uses memory)."""
    xid = str(closing_transaction_id or "").strip()
    tid = str(broker_trade_id or "").strip()
    if not xid or not tid:
        return False
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return True
        try:
            _pg_cursor.execute(
                """
                INSERT INTO broker_exit_ledger (closing_transaction_id, broker_trade_id, symbol)
                VALUES (%s, %s, %s)
                ON CONFLICT (closing_transaction_id, broker_trade_id) DO NOTHING
                """,
                (xid, tid, str(symbol or "").strip().upper()),
            )
            conn.commit()
            return _pg_cursor.rowcount > 0
        except Exception as exc:
            logger.warning("insert_broker_exit_ledger failed: %s", exc)
            conn.rollback()
            return True


def fetch_broker_exit_ledger() -> list[dict[str, Any]]:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return []
        try:
            _pg_cursor.execute(
                "SELECT closing_transaction_id, broker_trade_id, symbol FROM broker_exit_ledger"
            )
            return [
                {
                    "closing_transaction_id": str(r[0]),
                    "broker_trade_id": str(r[1]),
                    "symbol": str(r[2] or ""),
                }
                for r in _pg_cursor.fetchall()
            ]
        except Exception:
            return []


def upsert_broker_exit_pending(
    *,
    symbol: str,
    broker_trade_id: str,
    first_seen_utc: str,
    last_attempt_utc: str,
    last_error: str,
    snapshot: dict[str, Any] | None = None,
) -> None:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return
        try:
            _pg_cursor.execute(
                """
                INSERT INTO broker_exit_pending (
                    symbol, broker_trade_id, first_seen_utc, last_attempt_utc, last_error, snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    broker_trade_id = EXCLUDED.broker_trade_id,
                    last_attempt_utc = EXCLUDED.last_attempt_utc,
                    last_error = EXCLUDED.last_error,
                    snapshot = EXCLUDED.snapshot
                """,
                (
                    symbol.upper().strip(),
                    broker_trade_id,
                    first_seen_utc,
                    last_attempt_utc,
                    last_error,
                    Json(snapshot or {}),
                ),
            )
            conn.commit()
        except Exception as exc:
            logger.warning("upsert_broker_exit_pending failed: %s", exc)
            conn.rollback()


def delete_broker_exit_pending(symbol: str) -> None:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return
        try:
            _pg_cursor.execute(
                "DELETE FROM broker_exit_pending WHERE symbol = %s",
                (symbol.upper().strip(),),
            )
            conn.commit()
        except Exception:
            conn.rollback()


def fetch_broker_exit_pending() -> list[dict[str, Any]]:
    with _pg_lock:
        conn = get_connection()
        if conn is None or _pg_cursor is None:
            return []
        try:
            _pg_cursor.execute(
                """
                SELECT symbol, broker_trade_id, first_seen_utc, last_attempt_utc, last_error, snapshot
                FROM broker_exit_pending
                """
            )
            out: list[dict[str, Any]] = []
            for r in _pg_cursor.fetchall():
                ts0 = r[2]
                ts1 = r[3]
                out.append(
                    {
                        "symbol": str(r[0] or ""),
                        "broker_trade_id": str(r[1] or ""),
                        "first_seen_utc": ts0.isoformat() if hasattr(ts0, "isoformat") else str(ts0 or ""),
                        "last_attempt_utc": ts1.isoformat() if hasattr(ts1, "isoformat") else str(ts1 or ""),
                        "last_error": str(r[4] or ""),
                        "snapshot": r[5] if isinstance(r[5], dict) else {},
                    }
                )
            return out
        except Exception:
            return []
