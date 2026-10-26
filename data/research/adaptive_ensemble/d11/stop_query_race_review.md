# D.11 stop/query race

An unlocked check can lose to stop: the worker can see the event clear and then enter the database helper after stop has been requested.

The remediation closes that window for trade reads. The permission check and the query are ordered by `_pg_lock`. The test held that lock on another thread, let the worker block inside `_read_trades_if_running`, set the stop event, and then released the lock. The worker acquired the lock, observed the stop, and did not query.

A query that had already entered `execute` kept the lock. Stop returned `STOP_INCOMPLETE_WORKER_ALIVE` while that query was still held. Release did not finish until the query was released. No second query followed.

The same ordering covers `cmd_search`. No other Telegram command calls `fetch_all_trades_ordered` or `get_connection`.
