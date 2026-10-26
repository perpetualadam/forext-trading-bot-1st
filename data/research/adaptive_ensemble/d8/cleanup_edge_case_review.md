# D.8 cleanup edge cases

## Startup boundary

`initialise_fail_closed` and the `live_safety_initialised` check run before `get_connection`. A protected or corrupt safety file raises `StartupSafetyAbort` outside the resource `try`, so the `finally` block does not release a connection that was never opened. The isolated corrupt case connected zero times.

## What the `finally` block does

1. If Telegram start was attempted, it calls `stop_telegram_control` in its own `try`. A stop exception is recorded and does not skip task cleanup.
2. It awaits every owned task through `_await_owned_tasks`: cancel all, then await each. An await exception is recorded and the remaining tasks are still awaited.
3. It releases the database only when `startup_failure is not None and not telegram_stop_failed`.
4. Shutdown tail (`mark_bot_stopped`, phase offline, alert) runs only when startup succeeded.
5. Secondary exception type names are stored in `_last_cleanup_errors`. The original startup exception is re-raised by the `except` before `finally`. A secondary exception is raised afterward only when there was no startup failure, no body error, and the current task is not being cancelled.

## Why a Telegram stop failure skips database release

The condition is explicit at `app.py` lines 391–392. It is intentional. `stop_telegram_control` may have raised before `join`, so the poller thread may still be inside `fetch_all_trades_ordered`. Closing the shared connection in that state could close an object another thread is using. Keeping it is the conservative choice for that failure. It can also retain a connection when no borrower exists. The isolated `startup_stop` case observed exactly that: tasks were cleaned, the primary exception remained the startup failure, the cleanup list contained `RuntimeError`, and the fake connection stayed open until the harness closed it.

Production `start_telegram_control` documents that it does not raise to the caller. The release-after-failed-startup path that follows a raised `start` is therefore not the path production `start` takes. The lifespan condition still implements the skip.

## What cancellation does not stop

Cancelling the four asyncio tasks does not join the Telegram control thread. Successful `stop_telegram_control` can return after a 2-second timeout while that thread is alive, and it does not raise. Normal shutdown does not release the connection anyway, because `startup_failure` is null after a successful yield.

## Repeated lifespan

A second isolated startup with a valid BLOCKED document stayed BLOCKED, left all six strategies inactive, and left no owned task pending. The connection from the successful startup was still open at the application snapshot and was closed by the harness afterward. That matches the process-lifetime ownership chosen in D.7. It is not an application leak on the success path. The overlap leak in D8-CONC-01 is a different object: a second connection that was never stored.
