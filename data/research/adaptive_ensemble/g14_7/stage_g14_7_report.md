# STAGE G.14.7 — OFFLINE ACQUISITION TRANSPORT INTEGRATION AND FILESYSTEM BOUNDARY HARDENING REPORT

## 1. LIVE SAFETY

- Running container changed: no. The G.14.2 container identity was not refreshed. No Docker command was run.
- Docker commands executed: none.
- Docker images built: none.
- Docker images pulled: none.
- Network requests: none.
- Dependency downloads: none.
- Packages installed: none.
- Third-party package code executed: none.
- Broker API requests: none.
- Broker mutations: none.
- Live-order authorisation: unchanged. Not read and not written. Historical state remains BLOCKED, reason `operator_preflight_blocked`.
- Active strategies: unchanged. scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, and swing_breakout were not activated.
- Production database writes: none. The live database was not accessed.
- Operational-state changes: none. Operational-state mounts were not accessed.
- Shadow-mount changes: none. Shadow-state mounts were not accessed.
- Consensus Forecast modified: no. That project was not opened.

## 2. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`.
- Branch: `main`.
- Initial working-tree status: already dirty from earlier stages. Dockerfile, the consensus-pit scheduler audit and state files, and several research tests were already modified or untracked. Those files were not reset, cleaned, stashed, or committed.
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`.
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`.
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`.
- Frozen G.10 verification: archive `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`. Canonical manifest digest `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`, reconfirmed by the passing G.13.1 tests in this run.
- Frozen G.7 verification: archive `0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82`. Canonical manifest digest `ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989`, reconfirmed by the same tests.
- Unexpected changes: none in the frozen baselines. This stage did not edit production Python, the Dockerfile, `.dockerignore`, `requirements.txt`, or Compose.

## 3. STAGING CONTEXT

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`.
- Expected files: 63.
- Actual files: 63.
- Expected bytes: 617279.
- Actual bytes: 617279.
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`.
- Independent verification: PASS, using `tests/g14_1_verify.py`.
- Unexpected files: none.
- Sensitive backups excluded: yes. Their contents were not opened.
- Staging modified: no.

## 4. TRANSPORT ARCHITECTURE

- Transport implementation: `tests/g14_7_transport.py`.
- Default transport: `NETWORK_DISABLED`.
- Synthetic transport: `ScriptedTransport`, which returns scripted responses and does not open a socket.
- Real HTTPS sender present: no.
- Real-network fallback: no. `None` fails with `missing_transport`. Any other type fails with `real_network_fallback` before `exchange`.
- Import-time network behavior: the new modules do not import a network client. Import does not connect.
- Request-policy enforcement: `authorize_url` and `authorize_redirect_chain` run before every exchange.
- Redirect-policy enforcement: the transport does not follow a location. The workflow authorizes the next hop first.
- Response-policy enforcement: status, content type, size, chunk, timeout field, and retry limits are checked in `_request` and `_bounded`.
- Timeouts: a synthetic elapsed-time field of 5000 ms. The tests do not sleep.
- Retry limits: status 503 may be seen twice more. The next retryable status is `retry_exhausted`.
- Size limits: 65536-byte chunks, 1048576-byte artifacts, 4194304-byte cumulative total, 8192-byte header block.
- Remaining gaps: no live sender, no DNS, no certificate check, and no operating-system timeout. See `transport_architecture.md`.

## 5. STATE MACHINE

- States implemented: CREATED, POLICY_VALIDATED, TARGET_VALIDATED, RESOLUTION_VALIDATED, DESTINATION_VALIDATED, FETCHING_SYNTHETIC, ARTIFACTS_RECEIVED, ARTIFACTS_VERIFIED, DEPENDENCY_GRAPH_VERIFIED, SYNTHETIC_LOCK_PREPARED, COMPLETE_SYNTHETIC, FAILED_CLOSED.
- Illegal transitions rejected: yes. Calling a later `declare_*` method from CREATED raises `illegal_transition` and sets FAILED_CLOSED.
- Failed workflows fail closed: yes. A raised policy, filesystem, or verification error becomes FAILED_CLOSED and is not reported as success.
- Verification required before completion: yes.
- Graph validation required before completion: yes. The graph check is inside `verify_member_bytes`, and the lock step requires `DEPENDENCY_GRAPH_VERIFIED`.
- Synthetic lock marked: `SYNTHETIC_TEST_ONLY`. Source index is `synthetic://fixture`. `source_approved` is false.
- Bypass paths found: none that reach a socket or skip the policy calls.
- Remaining gaps: the state machine has no live-network state. Adding one would be a separate stage.

