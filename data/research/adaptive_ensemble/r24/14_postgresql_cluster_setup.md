# R.24 isolated cluster setup

Classification later recorded in `19_postgresql_integration_report.md`.

## Preflight

| Check | Result |
| --- | --- |
| Project root | `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st` |
| Branch | `main` |
| HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| `forex_bot/database.py` | `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` |
| `postgres.exe --version` | `postgres (PostgreSQL) 18.6` |
| `initdb.exe --version` | `initdb (PostgreSQL) 18.6` |
| Data directory before creation | `C:\R24_PostgreSQL_Test\pgdata` was absent |
| Port `55432` before start | Not listening |
| Tools and data directory | `C:\R24_PostgreSQL_Test`, not under OneDrive, not a reparse point |
| Existing service | `postgresql-x64-18` remained `C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe` with data directory `C:\Program Files\PostgreSQL\18\data` |

Application imports used an explicit child environment: host `127.0.0.1`, port `55432`, database `r24_synthetic_orders`, role `r24_tester`. `load_dotenv` was stubbed. A connection wrapper refused any other host, port, database, or role before calling the driver.

## Cluster

| Item | Value |
| --- | --- |
| `initdb` | `C:\R24_PostgreSQL_Test\tools\pgsql\bin\initdb.exe` |
| Data directory | `C:\R24_PostgreSQL_Test\pgdata` |
| Bootstrap role | `r24_bootstrap`, superuser, used only for setup |
| Application role | `r24_tester` |
| `listen_addresses` | `127.0.0.1` |
| Port | `55432` |
| `password_encryption` | `scram-sha-256` |
| Server process | PID `12896`, image `C:\R24_PostgreSQL_Test\tools\pgsql\bin\postgres.exe` |
| Server command | `-D C:/R24_PostgreSQL_Test/pgdata` |
| Listener | `127.0.0.1:55432` only |

`pg_hba.conf` allows only `host all all 127.0.0.1/32 scram-sha-256`. IPv6, other IPv4 addresses, local sockets, and replication are `reject`. No active `trust` rule was left. No Windows service was registered. PATH and the registry were not changed. No configuration or data was copied from another cluster.

The stored password verifier for `r24_tester` begins `SCRAM-SHA-256`. The password itself is not recorded.

## Roles and schema

`r24_tester` is login-capable and is not a superuser, not a replication role, and cannot create databases, roles, or bypass row security. A connection to database `postgres` as `r24_tester` was refused. `CONNECT` on `postgres`, `template1`, and `r24_synthetic_orders` was revoked from `PUBLIC`. `r24_tester` received `CONNECT` only on `r24_synthetic_orders`.

The first application `get_connection` created `exec_orders`, `trades`, `reconcile_metadata`, `operational_event_log`, `broker_exit_ledger`, and `broker_exit_pending`. `r24_tester` has `USAGE` and `CREATE` on schema `public` in that database only, because the application connection runs `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... IF NOT EXISTS`.
