# STAGE R.11 — OFFLINE HISTORICAL FILLED RECOVERY REPAIR AND STARTUP INTEGRATION REPORT

## 1. Executive summary

Overall classification: **R11_OFFLINE_HISTORICAL_RECOVERY_REPAIRED**.

The production recovery SQL now keeps historical FILLED rows whose exposure marker is missing, empty, NULL, or anything other than the internal `CONFIRMED_FLAT` token. Ingest preserves that uncertainty. The R.10 `initialise_application` seam uses the same rule with fake dependencies. R.8 and R.9 regressions passed.

This does not mean PostgreSQL executed the SQL, a broker was reconciled, a durable position exists, or the production launcher was tested.

| Gate | Result |
| --- | --- |
| A Production recovery trace | SOURCE-REVIEWED |
| B Historical FILLED policy | Defined before the edit |
| C Recovery query | CODE MODIFIED |
| D Ingestion | SYNTHETICALLY TESTED |
| E Startup integration | OFFLINE INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES |
| F SQL tests | Captured SQL text. PostgreSQL NOT_EVALUATED |
| G R.8/R.9 regressions | Passed |
| H Isolation | Socket and DNS barriers held |
| I Regression tests | 51 passed, 5 skipped NOT_EVALUATED, 0 failed |
| J Durable position design | Documented. Not implemented |
| K Integrity | No prohibited operation observed |

Source files modified: `forex_bot/database.py`, `forex_bot/orders.py`, `forex_bot/app.py`.

R.11 tests collected: 56. Passed: 51. Failed: 0. Skipped: 5. Recorded I01–I55: 50 PASS and 5 NOT_EVALUATED. One extra passing test covers a truncated recovery page.

Historical FILLED query: repaired in source, not engine-executed. Recovery ingestion: synthetic pass. Offline startup: real seam, fake dependencies. PostgreSQL engine: NOT_EVALUATED. Broker reconciliation: NOT_EVALUATED. Production startup: NOT_EVALUATED. Network requests: none succeeded. Broker requests: none.

Recommended next action: stop. Do not treat the source repair as a database or broker verification.

## 2. Safety and scope

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

`main.py` was not run. Lifespan was not entered. `run_bot` was not started. OANDA was not contacted. PostgreSQL was not started. `.env` was not read. No migration was created or applied. No package was installed. No Docker, WSL, or virtual machine was used. No git commit or reset was performed.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. Stage-start hashes matched. `r11` was absent before writing.

Post-stage hashes: `app.py` `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1`, `database.py` `16363fdc26929ed0a6fe71837806ba96c51043df76fa3d524a2d26f80736c486`, `orders.py` `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4`. `bot_loop.py` and the protected files are unchanged.

## 4. Production recovery trace

SOURCE-REVIEWED. The old fetch selected only active statuses or `exposure_safety = UNCONFIRMED`. JSONB NULL and a missing key were therefore omitted for historical FILLED rows. The reservation query had the same omission. `load_open_orders_from_db_into_memory` fail-closes when the fetch raises. `confirm_exposure_flat` does not write a durable marker.

## 5. Historical FILLED policy

FILLED, missing metadata, NULL metadata, and an empty position slot are not flat proof. Uncertain historical FILLED rows stay in the recovery set. `CONFIRMED_FLAT` is an internal token, not broker evidence, and it cannot hide an unresolved order. Unknown and malformed markers fail closed. There is no timer, replacement order, strategy activation, or migration.

## 6. Recovery SQL repair

CODE MODIFIED. The shared predicate is `status IN ('PENDING', 'PARTIAL', 'UNRESOLVED') OR (status = 'FILLED' AND COALESCE(metadata->>'exposure_safety', '') <> 'CONFIRMED_FLAT')`. Fetch and durable read both use it. A page larger than 2000 rows fails closed. The reservation check blocks unmarked FILLED rows. The symbol parameter stays bound. No DDL was added.

## 7. Recovery ingestion

SYNTHETICALLY TESTED. Missing, NULL, and empty metadata are selected and held. Malformed metadata and unknown markers fail closed. Multiple FILLED rows for one symbol are both retained. Conflicting identities for one client id fail closed. An empty read is not a failed read.