## 6. WHEELS-ONLY RESOLUTION

- Synthetic target: Linux, x86_64, CPython 3.12. Patch, SOABI, glibc, pip, and native tags stay `UNKNOWN`.
- Direct requirement parsing: `parse_requirement_document`.
- Extras and markers: preserved. A marker that is false on the Linux target fails. An unknown marker fails.
- Source distributions rejected: yes.
- Direct URLs rejected: by the existing inventory parser when present in requirement text, and by artifact URL policy for candidate URLs.
- VCS rejected: by the existing inventory parser and by URL scheme policy.
- Yanked releases rejected: yes.
- Unapproved prereleases rejected: yes.
- Incompatible tags rejected: yes. The positive wheel is `py3-none-any`.
- Remaining gaps: native-wheel compatibility is not verified. The production dependency graph is not verified.

## 7. ARTIFACT STREAMING

- Maximum artifact size: 1048576 bytes.
- Maximum cumulative size: 4194304 bytes.
- Streaming bounded: yes, on synthetic chunks.
- Interrupted streams rejected: yes, `interrupted_stream`.
- Partial artifacts rejected: a short write is `interrupted_write` and does not complete.
- Oversized responses rejected: yes.
- Unexpected content rejected: wrong content type, wrong hash, wrong size, and non-zip bodies fail closed.
- Remaining gaps: the limits are applied to the injected response object, not to a socket.

## 8. FILESYSTEM HARDENING

- Destination restrictions: repository, OneDrive, staging, `concensus-forecast`, Docker volume fragments, and shadow or operational path segments are rejected before create.
- Symlink handling: a reparse-point handle is rejected. Real `os.symlink` failed with errno 22 and those two tests were not counted as passes. Injected `lstat` results were rejected.
- Reparse-point handling: a real junction in a pytest temporary directory was rejected. An injected reparse attribute was rejected.
- Parent-link handling: an injected parent link fails with `symlink_parent`. A real parent symlink was not created.
- Parent-replacement race: after the directory handle is open, renaming that directory and putting a new directory at the old path does not receive the wheel or the lock. The initial `CreateFileW` is still a path lookup.
- Handle-relative operations: `NtCreateFile` with `RootDirectory` set to the opened directory, `FILE_CREATE`, and a single path segment.
- Exclusive creation: `FILE_CREATE`. An existing name is `unsafe_file_replacement`.
- Partial-write behavior: short write fails, the directory is kept, and no lock is written.
- Case-insensitive collisions: rejected.
- Unsupported Windows behaviors: directory symlink creation returned errno 22. POSIX `openat` was not assumed.
- Remaining classification: `ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED`.

## 9. END-TO-END SYNTHETIC WORKFLOW

- Synthetic packages: `demo` 1.0.0.
- Synthetic wheels: `demo-1.0.0-py3-none-any.whl`, built in memory. Its digest is not a published package digest and is not recorded here as one.
- Synthetic redirects: one same-host HTTPS redirect, then the wheel body.
- Synthetic destination: a pytest temporary directory, child `g14-7-synthetic`.
- Synthetic dependency graph: one package, no dependencies, `CONSISTENT_FOR_SYNTHETIC_SET`.
- Artifact verification: hash, size, ZIP, WHEEL, METADATA, and RECORD on bytes read from the file handle.
- Graph verification: required before the lock.
- Synthetic lock generated: `synthetic-lock.json`, marked `SYNTHETIC_TEST_ONLY`, source not approved.
- Final state: `COMPLETE_SYNTHETIC`.
- Real network calls: 0.
- Real downloads: none.
- Third-party code execution: none. The wheel was not installed or imported.

