# STAGE D.9 — DATABASE INITIALIZATION CONCURRENCY REMEDIATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: D9_REMEDIATION_COMPLETE_OFFLINE_TESTED
- D8-CONC-01: FIXED
- Gates A–E: PASS
- Pre-fix reproduction: D8_CONC_01_REPRODUCED_PRE_FIX
- Post-fix concurrency: one connection, one cursor, both callers received it, the second caller stayed blocked while the first was inside connect
- Tests passed: D.9 pytest 6 passed in 3.46s. D.2, D.3, D.4, and D.7: 133 passed in 9.83s
- Tests failed: none in the post-fix acceptance set. D.5 and D.6 stopped on their historical app.py hash pins. D.8 stopped because it still pins the pre-fix database.py hash and is written to detect the old leak
- Borrower quiescence: BORROWER_QUIESCENCE_UNVERIFIED
- Main blockers: production startup and the running image are unverified; live schema is unverified; Telegram stop can return while its thread is alive
- Recommended next stage: a separately approved stage if borrower quiescence must be closed. That work needs `telegram_control.py` or `app.py`, which this stage was not allowed to change. Do not start it from this report

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
- Network requests: none during the schedules; the self-check denials were cleared before the runs
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: BLOCKED
- Strategy activation: none

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: main
- Working-tree status: already dirty; preserved
- Original database.py hash: `74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9`
- Final database.py hash: `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`
- app.py hash: `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Unexpected changes: none. The other three production hashes are unchanged

## 4. DATABASE LOCK DESIGN

- Lock type: existing `threading.RLock`
- Lock acquisition point: the first statement of `get_connection`, before the reuse check
- Lock release point: when `get_connection` returns, including the failure return. The `with` statement releases it
- Initialization critical section: connect, cursor, existing SQL, commit
- Publication critical section: `_pg_conn = new_conn` then `_pg_cursor = new_cursor`, still inside the lock
- Nested helper compatibility: helpers already hold the same lock. The reentrant lock allows the nested call. A second thread's helper waits
- Lock-order review: one lock. Release takes it only to copy and clear, then closes outside it and does not call `get_connection`
- Deadlock findings: none

## 5. PRE-FIX DEFECT REPRODUCTION

- Scenario: two unlocked callers, barrier inside fake connect, before the source edit
- Worker count: 2
- Connections created: 2, both committed
- Connections published: 1
- Connections abandoned: connection 2, `close_calls` 0
- Application cleanup: none
- Harness cleanup: closed both after the snapshot
- Result: D8_CONC_01_REPRODUCED_PRE_FIX

## 6. POST-FIX CONCURRENCY RESULTS

- Simultaneous success: connect called once. Both callers returned id 1. The second was still blocked while the first was inside connect
- First failure, second success: cursor, SQL, and commit failures returned None, then the retry published id 2
- First success, second reuse: the nested helper's second call did not connect again
- Both failures: globals empty, application closed both, harness closed nothing
- Cursor failure: first connection closed by discard, no partial note, retry published
- SQL initialization failure: same
- Commit failure: same
- Cleanup failure: rollback, cursor close, and connection close each recorded `RuntimeError` and did not publish the failed attempt
- Release overlap: old id 1 closed; new id 2 stayed published and open
- Global publication: published cursor matched the published connection
- Connection reuse: overlapping callers and the second helper call reused it
- Worker termination: none remained alive
- Resource accounting: the abandoned pre-fix connection is gone. Post-fix overlap left one open connection, closed by the harness after the snapshot because successful startup retains it

## 7. D.7 CLEANUP PRESERVATION

- Partial initialization cleanup: failed local objects are discarded and not published
- Fatal startup cleanup: broker construction failure closed the connection in the application
- Pre-yield task cleanup: pending 0, harness cancelled 0
- Telegram stop failure: tasks were cleaned; after a startup failure the connection stayed open
- Task-await failure: the health error was reported and no owned task stayed pending
- Primary exception preservation: startup message remained `injected failure before yield`
- Secondary cleanup error reporting: `RuntimeError` was stored

## 8. BORROWER QUIESCENCE

- Telegram thread lifecycle: `start_telegram_control` can start a daemon thread and does not raise. Commands disabled means it returns without a thread
- Join timeout: `stop_telegram_control` joins for at most 2 seconds and does not raise on timeout
- Database borrowers: trade reads go through `fetch_all_trades_ordered`, which holds `_pg_lock` for the query and returns rows
- Active-borrower evidence: no run showed release during an in-progress execute
- Database release: release waits for the lock, so it does not close during a helper's locked section. It can still run after stop returns while the poller thread is alive
- Classification: BORROWER_QUIESCENCE_UNVERIFIED
- Remaining scope requirement: proving the poller has stopped would require `telegram_control.py` or `app.py`. Those files were not changed

## 9. SAFETY INVARIANTS

- Authorisation remains BLOCKED: yes
- Six strategies remain inactive: yes
- No real order routing: yes
- No broker interaction: yes
- No production database access: yes
- No operational-state access: yes
- No shadow-state access: yes
- No network access: yes, on the recorded schedule lists

## 10. REGRESSION COMPATIBILITY

- D.2: pass
- D.3: pass
- D.4: pass
- D.5: HISTORICAL_HASH_PIN_CONFLICT, 15 errors, not a pass
- D.6: HISTORICAL_HASH_PIN_CONFLICT, 12 errors, not a pass
- D.7: pass
- D.8: expected historical defect assertion conflict, 7 errors, not a post-fix acceptance result
- Safety-repair module: pass through the existing D.7 test
- Historical hash-pin conflicts: D.5 and D.6 still expect the pre-D.7 app.py hash. D.8 still expects the pre-D.9 database.py hash
- Remaining gaps: those modules were not executed past their pins

## 11. SOURCE CHANGE INVENTORY

- Files modified: `forex_bot/database.py` only, among production source
- Functions modified: `get_connection`
- Lines changed: 185–227
- SQL changes: none
- Public contract changes: none. Failure still returns None. Success still returns the shared connection. Release is unchanged
- New dependencies: none
- Unauthorised changes: none

## 12. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup was not run
- Database: live schema was not checked. D8-CONC-01 is fixed in the working tree only
- Dependencies: requirements unpinned; no lock; no offline wheelhouse
- Packaging: no candidate image; base-image digest unverified; runtime profile incomplete; no trusted receiving boundary
- Rollback: no verified rollback target
- Production state: container, operational state, and shadow state were not read
- Borrower quiescence: unverified
- Research compatibility: backtests may still assume strategies start active

## 13. VALIDATION

- Commands executed: pre-fix runner; D.9 pytest; D.2, D.3, D.4, and D.7 pytest; D.5, D.6, and D.8 pytest; ruff on the new test files
- Files read: `database.py`, `app.py`, `telegram_control.py`, `state.py`, and the D.7 runner
- Files created: the D.9 runner, the D.9 test module, and this directory
- Files modified: `forex_bot/database.py`
- Tests executed: the modules above. The full suite was not run
- Prohibited operations: none
- Missing evidence: no live poller was observed inside a query during release; D.5, D.6, and D.8 did not run past their pins; production startup was not verified

## 14. FINAL CLASSIFICATION

D9_REMEDIATION_COMPLETE_OFFLINE_TESTED

## 15. NEXT ACTION

- D.9 is complete.
- D8-CONC-01 is fixed in `forex_bot/database.py`.
- Borrower quiescence is not resolved.
- Actual-source concurrency tests ran.
- Actual lifespan regressions ran.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any further production change, and before any restart or deployment.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
