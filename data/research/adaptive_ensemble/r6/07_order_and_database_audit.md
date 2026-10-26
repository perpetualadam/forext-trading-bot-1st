# Order and database audit

R.5 claims checked against current source:

- Synthetic tests were reported as 65 passed in R.5. R.6 did not re-run them. That result is historical.
- `exec_orders.status` is `TEXT NOT NULL` with no check constraint. An unexpected word can be stored. Recovery now rejects an unknown word and fail-closes, in source.
- `load_open_orders_from_db_into_memory` is called from `app.py` lifespan before `run_bot`.
- `pg_advisory_xact_lock` is in `insert_exec_order_pending_if_absent`. It was not executed.
- A cancel update will not rewrite a row already marked `UNRESOLVED`.
- `OrderStatus.UNRESOLVED` exists. The old conversion of unknown status to PENDING is gone.
- There is no automatic retry and no timer that clears an unresolved intent.

Remaining holes:

- Two database sessions were not tested. Severity HIGH until an engine test exists.
- `fetch` raises when the connection is missing. The loader catches that and blocks new reservations. Lifespan still continues to broker and Telegram setup. Severity MEDIUM.
- Confirmed fill, reject, and cancel behaviour is synthetic, not broker-validated.
- Production PostgreSQL was not opened.