## 10. FAILURE INJECTION

- Negative integration cases: 40 required cases, listed in `failure_injection_results.json`.
- Passed: 38 required cases fully executed, plus the parent-replacement control. Real symlink creation did not run.
- Failed: 0.
- Not executed: destination symlink and parent symlink via `os.symlink` (errno 22). Injected `lstat` equivalents passed and are labeled as injection, not as OS symlink creation.
- Unsupported cases: those two symlink creations. A real junction was supported and was rejected.
- Network fallback attempts: the hostile transport was rejected before `exchange`. The socket guard was not tripped by the workflow.
- Unexpected writes: none outside pytest temporary directories. The staging directory, repository, OneDrive denial path, and synthetic consensus-forecast path were not written.

## 11. INDEPENDENT SECURITY RE-AUDIT

- Transport integration: `OFFLINE_INTEGRATION_VERIFIED`. Live behavior unverified.
- Network-policy integration: `OFFLINE_INTEGRATION_VERIFIED`. `NETWORK_POLICY_NOT_INTEGRATED` does not apply.
- Redirect-policy integration: `OFFLINE_INTEGRATION_VERIFIED`.
- Wheels-only integration: `OFFLINE_INTEGRATION_VERIFIED` for pure wheels.
- Streaming integration: `OFFLINE_INTEGRATION_VERIFIED` for synthetic responses.
- Filesystem integration: post-open binding tested. Initial path lookup remains `FILESYSTEM_RACE_RESISTANCE_UNVERIFIED`.
- Artifact-verification integration: `OFFLINE_INTEGRATION_VERIFIED` for synthetic bytes. `REAL_WHEEL_METADATA_UNVERIFIED`.
- Graph-verification integration: `OFFLINE_INTEGRATION_VERIFIED` for the synthetic set. Production graph remains unverified.
- Lock-generation integration: synthetic lock only, gated on verification.
- State-machine integrity: out-of-order completion is rejected.
- Remaining critical findings: none in the offline workflow.
- Remaining high findings: initial path lookup is not atomic; no live HTTPS sender; package source is not approved; target profile is incomplete.
- Remaining medium findings: real directory symlinks were not created; timeout and retry enforcement is on the synthetic response, not on a socket.

## 12. TARGET COMPATIBILITY

- Target OS: Linux.
- Target architecture: x86_64 / AMD64.
- Python implementation: CPython.
- Python major/minor: 3.12.
- Python patch: unknown. Not invented.
- SOABI: unknown. Not invented.
- glibc: unknown. Not invented.
- Pip version: unknown. Not invented.
- Native wheel tags: unknown. Not invented.
- Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.

## 13. BASE IMAGE

- Requested tag: `python:3.12-slim-bookworm`.
- Historical local image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. This was not refreshed.
- Registry manifest digest: unknown.
- Immutable FROM reference: not established.
- Classification: `BASE_IMAGE_DIGEST_UNVERIFIED`.

## 14. APPROVAL MATRIX

- Package metadata: not approved.
- Wheel-only resolution: offline policy tested; native compatibility not verified.
- Wheel downloads: not approved.
- Artifact verification: synthetic bytes only.
- Lockfile generation: not approved.
- Candidate packaging: not approved.
- Docker metadata: not approved.
- Docker build: not granted.
- Image export: not granted.
- Isolated runtime test: not granted.
- Production deployment: NO-GO.
- Rollback: NO-GO.

## 15. REMAINING BLOCKERS

- Package-source approval: required. `pypi.org` and `files.pythonhosted.org` are not approved.
- Live HTTPS sender: absent.
- Filesystem race resistance: initial path lookup unverified. Post-open handle binding was tested.
- Dependency lock: not created.
- Verified wheelhouse: not created.
- Target compatibility: incomplete.
- Base-image registry digest: unverified.
- Pip toolchain version: unverified.
- Docker daemon context behavior: unverified.
- Safety-state compatibility: unverified.
- Live database compatibility: unverified.
- Shadow-mount compatibility: unverified.
- Verified rollback target: none. The running image remains a historical partial rollback candidate, not a verified target.
- Production deployment readiness: NO-GO.

