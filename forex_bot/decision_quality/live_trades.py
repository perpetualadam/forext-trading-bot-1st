"""Optional read-only view of existing live diagnostics. Never writes."""

from __future__ import annotations

import os
from typing import Any


def try_load_live_diagnostics(limit: int = 500) -> tuple[list[dict[str, Any]], str]:
    """
    SELECT existing trades.diagnostics. Returns (rows, note).
    Never INSERT/UPDATE. Skips silently if Postgres is not configured or empty.
    """
    host = (os.getenv("POSTGRES_HOST") or "").strip()
    if not host:
        return [], "Postgres not configured; live-trade analysis skipped."
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return [], "psycopg2 missing; live-trade analysis skipped."

    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "trading"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASS", "password"),
            host=host,
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            connect_timeout=5,
        )
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT time, symbol, strategy, direction, pnl, entry_price, exit_price,
                       execution_kind, diagnostics
                FROM trades
                WHERE diagnostics IS NOT NULL
                ORDER BY time DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return [], "No trades.diagnostics rows found; live-trade analysis skipped."
        return rows, f"loaded {len(rows)} diagnostic rows (read-only)"
    except Exception as exc:
        return [], f"live-trade read failed ({type(exc).__name__}); skipped."
    finally:
        if conn is not None:
            conn.close()
