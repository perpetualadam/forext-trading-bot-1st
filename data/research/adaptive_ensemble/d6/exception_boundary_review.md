# Stage D.6 exception boundaries

## Safety preflight

`StartupSafetyAbort` is raised and not caught inside `lifespan`. No database, broker, or task work has started. This remains a fatal stop.

## Database

`get_connection` catches `Exception`, logs `PostgreSQL unavailable`, sets `_pg_conn` and `_pg_cursor` to `None`, and returns `None`. `lifespan` ignores that return value and continues. This is an expected nonfatal startup error for the caller. It is also a partial-initialization failure when the exception happens after `connect` has returned a connection, because that object is not closed or rolled back.

## Broker account summary and reconciliation

Both calls sit in their own `try/except Exception`. The exception is logged and startup continues. That nonfatal policy was preserved. These tests did not treat those exceptions as fatal.

## Broker construction

`build_api()` is not in a `try`. An exception propagates. Tasks have not been created. The `finally` block has not been entered.

## Background tasks and yield

The four `create_task` calls and `start_telegram_control()` sit before `try`. An exception there propagates and the `finally` block does not run.

`finally` always starts only after `yield` has been reached. Its first action is `stop_telegram_control()`. Each subsequent `await` catches only `asyncio.CancelledError`. A different exception skips the remaining cancels. There is no retry.

## Classification

| Boundary | Class |
| --- | --- |
| Invalid safety state | FATAL_STARTUP_ERROR |
| `psycopg2.connect` failure | EXPECTED_NONFATAL_STARTUP_ERROR |
| Failure after a connection object exists | PARTIAL_INITIALIZATION_FAILURE and EXPECTED_NONFATAL_STARTUP_ERROR |
| Account summary and one-shot reconciliation | EXPECTED_NONFATAL_STARTUP_ERROR |
| `build_api` and pre-task failures | FATAL_STARTUP_ERROR |
| Failure after at least one `create_task` | PARTIAL_INITIALIZATION_FAILURE |
| Failure inside `finally` | SHUTDOWN_FAILURE |

No boundary changes live-order authorisation or activates a strategy.
