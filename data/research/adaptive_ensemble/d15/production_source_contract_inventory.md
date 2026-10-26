# Production source contract inventory

Read from the current files. No production file was modified.

## Application

`forex_bot/app.py` lifespan begins at line 333. `initialise_fail_closed()` runs at line 344, before `get_connection()`. Line 345 aborts with `StartupSafetyAbort` when `live_safety_initialised()` is false. Broker construction, task creation, and `start_telegram_control()` are inside the same try. The start result is passed to `_note_telegram_start` at line 417. The yield is the else branch. The finally block calls `stop_telegram_control()` at line 431 and `_note_telegram_stop`. `_await_owned_tasks` then runs. `release_connection_after_failed_startup()` runs only when startup failed and the stop call itself did not raise, at line 440.

## Telegram

`forex_bot/telegram_control.py` lines 126–133 define the stop and start result constants. `start_telegram_control()` is lines 1177–1213. `stop_telegram_control()` is lines 1216–1240. The worker reference and stop event stay under `_poller_lock` at line 122. The stop event is set by stop and is not cleared by a refused start. The join timeout remains 2.0 seconds and happens outside the lock.

## Database

`forex_bot/database.py` uses `_pg_lock` at line 22. `release_connection_after_failed_startup()` is line 148. `get_connection()` is line 185 and holds the lock across reuse, initialization, and publication. There is no borrower counter. A failed attempt discards an unpublished connection and cursor. A successful application shutdown does not release the process-global connection.

## Safety

`live_safety_initialised()` at line 88 is true only when both `_initialised` and `_state_valid` are true. `_refuse_existing` at line 365 sets `_initialised` true and `_state_valid` false, so corrupt, future, and invalid files still fail the application predicate. Effective authorisation is set to BLOCKED on process start. `strategy_meta.Strategy.active` is true only when the assigned value is boolean True. The six strategy names remain scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, and swing_breakout.
