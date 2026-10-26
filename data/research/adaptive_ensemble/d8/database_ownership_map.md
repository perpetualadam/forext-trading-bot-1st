# D.8 database ownership map

Evidence level: static read of `forex_bot/database.py`, `forex_bot/app.py`, and `forex_bot/telegram_control.py`. No production connection was opened.

## `_pg_conn`

- RESOURCE: process-global PostgreSQL connection.
- CREATOR: `get_connection` after `psycopg2.connect`, cursor creation, SQL initialization, and `commit` all succeed (`database.py` lines 194–219).
- OWNER: the `forex_bot.database` module. There is no per-caller owner.
- BORROWERS: every database helper that calls `get_connection` while holding `_pg_lock`; lifespan at `app.py` line 317, which ignores the return value; Telegram command handlers through `fetch_all_trades_ordered`.
- SHARED_REFERENCES: one module global. A caller that keeps the returned object has a second reference. Lifespan does not keep it.
- SYNCHRONIZATION: publication is two unlocked assignments, `_pg_conn` then `_pg_cursor`. Helpers hold `_pg_lock` around the whole `get_connection` call. `get_connection` itself does not acquire the lock. Release copies and clears the global under the lock, then closes outside the lock.
- INTENDED_LIFETIME: process lifetime after a successful publish. A failed attempt never assigns its local connection.
- RELEASE_POINT: `release_connection_after_failed_startup`, and only when lifespan has a startup failure and Telegram stop did not raise. Normal shutdown does not release it.
- CONCURRENT_USE_RISK: two callers that both pass the empty check can each connect. The later publisher overwrites the global. The earlier connection stays open and unreferenced. Observed as D8-CONC-01.
- EVIDENCE_LEVEL: static, then actual-source execution under isolation.

## `_pg_cursor`

- RESOURCE: process-global cursor for the published connection.
- CREATOR: `new_conn.cursor()` inside `get_connection`, published only after commit.
- OWNER: the database module, paired with `_pg_conn` by convention rather than by an atomic assignment.
- BORROWERS: database helpers use `_pg_cursor` inside `_pg_lock`. They return rows, not the cursor.
- SHARED_REFERENCES: one module global.
- SYNCHRONIZATION: same as the connection. The two publications are separate statements.
- INTENDED_LIFETIME: same as the published connection.
- RELEASE_POINT: cleared under `_pg_lock` and closed outside it by the release helper. Failed initialization closes only its local cursor.
- CONCURRENT_USE_RISK: an overlapping publisher can replace the global cursor. In the executed overlap schedules the published cursor still belonged to the published connection. The two-assignment window was not forced apart.
- EVIDENCE_LEVEL: static plus executed schedules.

## `_pg_lock`

- RESOURCE: `threading.RLock` at `database.py` line 22.
- CREATOR: module import.
- OWNER: the database module.
- BORROWERS: every helper that wraps `get_connection`, and the release helper for the copy-and-clear section only.
- SHARED_REFERENCES: one lock.
- SYNCHRONIZATION: reentrant. `get_connection` does not acquire it, so a helper that already holds it can call `get_connection`.
- INTENDED_LIFETIME: process lifetime.
- RELEASE_POINT: each `with` block exits. Release drops the lock before `close`.
- CONCURRENT_USE_RISK: the lock serializes helper against helper. It does not exclude lifespan, because lifespan calls `get_connection` without the lock.
- EVIDENCE_LEVEL: static. The unlocked-versus-locked schedule confirmed the exclusion gap.

## Local initialization objects

- RESOURCE: `new_conn` and `new_cursor` inside one `get_connection` call.
- CREATOR: that call.
- OWNER: that call until publication.
- BORROWERS: none outside the call.
- SHARED_REFERENCES: none until the two global assignments.
- SYNCHRONIZATION: none around connect, cursor, SQL, or commit.
- INTENDED_LIFETIME: discarded on failure; published on success.
- RELEASE_POINT: `_discard_partial_connection` on the exception path. It closes only the local objects.
- CONCURRENT_USE_RISK: a failed attempt does not clear a connection another caller already published. Confirmed by the mixed-failure schedules.
- EVIDENCE_LEVEL: static plus execution.

## Callers of `get_connection`

Production callers are the helpers in `database.py` (each inside `with _pg_lock`) and `app.py` line 317 (unlocked, return value ignored). `release_connection_after_failed_startup` does not call `get_connection`.

Telegram reads go through `fetch_all_trades_ordered` (`telegram_control.py` lines 596 and 768), which takes the lock. No strategy module calls `get_connection` directly. `bot_loop` does not call it.

## Release callers

The lifespan `finally` block is the production caller (`app.py` lines 391–392). It runs only when `startup_failure is not None and not telegram_stop_failed`.
