# STAGE D.10 — TELEGRAM THREAD SHUTDOWN AND DATABASE BORROWER QUIESCENCE VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D10_AUDIT_COMPLETE_SHUTDOWN_OR_BORROWER_DEFECTS_FOUND`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS (execution completed; defects were found)
- Actual Telegram functions executed: `start_telegram_control`, `stop_telegram_control`, `_poller_loop`
- Actual database functions executed: `get_connection`, `fetch_all_trades_ordered`, `release_connection_after_failed_startup`
- Actual lifespan executed: `app.lifespan` under isolation
- Tests passed: D.10 pytest 14; compatible regression 139; repair module 23
- Tests failed: D.10 safety outcomes failed where a live worker, a post-release query, or a duplicate worker was observed. D.5, D.6, and D.8 stopped on historical hash pins (34 errors) and are not passes.
- Confirmed defects: D10-STOP-01, D10-DB-01, D10-TEL-02
- Borrower quiescence: `ACTIVE_BORROWER_DEFECT_CONFIRMED`
- Main blockers: stop can return while the poller is alive; that poller can publish a new database connection after release; a later start can overlap the old poller. All prior deployment blockers remain.
- Recommended next stage: a separately approved remediation limited to `forex_bot/telegram_control.py`. Do not start it from this stage.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Telegram network requests: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Network requests: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED; not changed; not reverified in production
- Strategy activation: the six strategies stayed inactive in the isolated runs; production activation was not changed

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: already dirty (74 entries observed). Existing changes were left in place.
- app.py hash: `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44` (match)
- database.py hash: `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e` (match)
- telegram_control.py hash: `270f2b48bbbc1c50b1bb89ae338716803c5e2772fada3b1aa39153fb8b300014` (recorded baseline; D.9 did not supply one)
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44` (match)
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` (match)
- Unexpected changes: none. The same production hashes were present after the tests.

## 4. TELEGRAM THREAD LIFECYCLE

- Thread creator: `start_telegram_control`
- Thread target: `_poller_loop`
- Daemon status: true
- Stop signal: `_stop_event`
- Blocking operations: `get_updates` holds its lock around `Session.get`. Error paths wait on the stop event. A successful poll does not.
- Join timeout: 2.0 seconds
- Stop return behaviour: returns None, including after the timeout
- Thread-alive observability: the stored thread is cleared before join, and nothing checks `is_alive()` afterwards
- Repeated start: refused only while `_poller_started` is true
- Repeated stop: a second call with no stored thread returns immediately

## 5. DATABASE BORROWERS

- Telegram database functions: `fetch_all_trades_ordered` from `cmd_trades` and from search
- Shared connection: yes
- Shared cursor: yes
- Lock coverage: the helper holds `_pg_lock` for the whole read. `get_connection` holds it across initialization.
- Retained references: the handler keeps rows, not the connection or cursor
- Potential future borrowers: a poller blocked in `get_updates` after stop has returned
- Post-release access paths: the next helper call creates and publishes a new connection

## 6. DETERMINISTIC THREAD RESULTS

- Normal stop: thread 19340 exited in 0.0002s
- Stop before start: returned immediately, no thread
- Repeated stop: returned immediately
- Repeated start: one thread while the started flag was set (14696)
- Stop during poll: thread 16048 still alive after 2.0135s
- Stop during database read: release waited while the helper held the lock. A stop that began while another thread held the lock returned in 0.3118s once the worker could finish. A full 2s hold inside `execute` was not run.
- Join timeout: 2.0135s and 2.006s, worker still alive
- Stop returns with live thread: yes
- Old worker survives restart: thread 13880 stayed alive
- Duplicate workers: 13880 and 17184

## 7. DATABASE QUIESCENCE RESULTS

