# D.8 lock coverage

`_pg_lock` is a reentrant lock. `get_connection` does not acquire it. The docstring says callers must hold it around cursor use. It does not say callers must hold it around initialization.

| Operation | Boundary | Evidence |
| --- | --- | --- |
| Empty-connection check | UNLOCKED inside `get_connection` | `database.py` lines 188–189 |
| `psycopg2.connect` | UNLOCKED | lines 194–200 |
| Cursor creation | UNLOCKED | line 201 |
| SQL initialization | UNLOCKED | lines 202–212 |
| Commit | UNLOCKED | line 213 |
| Publish `_pg_conn` | UNLOCKED | line 218 |
| Publish `_pg_cursor` | UNLOCKED | line 219 |
| Reuse of an open connection | UNLOCKED check; helpers happen to hold the lock before calling | line 188 |
| Helper body after connect | LOCKED | each helper's `with _pg_lock` includes the `get_connection` call and later cursor use |
| Release copy and global clear | LOCKED | lines 157–163 |
| Release cursor close and connection close | UNLOCKED, after the globals were cleared | lines 164–181 |
| Failed-attempt discard | UNLOCKED | `_discard_partial_connection` |
| Partial-cleanup note list | UNLOCKED | `_partial_cleanup_notes` |
| Lifespan `get_connection()` | UNLOCKED | `app.py` line 317 |
| Telegram trade reads | LOCKED, because they call `fetch_all_trades_ordered` | `telegram_control.py` lines 596–599 and 768–770 |

Lock order: helpers acquire `_pg_lock` and then call `get_connection`, which does not acquire another lock. Release acquires `_pg_lock`, releases it, then closes. It does not call `get_connection` while holding the lock. No lock cycle was found. The reentrant lock lets a helper call `get_connection` without deadlocking itself.

`get_connection` can be entered from another thread while one caller is inside connect, because the function does not take the lock. Async tasks on one thread do not interleave the synchronous function. The current lifespan calls it once, on the event-loop thread, before tasks and before Telegram start. That startup order does not itself overlap two initializations. The function still permits the overlap, and the unlocked-versus-locked test observed it.
