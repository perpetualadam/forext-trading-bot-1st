# STAGE R.24 — ISOLATED POSTGRESQL INTEGRATION REPORT

## 1. Classification

`R24_ISOLATED_POSTGRESQL_RECOVERY_INTEGRATED`

## 2. Isolation preflight

The project root was `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`, branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. `forex_bot/database.py` was `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` before and after the run. The standalone `postgres.exe` and `initdb.exe` both reported PostgreSQL 18.6. `C:\R24_PostgreSQL_Test\pgdata` did not exist. Port `55432` was free. The tools and data directory are outside OneDrive and are not reparse points. The existing service `postgresql-x64-18` points at `C:\Program Files\PostgreSQL\18` and was not the target.

## 3. Cluster and listener

`initdb` created only `C:\R24_PostgreSQL_Test\pgdata`. The server ran as PID `12896` from `C:\R24_PostgreSQL_Test\tools\pgsql\bin\postgres.exe` with that data directory. Its only listener was `127.0.0.1:55432`. Authentication was SCRAM-SHA-256. No `trust` rule remained. No Windows service was created.

Database `r24_synthetic_orders` and non-superuser role `r24_tester` were created. `r24_tester` cannot connect to database `postgres`. The application connection created the order and recovery tables.

## 4. Persistence

A synthetic `USD_CHF` order `cid-r24-persist` was inserted and updated to `FILLED` through the application functions, then read back as `FILLED`. A duplicate submission returned false. A triggered insert failure returned false, left no row, and did not dispatch.

## 5. Reservation atomicity and rollback

Two processes, PIDs `10224` and `18916`, competed for `NZD_USD`. PostgreSQL aborted one transaction with a deadlock. The application rolled that transaction back and returned false. The other process committed one row. One reservation remained.

A separate process held `pg_advisory_xact_lock` for `EUR_AUD` and rolled it back. PID `19656` was the holder and PID `17480` was the waiter. The waiter then inserted. After the failed `EUR_GBP` insert, a new process inserted `cid-r24-after`, so the failed transaction had released its lock.

## 6. Separate-process recovery

FILLED, UNRESOLVED, PENDING, and PARTIAL each crossed two operating-system processes. Process A exited before Process B started. Process B recovered through `load_open_orders_from_db_into_memory` and then the shared `evaluate` path. FILLED, UNRESOLVED, and PARTIAL stayed `exposure_unconfirmed`. PENDING stayed `active_reservation`. Process B dispatched nothing. `confirm_exposure_flat` did not clear those holds. Details are in `16_postgresql_restart_recovery.md`.

## 7. Startup recovery fail-closed

Connection refusal, a broken recovery query, and `ingest_recovery_snapshot([], False)` each made `evaluate` return `recovery_unreadable` with no reservation and no dispatch. A repeated evaluate stayed blocked. An empty recovery was readable and did not set the failure latch. A later successful recovery of a FILLED row cleared only that latch and left `exposure_unconfirmed` in place. A caller-supplied flat marker did not clear either condition.

## 8. Regressions

Offline R.8–R.23 and the R.24 recovery tests all exited 0. No failures. The regression suite had 120 passed, 7 skipped, and 1 deselected. R.24 offline recovery had 14 passed. The other suite counts are in `18_postgresql_regressions.json`.

## 9. Source integrity

These hashes were unchanged:

| File | SHA-256 |
| --- | --- |
| `forex_bot/database.py` | `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` |
| `forex_bot/bot_loop.py` | `a8b455dad91c464df8ba030b7f119f3c1795ce289e21b83de0af771309823ac2` |
| `forex_bot/orders.py` | `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4` |
| `forex_bot/app.py` | `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `forex_bot/config.py` | `13db72c668f60a8a50bf148789070c29cb941be748a51b298bd7bcb2971f99fd` |

No application source was modified.

## 10. Safety and network

Real broker calls: 0. A probe for `postgres@localhost:5432/trading` was refused by the test wrapper and did not connect. DNS lookups were blocked. `.env` was not read. `main.py`, `run_bot`, the production lifespan, and OANDA were not entered. The existing Windows service and `C:\Program Files\PostgreSQL\18` were not modified.

## 11. Shutdown

`pg_ctl -D C:\R24_PostgreSQL_Test\pgdata -m fast stop` completed. The postmaster pid file was gone. Port `55432` was not listening. `C:\R24_PostgreSQL_Test\pgdata` was left in place. `postgresql-x64-18` was still running from `C:\Program Files\PostgreSQL\18`.

## 12. Remaining limitations and hard stop

The concurrent reservation proof included one PostgreSQL deadlock. The losing transaction rolled back and did not leave a second row. This run does not make the bot production-durable, and it does not authorise trading.

`r24_tester` can create objects in schema `public` of `r24_synthetic_orders` because the application connection issues its own DDL. It cannot administer other databases.

R.25 has not started.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

END OF R.24 ISOLATED POSTGRESQL INTEGRATION
