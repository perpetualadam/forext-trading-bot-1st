# STAGE D.14 — TELEGRAM STARTUP RESULT CONTRACT AND APPLICATION REPORTING REMEDIATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: Telegram startup now returns an explicit result, and the application reports a previous-worker refusal.
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- D12-START-01: FIXED
- D12-STOP-01: FIXED
- Tests passed: D.14 10; D.2/D.3/D.4/D.7 133; safety-repair plus the unconfigured-start test 24; pre-fix D.13 8
- Tests failed: 0 assertion failures
- Historical conflicts: 109 setup errors
- Recommended next stage: a separately approved stage. D.15 was not started.

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
- Live-order authorisation: historically BLOCKED; isolated state remained BLOCKED
- Strategy activation: the six strategies remained inactive in the isolated state

## 3. BASELINE INTEGRITY

- Git HEAD: d080d897945bc44fa37c02caab504ed707146bec
- Branch: main
- Working-tree status: already dirty; preserved
- Original app.py hash: 4da4bb0e304b59db702053a1f0702aab227b9896e00bbe4259143def9f2ef3d9
- Final app.py hash: 3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1
- Original telegram_control.py hash: 193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780
- Final telegram_control.py hash: d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c
- database.py hash: cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e
- live_safety.py hash: 11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44
- strategy_meta.py hash: 492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d
- Unexpected changes: none before the edit. After the edit, only the two authorised production files changed among the protected hashes.

## 4. TELEGRAM STARTUP RESULT CONTRACT

- Result representation: string constants `START_STARTED`, `START_ALREADY_RUNNING`, `START_REFUSED_PREVIOUS_WORKER`, `START_DISABLED`, `START_FAILED`
- STARTED: `Thread.start()` returned for a new worker
- ALREADY_RUNNING: stored worker is alive and the stop event is clear
- REFUSED_PREVIOUS_WORKER: stored worker is alive and the stop event is set
- DISABLED: commands are not enabled, including an unconfigured bot
- START_FAILED: the existing `except Exception` handled thread construction or `start()`
- Exception propagation: `KeyboardInterrupt` still propagates
- Locking: the existing poller lock; the result is chosen in that same section
- Caller compatibility: the only production caller is `app.lifespan`, which now reports the result and still does not fail startup because of it

## 5. PRE-FIX REPRODUCTION

- D12-START-01: reproduced. D.13 tests passed, 8 in 17.96s, while asserting that the second lifespan succeeded with the same worker and no refusal warning.
- Actual functions: `app.lifespan`, `start_telegram_control`, `stop_telegram_control`
- Fake boundaries: in-process Telegram transport, fake PostgreSQL, fake broker, fake reconciliation, fake trading loop
- Application cleanup: recorded before harness cleanup
- Harness cleanup: recorded separately

## 6. POST-FIX STARTUP RESULTS

- Normal startup: `START_STARTED`, no refusal warning
- Commands disabled: `START_DISABLED`, no worker, no refusal warning
- Healthy already-running worker: `START_ALREADY_RUNNING`, stop event clear, one worker
- Previous stopped worker alive: `START_REFUSED_PREVIOUS_WORKER`, same identity, stop event set
- Concurrent starts: one `START_STARTED`, one `START_ALREADY_RUNNING`, one worker
- Start/stop overlap: refusal while stop is joining; stop event stays set; stop returns `STOP_INCOMPLETE_WORKER_ALIVE`
- Restart after worker exit: a new worker and `START_STARTED`
- Handled startup exception: `START_FAILED`, lifespan still yields
- Previously propagating exception: injected `KeyboardInterrupt` still leaves the function
- Unexpected result paths: an injected unknown string is logged as unrecognised and does not fail startup

## 7. APPLICATION REPORTING

- Start result captured: yes
- Refusal warning: yes
- Warning text: `D12-START-01 Telegram startup refused: previous polling worker remains alive after shutdown request.`
- Normal-start warning: absent
- Disabled-start warning: absent
- START_FAILED reporting: static line that trading continues; startup stays non-fatal
- Unknown result reporting: static unrecognised-status warning; startup stays non-fatal
- Application startup success: refusal still reaches lifespan yield
- Database ownership: the connection is reused across the refused second lifespan
- Asyncio task ownership: unchanged

## 8. D.13 SHUTDOWN REGRESSION

