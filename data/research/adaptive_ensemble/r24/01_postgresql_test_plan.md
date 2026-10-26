# R.24 isolated PostgreSQL test plan

Status: proposed and amended. No PostgreSQL process has been started. No port has been probed. No database client has been run. No credential file has been read. The configuration below is unchanged. Sections 19–23 are mandatory constraints on any later execution. This amendment is not approval to execute them.

## 1. Installation evidence

Already-known project evidence, not a new probe:

- R.7 recorded `postgres.exe` 18.1 and `initdb.exe` 18.0 at `C:\Program Files\PostgreSQL\18\bin`. Those tools were not on `PATH`. The server was not started. R.7 classified the engine `POSTGRESQL_ENGINE_NOT_EVALUATED`.
- `psycopg2` is already imported by `forex_bot/database.py`. No package will be installed.
- Compose declares a separate service, image `postgres:16-alpine`, database default `trading`, user default `postgres`, volume `pgdata`. The bot service uses host name `db` and port `5432`. Historical notes also name container `forexttradingbot1st-db-1` and volume `forexttradingbot1st_pgdata`.
- This stage did not re-check that the Program Files binaries still exist.

Docker, WSL, and virtual machines are prohibited. The Compose service is not the proposed instance.

## 2. Proposed instance

A new cluster created after approval by the PostgreSQL 18 `initdb` and `postgres` binaries, if those exact binaries are still present. It is not a Windows service, not the Compose container, and not an existing data directory.

If the binaries are missing, or their versions differ from the R.7 record, execution stops. No other server is substituted.

## 3. Proposed data directory

`C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st\data\research\adaptive_ensemble\r24\pgdata`

Created only by `initdb` after approval. It does not exist now.

## 4. Proposed database name

`r24_synthetic_orders`

## 5. Proposed role

`r24_tester`

A bootstrap superuser exists only inside the new cluster so the database and role can be created. The application connects as `r24_tester`. That role is granted create rights only inside `r24_synthetic_orders`.

## 6. Proposed endpoint

`127.0.0.1:55432`

`listen_addresses` is `127.0.0.1`. The port is `55432`. Any local socket directory is `data\research\adaptive_ensemble\r24\pgsocket`.

## 7. Distinction from operational databases

The application defaults, Compose, and `.env.example` use database `trading`, user `postgres`, host `localhost` or `db`, and port `5432`.

The test endpoint differs in all of these:

| Item | Operational default | Proposed test |
|---|---|---|
| Host | `localhost` or `db` | `127.0.0.1` only |
| Port | `5432` | `55432` |
| Database | `trading` | `r24_synthetic_orders` |
| User | `postgres` | `r24_tester` |
| Data | Compose volume `pgdata` | new `r24\pgdata` |

A connection whose host, port, database, or user differs from the approved tuple is refused before `psycopg2.connect`.

## 8. Production connection strings and credentials

`.env` is not read. `forex_bot/config.py` calls `load_dotenv()` on import. The test process stubs that function before importing the application, as the offline stages did.

The child environment is built explicitly. It does not inherit the parent environment. `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASS` are set to the approved test values in that child only.

No production password, token, or account identifier is loaded.

## 9. Test authentication

After approval, a throwaway password is generated in memory and supplied to the new cluster. It is not written to `.env`, the report, or the chat. `pg_hba.conf` in the new cluster allows only `127.0.0.1/32`, database `r24_synthetic_orders`, role `r24_tester`. Other databases and roles are rejected.

## 10. Schema creation

`get_connection` already runs `CREATE TABLE IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS` for `trades`, `reconcile_metadata`, `operational_event_log`, `exec_orders`, `broker_exit_ledger`, and `broker_exit_pending`. On the empty test database, that is the schema creation. No migration tool is used. No production database is altered.

`exec_orders` has a unique `client_order_id`. Recovery uses `RECOVERY_SELECTION_SQL`: pending, partial, unresolved, and filled rows whose `metadata.exposure_safety` is not `CONFIRMED_FLAT`. Reservation uses `pg_advisory_xact_lock` plus `RESERVATION_BLOCK_SQL`, then inserts `PENDING`.

The PostgreSQL table has no `reservation_status` column. That field exists only in the R.23 JSON store. The test must use the PostgreSQL columns and metadata that the current SQL writes.

## 11. Destructive SQL

The application statements are additive. The plan does not use `DROP DATABASE`, `DROP TABLE`, or `TRUNCATE` against any database other than objects inside the new cluster. Cleanup of the new cluster is filesystem shutdown of `r24\pgdata`, not SQL against another server.

`get_connection` returns `None` on failure and does not prove which server it reached. The test wrapper must record the approved endpoint before the call and fail if the connection is absent. `PERSIST_EXEC_ORDERS` must not be `0`. The R.23 JSON store must be disarmed, because an armed store bypasses PostgreSQL.

## 12. Access restriction

- Network barrier denies every socket except `127.0.0.1:55432`.
- DNS remains denied.
- OANDA construction and `execute_oanda_market_open` remain denied.
- The connection wrapper rejects any other host, port, database, or user.
- `main.py`, `run_bot`, and the production lifespan are not called.
- The JSON store is not armed.

## 13. Connection monitoring

The wrapper increments a counter for each accepted `psycopg2.connect` and records host, port, database name, and user. It does not record the password. Process results include that count and any refused attempt. `_pg_conn` must refer only to the approved database. An attempt outside the tuple stops the stage as `R24_SAFETY_SCOPE_VIOLATION`.

## 14. Synthetic records

Orders use client ids beginning `r24-`. Metadata includes `stage: r24`, `synthetic: true`, and the scenario name, plus the application's own `exposure_safety` value. Symbols stay on the existing synthetic `EUR_USD` fixture. No production account, broker, or operational row is copied.

