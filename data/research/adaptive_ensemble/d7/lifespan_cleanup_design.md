# D.7 lifespan cleanup design

`StartupSafetyAbort` remains before `get_connection`, `build_api`, and `create_task`. The resource `try` starts only after that guard. A protected file does not enter the cleanup `finally`, because no database connection or background task has been created.

Inside the `try`, each `asyncio.create_task(...)` result is appended to `owned_tasks` on the next line. The four call strings are unchanged. `telegram_start_attempted` is set only after the Telegram import succeeds and immediately before `start_telegram_control()`.

An exception before `yield` is stored and re-raised. The `else` clause contains `yield`, so an exception from the server block after a successful startup is not treated as a startup failure and does not release the database connection.

The `finally` block always:

1. Attempts `stop_telegram_control` if start was attempted. A stop exception is recorded and does not skip later steps.
2. Sets the lifespan phase to `stopping` only after a successful startup.
3. Cancels every owned task, then awaits every owned task.
4. Releases the published database connection only after those awaits, and only for a startup failure whose Telegram stop did not raise.
5. Runs the existing stopped-state updates only after a successful startup.

Account-summary and reconciliation failures stay inside their own handlers and still continue startup.
