# STAGE D.8 — DATABASE CONCURRENCY AND CLEANUP EDGE-CASE VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: D8_AUDIT_COMPLETE_CONCURRENCY_OR_CLEANUP_DEFECTS_FOUND
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: executed; defect observed
- Actual database concurrency tests executed: yes, against `forex_bot.database.get_connection`
- Actual lifespan edge-case tests executed: yes, against `forex_bot.app.lifespan`
- Tests passed: D.8 pytest 7 passed in 2.77s. Those tests include assertions that the abandoned connection exists. D.2, D.3, D.4, and D.7: 133 passed in 9.96s.
- Tests failed: T06, T11, and T12 as safety properties. Same defect, D8-CONC-01. D.5 and D.6 were not failures of product code; they stopped on HISTORICAL_HASH_PIN_CONFLICT (27 errors).
- Confirmed defects: D8-CONC-01
- Main blockers: the unlocked initialization race; borrower quiescence unverified; production startup and the running image still unverified
- Recommended next stage: a separately approved change limited to `forex_bot/database.py`, so `get_connection` holds `_pg_lock` across initialization and publication and discards a loser. Do not start that stage from this report.

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
- Network requests: none recorded; the guard list stayed empty
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: BLOCKED in every lifespan case
- Strategy activation: none; `active` was empty

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: main
- Working-tree status: already dirty; preserved. `app.py`, `database.py`, `live_safety.py`, and `strategy_meta.py` stay modified from earlier stages. D.8 added tests and this research directory only.
- app.py hash: `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`
- database.py hash: `74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Existing test hashes: D.5, D.6, and D.7 runners and tests match the hashes recorded at the start of this stage. They were not edited.
- Unexpected changes: none in production source. Hashes were the same after the tests.

## 4. DATABASE OWNERSHIP

- Connection owner: the `forex_bot.database` module, after a successful commit
- Cursor owner: the same module, assigned on the next line
- Borrowers: database helpers under `_pg_lock`; lifespan's one unlocked call; Telegram trade reads through `fetch_all_trades_ordered`
- Shared references: `_pg_conn` and `_pg_cursor`. A caller that keeps the return value has another reference.
- Intended lifetime: process lifetime after a successful publish
- Release mechanism: `release_connection_after_failed_startup`, only from lifespan when startup failed and Telegram stop did not raise
- Lock coverage: helpers hold `_pg_lock` around `get_connection`. `get_connection` itself does not take the lock. Release clears globals under the lock and closes outside it.
- Concurrent initialization risk: confirmed. Two overlapping callers both connect. The later publisher leaves the earlier connection open and unreferenced.

## 5. CONCURRENCY MODEL

- Threads: Telegram control can start one daemon thread. Alert sending has a thread and does not use the database. `asyncio.to_thread` runs account summary and reconciliation after the first `get_connection` returns.
- Async tasks: four lifespan tasks, created after that first call. Cancelling them does not stop the Telegram thread.
- Telegram control: `start_telegram_control` does not raise to the caller. `stop_telegram_control` joins for at most 2 seconds and does not raise on timeout.
- Database helper callers: every helper in `database.py` holds `_pg_lock` for the whole `get_connection` call. Two helpers cannot both initialize.
- Lock ordering: no cycle. The lock is reentrant. Release does not call `get_connection` while holding it.
- Reachable overlap: the function allows it. The current startup order does not start a second caller during the first `get_connection`. The only unlocked production caller is `app.py` line 317, and it runs before tasks and Telegram.
- Unverified concurrency paths: a live process was not inspected. Borrower quiescence after join timeout is unverified.

## 6. DETERMINISTIC TEST RESULTS

- Two simultaneous successful initializations: both committed. Published connection 1 with cursor 1. Connection 2 stayed open with `close_calls` 0. Application closed nothing. Harness closed both after the snapshot. The locked-versus-unlocked schedule did the same with published 3 and abandoned 4.
- First success, second failure: published 6, application closed 7, no abandoned open connection.
- First failure, second success: application closed 8, published 9.
- Both fail: globals empty, application closed both, harness closed nothing.
- Release during borrow: the application closed the object the caller still held. A second release did not connect.
- Release during initialization: release before publish was a no-op. Connection 14 was then published and stayed open.
- Retry after failure: the failed connect created no object. The retry published connection 18.
- Stale references: the abandoned overlap connections and their cursors had no global reference and were still open. The borrowed object was closed while the caller held it.
- Global publication: every executed overlap published a matching connection and cursor. The two assignments were not split, so a torn pair was not observed and is not claimed to be impossible.
- Resource leaks: D8-CONC-01. The failed-close injection left connection 12 open because `close` raised; that was the injected failure, and the note was `RuntimeError`. Connection 13 was closed by the application.
- Worker completion: every worker finished. `alive_workers` was 0.

Helpers that both hold the lock published one connection, id 5. A replacement during close closed old id 16 and left new id 17 published.

## 7. CLEANUP EDGE CASES

- Telegram stop failure: tasks were still cancelled and awaited.
- Database retention: when startup failed and stop raised, the connection stayed open. When startup failed and stop returned, the application closed it. When startup succeeded, the connection stayed open even if stop later raised.
- Active borrowers: not proven absent. `DATABASE_BORROWER_QUIESCENCE_UNVERIFIED`.
- Task-await failure: the health task's injected error was reported, and no owned task stayed pending.
- Cleanup error reporting: `RuntimeError` was stored for the stop failure and for the injected close failure.
- Primary exception preservation: the startup message remained `injected failure before yield` when stop also failed.
- Repeated startup: stayed BLOCKED, with no strategy active.
- Repeated shutdown: no owned task left pending.

## 8. SAFETY INVARIANTS

- Authorisation remains BLOCKED: yes, in the isolated lifespan cases
- Six strategies remain inactive: yes
- No real order routing: yes
- No broker interaction: yes
- No production database access: yes
- No operational-state access: yes
- No shadow-state access: yes
- No network access: yes, on the recorded guard list

## 9. REGRESSION COMPATIBILITY

- D.2: pass
- D.3: pass
- D.4: pass
- D.5: HISTORICAL_HASH_PIN_CONFLICT, 15 errors, not a pass
- D.6: HISTORICAL_HASH_PIN_CONFLICT, 12 errors, not a pass
- D.7: pass
- Safety-repair module: pass through the existing D.7 test. D.8 did not add a repair mode.
- Historical hash-pin conflicts: D.5 and D.6 still expect app.py `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`. Actual is `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`.
- Remaining gaps: those historical modules were not executed past the pin. Equivalent current-source lifespan checks ran in D.8.

## 10. CONFIRMED DEFECTS

- Defect ID: D8-CONC-01
- Severity: high for `get_connection` under overlapping callers. The current startup sequence does not enter that window.
- Source file: `forex_bot/database.py`
- Function: `get_connection`
- Schedule or failure window: S01 and S02; windows C01, C02, C04, C09, C10, C15, C16
- Trigger: two callers pass the empty check. The function does not acquire `_pg_lock`. A helper holding the lock does not exclude an unlocked caller.
- Observed result: two committed connections. One published. The other left open and unreferenced.
- Locks held: none inside `get_connection`
- Resource identities: published 1, abandoned 2; published 3, abandoned 4
- Application cleanup: none for the abandoned connection
- Harness cleanup: closed the abandoned connection and the published connection after the snapshot
- Proposed remediation: hold `_pg_lock` across the check, connect, cursor, SQL, commit, and both publications. If another caller published first, discard the loser and return the published connection.
- Required future source scope: `forex_bot/database.py` only. Not implemented.

Borrower quiescence is an unverified safety claim, not a second observed use-after-close.

## 11. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup was not run and is not verified
- Database: live schema was not checked; D8-CONC-01 is unfixed
- Dependencies: requirements unpinned; no lock; no offline wheelhouse
- Packaging: no verified candidate image; base-image digest unverified; runtime profile incomplete; no trusted receiving boundary
- Rollback: no verified rollback target
- Production state: container identity, operational state, and shadow state were not read
- Research compatibility: backtests may still assume strategies start active

## 12. VALIDATION

- Commands executed: D.8 pytest; D.2, D.3, D.4, and D.7 pytest; D.5 and D.6 pytest; ruff on the two new test files
- Files read: `database.py`, `app.py`, `telegram_control.py`, and the D.7 runner
- Files created: `tests/d8_concurrency_runner.py`, `tests/test_d8_database_concurrency.py`, and this directory
- Files modified: no production source, no D.2–D.7 test, no Dockerfile, no Compose file, no requirements file
- Tests executed: listed above. Full suite was not run.
- Prohibited operations: none
- Missing evidence: the torn publication was not forced; no live poller was observed inside a helper during release; D.5 and D.6 did not run past their pins; the D.8 runner does not wrap `connect_ex`, `create_connection`, or `asyncio.open_connection`

## 13. FINAL CLASSIFICATION

D8_AUDIT_COMPLETE_CONCURRENCY_OR_CLEANUP_DEFECTS_FOUND

## 14. NEXT ACTION

- D.8 is complete.
- A concurrency defect was found: D8-CONC-01.
- A cleanup edge-case defect of the D.7 kind was not found. Telegram stop failure does not skip task cleanup. It does skip database release after a startup failure, and that retention was observed. Borrower quiescence remains unverified, so database release is not classified as safe.
- Database ownership is mapped. Concurrent publication is not safe when two callers initialize together.
- Actual-source concurrency tests ran.
- Actual lifespan edge-case tests ran.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any source change.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
