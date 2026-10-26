# STAGE G.14.8 — OFFLINE FILESYSTEM TRUST BOUNDARY VERIFICATION REPORT

## 1. LIVE SAFETY

- Running container changed: no. The G.14.2 identity was not refreshed.
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
- Production database writes: none.
- Operational-state changes: none.
- Shadow-mount changes: none.
- Consensus Forecast modified: no.

## 2. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`.
- Branch: `main`.
- Initial working-tree status: already dirty from earlier stages. Those changes were not reset, cleaned, stashed, or committed.
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`.
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`.
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`.
- Frozen G.10 verification: archive `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`. Canonical manifest digest `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`.
- Frozen G.7 verification: archive `0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82`. Canonical manifest digest `ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989`.
- Unexpected changes: none in the frozen baselines.

## 3. STAGING CONTEXT

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`.
- Expected files: 63.
- Actual files: 63.
- Expected bytes: 617279.
- Actual bytes: 617279.
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`.
- Independent verification: PASS.
- Unexpected files: none.
- Sensitive backups excluded: yes. Their contents were not opened.
- Staging modified: no.

## 4. FILESYSTEM CODE-PATH INVENTORY

- Files reviewed: `tests/g14_7_fs.py`, `tests/g14_7_transport.py`, `tests/test_g14_7_integration.py`, and the path checks in `tests/g14_4_acquire.py`.
- Path-based operations: destination boundary checks and the one `CreateFileW` in `open_directory`.
- Handle-relative operations: `NtCreateFile` with `RootDirectory` for the child directory, artifact files, and the synthetic lock.
- Handle-bound operations: `GetFileInformationByHandle`, `ReadFile`, `WriteFile`, and `CloseHandle` on handles this helper opened.
- Unverified operations: the initial pathname open, directory symlinks, other reparse tags, and cross-volume creation.
- Initial trust boundary: `CreateFileW` on the caller-supplied parent path.

## 5. TRUSTED-PARENT MODEL

- Proposed trusted parent: none that is established before the open. The first handle is whatever object the path names at `CreateFileW` time.
- Parent ownership: not queried.
- Parent ACL assumptions: a same-user owner can rewrite a discretionary ACL. That was not tested as a control.
- Same-user interference: demonstrated. A rename swap before the open required no extra privilege.
- Other-user interference: not tested.
- Administrator interference: outside the model. Not claimed.
- Reparse-point assumptions: an opened object with the reparse attribute is rejected. A junction was tested. A directory symlink was not created.
- Trust-anchor classification: handle-bound only after the open. The path is not a trust anchor.

## 6. WINDOWS API REVIEW

- CreateFileW usage: one open of the parent, `OPEN_EXISTING`, backup semantics, open-reparse-point.
- NtCreateFile usage: relative `FILE_CREATE` only.
- RootDirectory usage: the already opened parent or child handle.
- File identity API usage: `GetFileInformationByHandle` volume serial and file index.
- Reparse-point flags: `FILE_FLAG_OPEN_REPARSE_POINT` on the parent open and `FILE_OPEN_REPARSE_POINT` on directory create.
- Create-new semantics: `FILE_CREATE`. `FILE_OPEN_IF` is not used.
- Sharing modes: read, write, and delete. `os.rmdir` succeeded while the handle was open; the next create failed closed.
- Handle lifetime: directory handles close once. File handles are closed by the workflow.
- NTSTATUS handling: 0 succeeds. `0xC0000035` is a collision. Every other status is `handle_create_failed`. The rest of the NTSTATUS table is `API_CONTRACT_UNVERIFIED`.
- Unverified API contracts: case-sensitive lookup when `Attributes` is 0, 32-bit structure layout, and every API that this helper does not call.

## 7. DIRECTORY IDENTITY

- Parent handle identity: volume serial and file index of the object that was opened.
- Child handle identity: its own file index, same volume serial, reparse attribute clear.
- Volume identity: compared. A normal child matched. A cross-volume create was not executed.
- File ID: 64-bit index from `GetFileInformationByHandle`, not a 128-bit file id.
- Directory attributes: reparse attribute is rejected.
- Reparse-point status: rejected when the attribute is set. The reparse tag is not read.
- Final path by handle: not queried and not used as proof.
- Identity verification classification: `DIRECTORY_HANDLE_IDENTITY_UNVERIFIED` for the initial parent. Child-relative-to-parent is `PARTIALLY_VERIFIED`.

## 8. HANDLE-RELATIVE DIRECTORY CREATION

- Implemented: yes. It was already the G.14.7 child create.
- Parent handle retained: yes, until the workflow closes it.
- Child created relative to parent: yes.
- Existing child rejected: yes, `destination_exists` or `case_collision`.
- Child handle retained: yes.
- Child identity verified: volume serial and reparse attribute on the success path.
- Path-based reopening: none on the workflow path.
- Remaining limitations: the parent open is still a pathname lookup. Relative creation does not move trust to a better anchor.

## 9. REPARSE POINTS AND JUNCTIONS

- Real junction tests: before open, rejected with `symlink_or_reparse`. After open, the junction target stayed empty.
- Real symlink tests: not executed. `os.symlink` returned errno 22.
- Injected symlink tests: unchanged G.14.7 lstat injections. They do not prove kernel symlink behavior.
- Parent reparse tests: a junction parent path is rejected.
- Child reparse tests: a new file or directory whose handle has the reparse attribute is rejected. A real reparse child was not manufactured beyond the junction cases.
- Unsupported scenarios: directory symlinks, and reparse tags other than the junction that was created.
- Classification: `JUNCTION_REJECTION_TESTED_SYMLINK_KERNEL_BEHAVIOR_UNVERIFIED`.

## 10. ACL AND OWNERSHIP

- Ownership reviewed: not read from the security descriptor.
- ACL reviewed: not read.
- Real ACLs modified: no.
- Same-user threat addressed: no. The swap showed the same user can replace the path.
- Remaining assumptions: an ACL is not a demonstrated control against that user. `ACL_RESTRICTION_NOT_APPLICABLE` for the same-user attacker. `ACL_RESTRICTION_UNVERIFIED` for the actual DACL contents.

## 11. INITIAL PATH RACE

- Initial path opened: the caller-supplied parent.
- Trust anchor: the object `CreateFileW` returns. Not an inherited trusted handle.
- Race window: from the caller's choice of path until that call returns.
- Parent replacement: before the open, the handle bound to the substitute and the child was created there. After the open, writes stayed on the original object.
- Junction substitution: rejected when the opened object is the junction.
- Symlink substitution: not executed.
- Handle identity: identifies the opened object only.
- Final classification: `INITIAL_PATH_RACE_UNVERIFIED`.

## 12. DETERMINISTIC RACE TESTS

- Cases planned: 30.
- Cases executed: 28.
- Cases passed as security controls: the post-open, junction, name-policy, deletion, and close cases.
- Cases failed: 0 test failures. Three scenarios did not fail closed: pre-open replacement, replacement between lstat and open, and file creation on that pre-open substitute.
- Cases not executed: real directory symlink; real cross-volume transition.
- Real Windows API tests: open, relative create, identity query, rename, rmdir, and junction creation inside pytest temporary directories.
- Injected tests: the volume-mismatch predicate, plus the existing G.14.7 lstat injections. The predicate is not a kernel result.
- Unexpected writes: none outside pytest temporary directories.
- Remaining coverage gaps: symlink kernel behavior, other reparse tags, cross-volume create, and any detection of a same-user swap before the first open.

## 13. HANDLE-BOUND OPERATIONS

- Artifact creation: relative `FILE_CREATE` on the child handle.
- Artifact writing: `WriteFile` on the new file handle.
- Artifact reading: `ReadFile` on that same handle.
- Artifact verification: `verify_member_bytes` on those bytes.
- Manifest creation: the synthetic lock document is built in memory.
- Synthetic lock creation: `write_exclusive` on the child handle after verification.
- Inventory verification: the workflow compares the names it created. It does not rescan by path.
- Path-based fallbacks: none added.
- Remaining gaps: all of these follow the parent chosen by the initial open.

## 14. HANDLE LIFETIME

- Handle ownership: `DirectoryHandle` closes its kernel handle. The workflow closes file handles.
- Double close: the second directory close is a no-op.
- Use after close: `handle_closed`.
- Interrupted writes: still `interrupted_write`, and the directory is kept.
- Partial files: not deleted.
- Cleanup behavior: handles are closed. Directories are not removed. Historical G.14.7 prototype directories were not removed.
- Resource leaks: none observed in the tests. A crash before close was not tested.
- Remaining gaps: no internal lock for concurrent use of one handle.

## 15. OFFLINE INTEGRATION REGRESSION

- Synthetic workflow: passed again.
- Final state: `COMPLETE_SYNTHETIC`.
- Synthetic lock: `SYNTHETIC_TEST_ONLY`.
- Network requests: none.
- Dependency downloads: none.
- Third-party code execution: none.
- Tests passed: 225.
- Tests failed: 0.
- Tests skipped: 3, all directory-symlink creation with errno 22.

## 16. INDEPENDENT RE-AUDIT

- Trust anchor: `UNVERIFIED`.
- Parent identity: `PARTIALLY_VERIFIED` as the opened object, not as the intended object.
- Child identity: `PARTIALLY_VERIFIED` relative to that parent.
- Handle-relative creation: `VERIFIED_WITH_ASSUMPTIONS`. The assumption is the parent handle.
- Reparse rejection: `PARTIALLY_VERIFIED`.
- Junction rejection: `VERIFIED` on this machine.
- Symlink rejection: `UNVERIFIED`.
- Race resistance: `FAILED` for the initial open. `VERIFIED` after the handle exists.
- Handle-bound verification: `VERIFIED` relative to the opened child.
- Lock creation: `VERIFIED_WITH_ASSUMPTIONS`.
- Remaining critical findings: a same-user replacement before `CreateFileW` selects the directory that receives the acquisition.
- Remaining high findings: initial identity unverified; real symlink behavior not executed; no live HTTPS sender; package source not approved.
- Remaining medium findings: incomplete NTSTATUS mapping, no 32-bit test, ACL bytes not read, no cross-volume test.

## 17. TARGET COMPATIBILITY

- Target OS: Linux.
- Target architecture: x86_64 / AMD64.
- Python implementation: CPython.
- Python major/minor: 3.12.
- Python patch: unknown.
- SOABI: unknown.
- glibc: unknown.
- Pip version: unknown.
- Native wheel tags: unknown.
- Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.

## 18. BASE IMAGE

- Requested tag: `python:3.12-slim-bookworm`.
- Historical local image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. Not refreshed.
- Registry manifest digest: unknown.
- Immutable FROM reference: not established.
- Classification: `BASE_IMAGE_DIGEST_UNVERIFIED`.

## 19. APPROVAL MATRIX

- Package metadata: not approved.
- Wheel-only resolution: offline only.
- Wheel downloads: not approved.
- Artifact verification: synthetic and handle-read only.
- Lockfile generation: not approved.
- Candidate packaging: not approved.
- Docker metadata: not approved.
- Docker build: not granted.
- Image export: not granted.
- Isolated runtime test: not granted.
- Production deployment: NO-GO.
- Rollback: NO-GO.

## 20. REMAINING BLOCKERS

- Filesystem trust anchor: unverified.
- Initial path race: unverified and demonstrated.
- Real HTTPS sender: absent.
- Package-source approval: required. `pypi.org` and `files.pythonhosted.org` were not contacted.
- Dependency lock: not created.
- Verified wheelhouse: not created.
- Target compatibility: incomplete.
- Base-image registry digest: unverified.
- Pip toolchain version: unverified.
- Docker daemon context behavior: unverified.
- Safety-state compatibility: unverified.
- Live database compatibility: unverified.
- Shadow-mount compatibility: unverified.
- Verified rollback target: none.
- Production deployment readiness: NO-GO.

## 21. TESTS

- Exact commands:
  - `python -m pytest tests/test_g13_packaging.py tests/test_g13_1_mutations.py tests/test_g14_context.py tests/test_g14_1_staging.py tests/test_g14_3_supply.py tests/test_g14_4_wheelhouse.py tests/test_g14_5_security.py tests/test_g14_6_security.py tests/test_g14_7_integration.py tests/test_g14_8_filesystem.py -q --tb=line -rs`
  - `python -m ruff check tests/g14_7_fs.py tests/g14_7_transport.py tests/test_g14_8_filesystem.py tests/test_g14_7_integration.py`
  - `python -m mypy tests/g14_7_fs.py tests/g14_7_transport.py tests/g14_4_verify.py tests/g14_4_acquire.py tests/g14_4_inventory.py`
- Tests passed: 225.
- Tests failed: 0.
- Tests skipped: 3.
- Ruff: all checks passed.
- Mypy: no issues in the five modules above.
- Windows API tests: open, relative create, identity query, rename, rmdir, and junctions inside pytest temporary directories.
- Injected tests: volume-mismatch predicate and the existing lstat injections.
- Unsupported tests: directory symlinks and a real second volume.
- Unexpected file changes: staging, production packaging, and frozen evidence were not modified. G.14.7 prototype directories `g147-fs-4o_59mie` and `g147-fs-8qypzh4u` were left in place and not inspected. Probe directories `g148-probe-0204t8r_`, `g148-del-5frkb3jx`, and `g148-swap-eodd93yo` were also left in the user temporary folder.
- Untested behavior: live HTTPS, DNS, pip, Docker, OANDA, and the live database. `tests/test_g10_snapshot.py` was not run.

## 22. FILES CHANGED

- Production Python: none.
- Dockerfile: none.
- .dockerignore: none.
- requirements.txt: none.
- Compose: none.
- Filesystem helper: `tests/g14_7_fs.py`. SHA-256 before `1b1b3954d32562e91a0dbe8304702dbb14596970a5282d523c894ea0053c77e4`. SHA-256 after `b828cc9bf8843a57d82462838ade4259904df641bf880324578576272e6f6980`. It now rejects reserved device names, trailing dots and spaces, and control characters; it rejects a closed handle; and it requires the new object's volume serial to match the parent.
- Transport helper: not modified. SHA-256 remains `dd619f915f7439236ff74efc7e4e0dd26f154484dfeed6abf2fb6b5313020d86`.
- New security helpers: none beyond the filesystem helper change.
- New tests: `tests/test_g14_8_filesystem.py`.
- G.14.8 artifacts: `data/research/adaptive_ensemble/g14_8/`.
- Staging directory: unchanged.
- Running production: unchanged.

G.14.4 through G.14.7 evidence was not overwritten. No Git commit was created.

## 23. FINAL CLASSIFICATION

`G14_8_FILESYSTEM_HARDENING_PARTIAL_GATE_B_BLOCKED`

Name checks, closed-handle checks, and parent-volume checks were added. Post-open handle binding still holds, including against a junction placed at the old path. The initial `CreateFileW` lookup remains a same-user race, and a test showed that the substitute receives the child. That is not a verified trust boundary, and it does not grant Gate B.

## 24. NEXT ACTION

The filesystem trust boundary is not verified. The initial path race is not eliminated and is not contained by a trust anchor. The model cannot assume the same user is benign, because the swap demonstrated the opposite. Further offline hardening of this lookup cannot close it without an inherited trusted handle that this process does not have. Gate B remains blocked. A real HTTPS sender is still absent. Package-source approval remains outstanding. Target compatibility remains incomplete. Any network operation, package download, Docker build, deployment, rollback, or later stage requires separate approval. No network operation is authorised by this report.

GATE B APPROVAL: NOT GRANTED.
DOCKER BUILD APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
