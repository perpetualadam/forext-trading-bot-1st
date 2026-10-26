# STAGE D.4 — FAIL-CLOSED APPLICATION STARTUP AND SAFETY-STATE INTEGRATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D4_REMEDIATION_COMPLETE_OFFLINE_TESTED`
- Confirmed startup defect: `initialise_fail_closed()` returned normally for a corrupt, invalid, unreadable, or future-schema file, and `lifespan` then opened the database, built the broker client, requested an account summary, reconciled, and started background tasks.
- Source correction implemented: `lifespan` now raises `StartupSafetyAbort` unless `live_safety_initialised()` is true after that call. A valid BLOCKED document remains startup-compatible.
- Corrections blocked: none inside `app.py`. The real lifespan was not executed because importing `app.py` loads configuration that reads `.env`.
- Test outcome: 115 passed, 0 failed, 0 skipped. 50 new tests, 30 D.2 preservation tests, and 35 D.3 activation tests.
- Recommended next stage: do not restart or build from this result. A later approved stage would be required before any process start.

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
- Network requests: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Not read and not changed.
- Strategy activation: no production strategy was activated.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: the D.2 and D.3 edits were already present and were left in place. This stage modified `forex_bot/app.py` and added the D.4 test and research files.
- Original app.py hash: `77888f0fa40b5a2935913be6d9b8770c1df0aa204d21c72537cef9e01ac0f70d`
- Final app.py hash: `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Unexpected changes: none. `app.py` was clean before the edit. The other two hashes matched D.2 and D.3.

## 4. STARTUP SOURCE MAP

- Import-time behaviour: importing `app.py` still imports database, broker, and bot-loop modules and would load `.env` through configuration. Connection and account requests are separate later calls. This import was not performed.
- Lifespan entry: line 252.
- Safety-state initialization: line 262, `initialise_fail_closed()`.
- Safety-state classification: lines 263-272. `StartupSafetyAbort` when `live_safety_initialised()` is false.
- Database initialization: line 274, `get_connection()`, after the raise.
- Broker initialization: line 280, `build_api()`, after the raise.
- Broker account requests: line 282, `fetch_account_summary`, after the raise.
- Reconciliation: line 287, after the raise.
- Scheduler: line 312, `create_task(run_bot())`, after the raise.
- Background tasks: lines 309-315, after the raise.
- Shutdown: the task-cancel `finally` belongs to the `yield`. It does not run when startup raises first. No tasks have been created on that path.

## 5. SAFETY-STATE API

- Existing inspection API: `live_safety_initialised()`, `live_order_auth_reason()`, `live_order_auth_state()`, and `live_safety_snapshot()`.
- Valid supported state classification: `live_safety_initialised()` is true only when the document was accepted and the status flag is valid.
- Protected state classification: the same function is false. The reason code distinguishes future schema, unreadable files, and the shared corrupt/invalid code.
- Missing-file handling: the existing creator may write one BLOCKED document. Startup continues only if that result is valid.
- Unsupported schema handling: not valid, file unchanged, startup abort in source.
- Error propagation: `StartupSafetyAbort` is not caught in `lifespan`. A serialization `TypeError` from the safety writer also propagates.
- API limitations: corrupt JSON and an invalid version-1 document share `corrupt_or_unreadable_state`. Both abort. `live_safety.py` was not changed.

## 6. IMPLEMENTATION

- Files modified: `forex_bot/app.py`.
- Functions modified: `lifespan`. New type: `StartupSafetyAbort`.
- Startup preflight: call the existing initializer, then read `live_safety_initialised()`.
- Protected-state abort: raise before database, broker, reconciliation, and tasks.
- Valid BLOCKED-state behaviour: a valid BLOCKED document is initialised, so startup is not aborted for being BLOCKED. Effective authorisation stays BLOCKED.
- Exception handling: the new exception is not swallowed. Existing account-summary and reconciliation handlers remain after the guard and apply only to the valid path.
- Public API changes: none outside this exception type. No new environment variable, dependency, or authorisation flag.
- Dependencies added: none.

## 7. TEST RESULTS

- Tests added: 50 in `tests/test_startup_safety_preflight.py`.
- Tests modified: none. The first T29 assertion matched an import line. It was pointed at the `await` call.
- Tests executed: the new file, `tests/test_live_safety_preservation.py`, and `tests/test_strategy_activation_defaults.py`.
- Tests passed: 115
- Tests failed: 0
- Tests skipped: 0
- Test isolation: temporary safety path; `app.py` was not imported; database, broker, and bot-loop modules were not loaded by the new tests.
- Static assertions: T16-T22, T24, T29, T43, T44, T46, and T50. They read lifespan source.
- Synthetic model tests: T49. It copies the predicate and does not call lifespan.
- Isolated component tests: the safety initializer and the validity flag, plus D.2 and D.3 regressions.
- Actual-lifespan tests: none.
- Untested runtime behaviour: importing `app.py`, running `lifespan`, Uvicorn, the broker, and PostgreSQL.

## 8. PROTECTED-STATE BEHAVIOUR

- Corrupt JSON: not startup-compatible. Bytes unchanged. Component tested.
- Invalid document: not startup-compatible. Bytes unchanged. Component tested.
- Unsupported schema: not startup-compatible. Bytes unchanged. Reason `unsupported_future_schema`. Component tested.
- Unreadable file: not startup-compatible. Reason `safety_state_unreadable`. Component tested.
- Permission failure: same unreadable reason. Not treated as a missing file. Component tested.
- Unknown classification: a non-object root is not startup-compatible. Any false validity result raises in source. There is no allow-list that continues.
- File preservation: tested for those fixtures.
- Startup abort: present in source before downstream calls. The function was not executed.

## 9. STARTUP SIDE-EFFECT PREVENTION

- Database: `get_connection()` is after the raise. Static.
- Broker initialization: `build_api()` is after the raise. Static.
- Broker requests: `fetch_account_summary` is after the raise. Static.
- Reconciliation: after the raise. Static.
- Scheduler: `create_task(run_bot())` is after the raise. Static.
- Trading loop: not called by these tests.
- Other background tasks: reconciliation, health, telegram, and telegram control are after the raise. Static.
- Partial-start cleanup: the abort is before those objects are created, so the yield `finally` is not the protection. Static.

## 10. REGRESSION COMPATIBILITY

- D.2 safety-state preservation: passed, including the new unknown-field check.
- D.2 future-schema protection: passed.
- D.2 corrupt-state protection: passed.
- D.2 atomic writes: a forced replace failure keeps the original bytes and is not startup-compatible.
- D.3 inactive construction: passed.
- D.3 invalid activation: passed.
- D.3 operator activation: confirmation is still required. Authorisation stays BLOCKED.

## 11. INTEGRATION VERDICT

- Safety-state classification: `PASS_ISOLATED_COMPONENT`
- Valid BLOCKED state: `PASS_ISOLATED_COMPONENT`
- Protected-state abort: `PASS_STATIC_ONLY`
- Database ordering: `PASS_STATIC_ONLY`
- Broker ordering: `PASS_STATIC_ONLY`
- Broker requests: `PASS_STATIC_ONLY`
- Reconciliation: `PASS_STATIC_ONLY`
- Scheduler: `PASS_STATIC_ONLY`
- Background tasks: `PASS_STATIC_ONLY`
- Strategy activation: `PASS_ISOLATED_COMPONENT`
- Live-order gate: `PASS_ISOLATED_COMPONENT`
- Failure propagation: `PASS_STATIC_ONLY`
- Cleanup: `PASS_STATIC_ONLY`
- Production image: `UNKNOWN`

## 12. REMAINING DEPLOYMENT BLOCKERS

- Startup: the valid-state path still contacts the broker and the database. The protected-state abort has not been run inside the process. The running image does not contain this edit.
- Database: live schema compatibility remains unverified.
- Dependencies: unpinned requirements, no lock, no wheelhouse.
- Packaging: no candidate image and no trusted receiving boundary.
- Rollback: no verified rollback target.
- Production state: container identity, operational state, shadow mount, and the live safety file were not reverified.
- Research compatibility: backtests that depended on strategies starting active can open no new trades until a later explicit change.

## 13. VALIDATION

- Commands executed: git identity, hashes, pytest on the three isolated modules, ruff on the new test file.
- Files read: `app.py`, the safety status functions, and `initialise_fail_closed`.
- Files created: the preflight tests and `data/research/adaptive_ensemble/d4/`.
- Files modified: `forex_bot/app.py` only, in this stage.
- Tests executed: 115 passed.
- Prohibited operations: none.
- Missing evidence: no lifespan execution, no `app.py` import, no live safety-file read, no image update.

## 14. FINAL CLASSIFICATION

`D4_REMEDIATION_COMPLETE_OFFLINE_TESTED`

## 15. NEXT ACTION

- D.4 is complete for the authorised `app.py` guard.
- Protected safety state now aborts in the lifespan source before database, broker, reconciliation, and background tasks.
- A valid BLOCKED document remains startup-compatible, and effective authorisation stays BLOCKED.
- The D.2 and D.3 regression modules passed.
- Real startup has not been tested.
- The bot may not be restarted.
- An image may not be built.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is required before any process start, image build, or deployment. D.5 was not started.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
