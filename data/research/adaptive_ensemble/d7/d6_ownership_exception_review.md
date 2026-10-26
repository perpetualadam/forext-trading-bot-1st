# D6-OWN-01 ownership decision

The successful-startup connection is intentionally process-global.

- Owner: the `database` module, through `_pg_conn` and `_pg_cursor`.
- Borrowers: database helpers under `_pg_lock`, the Telegram control poller through `fetch_all_trades_ordered`, and any request handler that reaches those helpers after the server begins serving.
- Lifetime: from successful `commit` inside `get_connection` until process exit, except when startup itself fails before `yield`.
- Normal lifespan shutdown does not close it. `stop_telegram_control` joins for at most 2 seconds and returns while the poller can still be alive. Request handlers are not part of the four lifespan tasks. Closing the shared connection there would require changes outside `app.py` and `database.py`.
- Failed startup does close it, after the tasks created by that attempt have been cancelled and awaited, and only if Telegram stop did not raise.

This is a resolved ownership decision. It is not an open defect and it is not a speculative close of a borrowed connection. The baseline isolated lifespan left `pg_conn_held` true and `close_calls` at 0. The harness closed that fake afterward; that close is harness cleanup.
