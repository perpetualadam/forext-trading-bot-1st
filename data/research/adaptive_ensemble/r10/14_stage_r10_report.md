# STAGE R.10 — OFFLINE APPLICATION STARTUP AND INTEGRATION HARNESS REPORT

## 1. Executive summary

Overall classification: **R10_OFFLINE_STARTUP_INTEGRATED**.

This classification means the real `initialise_application` orchestration ran with fake external dependencies, completed offline initialization, fail-closed on the required faults, and shut down. It does not mean the production launcher, PostgreSQL, broker reconciliation, or the trading loop was verified.

| Gate | Result |
| --- | --- |
| A Trace actual startup | SOURCE-REVIEWED |
| B Offline initialization seam | CODE MODIFIED |
| C Fake service contracts | Implemented for the traced dependencies |
| D Startup phases | Executed through the real seam |
| E Order and position recovery | SYNTHETICALLY TESTED. Historical FILLED SQL gap NOT RESOLVED |
| F Failure modes | Fail closed |
| G Shutdown | Verified for the fake resources |
| H Test isolation | Socket and DNS barriers held |
| I Integration tests | 69 passed, 5 skipped NOT_EVALUATED, 0 failed |
| J Implementation discipline | Real initialization function completed an offline lifecycle |
| K Final integrity | No prohibited operation observed |

Source file modified: `forex_bot/app.py`. Existing hash pins updated in `tests/test_r8_reservation_safety.py` and `tests/test_r9_position_safety.py`.

R.10 tests collected: 74. Executed and passed: 69. Failed: 0. Skipped: 5. Recorded I01–I68: 63 PASS and 5 NOT_EVALUATED. The six extra passing tests cover E08, E10, E11, E12, F16, and F19.

Real initialization orchestration executed: yes, with fake dependencies. Normal launcher executed: no. `run_bot` executed: no. Fake services used: yes. PostgreSQL used: no. Broker contacted: no. Network succeeded: no.

Recommended next action: stop. Do not start the bot and do not treat this result as trading readiness.

## 2. Safety and scope

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

The work stayed in this project. `main.py` was not run. Lifespan was not entered. No OANDA client was constructed by the offline path. No PostgreSQL server was started. `.env` was not read; the runner replaced `load_dotenv` before import. No package was installed. No Docker, WSL, or virtual machine was used. No git commit, reset, stash, checkout, or clean was performed.

## 3. Baseline integrity

Git HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. The stage-start hashes matched, including `forex_bot/app.py` at `3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1`. The output directory was absent before this stage, so there was no output collision.

Post-stage `app.py` is `7a925e3f5a247b9f92ab42db17242c5a895de099b6897145fba6bfb7d737ef9e`. `bot_loop.py`, `database.py`, `orders.py`, and the protected files still match the stage-start hashes.

## 4. Actual startup call graph

SOURCE-REVIEWED. `main.py` lines 19–26 call `uvicorn.run("forex_bot.app:app")`. Lifespan at `forex_bot/app.py` line 653 calls `initialise_application`. The production ports at line 535 then validate symbols, run `initialise_fail_closed`, open the database, load orders and reconcile state, build the OANDA API, fetch the account summary, run one reconciliation, warn on pre-trade blocks, and only then schedule tasks including `run_bot`.

That production sequence was not executed. The offline tests call `initialise_application` with fake ports and stop before any of those external calls.

## 5. Dependency injection design

`StartupPorts` is the explicit boundary. Production mode and offline mode share `initialise_application`. Offline mode requires the scheduler to return `recorded_not_started`. `trading_ready` stays false. `offline_ready` means offline initialization finished, not that trading may start.

`ReconciliationUnavailable` is recorded without clearing exposure holds. Other dependency exceptions fail closed and close resources already opened by the offline path. A second initialization and an initialization after shutdown are refused unless a test explicitly allows them.

## 6. Fake service implementations

`tests/r10_fakes.py` supplies persistence, recovery, broker, market data, messaging, health, and a scheduler. The broker rejects submit and close. Messaging records a local attempt and raises. The scheduler does not import `run_bot`. None of these fakes opens a socket or a database connection.

## 7. Offline initialization execution

REAL INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES.

I01 calls `initialise_application`, observes `offline_initialization_ready`, confirms `trading_ready` is false, and then calls `shutdown_application`. I02 confirms the phase order. I04 confirms effective live-order auth remains `BLOCKED`. I05 confirms the strategy objects stay inactive. I06 confirms the OANDA modules were not imported by that startup. I09 confirms the schedule was recorded and `run_bot` was not imported. I10 confirms offline ready is not trading ready.

## 8. Order and position recovery

SYNTHETICALLY TESTED through `ingest_recovery_snapshot` and `exposure_entry_block_reason`.

PENDING, PARTIAL, and UNRESOLVED block a new client id. FILLED with UNCONFIRMED, and a supplied FILLED row without a marker, leave `exposure_unconfirmed`. An empty position slot and the token `CONFIRMED_FLAT` do not clear an unresolved order. Corrupt, incomplete, and failed recovery do not reach ready. Repeated ingest of the same client id does not duplicate the order.

