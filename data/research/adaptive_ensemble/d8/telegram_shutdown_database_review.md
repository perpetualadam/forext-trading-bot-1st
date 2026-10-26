# Telegram shutdown and the database

## Observed

`startup_stop` injects a startup exception after the four tasks exist and makes `stop_telegram_control` raise. Actual lifespan then:

- left `pending` at 0 and `harness_cancelled` at 0, so task cleanup was not skipped;
- kept the primary message as `injected failure before yield`;
- recorded `RuntimeError` in `startup_cleanup_errors`;
- left the fake connection open (`pg_conn_held` true, `application_closed` 0);
- left the harness to close that one connection afterward.

`before_yield` uses the same startup exception but lets stop return. The application then closed the connection (`application_closed` 1, `harness_closed` 0).

`shutdown_stop` yields successfully and then stop raises. The connection stays open because startup succeeded, not because of the stop-failure flag. That is the D.7 process-lifetime decision. Task cleanup still finished.

## Why the flag exists

`app.py` lines 391–392 release only when startup failed and Telegram stop did not raise. The stop helper sets an event and joins for 2 seconds. If stop raises, join may not have run. The poller can still be in `fetch_all_trades_ordered`. Cancelling the four asyncio tasks does not stop that thread. Retaining the connection avoids closing it under that thread. It can also retain a connection when the thread was never created. The tests used a fake stop, so they do not prove a real poller was inside the database.

## Production start does not raise

`start_telegram_control` returns immediately when commands are disabled, and otherwise swallows thread-start exceptions. The lifespan branch that releases after a raised start is not entered by that function. The condition is still present and was executed with a test double.

## Quiescence

Nothing in lifespan reads `thread.is_alive()` after join. A timeout is not an exception, so a still-running poller does not by itself set `telegram_stop_failed`. Normal shutdown does not release the connection, so that timeout does not currently cause a close. There is no registry of helpers that borrowed the connection. See `database_borrower_quiescence.md`.
