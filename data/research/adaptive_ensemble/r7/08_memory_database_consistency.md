# Memory and database consistency

SOURCE-REVIEWED, with synthetic recovery snapshots.

`app.py` calls `load_open_orders_from_db_into_memory` before `run_bot`. That loader calls `fetch_exec_orders_open_for_recovery` and then `ingest_recovery_snapshot`. R.7 did not import `app.py`.

`ingest_recovery_snapshot` keeps `UNRESOLVED`, `PENDING`, and `PARTIAL`. It does not invent BUY for a bad side. It does not turn an unknown status into a finished or pending order.

`mark_order_failed_or_cancelled` returns without a change when the in-memory order or the process map says unresolved.

`broker_entry_block_reason` runs before a new client id is generated on the broker path. With persistence off, recovery is unreadable, so that function blocks. That path was called directly. The trading loop was not run.

A failed fetch used to look like an empty book. The current source raises `OrderRecoveryUnreadable` instead. The loader catches it and sets the fail-closed flag. That raise was not executed against PostgreSQL.

The process map and a database row can still disagree if a commit is ambiguous. That case was not engine-tested.