## 16. TESTS

- Exact commands:
  - `python -m pytest tests/test_g13_packaging.py tests/test_g13_1_mutations.py tests/test_g14_context.py tests/test_g14_1_staging.py tests/test_g14_3_supply.py tests/test_g14_4_wheelhouse.py tests/test_g14_5_security.py tests/test_g14_6_security.py tests/test_g14_7_integration.py -q --tb=line -rs`
  - `python -m ruff check tests/g14_7_fs.py tests/g14_7_transport.py tests/test_g14_7_integration.py tests/g14_4_verify.py tests/g14_4_acquire.py tests/g14_4_inventory.py`
  - `python -m mypy tests/g14_7_fs.py tests/g14_7_transport.py tests/g14_4_verify.py tests/g14_4_acquire.py tests/g14_4_inventory.py`
- Tests passed: 201.
- Tests failed: 0.
- Tests skipped: 2 (`symlink_unavailable:22`).
- Ruff: all checks passed.
- Mypy: no issues in the five modules above.
- Synthetic fixtures: in-memory wheels marked `SYNTHETIC_TEST_ONLY`.
- Unsupported platform tests: real directory symlinks. Not passed.
- Unexpected file changes: the scoped tests did not modify the staging context, the Dockerfile, or the frozen archives. A handle-binding prototype directory under the user temporary folder was left in place. It is not the 63-file staging context and it is not a wheelhouse.
- Untested behavior: live HTTPS, DNS, certificate validation, real wheel metadata, native tags, pip, and Docker. `tests/test_g10_snapshot.py` was not run.

One pre-existing warning remained: a duplicate ZIP member name inside the G.14.6 malformed-archive test.

## 17. FILES CHANGED

- Production Python: none.
- Dockerfile: none.
- .dockerignore: none.
- requirements.txt: none.
- Compose: none.
- Acquisition helper: not modified. SHA-256 remains `0773587232e4974eff0f39c8851bbce5f5a60e766b123ddff3bdf31f2023fc39`.
- Wheel verifier: `tests/g14_4_verify.py` now exposes `verify_member_bytes`. SHA-256 `711b910af4571af13dfc91a8fa86e4d58ba6ee7f52093d049648e828477c4c3f`. Path-based verification remains for earlier tests.
- Inventory helper: not modified. SHA-256 remains `7920d1122e242c21c79193503831d3740f8f064f52d03ab55cffa4ecc4507558`.
- New transport modules: `tests/g14_7_transport.py`.
- New filesystem helpers: `tests/g14_7_fs.py`.
- New integration tests: `tests/test_g14_7_integration.py`.
- G.14.7 artifacts: `data/research/adaptive_ensemble/g14_7/`.
- Staging directory: unchanged.
- Running production: unchanged.

G.14.4, G.14.5, and G.14.6 evidence was not overwritten. No Git commit was created.

## 18. FINAL CLASSIFICATION

`G14_7_OFFLINE_INTEGRATION_COMPLETE_FILESYSTEM_BOUNDARY_BLOCKED`

The synthetic transport, URL and redirect policy, wheels-only checks, bounded synthetic receipt, artifact verification, graph verification, and synthetic lock gate are integrated and covered by failing-closed tests. The initial parent open is still a path lookup, so the filesystem boundary is not fully verified. That result does not grant Gate B.

## 19. NEXT ACTION

Offline integration of the injected transport is complete. The filesystem boundary is not fully verified: writes after the directory handle is open stayed on that object, and the first open by path remains a race window. A real HTTPS sender is still absent. The initial path lookup, the missing sender, the unapproved package source, and the incomplete target profile remain security blockers. Package-source approval is still required. Target compatibility remains incomplete. This report does not authorise another stage, a network operation, Gate B, a Docker build, a deployment, or a rollback.

GATE B APPROVAL: NOT GRANTED.
DOCKER BUILD APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
