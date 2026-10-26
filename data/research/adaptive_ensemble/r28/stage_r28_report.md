# STAGE R.28 — POSTGRESQL RESERVATION DEADLOCK REPAIR REPORT

**Classification: `R28_POSTGRESQL_DEADLOCK_REPAIRED`**

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Existing work was left in place. No commit, reset, stash, clean, deploy, or rollback.

**PRODUCTION DEPLOYMENT: NO-GO**
**PRACTICE ORDERS: NOT AUTHORISED**
**LIVE TRADING: NOT AUTHORISED**
**ROLLBACK: NO-GO**

R.29 was not started.

## Root cause

Relation `16428` in database `16389` is `public.exec_orders` on `r24_synthetic_orders`. The pre-repair application race reproduced the R.24 failure three times in eight gated pairs. Each pair left one row. The loser rolled back and returned false.

The server log names both statements:

- `INSERT INTO exec_orders (client_order_id, symbol, side, units, status, metadata)` waits for `RowExclusiveLock` on relation `16428`.
- `ALTER TABLE exec_orders ADD COLUMN IF NOT EXISTS filled_units DOUBLE PRECISION` waits for `AccessExclusiveLock` on the same relation.

`get_connection` ran that `ALTER`, plus `CREATE TABLE IF NOT EXISTS`, on every new connection and committed only after the whole DDL script. `CREATE TABLE IF NOT EXISTS` on the existing table holds `AccessShareLock` until that commit. The other process had already committed its DDL, then taken `AccessShareLock` with `SELECT status FROM exec_orders` and requested `RowExclusiveLock` for the insert. The queued `AccessExclusiveLock` and the lock upgrade deadlock each other. The advisory lock was not the conflicting lock. The unique constraint `exec_orders_client_order_id_key` remained in place and was not the deadlock.

A narrower probe, `SELECT` then `ALTER` then `INSERT` without the earlier `CREATE TABLE` lock, showed `AccessExclusiveLock` waiting behind `AccessShareLock` and did not deadlock. The deadlock requires the connection-setup DDL transaction, which is why the original reservation path hit it. DDL was not inside the reservation transaction; it overlapped that transaction from the other process because both processes open a connection inside `insert_exec_order_pending_if_absent`.

## Repair

`get_connection` no longer executes `CREATE` or `ALTER`. It runs one read-only catalog check and commits that check before returning the connection. The check requires the six existing tables, the columns previously added by `ALTER`, and the unique constraint on `client_order_id`. If any of those are absent, the connection is closed and the function returns `None`. Reservation then fail-closes and does not dispatch.

The advisory-lock, blocking-status, `INSERT ... ON CONFLICT DO NOTHING`, commit, and rollback path in `insert_exec_order_pending_if_absent` is unchanged. The old DDL text remains in the module and is not executed. No production migration was added.

`forex_bot/database.py` SHA-256 moved from `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` to `dfcab6b9b1b2c6f0d025666acc8878f17049eda11078406995d85280dae790b1`. The R.10 source pin was updated to that hash.

## Isolated server

PostgreSQL `18.6` from `C:\R24_PostgreSQL_Test\tools\pgsql\bin\postgres.exe`. Data directory `C:\R24_PostgreSQL_Test\pgdata` is not a symlink or junction. `listen_addresses` is `127.0.0.1` and the port is `55432`. The Windows service `postgresql-x64-18` uses `C:\Program Files\PostgreSQL\18\data` and was not the target.

The existing cluster was started without `initdb`. Postmaster PID `12784`. Listener `127.0.0.1:55432`, database `r24_synthetic_orders`, role `r24_tester`.

## Concurrency after the repair

Twelve gated pairs, two operating-system processes each, produced zero deadlocks. Every pair committed exactly one row and the other attempt returned false. Example process pairs include `7696`/`7908` and `10936`/`20312`. The server log has no deadlock after the pre-repair reproductions at 23:40.

A trigger rejected one insert. That process, PID `15660`, returned false, left no row, and stayed alive after rollback. PID `19100` then reserved the same symbol and committed one row, so the advisory lock had been released.

Dropping `filled_units` made the next reservation return false. The application did not add the column back. The test restored it with its own `ALTER`. A second reservation with client id `cid-r28-dup` returned false.

Direct recovery of the four statuses blocked new entries: `PENDING` and `PARTIAL` as `active_reservation`, `FILLED` as `exposure_unconfirmed`, and `UNRESOLVED` as `unresolved_intent`. The shared `evaluate` path, in a separate process, blocked `EUR_USD`, `GBP_USD`, `AUD_USD`, and `USD_CAD` with `broker_requests == 0`, `reservation_attempted == false`, and `production_eligible == false`. A missing-NAV OANDA document blocked at `broker_equity_missing` during `account_reconciliation`, before reservation, with no broker request.

## Regressions

| Suite | Result |
| --- | --- |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 first three runs | 1 failed, 68 passed, 5 skipped, each from `WinError 5` replacing `r10/synthetic_live_safety_state.json` |
| R.10 fourth run | 69 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

The failed R.10 tests were `test_i23_historical_filled_row`, `test_i41_clean_shutdown`, and `test_i27_missing_dependency`. `live_safety.py` was not changed and the state file was not deleted.

## Shutdown

`pg_ctl -D C:\R24_PostgreSQL_Test\pgdata -m fast stop` completed. `postmaster.pid` is gone. `127.0.0.1:55432` is not listening. The data directory is still in place. `postgresql-x64-18` is still running from `C:\Program Files\PostgreSQL\18\data`.

## Limitations

The R.28 row cleanup deleted the original `NZD_USD` race row. It was put back as `cid-r24-race-b`, `PENDING`, 1000 units, which is the winner recorded in the R.24 trace. The original timestamp was not recovered.

`r24_tester` can still create objects if a test issues DDL itself. The application connection no longer does that during reservation. An empty database now fail-closes instead of creating tables. No broker call, OANDA request, production launcher, or Windows-service connection was made.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**