- Release during active query: it waited. It did not close during the locked `execute`.
- Release after stop return: connection 1 was still open when stop returned, then release closed it
- Release with live worker: yes. The worker was in `getUpdates`, not in a query.
- Post-release database access: thread 16048 executed `FROM trades` while alive
- Post-release reconnect: connection 2, and direct helper connection 6 after connection 5
- Closed connection reuse: not observed
- Closed cursor reuse: not observed
- Application cleanup: stop and release returned before the post-release query. The new connection was not released by the application.
- Harness cleanup: closed connection 2 after the worker had left the loop

## 8. ACTUAL LIFESPAN RESULTS

- Startup failure before Telegram: corrupt state made no connection and no thread. Broker failure released the connection and started no thread.
- Startup failure after Telegram: `NOT_REACHABLE_IN_CURRENT_SOURCE`
- Normal shutdown: the fast poller exited, four tasks were cancelled, and the connection stayed open
- Telegram stop exception: an injected raise after the real stop still cleaned the tasks and kept the connection. Production stop does not raise.
- Task-await exception: recorded `RuntimeError`, pending 0
- Database release exception: `RuntimeError` recorded, broker message preserved, global cleared, object left open until the harness closed it
- Remaining tasks: 0
- Remaining threads: thread 3836 was alive after the blocked shutdown. The fast shutdown left none.

## 9. SAFETY INVARIANTS

- Authorisation remains BLOCKED: yes in the isolated lifespan
- Six strategies remain inactive: yes
- No real order routing: yes
- No broker interaction: yes
- No PostgreSQL access: yes
- No Telegram network access: yes
- No operational-state access: yes
- No shadow-state access: yes
- No network access: yes

## 10. REGRESSION COMPATIBILITY

- D.2: EXECUTED_PASS
- D.3: EXECUTED_PASS
- D.4: EXECUTED_PASS
- D.5: HISTORICAL_HASH_PIN_CONFLICT (15)
- D.6: HISTORICAL_HASH_PIN_CONFLICT (12)
- D.7: EXECUTED_PASS
- D.8: HISTORICAL_HASH_PIN_CONFLICT (7). Pre-fix defect assertions were not reached.
- D.9: EXECUTED_PASS
- Safety-repair module: EXECUTED_PASS (23)
- Historical hash-pin conflicts: D.5, D.6, and D.8
- Remaining gaps: full suite not run; F07's full 2s in-query join, poll exceptions, and overlapping `stop` calls were not executed

## 11. CONFIRMED DEFECTS

### D10-STOP-01

- Defect ID: D10-STOP-01
- Severity: shutdown ownership
- Source file: `forex_bot/telegram_control.py`
- Function: `stop_telegram_control`
- Schedule: S11, S12, blocked lifespan shutdown
- Trigger: worker blocked in `get_updates` for longer than 2 seconds
- Observed result: returned None after 2.0135s and 2.006s
- Thread state: 16048, 13880, and lifespan thread 3836 alive; stored reference already cleared
- Database state: unchanged by stop
- Lock state: database lock free
- Application cleanup: lifespan returned with an empty cleanup-error list
- Harness cleanup: released the fake poll and joined the worker after the snapshot
- Proposed remediation: do not clear the worker reference or return until `is_alive()` is false, and do not treat join timeout as completion
- Required future source scope: `forex_bot/telegram_control.py`

### D10-DB-01

- Defect ID: D10-DB-01
- Severity: borrower ownership
- Source file: `forex_bot/telegram_control.py` calling `forex_bot/database.py`
- Function: `_poller_loop_inner`, `fetch_all_trades_ordered`, `get_connection`
- Schedule: S15, S16, S17
- Trigger: release completed while the worker was still inside `getUpdates`; the update was then processed
- Observed result: connection 1 closed; thread 16048 published connection 2. Direct helper moved from connection 5 to connection 6.
- Thread state: `telegram-control` alive during the query
- Database state: new connection published; old object not reused
- Lock state: free at release; held by the later helper
- Application cleanup: release had already returned; connection 2 was not released
- Harness cleanup: closed connection 2
- Proposed remediation: the worker must be unable to enter a database helper before stop returns or before release runs
- Required future source scope: `forex_bot/telegram_control.py`. `forex_bot/app.py` only if a later stage requires lifespan to observe the worker.

