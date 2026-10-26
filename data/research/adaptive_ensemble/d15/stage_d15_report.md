# STAGE D.15 — CONSOLIDATED LIFECYCLE SAFETY AND REGRESSION COMPATIBILITY AUDIT REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D15_AUDIT_COMPLETE_ALL_TESTED_INVARIANTS_PASS`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Confirmed defects: none new. D12-START-01 and D12-STOP-01 remain fixed in the isolated tests.
- Coverage gaps: none. The 109 hash-blocked tests have a current-source replacement for the safety property they were written to protect.
- Tests passed: D.15 16 in 28.16s; D.2/D.3/D.4/D.7/D.14 143 in 34.62s; safety-repair 23 in 4.95s
- Tests failed: 0 after the D.15 safety-test import correction. The first D.15 run had 15 passes and 1 test-import error. That error was not a production failure.
- Historical setup conflicts: 109 errors in 1.13s. No test body ran.
- Production source modified: no
- Recommended next stage: a separately approved stage. D.15 does not authorise one to start automatically.

This result does not mean deployment ready.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: 0
- Broker mutations: 0
- Production database access: no
- Telegram network requests: 0
- Operational-state access: no
- Shadow-mount access: no
- Docker commands: 0
- WSL commands: 0
- VM commands: 0
- Network requests: 0
- Dependency downloads: 0
- Package installations: 0
- Live-order authorisation: historically BLOCKED. Isolated effective state was BLOCKED. Current production authorisation was not inspected.
- Strategy activation: none in production. Isolated defaults stayed inactive unless an explicit boolean True was confirmed in the temporary file.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: already dirty. Existing changes were preserved. No reset, stash, clean, or commit.
- app.py hash: `3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1` (24456 bytes)
- telegram_control.py hash: `d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c` (46024 bytes)
- database.py hash: `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e` (27888 bytes)
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44` (22301 bytes)
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` (6823 bytes)
- Unexpected changes: none. The same five hashes were present after the tests. The D.15 directory was absent at the start.

## 4. SOURCE CONTRACT INVENTORY

- Application lifespan: safety preflight, then database, broker, tasks, and Telegram start. Shutdown reports stop status, drains tasks, and releases the database only after a failed startup when stop itself did not raise.
- Telegram startup results: `START_STARTED`, `START_ALREADY_RUNNING`, `START_REFUSED_PREVIOUS_WORKER`, `START_DISABLED`, `START_FAILED`.
- Telegram shutdown results: `STOP_COMPLETED`, `STOP_INCOMPLETE_WORKER_ALIVE`, `STOP_NOT_RUNNING`.
- Telegram worker ownership: the live thread stays stored after the bounded join. A refused restart does not clear the stop event or create a second worker.
- Database ownership: one published connection under `_pg_lock`. No borrower counter. Successful shutdown retains it. Failed startup releases it under the existing condition.
- Safety-state preflight: `live_safety_initialised()` requires both flags. Corrupt, future, invalid, and persist-failure states leave it false and authorisation BLOCKED.
- Strategy activation: six original strategies start inactive. Only boolean True activates a strategy. Operator confirmation is required for the durable setter.

## 5. ISOLATION

- Child-process design: one mode per process, 180-second parent timeout.
- Network guards: socket, asyncio, urllib, and subprocess entry points denied. `network_after` empty.
- Filesystem guards: production env, credential, operational, shadow, and database-volume paths denied. `shutil.copyfile` and `shutil.copytree` remain unwrapped and were not used.
- Configuration isolation: synthetic environment, empty OANDA tokens, invalid PostgreSQL target, temporary safety file.
- Fake service boundaries: PostgreSQL driver, Telegram transport, broker, reconciliation, trading loop, and order routing.
- Hard timeout: parent 180 seconds. Production stop join remains 2.0 seconds.
- Containment limitations: the child can be killed by the parent timeout. No child needed that kill. Final escaped-worker lists were empty.

## 6. CONSOLIDATED LIFESPAN