## 15. Shutdown

After the tests, `pg_ctl stop -D` the `r24\pgdata` directory and wait until that process has exited. No Windows PostgreSQL service is started or stopped. The Compose project is not started or stopped.

## 16. Files and objects that would be created

- `r24\pgdata`, the new cluster.
- `r24\pgsocket`, if a local socket directory is required.
- Stage logs and traces under `r24`.
- Database `r24_synthetic_orders`.
- Role `r24_tester` and the cluster-local bootstrap role.
- Tables created by the existing `get_connection` statements.
- Synthetic `exec_orders` rows for the FILLED, UNRESOLVED, and reservation cases.

## 17. Cleanup boundary

Stopping the `r24` server and removing only `r24\pgdata` and `r24\pgsocket` does not touch Program Files, the Compose volume, any other research directory, or the dirty working tree. Those directories are not removed during this checkpoint.

## 18. Uncertainties

- The R.7 binary path and the 18.1/18.0 version difference have not been rechecked.
- Port `55432` has not been probed. If it is occupied after approval, stop and request a new port. Do not move to `5432`.
- Whether a PostgreSQL Windows service is already running is unknown. It will not be used.
- A refused or dropped connection can look like a failed commit. The uncertain-commit case needs a deliberate break of the approved test connection, not a guess about another server.
- `persist_unresolved_order` updates status and the ambiguous-reason metadata. The shared order path also calls `update_exec_order_row`. The test has to observe which statement actually commits `UNRESOLVED` and `exposure_safety`.
- Two Python processes cannot share one `psycopg2` connection. Each must open its own counted connection to the same approved database.

## Approval required before any of the following

- Confirming the PostgreSQL 18 binaries.
- Running `initdb`.
- Starting `postgres` or `pg_ctl`.
- Creating the test role or database.
- Opening a socket to `127.0.0.1:55432`.
- Calling `psycopg2.connect` or `get_connection`.
- Running the application schema statements.

No other endpoint, port, database, role, or data directory is included in this request.

## 19. Mandatory pre-execution cluster checks

These checks are not performed by this amendment. They become mandatory only after a separate approval, and they happen before `initdb`, `postgres`, or any database connection.

- The data directory must be absent, or it must not contain `PG_VERSION` or `postgresql.conf`. An existing cluster is an immediate stop. It is not reused, deleted, or repaired.
- The only cluster that may be started is one just created in `data\research\adaptive_ensemble\r24\pgdata`. `pg_ctl` or `postgres` must receive that data directory explicitly.
- No Windows PostgreSQL service is queried, started, stopped, or reused. The Compose project, container `forexttradingbot1st-db-1`, and volume `pgdata` are not used.
- Port `55432` must be bindable on `127.0.0.1` by the test runner before the server starts. An occupied port is an immediate stop.
- There is no fallback to port `5432`, host `localhost` or `db`, database `trading`, role `postgres`, or any other endpoint. A mismatch between the running postmaster and `127.0.0.1:55432` / `r24_synthetic_orders` / `r24_tester` is an immediate stop.

## 20. Authentication and network configuration

The new cluster, if later approved, must be configured before any application SQL:

- `listen_addresses = '127.0.0.1'`.
- `port = 55432`.
- No other interface is enabled.
- `pg_hba.conf` contains no `trust` entry for local or loopback users.
- Authentication is `scram-sha-256` for `127.0.0.1/32`, database `r24_synthetic_orders`, role `r24_tester` only.
- Cluster initialisation uses a bootstrap role inside the new cluster only. That role is not the application role and is not used by `get_connection`.
- `r24_tester` is `NOSUPERUSER`, `NOCREATEDB`, and `NOCREATEROLE`. It can connect only to `r24_synthetic_orders` and can create the application's tables there. It cannot connect to `postgres`, `trading`, or any other database.

Before the first application statement, the test reads the new cluster's `postgresql.conf` and `pg_hba.conf`, then uses the bootstrap role to confirm `r24_tester` is not a superuser and can connect only to `r24_synthetic_orders`. A connection attempt to another database or role on this cluster must fail. Application SQL starts only after those checks pass.

## 21. Configuration isolation

The offline driver builds a fresh environment. It does not inherit the parent process environment. It stubs `load_dotenv` before importing `forex_bot`, so `.env` is not loaded. It sets `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=55432`, `POSTGRES_DB=r24_synthetic_orders`, `POSTGRES_USER=r24_tester`, and a throwaway `POSTGRES_PASS` that is not written to `.env` or the report.

After import, the driver must observe `Config.POSTGRES` equal to that endpoint, database, and role. A different value stops the test before `get_connection`. The R.23 store is disarmed, and `offline_exec_order_store_path()` must be `None`. `PERSIST_EXEC_ORDERS` is not `0`.

The connection wrapper accepts only the approved tuple. If `get_connection` returns `None`, the test records a failed connection and stops that case. It does not retry with `localhost`, `5432`, `trading`, or `postgres`. `lifespan`, the production scheduler, and `run_bot` are not called.

## 22. Startup recovery failure

Source inspection does not prove that every failed PostgreSQL recovery blocks a later evaluation. The marker is `STARTUP_RECOVERY_FAIL_CLOSED_NOT_PROVEN`. The required test and the possible repair are in `02_postgresql_safety_amendment.md`. No source change is made in this amendment.

## 23. Separate approval checkpoint

Execution still requires a separate user approval of this exact cluster, endpoint `127.0.0.1:55432`, database `r24_synthetic_orders`, role `r24_tester`, scram authentication limited as above, and the operations listed in the amendment. Approval of this prompt, of R.23, or of the original plan does not authorise those operations.
