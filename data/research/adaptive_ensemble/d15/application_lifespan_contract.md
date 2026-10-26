# Application lifespan contract

`lifespan` is `forex_bot/app.py` lines 333–451.

Startup order:

1. Clear `_last_cleanup_errors`.
2. `initialise_fail_closed()`.
3. Abort before database, broker, reconciliation, and tasks when safety is not startup-compatible.
4. `get_connection()`, order and reconcile loads, `build_api()`, account summary, and reconciliation.
5. Create the reconciliation, health, Telegram inbound, and trading-loop tasks.
6. Call `start_telegram_control()` and report its string result.
7. Yield.

Shutdown order:

1. If start was attempted, call `stop_telegram_control()`.
2. A stop exception is recorded and sets `telegram_stop_failed`.
3. A returned status is reported by `_note_telegram_stop` without raising.
4. Cancel and await every owned task.
5. Release the database only after a startup exception when stop did not raise.
6. On a successful shutdown, send the stopped alert and leave the database published.

`_note_telegram_start` lines 99–122 logs `D12-START-01` for `START_REFUSED_PREVIOUS_WORKER`, a static continuation line for `START_FAILED`, and an unrecognised-status line otherwise. `None`, `START_STARTED`, `START_ALREADY_RUNNING`, and `START_DISABLED` produce no refusal warning. The warning is not added to cleanup errors.

`_note_telegram_stop` lines 79–96 is silent for `None`, `STOP_COMPLETED`, and `STOP_NOT_RUNNING`. `STOP_INCOMPLETE_WORKER_ALIVE` logs and records `D12-STOP-01`. Another value records `D12-STOP-UNKNOWN`. Neither status raises or releases the database.