The historical FILLED gap is NOT RESOLVED. `fetch_exec_orders_open_for_recovery` still does not select an unmarked FILLED row. That SQL was inspected and was not changed. PostgreSQL was NOT_EVALUATED. Broker position recovery was NOT_EVALUATED.

## 9. Failure-mode results

Invalid configuration, a missing dependency, persistence failure, recovery failure, corrupt recovery, broker failure, market-data failure, messaging failure, health failure, scheduler refusal, an unexpected exception, an interrupted startup, duplicate initialization, initialization after shutdown, a bad scheduler result, and an unexpected application state all fail closed. Cleanup after a partial startup closes the resources that had opened. A cleanup error string remains visible on the report. No failure reports trading readiness.

## 10. Shutdown and cleanup

Clean shutdown closes scheduler, health, messaging, market data, broker, and persistence in that order. Repeated shutdown is safe. No trading task is created. No real database, broker, or messaging connection exists. A stopped lifecycle does not restart itself.

## 11. Source modifications

CODE MODIFIED: `forex_bot/app.py` only, among application modules. The change extracts `initialise_application`, moves broker and `run_bot` imports behind the production functions, and keeps the production scheduler able to start `run_bot` if lifespan is entered later.

`bot_loop.py`, `database.py`, and `orders.py` were not edited. Protected hashes match. R.8 and R.9 tests now expect the new `app.py` hash. The R.9 network assertion matches the blocked-socket text used by this runner; the socket still raises.

The cumulative diff against Git HEAD for the four long-running dirty files is 1444 insertions and 208 deletions. That number includes work from before this stage.

## 12. Test isolation

The runner installs a raising socket subclass and a DNS stub before pytest imports the tests. `AF_INET`, `AF_INET6`, and `AF_UNIX` are not permitted. Startup and regression run in separate processes so the older tests can still prove they did not import `forex_bot.app`.

Startup process: exit 0, 5 blocked attempts, 1 dotenv stub call. Regression process: exit 0, 5 blocked attempts, 1 dotenv stub call. Those counts are blocked attempts, not successful connections. `main` was not imported. Lifespan was not entered.

## 13. Integration test results

R.10 file: 74 collected, 69 passed, 0 failed, 5 skipped. The skips are I64–I68 and are NOT_EVALUATED, not passes.

Recorded I-tests: 63 PASS, 5 NOT_EVALUATED. The startup seam executed in 57 of those 68 records. I54, I55, I59, I60, I61, and I63 exercise gates or barriers without the seam. I64–I68 do not execute it either.

Regression in a fresh process: 120 passed, 7 skipped, 1 deselected, 0 failed. The skips and the deselected restart test are the earlier NOT_EVALUATED cases.

Per-test evidence is in `10_integration_test_results.json`.

## 14. Remaining defects

The durable recovery query still omits a historical FILLED row that has no R.9 exposure marker. This stage did not repair that query. A snapshot supplied to ingest blocks the symbol, which is a different path from the production fetch.

Positions are still memory-only. Flat confirmation still does not erase a durable UNCONFIRMED marker. Production startup, PostgreSQL, broker reconciliation, and `run_bot` remain NOT_EVALUATED.

## 15. Next three priorities

1. Leave the unmarked historical FILLED fetch gap visible. Do not describe the offline ready flag as proof those rows were recovered.
2. Keep PostgreSQL recovery NOT_EVALUATED until a later stage can test it without opening a forbidden socket.
3. Keep the production lifespan, broker reconciliation, and trading loop unrun until a separate stage authorises that work.

## 16. Recommended next stage

No next stage should start from this result. A later stage would need its own approval before touching the recovery SQL, a database engine, the broker, or the launcher.

## 17. Final integrity

HEAD and branch are unchanged. Protected hashes match. No normal launch, `run_bot`, broker request, PostgreSQL connection, Telegram or Discord connection, DNS success, credential read, production-state read, trading order, strategy activation, live-order permission change, package install, container, deployment, or git rollback was performed.

The offline safety file written by `initialise_fail_closed` is `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. Test logs and the result JSON are under the same directory.

## 18. Final classification

**R10_OFFLINE_STARTUP_INTEGRATED**

Labels:

- SOURCE-REVIEWED: the normal startup call graph.
- CODE MODIFIED: `forex_bot/app.py`.
- REAL INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES: `initialise_application` and `shutdown_application`.
- SYNTHETICALLY TESTED: recovery, failure, and shutdown.
- POSTGRESQL-ENGINE TESTED: no.
- BROKER-VERIFIED: no.
- NOT_EVALUATED: I64, I65, I66, I67, I68, and the historical fetch gap as a repair.

## 19. Hard stop

R.10 is finished. R.11 is not started. `main.py` was not run. The normal bot was not run. `run_bot` was not run. Strategies were not activated. Live orders were not enabled. OANDA was not contacted. No practice or real order was placed. PostgreSQL was not started. Production was not accessed. Nothing was deployed. No database was migrated. No market data was downloaded. No profitability backtest was run.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