## 8. Offline startup integration

`initialise_application` runs injected rows through `select_rows_for_recovery` and then the real ingest. A legacy FILLED row blocks the symbol. A CANCELLED companion is not ingested. Offline ready stays distinct from trading ready. Shutdown closes fake resources and leaves the exposure hold in place.

## 9. SQL synthetic tests

A fake cursor captured the SQL text and returned controlled rows. That does not prove PostgreSQL would select the same rows. The captured statement contains the active statuses and the FILLED predicate, has no `%s`, and performs no DDL. I51 and I52 remain NOT_EVALUATED.

## 10. R.8/R.9 safety regressions

Separate processes: 120 passed, 7 skipped, 1 deselected, then the R.10 suite 69 passed and 5 skipped. Pending, partial, unresolved, and unconfirmed exposure holds remain. The reservation source check now includes unmarked FILLED rows.

## 11. Source modifications

`database.py`, `orders.py`, and `app.py` changed. `bot_loop.py` did not. Existing tests were updated only so their source pins match the repaired SQL and the new hashes. The cumulative diff against Git HEAD includes earlier uncommitted work: 1296 insertions and 154 deletions across those three files.

## 12. Test isolation

The runner installs the raising socket subclass and a dotenv stub before pytest. R.11, the older regressions, and R.10 run in separate processes. R.11 log: exit 0, 4 blocked attempts, 1 dotenv stub call. Regression: exit 0, 5 blocked, 1 dotenv stub. R.10: exit 0, 5 blocked, 1 dotenv stub. Those are blocked attempts, not connections.

## 13. Regression test results

R.11 file: 56 collected, 51 passed, 0 failed, 5 skipped. The skips are I51–I55 and are NOT_EVALUATED. Recorded I-tests: 50 PASS, 5 NOT_EVALUATED. Evidence is in `10_regression_test_results.json`.

## 14. Durable position design

Positions are one in-memory slot per symbol. `exec_orders` can show that a fill happened. It cannot show that the broker is still open or flat. A later position table and migration would be required, and both need fresh authorisation. Historical rows stay blocking until broker-flat evidence is stored. `CONFIRMED_FLAT` is not that evidence.

## 15. Remaining defects

The repaired SQL has not been executed by PostgreSQL. Broker reconciliation has not run. Production startup has not run. Durable positions are not implemented. A large historical book can therefore remain blocked until a later authorised reconciliation. A recovery page over 2000 rows fail-closes in source only.

## 16. Next three priorities

1. Leave the repaired query unexecuted against PostgreSQL until a stage can do that without a forbidden socket.
2. Do not treat `CONFIRMED_FLAT` or an empty position slot as broker-flat proof.
3. Seek separate approval before any position-table migration or broker position read.

## 17. Recommended next stage

No next stage starts from this result. A later stage needs its own approval before engine execution, migration, broker contact, or the launcher.

## 18. Final integrity

HEAD and branch are unchanged. Protected hashes match. No launcher, trading loop, broker request, PostgreSQL connection, messaging connection, DNS success, credential read, production-state read, order, strategy activation, live-order permission change, package install, container, deployment, or git rollback occurred.

## 19. Final classification

**R11_OFFLINE_HISTORICAL_RECOVERY_REPAIRED**

- SOURCE-REVIEWED: the old query omitted unmarked FILLED rows.
- CODE MODIFIED: `database.py`, `orders.py`, `app.py`.
- SYNTHETICALLY TESTED: selection predicate, ingest, and captured SQL text.
- OFFLINE INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES: `initialise_application`.
- POSTGRESQL-ENGINE TESTED: no.
- BROKER-VERIFIED: no.
- NOT_EVALUATED: I51, I52, I53, I54, I55.

## 20. Hard stop

R.11 is finished. R.12 is not started. `main.py` was not run. Production lifespan was not entered. `run_bot` was not started. Strategies were not activated. Live orders were not enabled. OANDA was not contacted. No practice or real order was placed. PostgreSQL was not started. Nothing was deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
