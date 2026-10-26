# STAGE D.2 — SAFETY-STATE PRESERVATION AND FAIL-CLOSED STARTUP REMEDIATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D2_REMEDIATION_COMPLETE_OFFLINE_TESTED`
- Confirmed defects: unknown nested strategy fields were dropped on save; an unsupported newer schema and corrupt JSON were replaced with a fresh BLOCKED document; a non-boolean `active` could be treated as true.
- Fixes implemented: supported documents keep unknown top-level keys, unknown nested strategy keys, and unknown strategy names; future, invalid, and unreadable files are not rewritten; effective authorisation stays BLOCKED; interrupted saves do not replace the original file.
- Fixes blocked: the in-memory strategy default `active = True` in `strategy_meta.py` was left unchanged because that file is outside this stage.
- Test outcome: 53 passed, 0 failed, 0 skipped. Thirty new preservation tests and 23 existing repair tests.
- Recommended next stage: a separately approved stage may review startup ordering. Do not start it from this result. Do not restart, rebuild, or deploy.

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
- Live-order authorisation: historically BLOCKED. Not read and not changed on the live file.
- Strategy activation: the six strategies were not activated.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: pre-existing dirty tree was left in place. This stage added a modification to `forex_bot/live_safety.py` and two untracked paths: `tests/test_live_safety_preservation.py` and `data/research/adaptive_ensemble/d2/`.
- Original live_safety.py hash: `6e59666960dfec0ff379343c8973e389363faaab49278d9806c160a18ebe8f4f`
- Final live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- Unexpected changes: none in `forex_bot/live_safety.py` before the edit. The file matched the D.1 hash.

## 4. DEFECT ANALYSIS

- Nested-field loss: CONFIRMED before the edit. TESTED fixed for supported documents.
- Unsupported schema overwrite: CONFIRMED before the edit. TESTED: the original bytes remain.
- Corrupt-state overwrite: CONFIRMED before the edit. TESTED: the original bytes remain.
- Activation interpretation: CONFIRMED that `bool("false")` is true. TESTED: a non-boolean `active` now fails closed and does not activate.
- Atomic-write weaknesses: the previous writer replaced without flush or fsync. Flush and fsync of the temporary file were added. Power-loss durability remains UNVERIFIED.

## 5. IMPLEMENTATION

- Files changed: `forex_bot/live_safety.py`. Tests added: `tests/test_live_safety_preservation.py`.
- Functions changed: validation, inspection, atomic write, snapshot merge, startup load, evolve persistence, and both operator setters.
- Public API changes: no signature changes. New exception type `SafetyStateProtected` for writers that must not replace a protected file. `initialise_fail_closed` still returns a document and does not raise for a future or corrupt file.
- Schema changes: none. Supported schema remains version 1.
- Dependencies added: none.
- Backward compatibility: a valid version-1 BLOCKED document still loads. TESTED.
- Forward compatibility: an integer schema version above 1 is not overwritten. TESTED.

## 6. TEST RESULTS

- Tests added: 30 in `tests/test_live_safety_preservation.py`.
- Tests modified: none. The first T23 assertion expected an exception that `initialise_fail_closed` is specified to catch. That assertion was corrected before the final run.
- Tests executed: the new file and `tests/test_live_safety_repair.py`.
- Tests passed: 53
- Tests failed: 0
- Tests skipped: 0
- Safety invariants verified: A through L for the safety-state module, using synthetic files and the executed tests.
- Safety invariants unverified: running-process startup, the live safety file, and power-loss durability.

## 7. UNKNOWN-FIELD PRESERVATION

- Top-level fields: TESTED. Unknown scalars and nested objects survive a supported round trip.
- Nested strategy fields: TESTED. Unknown scalars and objects on a known strategy survive.
- Unknown future strategy entries: TESTED. Names outside the six are kept.
- Serialization behaviour: supported writes sort keys and refresh sample fields. Values of unknown keys are preserved. Byte identity is claimed only for files that are not written.

## 8. FUTURE-SCHEMA PROTECTION

- Unsupported schema detection: an integer version greater than 1.
- Non-destructive handling: TESTED. Bytes unchanged.
- Effective authorisation: BLOCKED, reason `unsupported_future_schema`.
- Repeated-read behaviour: TESTED. Repeated reads and refused writes do not replace the file.

## 9. CORRUPT-STATE RECOVERY

- Invalid JSON: preserved, fail closed. TESTED.
- Missing fields: preserved, fail closed. TESTED.
- Invalid types: preserved, fail closed. TESTED.
- Original-file preservation: TESTED for the corrupt fixtures.
- Fail-closed behaviour: no ALLOWED authorisation and no active strategy. A truly missing file still creates one BLOCKED document. A permission error does not.

## 10. ATOMIC WRITES

- Write mechanism: same-directory temporary file, flush, fsync, `os.replace`.
- Temporary-file behaviour: removed if the write or replace fails.
- Replacement behaviour: the target is replaced only after the temporary file is written.
- Failure recovery: TESTED. Original bytes remain. No partial target remains after the injected failures.
- Durability limitations: directory fsync and power loss were not tested.

## 11. STRATEGY ACTIVATION

- Existing activation representation: JSON boolean `active` on each known strategy row.
- Invalid values: do not become active. TESTED.
- Missing values: do not become active. TESTED.
- Default behaviour: a new missing-file document has all six inactive. TESTED.
- Unresolved startup risks: `Strategy.active` defaults to True at construction in `strategy_meta.py`. Startup was not run.

## 12. CALLER COMPATIBILITY

- Startup callers: `app.py` calls `initialise_fail_closed` without using the return value. A future or corrupt file no longer raises from that call. Lifespan was not executed.
- Scheduler callers: `evolve` already catches a failure from `persist_evolve_disable`. A protected file raises `SafetyStateProtected` and is not replaced. That path was inspected, not executed.
- Order-routing callers: no new allow path. Existing repair tests passed, including persisted ALLOWED remaining effectively BLOCKED.
- API compatibility: public signatures unchanged.
- Remaining integration tests: the running process and the historical image were not exercised.

## 13. REMAINING BLOCKERS

- Safety-state blockers: the source writer defect is fixed and offline-tested. The running image still has the old file. The live safety file was not read.
- Startup blockers: strategy objects start active until `initialise_fail_closed` runs.
- Database blockers: live schema compatibility remains unverified.
- Dependency blockers: requirements remain unpinned. No lockfile.
- Packaging blockers: no candidate image and no verified rollback target.
- Rollback blockers: unchanged. Rollback is not authorised.

## 14. VALIDATION

- Commands executed: pytest on the two safety modules, ruff on the two Python files, hash and limited git status.
- Files read: `live_safety.py`, the new tests, the existing repair tests, conftest isolation, the evolve call site, and the strategy class.
- Files created: the preservation test module and the D.2 research directory.
- Files modified: `forex_bot/live_safety.py` only, among production source.
- Tests executed: 53 passed.
- Prohibited operations: none performed.
- Missing evidence: no startup run, no live safety-file read, no power-loss test, no dedicated deep-recursion fixture.

## 15. FINAL CLASSIFICATION

`D2_REMEDIATION_COMPLETE_OFFLINE_TESTED`

## 16. NEXT ACTION

- D.2 is complete for the authorised safety-state writer.
- The confirmed safety-state defect is fixed in source.
- Offline tests prove that fix on synthetic files.
- Startup is not verified safe.
- The bot may not be restarted.
- A new Docker image may not be built.
- Production deployment is not authorised.
- Live trading is not authorised.
- A separately approved later stage would be required before any startup, image, or deployment work. D.3 was not started.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
