# STAGE G.13.1 — HISTORICAL TEST MIGRATION AND PACKAGING BASELINE VERIFICATION REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: `BLOCKED`, reason `operator_preflight_blocked`. The safety-state file was not written.
- Active strategies: none. The six original strategies were left inactive.
- Production database writes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Initial working-tree status: the uncommitted G.13 Dockerfile, G.13 tests and artifacts, and the two scheduler files `audit.jsonl` and `state.json`.
- Final working-tree status: those same files, plus the three migrated tests, `tests/g13_1_baseline.py`, `tests/test_g13_1_mutations.py`, and `data/research/adaptive_ensemble/g13_1/`.
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- `.dockerignore` SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 archive verification: `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`
- G.10 manifest verification: canonical digest `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`
- G.10 allowlist verification: file hash `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`, 63 paths, 62 unchanged
- Unexpected changes: none. G.7 archive and canonical manifest also matched. A test run briefly rewrote three G.5/G.6 JSON files; those files were restored. Scheduler files were not edited.

## 3. Historical failure investigation

### G.10 fresh manifest

- Original test: `tests/test_g10_snapshot.py::test_official_archive_is_independently_verified_and_not_rewritten`
- Original assertion: the fresh working-tree manifest digest equals the frozen digest `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`
- Historical purpose: prove the working tree had not moved away from the immutable G.10 snapshot
- Root cause: the fresh digest is `bb0d46140525b1aab6cf3008022d8f051d26fb2767f5ebeb899051053547959a`. All 196 snapshot paths still match except `Dockerfile`.
- Genuine regression or obsolete expectation: obsolete expectation
- Replacement assertion: archive and frozen manifest stay unchanged; every non-Dockerfile snapshot hash matches; the current Dockerfile hash is the G.13 digest
- Evidence that the replacement is not weaker: a one-file snapshot mutation and an unexpected Dockerfile hash both fail the new comparison

### G.11 allowlist drift

- Original test: `tests/test_g11_audit.py::test_g10_allowlist_has_not_drifted`
- Original assertion: `allowlist_drift(...) == []`
- Historical purpose: detect allowlisted bytes that differ from the audited pin and the frozen manifest
- Root cause: the helper returned exactly `['Dockerfile']`
- Genuine regression or obsolete expectation: obsolete expectation
- Replacement assertion: drift must be exactly `Dockerfile`, the allowlist file hash stays pinned, and the working-tree Dockerfile hash is the G.13 digest. Research-only paths remain excluded.
- Evidence that the replacement is not weaker: the original synthetic `main.py` drift check remains, and new fixtures reject a changed Python file, a removed file, an extra allowlist entry, and a rewritten Dockerfile pin

### Broad copy assertion

- Original test: `tests/test_macro_prospective_recorder_stage2.py::test_host_store_is_not_a_bot_container_path`
- Original assertion: `COPY forex_bot ./forex_bot` is present
- Historical purpose: the prospective recorder store is not part of the bot image context
- Root cause: G.13 removed that broad copy on purpose
- Genuine regression or obsolete expectation: obsolete expectation
- Replacement assertion: the static checker accepts only the explicit allowlist copies, `main.py` once, and rejects broad, wildcard, credential, research, test, and operational copies
- Evidence that the replacement is not weaker: the compose, recorder-path, and `bot_loop` assertions remain, and synthetic Dockerfiles with equivalent broad copies fail

## 4. Test migration

- Historical test files modified: the three files above
- Assertions replaced: the full-manifest equality, the empty drift list, and the required broad `COPY`
- Assertions preserved: archive verification, synthetic drift, recorder isolation, compose mounts, and the event-record check
- Tests deleted: none
- Tests skipped: none
- Frozen evidence modified: no
- Regression coverage added: `tests/test_g13_1_mutations.py`

## 5. Packaging verification

- Allowlist file count: 63
- Verified unchanged files: 62
- Authorised Dockerfile exception: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- Missing files: none
- Unexpected files: none
- Broad COPY detected: no
- Duplicate `main.py`: no
- Runtime dependencies: the G.13 closure remains 60 Python modules, with no missing required module
- Static Dockerfile verification: passed
- Docker daemon verification: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`

The 63 audited files are 59 package files, `requirements.txt`, `main.py`, and `Dockerfile`. `Dockerfile` and `.dockerignore` are not runtime copies. The image copy count remains 61.

## 6. Negative mutation testing

- Mutation scenarios executed: 19 rejection cases, each preceded by an accepted fixture where that was needed to show the mutation caused the failure
- Mutations correctly rejected: changed Python file, changed Dockerfile hash, rewritten Dockerfile pin, removed file, extra allowlist entry, `COPY . .`, whitespace-equivalent `COPY forex_bot/`, wildcard copy, duplicate `main.py`, `.env`, test fixture, research artifact, operational-state file, changed startup command, changed dependency command, path traversal, symlink, reparse point, and JSON-array `COPY`
- Mutations incorrectly accepted: none
- Untested mutation scenarios: a real operating-system symlink was not created
- Test implementation limitations: symlink and reparse coverage use controlled fixture behaviour. Unsupported JSON and continued `COPY` forms fail closed instead of being interpreted. No Docker build was run.

## 7. Persistent-state blockers

- Safety-state forward compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`
- Deployment readiness: no. The running image remains `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`.

Passing packaging tests does not resolve those blockers. The safety parser was not changed.

## 8. Test results

- Exact commands: recorded in `test_results.json`
- Tests passed: 274 in the scoped offline suite
- Tests failed: 0
- Tests skipped: 0
- Ruff: the new modules and the G.10/G.11 test files passed. The recorder test file still has its pre-existing unused import, naive datetime, and percent-format findings.
- Mypy: the new modules reported no errors. Pre-existing findings remain in the older loader code, the G.10 tar helper, and the pandas import.
- Warnings: two existing `datetime.utcnow` deprecation warnings
- Tests not executed: the rest of the repository suite, and anything that would contact Docker, OANDA, or the live database

## 9. Files changed

- Historical tests: the three files named above
- New tests: `tests/test_g13_1_mutations.py`
- Audit helpers: `tests/g13_1_baseline.py`
- G.13.1 artifacts: `data/research/adaptive_ensemble/g13_1/`
- Dockerfile: unchanged
- Production Python: unchanged
- Running production: unchanged

## 10. Final classification

`PACKAGING_BASELINE_VERIFIED_OFFLINE_BUILD_APPROVAL_REQUIRED`

This does not authorise a Docker build.

## 11. Next action

Prepare a separate approval request for Stage G.14 — Offline Docker Build-Context and Candidate-Image Verification. Do not execute that stage. It needs its own permission because it would talk to the Docker daemon and expose the build context.

The request should carry these unresolved blockers forward:

- `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- `NO_VERIFIED_ROLLBACK_TARGET`
