# Stage D.6 resource lifecycle source map

Inspection was static. `forex_bot.app` was not imported for this map. Evidence level for this file is STATIC_ONLY. Runtime confirmation is in the fault-injection results.

## Sequence in `lifespan`

1. Local import of `initialise_fail_closed`, `live_order_auth_reason`, `live_safety_initialised`, and logging configuration.
2. `configure_forex_bot_logging()`.
3. `initialise_fail_closed()`.
4. If `live_safety_initialised()` is false, raise `StartupSafetyAbort`. This is before any database, broker, or task work.
5. `set_lifespan_phase("starting")`.
6. `get_connection()`. The return value is ignored.
7. Load open orders and reconcile state.
8. `build_api()`.
9. `fetch_account_summary` inside `try/except Exception`. A failure is logged and startup continues.
10. `run_reconciliation_once` inside `try/except Exception`. A failure is logged and startup continues.
11. Paper-mode check. This process sets `EXECUTION_MODE=paper`, so the non-paper branch is skipped.
12. `mark_bot_started()`, phase `running`, operational-event cache, alert, live-window log.
13. Four `asyncio.create_task` calls: reconciliation loop, health loop, telegram inbound loop, `run_bot`.
14. `start_telegram_control()`.
15. `try: yield` then `finally` stops Telegram control, cancels the four tasks, and awaits each one. Only `CancelledError` is swallowed on those awaits.

## Resources

| RESOURCE_NAME | CREATION_POINT | OWNER | CLOSE_OR_CANCEL_POINT | FAILURE_BEFORE_YIELD | FAILURE_AFTER_YIELD | POTENTIAL_LEAK | EVIDENCE_LEVEL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Postgres connection | `database.get_connection` via `psycopg2.connect` | `database._pg_conn` for the process | none in `lifespan` | exception handler in `get_connection` nulls the global without `close()`; a later fatal error leaves the global set | `finally` does not close it | yes on the failure path; success path keeps it open by design | STATIC_ONLY |
| Postgres cursor | `connection.cursor()` inside `get_connection` | `database._pg_cursor` | none | nulled without `close()` if init fails after creation | not closed | yes on the failure path | STATIC_ONLY |
| DDL and commit | `cursor.execute` then `connection.commit` inside `get_connection` | database module | commit on success; no rollback in the exception handler | exception returns None and startup continues | not applicable | abandoned connection if commit or execute fails | STATIC_ONLY |
| Broker client | `build_api()` | `oanda_client._api` when a token exists | none in `lifespan` | an exception from `build_api` propagates; no task exists yet | not closed by `finally` | client remains if it was created | STATIC_ONLY |
| Account summary | `fetch_account_summary` | caller discards the return | not a long-lived handle in `lifespan` | caught, startup continues | not applicable | no handle retained by `lifespan` | STATIC_ONLY |
| Reconciliation once | `run_reconciliation_once` | none retained | not applicable | caught, startup continues | not applicable | no handle retained by `lifespan` | STATIC_ONLY |
| Four background tasks | `asyncio.create_task` before `yield` | local variables in `lifespan` | `finally` after `yield` | `finally` does not run, so tasks already created stay scheduled | `finally` cancels them unless an earlier cleanup line raises | yes if creation fails midway or shutdown raises | STATIC_ONLY |
| Telegram control | `start_telegram_control` immediately before `yield` | telegram module | `stop_telegram_control` is the first line of `finally` | if it raises, `finally` has not started | if `stop` raises, later cancels do not run | tasks left running | STATIC_ONLY |

`lifespan` does not call `cursor.close`, `connection.close`, `commit`, or `rollback`. Those operations exist only inside `database.get_connection` and later database helpers. The helpers are not on the startup path after `get_connection` returns.
