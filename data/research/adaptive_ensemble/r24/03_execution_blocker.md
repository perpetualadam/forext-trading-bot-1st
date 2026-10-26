# R.24 execution stopped before a cluster existed

The approved configuration was not changed. No PostgreSQL server was started. No port other than the availability check of `127.0.0.1:55432` was used. No database connection was opened. No application SQL was run. No application source was modified.

## Checks that passed

- `postgres.exe`, `initdb.exe`, `pg_ctl.exe`, and `psql.exe` exist in `C:\Program Files\PostgreSQL\18\bin`.
- `postgres.exe` and `pg_ctl.exe` report PostgreSQL 18.1. `initdb.exe` reports PostgreSQL 18.0. That pair matches the R.7 record.
- `data\research\adaptive_ensemble\r24\pgdata` did not exist.
- `127.0.0.1:55432` accepted a local bind and was released.
- The R.24 plan and safety amendment were present.
- Parent `POSTGRES_*` variables were unset. `.env` was not read.
- The installation's `data` directory was not opened. Docker, port `5432`, database `trading`, and role `postgres` were not used.

## Check that failed

`initdb` refused to create the cluster:

`program "postgres" was found by initdb but was not the same version as initdb`

`postgres` and `initdb` are not on `PATH`. The only binaries are the approved PostgreSQL 18 pair, and there is no second `initdb`. `initdb` 18.0 will not initialise a cluster with `postgres` 18.1. `pgdata` was not created. `pg_ctl start` was not run.

No other port, cluster, database, role, or data directory was selected.

## Recheck

A later approval was checked again before any startup. `postgres.exe` file version 18.1, `initdb.exe` file version 18.0, `pg_ctl.exe` reports 18.1. `r24\pgdata` was still absent. `127.0.0.1:55432` was still free. `initdb` was not run again. No other installation was selected.

## Classification

`R24_BLOCKED_DATABASE_ISOLATION`
