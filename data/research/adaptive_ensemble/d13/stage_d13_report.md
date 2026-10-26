# STAGE D.13 — APPLICATION TELEGRAM LIFECYCLE REPORTING REMEDIATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: shutdown reporting is fixed offline; startup-refusal reporting needs a supported interface in `telegram_control.py`.
- Gate A: PASS
- Gate B: PASS for the separable shutdown design; startup interface missing
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS for shutdown reporting; startup-refusal schedules remain scope-blocked
- D12-STOP-01: FIXED
- D12-START-01: UNRESOLVED_SCOPE_EXPANSION_REQUIRED
- Tests passed: D.13 8; D.2/D.3/D.4/D.7 133; safety-repair 23; pre-fix D.12 16
- Tests failed: 0 assertion failures. Historical hash pins: 101 setup errors
- Application reporting classification: APPLICATION_SHUTDOWN_REPORTING_ONLY_REMEDIATED
- Scope expansion required: yes, for D12-START-01
- Recommended next stage: a separately approved stage that can change the Telegram start contract. D.14 was not started.

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
- Live-order authorisation: historically BLOCKED; isolated safety state remained BLOCKED
- Strategy activation: the six strategies remained inactive in the isolated safety state

## 3. BASELINE INTEGRITY

- Git HEAD: d080d897945bc44fa37c02caab504ed707146bec
- Branch: main
- Working-tree status: already dirty; preserved
- Original app.py hash: 08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44
- Final app.py hash: 4da4bb0e304b59db702053a1f0702aab227b9896e00bbe4259143def9f2ef3d9
- database.py hash: cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e
- telegram_control.py hash: 193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780
- live_safety.py hash: 11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44
- strategy_meta.py hash: 492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d
- Unexpected changes: none among the protected production hashes before the edit. After the edit, only app.py changed among those files.

## 4. TELEGRAM STARTUP INTERFACE

- start_telegram_control return contract: `None` on success, on a live-worker refusal, on commands disabled, and after a swallowed start exception
- Reliable supported status interface: absent
- Normal start detection: unavailable from the return value
- Refused start detection: unavailable from the return value
- Commands-disabled detection: `commands_enabled()` reports configuration only; it does not prove that a start was refused
- Scope expansion required: yes. Markers: D13_START_REPORTING_INTERFACE_MISSING and D13_SCOPE_EXPANSION_REQUIRED

## 5. TELEGRAM SHUTDOWN REPORTING

- Stop status captured: yes, inside the existing try
- STOP_COMPLETED: no warning
- STOP_NOT_RUNNING: no warning
- STOP_INCOMPLETE_WORKER_ALIVE: warning plus cleanup diagnostic `D12-STOP-01`
- Unknown status: static warning plus `D12-STOP-UNKNOWN`; the value is not logged
- Stop exception: existing cleanup path, including `telegram_stop_failed`
- Warning output: `D12-STOP-01 Telegram shutdown incomplete: polling worker remains alive after bounded join.`
- Cleanup diagnostics: `startup_cleanup_errors()`
- Task cleanup: continues after the diagnostic
- Database ownership: unchanged

`None` from a stub is an absent status. It produces no warning and is not recorded as `STOP_COMPLETED`.

## 6. PRE-FIX REPRODUCTION

- D12-STOP-01: reproduced. D.12 tests passed, 16 in 16.66s, while asserting an empty cleanup list, no incomplete-stop log, a live worker, a published database connection, and drained tasks.
- D12-START-01: reproduced. The second lifespan reached startup with the same worker and no refusal report.
- Actual source functions: `app.lifespan`, `start_telegram_control`, `stop_telegram_control`
- Fake boundaries: in-process Telegram transport, fake PostgreSQL, fake broker, fake reconciliation, fake trading loop
- Application cleanup: recorded before harness cleanup
- Harness cleanup: recorded separately

## 7. POST-FIX ACTUAL-LIFESPAN RESULTS

- Normal lifespan: yields, empty cleanup list, connection retained, tasks drained
- Successful Telegram start: no refusal warning
- Refused Telegram start: still unreported; startup still succeeds; worker count stays at one
- Commands-disabled: yields, no worker, no incomplete-stop diagnostic
- Completed stop: no false warning
- Incomplete stop: `D12-STOP-01` in the cleanup list and in the warning
- Worker alive after lifespan: yes, on the blocked schedule, and still tracked
- Repeated lifespan: second lifespan yields with the same worker and the stop event still set
- Third lifespan: a fresh worker starts after the old worker exits, then a completed stop leaves no incomplete-stop diagnostic
- Database reuse: the same connection id is reused across the first two lifespans
- Asyncio task cleanup: pending owned tasks are 0
- Primary exception preservation: broker failure remains `RuntimeError` and releases the database

## 8. DATABASE OWNERSHIP