- Normal startup: yielded, no escaped exception, no refusal warning.
- Normal shutdown: cleanup errors empty, worker stopped, database retained, pending owned tasks 0.
- Telegram startup refusal: second lifespan logged `D12-START-01` and still yielded.
- Telegram startup failure: injected `Thread.start` failure returned through `START_FAILED`, logged that trading continues, and did not raise.
- Telegram incomplete shutdown: blocked poll recorded `D12-STOP-01`, left the worker alive, and did not raise.
- Application reporting: `STOP_COMPLETED` and disabled start produced no false warning. An unrecognised start status was logged and was non-fatal.
- Database retention: successful and incomplete shutdowns left the connection open.
- Failed-startup release: broker failure closed the connection.
- Task cleanup: owned tasks were drained, including after a task-await failure.
- Exception precedence: the broker `RuntimeError` stayed the escaped startup error.

## 7. REPEATED LIFESPANS

- First lifespan: started worker A and blocked its fake poll.
- Blocked worker: the worker remained in the fake poll.
- Incomplete stop: `D12-STOP-01`, worker A still tracked, stop event set.
- Second lifespan: yielded.
- Refusal warning: `D12-START-01` and the previous-worker phrase were logged.
- Duplicate workers: none. The stored identity stayed worker A.
- Database reuse: the connection id matched the first lifespan.
- Worker exit: after the fake poll was released, the join reported no escaped worker.
- Third lifespan: started worker B, a different identity, with no refusal warning.
- Final cleanup: worker B was not alive after shutdown, the connection stayed open, and the network list stayed empty.

## 8. TELEGRAM CONCURRENCY

- Concurrent starts: one `START_STARTED`, one `START_ALREADY_RUNNING`, one worker.
- Start/stop overlap: the start during the blocked stop returned `START_REFUSED_PREVIOUS_WORKER` and left the stop event set.
- Concurrent stops: both returned `STOP_INCOMPLETE_WORKER_ALIVE` for the same live worker, and both joins finished.
- Stop timeout: the incomplete stop returned in under four seconds. The production timeout was not changed.
- Worker ownership: the reference remained the same thread after repeated stops.
- Stop-event lifetime: it stayed set through the refused restart.
- Restart after exit: `START_STARTED` with a new identity.
- Polling exception: the worker exited, the reference was cleared, and no trade query was added.
- Database exception: `cmd_trades` contained the injected query error. A later call with stop set added no query.

## 9. DATABASE CONCURRENCY

- Concurrent initialization: one connect and one connection id.
- Connection publication: one published connection.
- Cursor publication: the failed attempts did not publish a cursor.
- Initialization failure: connect failure published nothing. SQL failure closed the unpublished connection and cursor.
- In-flight query: release did not finish while the query hold was set.
- Release serialization: release stayed blocked until the query was released.
- Post-stop query: delayed poll, gated commands, and the foreign-lock waiter added no query.
- Post-release reconnection: connect delta 0.
- Closed resource reuse: `use_after_close` was empty.

## 10. EXCEPTION PRECEDENCE

- Primary error: broker failure escaped as `RuntimeError`.
- Telegram stop error: recorded after the real stop returned `STOP_COMPLETED`. The connection stayed open.
- Task-await error: recorded. Pending owned tasks were 0.
- Database release error: recorded on the failed-startup path. The connection was not left open.
- Reporting error: the alert failure was recorded and escaped. The connection stayed open.
- Cleanup continuation: task cleanup still ran after the stop exception.
- Pending owned tasks: the cancellation schedule left `pending_owned` at 0. The worker remained alive because the poll was still blocked, and the connection stayed open.

## 11. SAFETY INVARIANTS

- Live-order authorisation: BLOCKED in the isolated valid, corrupt, future, invalid, and write-failure cases.
- Six strategy defaults: inactive after initialise.
- Fail-closed preflight: corrupt lifespan escaped as `StartupSafetyAbort` before a connection was published.
- Corrupt state: bytes kept, initialised false, authorisation BLOCKED.
- Future state: bytes kept, initialised false, authorisation BLOCKED.
- Invalid state: initialised false, authorisation BLOCKED.
- Write failure: injected `os.replace` failure left initialised false, authorisation BLOCKED, and no temporary file.
- Unknown fields: `future_metadata` survived initialise.
- Atomic writes: the production helper still writes a temporary sibling and replaces it. The failure path removed that sibling.
- Broker/order-routing isolation: no real broker or order call. `network_after` empty.

## 12. HISTORICAL REGRESSION COMPATIBILITY

