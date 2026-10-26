# Application lifespan shutdown map

Source: `forex_bot/app.py` `lifespan`, lines 286-415. Gate A did not execute it. Gate D executed `app.lifespan` under isolation.

Startup order inside the `try`:

1. Safety preflight `initialise_fail_closed`. A protected, corrupt, or invalid state raises `StartupSafetyAbort` before `get_connection`.
2. `get_connection()`.
3. Order load, reconciliation load, `build_api`, account summary, one reconciliation pass.
4. Four `asyncio` tasks: reconciliation loop, health snapshot, telegram inbound, `run_bot`.
5. `telegram_start_attempted = True`, then `start_telegram_control()`.

`start_telegram_control` is the last statement in the `try`. It catches its own start errors and does not raise to `lifespan`. Nothing after a successful start can set `startup_failure`.

Shutdown `finally`:

- If start was attempted, call `stop_telegram_control` inside its own `try`. A stop exception is recorded and sets `telegram_stop_failed`. Cleanup continues.
- Then `_await_owned_tasks` cancels every owned task and awaits each one. One await failure does not skip the others.
- `release_connection_after_failed_startup` runs only when `startup_failure is not None` and `telegram_stop_failed` is false.
- A successful startup does not release the database connection.
- The shutdown tail (`mark_bot_stopped` and the stopped alert) runs only when startup succeeded.
- Secondary exceptions are re-raised only when there is no startup failure, no body error, and the lifespan task is not being cancelled.

Answers:

- Telegram stop is invoked on normal shutdown and on startup failure after start was attempted.
- Telegram stop is not invoked when startup fails before `telegram_start_attempted` is set.
- Stop errors are caught. They do not skip task cleanup. They do skip database release.
- A returned stop is treated as finished. The lifespan does not read `is_alive()`.
- On the success path, database release does not run after stop.
- On the failure path, release runs when stop did not raise. It does not run because stop raised.
- A still-alive Telegram thread is not detected. `blocked_shutdown` left thread 3836 alive with `cleanup_errors` empty.
- Application shutdown can finish while that thread remains alive. Observed in `blocked_shutdown`.

`startup_failure` after the Telegram thread exists is `NOT_REACHABLE_IN_CURRENT_SOURCE` without replacing `start_telegram_control`. The production start function does not raise, and it is the last statement in the startup `try`.
