# Database ownership contract

`_pg_lock` is an `RLock` at `database.py` line 22. `get_connection()` holds it across the reuse check, `psycopg2.connect`, cursor creation, schema statements, commit, and publication of `_pg_conn` and `_pg_cursor`.

Initialization failure calls `_discard_partial_connection` and returns `None`. The unpublished objects are closed. The published globals are not replaced by that failed attempt.

`release_connection_after_failed_startup()` clears the published globals while the lock is held, then closes the cursor and connection outside the lock. It does not connect again.

No attribute containing `borrow` exists on the database module. Quiescence is the stop check inside `_read_trades_if_running`, which holds the same lock release uses.

Distinctions:

- A. Successful shutdown keeps the process-global connection. That is intentional retention.
- B. Failed startup releases it when `startup_failure` is set and `telegram_stop_failed` is false.
- C. An in-flight query holds `_pg_lock`, so release waits.
- D. A stopped Telegram worker returns before `fetch_all_trades_ordered`.
- E. The delayed-poll schedule created no new connection after release.