- Total historical tests inventoried: D.2 through D.14 plus safety-repair. The hash-blocked set is 109. The executed compatible set is 143 plus 23.
- D.14-reported setup errors: 109
- Independently classified setup errors: 109
- Source-hash conflicts: 109
- Obsolete contract assertions: D.12 incomplete-stop silence and D.13 refusal silence, latent because the bodies did not run
- Obsolete defect assertions: D.6 pre-fix cleanup, D.8 abandoned connection, and D.10 duplicate worker, latent for the same reason
- Current-source compatible passes: 143, plus safety-repair 23
- Current-source compatible failures: 0
- Unclassified cases: 0
- Replacement coverage: 109 rows, all PASS at the current-source property
- Coverage gaps: 0

## 13. CONSOLIDATED INVARIANT DECISION

- Total invariants: 30
- PASS: 30
- FAIL: 0
- PARTIAL: 0
- NOT_VERIFIED: 0 for the isolated invariants. Production state is unverified and is not one of the 30 isolated results.
- Evidence levels: `ACTUAL_LIFESPAN_ISOLATED`, `ACTUAL_CONCURRENT_SOURCE_ISOLATED`, `ACTUAL_SOURCE_ISOLATED`, `HISTORICAL_TEST_COMPATIBILITY`, and `SOURCE_INSPECTION_ONLY`
- Remaining limitations: production was not inspected. `shutil.copyfile` and `shutil.copytree` are outside the existing filesystem wrapper. An undocumented Telegram start status is not produced by `start_telegram_control`; the application branch was tested with a substituted return. There is no database borrower counter. Deployment blockers remain open.

## 14. DEFECT REGISTER

No new defect was confirmed.

The first D.15 safety test failed because it imported `restore_strategy_runtime_defaults_for_tests` from `strategy_meta`. That helper is defined in `live_safety.py`. The test was corrected. Production source was not changed. The corrected safety schedule passed.

D12-START-01 and D12-STOP-01 were reconfirmed as fixed in the isolated lifespan. Production impact of every finding remains UNVERIFIED because production was not inspected.

## 15. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup and container identity are unverified. The running image lacks the working-tree fixes.
- Database: live schema compatibility is unverified.
- Dependencies: requirements are unpinned. There is no verified lock or offline wheelhouse.
- Packaging: base-image digest, runtime profile, trusted receiving boundary, and candidate image are unverified.
- Rollback: no verified rollback target.
- Production state: operational state and shadow state are unverified.
- Historical tests: 109 source pins still stop the old bodies. Some of those bodies encode an obsolete defect or an obsolete contract.
- Research compatibility: backtests may still assume strategies start active. That is separate from this lifecycle result.

## 16. VALIDATION

- Commands executed:
  - Historical pytest, exit 1, `109 errors in 1.13s`
  - D.2, D.3, D.4, D.7, and D.14 pytest, exit 0, `143 passed in 34.62s`
  - Safety-repair pytest, exit 0, `23 passed in 4.95s`
  - Ruff on the new D.15 files, exit 0, `All checks passed`
  - D.15 pytest, exit 0, `16 passed in 28.16s`
- Files read: the five protected production files, the D.11–D.14 runners and tests needed to classify pins, and the D.15 child reports through pytest.
- Files created: new D.15 tests, `tests/d15_lifecycle_runner.py`, `tests/d15_harness.py`, and the D.15 research artifacts.
- Files modified: none of the production files, Docker files, requirements, historical tests, or D.1–D.14 evidence.
- Tests executed: the sets above.
- Tests blocked: 109 historical setups. Their bodies were not executed.
- Prohibited operations: none observed.
- Missing evidence: current production container, database, operational state, shadow state, and broker state were intentionally not read.

## 17. FINAL CLASSIFICATION

`D15_AUDIT_COMPLETE_ALL_TESTED_INVARIANTS_PASS`

The reachable D.15 schedules passed. All 30 isolated invariants passed. The 109 historical conflicts are classified. Their safety properties have current-source coverage. No new lifecycle defect was confirmed. No prohibited operation occurred. Production source stayed unchanged.

This classification does not authorise deployment.

## 18. NEXT ACTION

D.15 completed. No new lifecycle defect was found. Historical compatibility was classified. No coverage gap remains for the safety properties behind the 109 blocked tests. Production source remained unchanged. Actual `app.lifespan` was tested in isolation. Actual Telegram start and stop were tested in isolation. Actual database initialization, query, and release functions were tested in isolation. Production startup was not verified. The bot may not be restarted. An image may not be built. Deployment is not authorised. Live trading is not authorised. A separately approved next stage is required before any further action.

PRODUCTION DEPLOYMENT: NO-GO.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
