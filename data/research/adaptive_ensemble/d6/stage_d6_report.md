# STAGE D.6 — PARTIAL-STARTUP FAILURE RECOVERY AND RESOURCE CLEANUP VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D6_AUDIT_COMPLETE_CLEANUP_DEFECTS_FOUND`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Actual lifespan fault injection executed: yes
- Tests passed: 142 in the parent pytest command, plus 23 repair tests in the guarded child
- Tests failed: 0
- Confirmed cleanup defects: D6-DB-01, D6-DB-02, D6-TASK-01, D6-SHUT-01, D6-SHUT-02
- Main blockers: those cleanup defects are unfixed; production startup is unverified; the running image lacks D.2–D.4
- Recommended next stage: a separately approved remediation stage for `forex_bot/app.py` and `forex_bot/database.py`. D.7 was not started.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: no
- Broker mutations: no
- Production database access: no
- Operational-state access: no
- Shadow-mount access: no
- Docker commands: no
- WSL commands: no
- VM commands: no
- Network requests: no
- Dependency downloads: no
- Package installations: no
- Live-order authorisation: BLOCKED in every isolated case. Production authorisation was not read or changed.
- Strategy activation: none. Isolated strategies stayed inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty. The nine previously tracked modifications were left in place.
- app.py hash: `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- D.5 test hashes: unchanged, `8cf8c712979ad32eac648b4a8f18d65546bf24a72d2a4e6f4f3ff6041bd88dd4` and `0729bea1df8a59d5dde3c66c396a476a0abb80c9c36213f15f08fcb77f2a3b60`
- Unexpected changes: none

## 4. RESOURCE LIFECYCLE

- Database connection: created inside the real `get_connection` against a fake driver. Success keeps it for the process. Failure after connect drops it without close.
- Database cursor: created inside `get_connection`. Never closed by startup.
- Broker client: `build_api` is called after the database call and is not inside `try`.
- Account-summary request: failure is logged and startup continues.
- Reconciliation: failure is logged and startup continues.
- Background tasks: four tasks are created before `try/yield`.
- Lifespan yield: the `finally` block starts only after yield.
- Normal shutdown: the application cancelled all four inert tasks.
- Pre-yield failure: `finally` does not run.
- Post-yield failure: the first error in `finally` skips the remaining cancels.

## 5. ISOLATION REVIEW

- D.5 harness: reviewed and not modified. Its database fake cannot exercise `get_connection`'s partial-failure path, and it does not guard `os.replace`.
- Network denial: connect, connect_ex, create_connection, urlopen, asyncio streams, requests, and getaddrinfo raise in the D.6 child.
- Socketpair exception: original connect is used only for the port that same call just bound. A later connect to `127.0.0.1:5432` and to that port was denied.
- Filesystem confinement: the D.6 child also denies `os.open`, `os.replace`, rename, remove, unlink, and the shutil copies and moves for `.env`, `data/ops`, `v2_shadow`, and credential names.
- Synthetic configuration: child environment is constructed, not inherited.
- Subprocess isolation: temporary directory, 180-second timeout, guards only in the child.
- Remaining isolation risks: the D.5 runner still lacks the `os.replace` and DNS wrappers. D.6 did not change it. Production paths were not used.

## 6. FAULT-INJECTION RESULTS

- Database acquisition: nonfatal. No connection object. Startup yields.
- Database cursor: nonfatal. Connection abandoned without close.
- Database initialization: nonfatal. Connection and cursor abandoned without close or rollback.
- Database commit: nonfatal. Same abandoned connection. Rollback count is 0.
- Broker construction: fatal. No tasks. Connection left held.
- Account summary: nonfatal. Normal task shutdown.
- Reconciliation: nonfatal. Normal task shutdown.
- First task creation: the failure injected at `alert` creates no task and leaves the connection held.
- Later task creation: 1 or 3 tasks remain pending.
- Pre-yield failure: all 4 tasks remain pending.
- Shutdown: `stop_telegram_control` raising leaves all 4 tasks pending.
- Task cancellation: `Task.cancel()` has no raising path in this source. Not applicable.
- Task awaiting: a non-cancellation error from the health task leaves the other 3 tasks pending.
- Repeated startup: after harness cleanup of a one-task leak, a second lifespan yields with authorisation BLOCKED.

## 7. RESOURCE CLEANUP

- Resources created: one fake connection whenever `connect` returned, and up to four inert tasks.
- Application-closed resources: tasks on the normal shutdown path. No connection was closed by the application.
- Harness-closed resources: abandoned or retained connections, and every task the application left pending.
- Resources left open by the application: the connection on cursor, execute, commit, broker, and pre-task failures; the process-global connection after successful shutdown.
- Tasks created: 0, 1, 3, or 4 depending on the injection point.
- Tasks cancelled by the application: 4 on normal and nonfatal paths; 0 on pre-yield and shutdown defects.
- Tasks cancelled by the harness: the ones still pending after the snapshot.
- Tasks left active after harness cleanup: none. That harness result does not erase the application defect.
- Confirmed defects: five, listed below. Success-path connection retention is ownership exception D6-OWN-01.

## 8. SAFETY INVARIANTS

- Authorisation remains BLOCKED: yes
- Six strategies remain inactive: yes
- No real order routing: yes
- No broker interaction: yes
- No production database access: yes
- No operational-state access: yes
- No shadow-state access: yes
- No network access: yes
- Synthetic safety-state preservation: file authorisation stayed BLOCKED

## 9. REGRESSION COMPATIBILITY

- D.2: 30 passed
- D.3: 35 passed
- D.4: 50 passed
- D.5: 15 passed, files unchanged
- Safety-repair module: 23 passed inside the guarded child
- Remaining gaps: the full suite was not run

## 10. CONFIRMED DEFECTS

- Defect ID: D6-DB-01
- Severity: partial initialization leak
- Source file: `forex_bot/database.py`
- Function: `get_connection`
- Failure window: cursor, execute, or commit after connect
- Trigger: the fake driver raises
- Observed result: startup continues and the connection is dropped with `close_calls` 0
- Resource or task affected: database connection and cursor
- Application cleanup: none
- Harness cleanup: closed the connection after the snapshot
- Proposed remediation: roll back, close the cursor, close the connection, then clear the globals
- Required future source scope: `forex_bot/database.py`

- Defect ID: D6-DB-02
- Severity: fatal startup leaves the connection open
- Source file: `forex_bot/app.py`
- Function: `lifespan`
- Failure window: broker construction, or any raise after a successful `get_connection` and before yield
- Trigger: `build_api` or `alert` raises
- Observed result: exception escapes and `_pg_conn` stays held
- Resource or task affected: process-global connection
- Application cleanup: `finally` does not run
- Harness cleanup: closed the connection after the snapshot
- Proposed remediation: close the connection when startup aborts after it was opened
- Required future source scope: `forex_bot/app.py` and `forex_bot/database.py`

- Defect ID: D6-TASK-01
- Severity: background tasks left running
- Source file: `forex_bot/app.py`
- Function: `lifespan`
- Failure window: after the first task and before yield
- Trigger: a later `create_task` or `start_telegram_control` raises
- Observed result: 1, 3, or 4 tasks stayed pending
- Resource or task affected: inert stand-ins for the real loops
- Application cleanup: `finally` is attached only to `yield`
- Harness cleanup: cancelled the pending tasks
- Proposed remediation: start `try` before the first `create_task`
- Required future source scope: `forex_bot/app.py`

- Defect ID: D6-SHUT-01
- Severity: shutdown stops at the first error
- Source file: `forex_bot/app.py`
- Function: `lifespan`
- Failure window: `stop_telegram_control`
- Trigger: stop raises
- Observed result: all 4 tasks stayed pending
- Resource or task affected: four background tasks
- Application cleanup: aborted at the first `finally` line
- Harness cleanup: cancelled 4
- Proposed remediation: log the stop error and still cancel every task
- Required future source scope: `forex_bot/app.py`

- Defect ID: D6-SHUT-02
- Severity: one failed await skips later cancels
- Source file: `forex_bot/app.py`
- Function: `lifespan`
- Failure window: `await health_task`
- Trigger: the awaited task raises a non-cancellation error
- Observed result: the other 3 tasks stayed pending
- Resource or task affected: telegram, reconciliation, and trading-loop tasks
- Application cleanup: `except` handles only `CancelledError`
- Harness cleanup: cancelled the remaining 3
- Proposed remediation: isolate each await and continue through the rest
- Required future source scope: `forex_bot/app.py`

Ownership exception D6-OWN-01: a successful startup intentionally leaves the database connection open for the process. `lifespan` does not close it on the success path.

## 11. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup unverified. The cleanup defects above are unfixed.
- Database: live schema unverified. Partial connect is not closed.
- Dependencies: unpinned requirements, no lock, no wheelhouse.
- Packaging: running image lacks D.2–D.4. No candidate image. Base-image digest unverified.
- Rollback: no verified rollback target.
- Production state: not read. Historical authorisation BLOCKED. Six strategies historically inactive.
- Research compatibility: inactive strategy defaults still change backtests that skip inactive strategies.

## 12. VALIDATION

- Commands executed: git identity, hashes, ruff, and the pytest command below.
- Files read: lifespan, `get_connection`, config, the D.5 runner, the repair tests, and conftest. No `.env`, production safety file, operational mount, shadow mount, or database.
- Files created: two D.6 test files and `data/research/adaptive_ensemble/d6/`.
- Files modified: no production source and no D.5 file.
- Tests executed: 142 parent tests passed in 7.65s. Nested repair pytest exit code 0 for 23 tests.
- Prohibited operations: none.
- Missing evidence: production environment, production safety state, refreshed image identity, and the full suite.

Command:

`python -m pytest tests/test_d6_partial_startup_cleanup.py tests/test_live_safety_preservation.py tests/test_strategy_activation_defaults.py tests/test_startup_safety_preflight.py tests/test_d5_lifespan_isolation.py -q --tb=line`

## 13. FINAL CLASSIFICATION

`D6_AUDIT_COMPLETE_CLEANUP_DEFECTS_FOUND`

## 14. NEXT ACTION

- D.6 is complete as an audit and isolated fault-injection stage.
- Cleanup defects were found. They were not fixed.
- Production remediation is required before these paths can be treated as safe. It was not done here.
- Actual lifespan fault injection ran.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any source change, rebuild, restart, or deploy.

PRODUCTION DEPLOYMENT: NO-GO.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