- Normal retention: connection stays published; application close calls stay 0
- Failed-startup release: broker failure leaves the connection closed
- Incomplete-stop retention: connection stays published
- In-flight query: existing D.11/D.12 ownership path still waits
- Post-stop query: delayed poll query delta 0
- Post-release reconnection: connect delta 0
- New reporting-related database work: none

## 9. REGRESSION COMPATIBILITY

- D.2: EXECUTED_PASS (30)
- D.3: EXECUTED_PASS (35)
- D.4: EXECUTED_PASS (50)
- D.5: HISTORICAL_HASH_PIN_CONFLICT (15 errors)
- D.6: HISTORICAL_HASH_PIN_CONFLICT (12 errors)
- D.7: EXECUTED_PASS (18)
- D.8: HISTORICAL_HASH_PIN_CONFLICT (7 errors)
- D.9: HISTORICAL_HASH_PIN_CONFLICT (6 errors)
- D.10: HISTORICAL_HASH_PIN_CONFLICT (14 errors)
- D.11: HISTORICAL_HASH_PIN_CONFLICT (31 errors)
- D.12: HISTORICAL_HASH_PIN_CONFLICT and HISTORICAL_DEFECT_ASSERTION_CONFLICT (16 errors)
- Safety-repair module: EXECUTED_PASS (23)
- Historical hash-pin conflicts: 101 setup errors in 1.11s
- Remaining gaps: D12-START-01, and the historical pins above

D.2, D.3, D.4, and D.7 together: 133 passed in 11.57s.

## 10. SOURCE CHANGE INVENTORY

- Files modified: `forex_bot/app.py` among production source
- Functions modified: `lifespan`; helper added: `_note_telegram_stop`
- Lines changed: the stop call now keeps its return value; the helper and the cleanup-list append are new
- Logging changes: two static warnings
- Public contract changes: `startup_cleanup_errors()` may include `D12-STOP-01` or `D12-STOP-UNKNOWN`
- Telegram changes: reporting only; worker, commands, and authentication unchanged
- Database changes: none
- Trading changes: none
- New dependencies: none
- Unauthorised changes: none

## 11. DEFECT ACCEPTANCE

D12-STOP-01

- Pre-fix result: actual lifespan ignored `STOP_INCOMPLETE_WORKER_ALIVE`
- Post-fix result: the status is captured and recorded
- Actual-source evidence: isolated `app.lifespan` and `stop_telegram_control`
- Remaining limitations: historical D.12 tests still expect the old silence
- Status: FIXED

D12-START-01

- Pre-fix result: silent refusal, startup still succeeds
- Post-fix result: still silent, because no supported result exists
- Actual-source evidence: `start_telegram_control` returns `None` at the refusal branch
- Remaining limitations: reporting requires a documented start result
- Status: UNRESOLVED_SCOPE_EXPANSION_REQUIRED

## 12. APPLICATION REPORTING DECISION

- Classification: APPLICATION_SHUTDOWN_REPORTING_ONLY_REMEDIATED
- Evidence: 8 isolated D.13 tests passed
- Limitations: startup refusal is still invisible to `app.py`
- Startup observability: unchanged
- Shutdown observability: incomplete stop is now visible
- Database ownership: preserved
- Required future action: add a supported start result, then report the refusal from `app.py`

## 13. REMAINING DEPLOYMENT BLOCKERS

- Startup: production startup remains unverified
- Database: live schema compatibility remains unverified
- Dependencies: requirements remain unpinned; no lock; no offline wheelhouse
- Packaging: base-image digest unverified; runtime profile incomplete; no candidate image; trusted receiving boundary unimplemented
- Rollback: no verified rollback target
- Production state: container identity, operational state, and shadow state remain unverified
- Telegram reporting: D12-START-01 remains unresolved
- Research compatibility: backtests may assume strategies start active

## 14. VALIDATION

- Commands executed: pre-fix D.12 pytest; D.13 ruff; D.13 pytest; D.2–D.4 and D.7 pytest; safety-repair pytest; historical hash-pin pytest
- Files read: `app.py`, `telegram_control.py`, `database.py`, and the D.11/D.12 runners and tests
- Files created: D.13 tests and `data/research/adaptive_ensemble/d13/`
- Files modified: `forex_bot/app.py`
- Tests executed: listed in section 9
- Prohibited operations: none
- Missing evidence: a supported startup-refusal result; production startup

## 15. FINAL CLASSIFICATION

D13_REMEDIATION_PARTIAL_SCOPE_EXPANSION_REQUIRED

## 16. NEXT ACTION

- D.13 is complete as a partial offline remediation.
- D12-STOP-01 is fixed.
- D12-START-01 is not fixed.
- Startup reporting requires a new supported interface.
- Actual lifespan was tested under isolation.
- Production startup was not verified.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
