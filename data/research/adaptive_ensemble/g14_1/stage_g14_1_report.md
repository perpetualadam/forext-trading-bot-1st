# STAGE G.14.1 — SECRET-SAFE MINIMAL BUILD CONTEXT AND SUPPLY-CHAIN PREPARATION REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: BLOCKED (`operator_preflight_blocked`)
- Active strategies: none of the six original strategies
- Production database writes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Initial working-tree status: modified Dockerfile, two scheduler files, three migrated tests, and untracked G.13, G.13.1, and G.14 artifacts and helpers
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Frozen evidence verification: G.10 archive, G.10 manifest digest, G.7 archive, and G.7 manifest digest matched
- Unexpected changes: none in frozen evidence. The test run rewrote three G.5/G.6 JSON files; those three were restored.

## 3. Allowlist reconciliation

- Actual G.10 allowlist count: 63
- Python package files: 59
- main.py: 1
- requirements.txt: 1
- Dockerfile: 1
- .dockerignore: 1
- Other: 0
- Expected application files: 61
- Expected context files: 63
- Discrepancy resolved: yes. `59 + 1 + 1 + 1 + 1 = 63`. Counting five labels on top of 59 produces the reported 64. Omitting `.dockerignore` produces 62. The allowlist file was not edited. `.dockerignore` is inside the 63.

## 4. Minimal staging context

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Outside OneDrive: yes
- Created: yes, a new empty directory
- Expected files: 63
- Actual files: 63
- Total bytes: 617279
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- Unexpected files: none
- Symlinks/reparse points: none
- Independent verification: PASS
- Context classification: local staged context verified. `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`

## 5. Secret exclusion

- First backup filename excluded: yes
- Second backup filename excluded: yes
- Backup contents read: no
- .env excluded: yes
- Credentials excluded: yes
- Research excluded: yes
- Tests excluded: yes
- Operational state excluded: yes
- Arbitrary unallowlisted files excluded: yes, including `notes.txt`
- Negative tests passed: yes
- Conclusion: `UNALLOWLISTED_FILES_CANNOT_ENTER_STAGED_CONTEXT`

## 6. Dockerfile compatibility

- All COPY sources present: yes
- Broad COPY: no
- Wildcard COPY: no
- Duplicate main.py: no
- Duplicate requirements.txt: no
- Entrypoint preserved: yes
- Dependency installation preserved: yes
- Static verification: pass. The Dockerfile and `.dockerignore` were not modified.

## 7. Supply-chain assessment

- Base image: `python:3.12-slim-bookworm`
- Immutable base digest known: no
- Base image locally available: unknown; Docker was not queried
- Requirements fully pinned: no
- Dependency hashes verified: no
- Wheelhouse available: no
- External network required: yes
- Build-time scripts: the Dockerfile's pip upgrade and `pip install -r requirements.txt`, which can run package hooks
- Reproducibility classification: `BASE_IMAGE_DIGEST_UNVERIFIED`, `PYTHON_DEPENDENCY_RESOLUTION_UNPINNED`, `NETWORK_REQUIRED`

## 8. Future build proposal

- Exact proposed command: `docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"`
- Context directory: the staging directory above
- Candidate tag: `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`
- Network access: required for a cold build
- Pull behavior: a missing mutable base tag can still be pulled
- Build-cache behavior: default cache remains enabled and was not inspected
- Secret exposure: the staged context does not contain the backup files, `.env`, or credentials
- Running-production isolation: the command does not start a container or replace the running image
- Docker daemon approval granted: no
- Tag availability: `CANDIDATE_TAG_AVAILABILITY_UNVERIFIED`

## 9. Persistent-state and rollback blockers

- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: no. The running image remains `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`
- Runtime validation: not performed
- Deployment readiness: not ready

## 10. Tests

- Exact commands: recorded in `data/research/adaptive_ensemble/g14_1/test_results.json`
- Tests passed: 304 in the scoped suite, including 27 G.14.1 tests
- Tests failed: 0
- Tests skipped: 0
- Ruff: pass on the new G.14.1 modules
- Mypy: pass on the new G.14.1 modules
- Untested behavior: Docker daemon context handling, base-image presence, candidate-tag collision, and package resolution

## 11. Files changed

- Production Python: unchanged
- Dockerfile: unchanged in this stage
- .dockerignore: unchanged
- Compose: unchanged
- New test helpers: `tests/g14_1_stage.py`, `tests/g14_1_verify.py`, `tests/g14_1_run_stage.py`
- New tests: `tests/test_g14_1_staging.py`
- G.14.1 artifacts: `data/research/adaptive_ensemble/g14_1/`
- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2` (retained)
- Running production: unchanged

## 12. Final classification

`MINIMAL_BUILD_CONTEXT_PREPARED_BUILD_APPROVAL_REQUIRED`

This classification does not mean an image was built and does not authorise deployment.

## 13. Next action

Approve or refuse the candidate-image build in `data/research/adaptive_ensemble/g14_1/phase2_approval_request.md`. The build was not executed.

The staging directory remains until a separate cleanup is authorised. Cleanup must check the exact directory and manifest digest `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b` before deleting only those 63 files.