### D10-TEL-02

- Defect ID: D10-TEL-02
- Severity: lifecycle race
- Source file: `forex_bot/telegram_control.py`
- Function: `stop_telegram_control` then `start_telegram_control`
- Schedule: S28, S29
- Trigger: start after a timed-out stop
- Observed result: threads 13880 and 17184 both alive; the second start cleared the stop event
- Thread state: two daemon workers
- Database state: not part of this schedule
- Lock state: `getUpdates` calls share one lock, so the HTTP bodies do not run together
- Application cleanup: the first stop had returned and dropped the stored thread
- Harness cleanup: set the stop event again and joined both
- Proposed remediation: `start` must not clear the stop event or create a thread while an older worker is alive
- Required future source scope: `forex_bot/telegram_control.py`

No production file was modified.

## 12. BORROWER QUIESCENCE DECISION

- Classification: `ACTIVE_BORROWER_DEFECT_CONFIRMED`
- Evidence supporting decision: thread 16048 called `fetch_all_trades_ordered` after `release_connection_after_failed_startup` closed connection 1
- Evidence limitations: the current lifespan does not release the connection after a successful start. Startup failure after `start_telegram_control` is not reachable. The D.9 lock serializes one in-flight query and does not prove later quiescence.
- Active borrowers: thread 16048 during the post-release read
- Potential future borrowers: a poller blocked in `getUpdates` after stop; lifespan thread 3836 with the startup connection still open
- Database release safety: unsafe when release follows a stop that returned with the worker alive
- Required future action: separately approved remediation. Not started here.

`SCOPE_EXPANSION_REQUIRED` is also recorded for that remediation because this stage cannot edit production source.

## 13. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup unverified
- Database: live schema unverified; borrower quiescence failed in the isolated composition
- Dependencies: unpinned requirements, no lock, no wheelhouse
- Packaging: no verified candidate image; base-image digest unverified; running image lacks D.2–D.9 source
- Rollback: no verified rollback target
- Production state: container, operational state, and shadow state unverified
- Telegram shutdown: stop can return with a live poller; a later start can overlap it
- Research compatibility: backtests may assume strategies start active; historical D.5, D.6, and D.8 pins remain

## 14. VALIDATION

- Commands executed: D.10 pytest, D.2/D.3/D.4/D.7/D.9 pytest, D.5/D.6/D.8 pytest, repair pytest, ruff
- Files read: production `app.py`, `database.py`, `telegram_control.py`, `telegram_cloud.py`, and the D.7–D.9 runners, read only
- Files created: `tests/d10_telegram_shutdown_runner.py`, `tests/test_d10_telegram_shutdown.py`, `tests/test_d10_database_borrower_quiescence.py`, and this D.10 research directory
- Files modified: no production source, no Dockerfile, no historical tests, no D.1–D.9 artifacts
- Tests executed: 14 D.10, 139 compatible regression, 23 repair, 34 historical hash-pin errors
- Prohibited operations: none
- Missing evidence: a 2s join while the worker held `_pg_lock` for the whole timeout; injected poll and database exceptions during shutdown; overlapping `stop` calls; startup failure after the Telegram thread exists

## 15. FINAL CLASSIFICATION

`D10_AUDIT_COMPLETE_SHUTDOWN_OR_BORROWER_DEFECTS_FOUND`

## 16. NEXT ACTION

- D.10 is complete.
- Shutdown defects were found.
- Database borrower quiescence is not verified. An active post-release borrower was observed.
- Actual Telegram functions were tested.
- Actual database functions were tested.
- Actual lifespan was tested under isolation.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved remediation stage is required before this shutdown behaviour can be changed. It was not started.

PRODUCTION DEPLOYMENT: NO-GO. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
