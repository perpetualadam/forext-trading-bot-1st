# R.24 PostgreSQL safety amendment

This amendment plans later execution. It does not authorise it. No server was started, no port was probed, and no application source was changed. The proposed cluster remains `r24\pgdata`, `127.0.0.1:55432`, database `r24_synthetic_orders`, role `r24_tester`.

## New-cluster isolation

Later execution must stop immediately unless all of these are true:

- `r24\pgdata` contains no existing cluster.
- `127.0.0.1:55432` can be bound before PostgreSQL is started.
- The process started is the new cluster only.
- No Windows service, Compose database, port `5432`, database `trading`, or role `postgres` is used.

An existing cluster or an occupied port is a stop, not a reason to choose another endpoint.

## Authentication and network

The server listens only on `127.0.0.1:55432`. Host authentication does not use `trust`. The application role is not a superuser and can connect only to `r24_synthetic_orders`. Bootstrap administration is separate and is not used by `get_connection`. These settings are read back from the new cluster, and a rejected cross-database connection is observed, before application SQL runs.

## Configuration isolation

The driver stubs `load_dotenv`, supplies only the approved `POSTGRES_*` values, and checks `Config.POSTGRES` before connecting. The JSON store stays disarmed. A failed connection is not retried against the operational defaults. The production lifespan, scheduler, and `run_bot` are outside the driver.

## Startup recovery assessment

`STARTUP_RECOVERY_FAIL_CLOSED_NOT_PROVEN`

`get_connection` returns `None` on failure and does not set `_process_fail_closed`. Returning `None` is not a block.

| Outcome | What the source does | Later `evaluate` |
|---|---|---|
| Connection not obtained | `init_persistence` ignores `None`. `fetch_exec_orders_open_for_recovery` raises `OrderRecoveryUnreadable`. `read_durable_recovery` returns `[], False` and does not fail-close. | Shared `evaluate_one_instrument_iteration` calls `exposure_entry_block_reason`, not `read_durable_recovery`. With the flag unset, it returns no block. |
| Recovery query fails | `fetch_exec_orders_open_for_recovery` raises. `load_open_orders_from_db_into_memory` catches that and calls `force_order_recovery_fail_closed`, then returns 0. `read_durable_recovery` returns unreadable without setting the flag. `initialise_application` does not set the flag when recovery raises. | The exposure gate blocks only if that flag was set. The shared evaluation does not repeat the query. |
| Empty successful result | A completed query returning no rows is ingested with `readable=True`. No exposure is recorded. | No recovery block. This is an empty success, not a failure. |
| FILLED or UNRESOLVED recovered | `ingest_recovery_snapshot` records unconfirmed exposure or unresolved intent. | `exposure_entry_block_reason` returns `exposure_unconfirmed` or `unresolved_intent` before reservation. |

The production loader can set the flag, but startup continues after it returns 0. The offline startup ports default `recovery_readable` to true and do not call that loader unless a provider does. The shared entry path never consults the readable flag. PostgreSQL behaviour of these branches has not been executed.

Required later test, only after approval: with a committed synthetic FILLED row, make the approved connection or recovery query fail, run the actual startup recovery function, then run `evaluate`. The pass condition is `recovery_unreadable`, zero reservation attempts, and zero adapter calls. Repeat for an empty successful database, which must not be labeled unreadable, and for a present FILLED or UNRESOLVED row, which must block on exposure. If the failed case evaluates as flat, the repair is to fail-close inside the connection and recovery functions that currently return `None` or `[], False`, or to make the shared evaluation honour that unreadable result. That repair is not made here.

## Approval boundary

A separate approval must name this cluster, endpoint, database, role, scram authentication, and the pre-execution checks. This document does not give that approval.

## Operations that remain unauthorised

Confirming binaries, binding or probing `55432`, `initdb`, starting `postgres`, creating the role or database, `psycopg2.connect`, `get_connection`, and application SQL.
