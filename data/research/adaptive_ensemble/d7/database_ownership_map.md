# D.7 database ownership map

Static inspection of `forex_bot/database.py` before the edit. The module was not executed against PostgreSQL.

| Resource | Creator | Owner | Borrowers | Expected lifetime | Release point | Failure behaviour before D.7 | Shared-reference risk | Safe to close | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| New connection inside `get_connection` before commit | `psycopg2.connect` in `get_connection` | The initializing call, until publication | None until assigned to `_pg_conn` | The initialization attempt | End of the failed attempt | Assigned to `_pg_conn` immediately, then the global was set to None without close or rollback | High if published before commit | Yes, only that new object | STATIC_ONLY, then confirmed by isolated tests |
| `_pg_conn` after a successful commit | `get_connection` | `database` module | Every `get_connection` caller; database helpers under `_pg_lock`; `telegram_control` via `fetch_all_trades_ordered`; process request handlers after lifespan yield | Process lifetime after publication | Not on the success path | Left open for the process | Callers share one connection and one cursor | Only after borrowers have stopped, and only if the global still points at that object | STATIC_ONLY |
| `_pg_cursor` | `connection.cursor()` during initialization | `database` module | Database helpers that use the global cursor under `_pg_lock` | Same as the published connection | Same as the connection | Left open when initialization failed after cursor creation | One shared cursor | Yes, together with the connection that created it | STATIC_ONLY |
| Connection returned by `get_connection` | Same object as `_pg_conn` | Module, not the caller | Caller holds a borrowed reference | Process lifetime | Caller must not close it | Returned and also stored globally | Closing a borrower's copy closes the shared object | No, unless it is still the module global and borrowers have stopped | STATIC_ONLY |

`get_connection` returns the shared connection. It does not return the cursor. Later database functions call `get_connection` and then use `_pg_cursor` while holding `_pg_lock`. `lifespan` calls `get_connection` once and ignores the return value.

`alerts.py` does not reference the database. `bot_loop.py` does not call `get_connection` directly. `telegram_control.py` imports `fetch_all_trades_ordered` from the poller path. `stop_telegram_control` joins that thread for at most 2 seconds and does not raise if the thread is still alive.

No separate connection-release function existed before this stage.
