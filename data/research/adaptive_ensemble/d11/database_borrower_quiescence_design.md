# D.11 database borrower quiescence design

Guarantee A and Guarantee B are separate.

Guarantee A: `cmd_trades` and `cmd_search` call `_read_trades_if_running`. That function holds `_pg_lock`, reads the stop event, and only then calls `fetch_all_trades_ordered`. The helper re-enters the same lock. If stop is already set, it returns no rows and does not connect.

Guarantee B: if the check has already passed, the query still holds `_pg_lock`. `release_connection_after_failed_startup` takes that lock before it clears and closes the published connection, so it waits for the query.

Stop does not take `_pg_lock`. The lifecycle lock is not held across the network call, the query, or `join`.

`database.py` was not modified.