- STOP_COMPLETED: no incomplete-stop warning
- STOP_NOT_RUNNING: direct stop returns that status and adds no warning
- STOP_INCOMPLETE_WORKER_ALIVE: `D12-STOP-01` is recorded
- Unknown stop status: D.13 policy remains
- Stop exception: existing cleanup path remains
- Cleanup diagnostic: `startup_cleanup_errors()`
- Task cleanup: pending tasks are 0
- Database retention: successful and incomplete shutdowns leave the connection published; a broker startup failure still releases it

## 9. DATABASE AND WORKER REGRESSION

- Worker ownership: a timed-out worker stays tracked
- Duplicate-worker prevention: intact
- Stop-event lifetime: refusal leaves it set
- Delayed polling response: query delta 0
- Stop-before-database-entry: gate query delta 0
- In-flight query: release stays blocked until the query finishes
- Database release: waits for that query
- Post-release reconnection: connect delta 0
- Concurrent get_connection: one connection, connect delta 1
- Closed cursor reuse: final open cursors and use-after-close are empty

## 10. SAFETY REGRESSION

- D.2: EXECUTED_PASS (30)
- D.3: EXECUTED_PASS (35)
- D.4: EXECUTED_PASS (50)
- D.7: EXECUTED_PASS (18)
- D.9: historical hash pin; new isolated overlap check passed
- D.11: historical hash pin; new isolated worker and database checks passed
- D.13: historical hash pin; new shutdown checks passed
- Safety-repair module: EXECUTED_PASS (23)
- Historical hash-pin conflicts: 109 setup errors in 1.45s
- Remaining gaps: historical pins, unverified production startup

## 11. SOURCE CHANGE INVENTORY

- Files modified: `forex_bot/telegram_control.py`, `forex_bot/app.py`
- Functions modified: `start_telegram_control`, `lifespan`
- Lines changed: start now returns a status; lifespan reports it
- New result constants/types: the five `START_*` strings
- Logging changes: refusal warning, internal-failure warning, unrecognised-start warning
- Public contract changes: `start_telegram_control` returns `str` instead of `None`
- Worker lifecycle changes: none beyond the result value
- Database changes: none
- Trading changes: none
- New dependencies: none
- Unauthorised changes: none

## 12. DEFECT ACCEPTANCE

D12-START-01

- Pre-fix: silent `None` return and no application warning
- Post-fix: explicit refusal result and an application warning
- Actual-source evidence: isolated `start_telegram_control` and `app.lifespan`
- Remaining limitations: historical D.13 tests still expect the old silence and now stop on the telegram hash pin
- Status: FIXED

D12-STOP-01

- Pre-fix: fixed in D.13
- Post-fix: incomplete stop still records `D12-STOP-01`
- Actual-source evidence: isolated lifespan with a blocked poll
- Remaining limitations: historical hash pins
- Status: FIXED

## 13. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup remains unverified
- Database: live schema compatibility remains unverified
- Dependencies: requirements remain unpinned; no lock; no offline wheelhouse
- Packaging: base-image digest unverified; runtime profile incomplete; no candidate image; trusted receiving boundary unimplemented
- Rollback: no verified rollback target
- Production state: container identity, operational state, and shadow state remain unverified
- Telegram reporting: D12-START-01 and D12-STOP-01 are fixed offline only
- Research compatibility: backtests may assume strategies start active

## 14. VALIDATION

- Commands executed: pre-fix D.13 pytest; D.14 pytest; D.14 ruff; D.2–D.4 and D.7 pytest; safety-repair and start-noop pytest; historical hash-pin pytest
- Files read: `telegram_control.py`, `app.py`, and the D.11–D.13 runners and tests
- Files created: D.14 tests and `data/research/adaptive_ensemble/d14/`
- Files modified: `forex_bot/telegram_control.py`, `forex_bot/app.py`
- Tests executed: listed in section 10
- Prohibited operations: none
- Missing evidence: production startup

## 15. FINAL CLASSIFICATION

D14_REMEDIATION_COMPLETE_OFFLINE_TESTED

## 16. NEXT ACTION

- D.14 is complete as an offline remediation.
- D12-START-01 is fixed.
- D12-STOP-01 remains fixed.
- Actual Telegram startup was tested under isolation.
- Actual `app.lifespan` was tested under isolation.
- Worker ownership remains safe in those tests.
- Database ownership remains safe in those tests.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
