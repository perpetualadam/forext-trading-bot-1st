# STAGE D.7 — STARTUP RESOURCE CLEANUP AND SHUTDOWN RESILIENCE REMEDIATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: D7_REMEDIATION_COMPLETE_OFFLINE_TESTED
- D6-DB-01: PASS
- D6-DB-02: PASS
- D6-TASK-01: PASS
- D6-SHUT-01: PASS
- D6-SHUT-02: PASS
- D6-OWN-01: RESOLVED_NOT_A_DEFECT. The successful-startup connection stays process-global and is not closed on normal shutdown.
- Tests passed: 133 in the final combined command (18 D.7, 30 D.2, 35 D.3, 50 D.4), plus the D.5 runner replay and the isolated repair module inside those 18.
- Tests failed: 0 in the authorised regression set. The unmodified D.5 and D.6 pytest modules error on their frozen pre-D.7 `app.py` hash (27 errors).
- Main blockers: production startup, image identity, live schema, dependencies, and rollback remain unverified.
- Recommended next stage: none. D.7 does not authorise another stage.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Network requests: none. Guard self-checks denied connect and DNS before lifespan.
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: unchanged, historically BLOCKED
- Strategy activation: none. All six remain inactive by default.

## 3. BASELINE INTEGRITY

- Git HEAD: d080d897945bc44fa37c02caab504ed707146bec
- Branch: main
- Working-tree status: dirty before and after. `database.py` was clean before the edit.
- Original app.py hash: f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4
- Final app.py hash: 08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44
- Original database.py hash: 98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72
- Final database.py hash: 74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9
- live_safety.py hash: 11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44
- strategy_meta.py hash: 492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d
- Unexpected changes: none. The pre-existing dirty files were left in place.

## 4. DATABASE OWNERSHIP

- Connection owner: the `database` module, after a successful commit.
- Cursor owner: the same module, through `_pg_cursor`.
- Borrowers: database helpers under `_pg_lock`, and `telegram_control` through `fetch_all_trades_ordered`.
- Shared references: one process-global connection and one process-global cursor. Callers receive the connection object itself.
- Intended lifetime: process lifetime after publication.
- Release mechanism: an unpublished failed attempt is discarded inside `get_connection`. A published connection is released only by `release_connection_after_failed_startup` after a failed startup.
- Retry behaviour: a failed attempt is not stored, so the next call connects again.
- Concurrency concerns: `get_connection` still does not hold `_pg_lock` during the initial connect. That limitation was documented and not redesigned.
- D6-OWN-01 decision: normal shutdown does not close the published connection.

## 5. DATABASE REMEDIATION

- Connection acquisition: unchanged connect arguments. The object stays local until commit.
- Cursor creation failure: rollback and close the new connection, return None.
- Initialization failure: close the cursor, rollback, close the connection, return None.
- Commit failure: same cleanup, return None.
- Rollback: attempted only on the still-open connection created by that attempt.
- Cursor cleanup: one close when the cursor exists and is not already closed.
- Connection cleanup: one close when the connection is still open.
- Global-state clearing: failed objects are never assigned. Release clears globals only when they still point at the objects being closed.
- Error propagation: the original initialization failure remains the `None` return and the existing warning. Cleanup failures are recorded by type name.

## 6. LIFESPAN REMEDIATION

- Startup cleanup boundary: the resource `try` begins after the D.4 safety abort.
- Fatal pre-yield cleanup: `finally` cancels and awaits owned tasks, then releases the database connection when Telegram stop did not fail.
- Broker construction failure: connection closed, no tasks left pending.
- Background-task creation failure: earlier tasks are cancelled and awaited.
- Telegram control startup failure: all four tasks are cleaned up and the connection is released.
- Normal shutdown: tasks are cancelled and awaited. The published connection stays open.
- Cleanup ordering: stop Telegram, cancel tasks, await tasks, then database release.
- Database release: only on startup failure, after the awaits.
- Exception preservation: the startup exception is re-raised and is not replaced by a cleanup error.

## 7. SHUTDOWN RESILIENCE

- Telegram stop failure: recorded, then all four tasks are still cancelled and awaited.
- Health task failure: recorded, and the other three tasks are still awaited.
- Other task failures: a reconciliation-task failure has the same result.
- Cancellation: every owned task is cancelled before the awaits.
- Awaiting: each await has its own handler.
- Remaining tasks: none pending after application cleanup in the injected cases.
- Secondary cleanup errors: stored by type name in `startup_cleanup_errors()`.
- Primary failure propagation: the injected shutdown or task error is the exception that leaves `lifespan` when startup itself succeeded.

## 8. TEST RESULTS

- Tests added: `tests/test_d7_resource_cleanup.py`, `tests/d7_resource_cleanup_runner.py`
- Tests modified: none
- Tests executed: D.7, D.2, D.3, D.4, the D.5 runner, the repair module, and the D.5/D.6 pytest modules
- Tests passed: 133 in 10.86s for D.7 plus D.2, D.3, and D.4
- Tests failed: 0 in that command
- Tests skipped: 0
- Actual-lifespan isolated tests: the D.7 lifespan mode and the D.5 runner replay
- Isolated database tests: the D.7 database mode
- Static assertions: D.4 source-order checks and the D.7 guard-order check
- Tests not run: the full suite. The D.5 and D.6 modules stop at their hash pin.
- Isolation violations: none

## 9. D.6 DEFECT ACCEPTANCE

- D6-DB-01: PASS
- D6-DB-02: PASS
- D6-TASK-01: PASS
- D6-SHUT-01: PASS
- D6-SHUT-02: PASS
- D6-OWN-01: resolved. The open connection after a successful shutdown is intentional.
- Remaining defects: none of the five confirmed cleanup defects. The database lock is still not held across first connect.

## 10. REGRESSION COMPATIBILITY

- D.2: 30 passed
- D.3: 35 passed
- D.4: 50 passed
- D.5: runner behaviour passed. The pytest module conflicts with the frozen hash.
- D.6: historical defect tests were not modified and did not run past the hash pin. Their leak assertions would conflict with the fix. Compatibility of that module is not claimed.
- Safety-repair module: exit 0 under the D.7 guards
- Remaining gaps: full suite not run; production startup not verified

## 11. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup was not verified
- Database: live schema was not verified
- Dependencies: requirements are unpinned and there is no lock or wheelhouse
- Packaging: no verified candidate image or base-image digest
- Rollback: no verified rollback target
- Production state: operational and shadow state were not read
- Research compatibility: backtests may still assume strategies start active

## 12. VALIDATION

- Commands executed: the pytest commands recorded in `test_execution_results.json`, plus ruff and hash checks
- Files read: the lifespan, database, safety, Telegram control, and D.5/D.6 test sources
- Files created: the D.7 runner, the D.7 tests, and this research directory
- Files modified: `forex_bot/app.py` and `forex_bot/database.py`
- Tests executed: listed above
- Prohibited operations: none
- Missing evidence: production container identity, live schema, and a full-suite run

## 13. FINAL CLASSIFICATION

D7_REMEDIATION_COMPLETE_OFFLINE_TESTED

## 14. NEXT ACTION

- D.7 is complete for the five confirmed cleanup defects.
- All five D.6 defects are fixed.
- Database ownership is resolved: the published connection remains process-global after a successful startup.
- Actual lifespan was tested offline under the D.7 harness and the unmodified D.5 runner.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any deployment work. D.8 was not started.

PRODUCTION DEPLOYMENT: NO-GO.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
