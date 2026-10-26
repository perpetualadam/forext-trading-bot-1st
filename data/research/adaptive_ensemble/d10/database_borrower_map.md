# Database borrower map

Source: `forex_bot/database.py`. Telegram reachability: `cmd_trades` and the search handler in `telegram_control.py`.

Shared state:

- `_pg_conn`, `_pg_cursor`, `_pg_lock` (`threading.RLock`).
- `get_connection` holds `_pg_lock` across the reuse check, connect, cursor, initialization SQL, commit, and publication.
- `fetch_all_trades_ordered` holds `_pg_lock` for `get_connection`, `execute`, and `fetchall`, then returns rows. It does not retain the connection or cursor in the Telegram handler.
- `release_connection_after_failed_startup` copies and clears the globals under the lock, then closes the cursor and connection outside the lock. It does not connect. Its docstring says the caller must already have stopped borrowers.

Telegram does not open its own connection. It calls the shared helper. That helper uses the shared connection and shared cursor. After release clears the globals, the next helper call creates and publishes a new pair.

| Borrower | Thread or task | Resource | Access function | Lock held | Classification |
| --- | --- | --- | --- | --- | --- |
| Poller command path | `telegram-control` | Shared connection and cursor | `fetch_all_trades_ordered` | Yes, for the whole helper | ACTIVE_BORROWER while inside the helper. POTENTIAL_FUTURE_BORROWER while blocked in `get_updates`. |
| Direct helper call | Caller of `fetch_all_trades_ordered` | Same globals | `get_connection` then cursor execute | Yes | ACTIVE_BORROWER for the duration of the helper |
| Lifespan startup | Lifespan task | Shared connection | `get_connection` | Yes during init | Publishes the process connection. Success path does not release it. |
| Other database helpers | Whatever thread calls them | Same globals | `with _pg_lock` then `get_connection` | Yes | Same publication. Not separately executed as Telegram borrowers. |

| Question | Result |
| --- | --- |
| CAN_RETRY_AFTER_STOP | Yes. The poll loop does not check `_stop_event` until the current `get_updates` and `process_updates` finish. |
| CAN_ACCESS_AFTER_RELEASE | Yes. The next helper call finds `_pg_conn is None` or closed and calls `psycopg2.connect` again. |
| Retained worker reference to the old connection | No. The handler keeps rows only. |
| Use of the closed object | Not observed. `use_after_close` stayed empty. |

Observed classifications after Gate D:

- Thread 16048 was an active borrower after release: it executed `FROM trades` on new connection 2 while `caller_alive` was true.
- During a blocked `get_updates`, the same worker was a potential future borrower. Release of connection 1 completed because the worker did not hold `_pg_lock`.
- While `fetch_all_trades_ordered` held `_pg_lock` inside a blocked `execute`, release did not finish until the query was released. That borrower was quiescent for the close itself because the lock serialized it. It was not quiescent for a later call.
