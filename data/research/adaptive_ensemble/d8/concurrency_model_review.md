# D.8 concurrency model

Classification of the database initialization path: THREAD_CONCURRENCY is possible. ASYNC_INTERLEAVING does not split the synchronous `get_connection` body on one thread. The current startup order is SEQUENTIAL for the first connection.

## Threads

- `telegram_control.start_telegram_control` can start a daemon thread named `telegram-control` (`telegram_control.py` lines 1152–1158). With `TELEGRAM_COMMANDS=0` it returns before creating a thread. Production `start_telegram_control` catches its own start exception and does not raise to lifespan.
- The poller can call `fetch_all_trades_ordered`, which holds `_pg_lock` for the whole helper call.
- `stop_telegram_control` sets a stop event and `join`s for at most 2.0 seconds (`telegram_control.py` line 1174). A timeout does not raise. The thread can still be alive.
- `app.py` uses `asyncio.to_thread` for account summary and one reconciliation pass after `get_connection` has returned.
- Alert sending uses its own thread and does not call the database.

## Async tasks

Lifespan creates four tasks after the first `get_connection` returns: reconciliation, health snapshot, Telegram inbound, and `run_bot`. Cancelling those tasks does not stop the Telegram control thread. Synchronous `get_connection` bytecode does not interleave with other coroutines on the same thread.

## Database helpers

Every helper in `database.py` takes `_pg_lock` before `get_connection`. Two helpers therefore cannot both be inside initialization. The second waits, then either reuses the published connection or initializes only if the first did not publish.

## Reachable overlap

The current startup call at `app.py` line 317 is the only production caller that does not hold `_pg_lock`. It runs before the four tasks, before `to_thread` database work, and before Telegram start. Those later callers see a published connection, or they take the lock if they are the ones reconnecting.

An overlap is still possible if any unlocked caller runs while another caller is inside `get_connection` and no connection is published. The tests created that schedule on the real function. The current lifespan sequence does not start the second caller during that window.

## Unverified paths

No production operational process was inspected. Whether a live process has an extra thread inside `get_connection` was not checked. Borrower quiescence after `join` timeout is unverified.
