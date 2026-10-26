# STAGE G.14.11 — TRUSTED RECEIVING BOUNDARY DESIGN AND VERIFICATION PLAN REPORT

## 1. LIVE SAFETY

- Running container changed: no. The G.14.2 identity was not refreshed.
- Docker commands executed: none.
- Docker images built: none.
- Docker images pulled: none.
- WSL commands executed: none.
- VM commands executed: none.
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
- Initial working-tree status: dirty from earlier stages. 42 porcelain entries, including untracked G.14.10. Those changes were not reset, cleaned, stashed, or committed.
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
- Independent verification: PASS, through `verify_directory`.
- Unexpected files: none.
- Sensitive backups excluded: yes. Their contents were not opened.
- Staging modified: no.

## 4. G.14.10 FINDINGS

- Prior classification: `G14_10_FEASIBILITY_REVIEW_COMPLETE_NO_BOUNDARY_VERIFIED`.
- Isolation architecture selected: none.
- Trusted receiving principal: none.
- Receiving directory: none.
- Artifact import: none demonstrated.
- Same-user resistance: not demonstrated for a protected directory. The G.14.8 path swap still stands and was not re-run.
- Production isolation: unverified.
- Remaining critical blocker: no verified receiving boundary.

## 5. RECEIVER SECURITY OBJECTIVE

- Required invariant: no success report unless the bytes were written into an independently authorised object and stayed bound to it through verification and publication.
- Threat model: the demonstrated same-user pre-open substitution, plus the unverified cases in the threat-model document.
- Correct bytes: receiver hash of its own handle read-back.
- Correct source: an approval that does not exist. A hash is not a source.
- Correct principal: a dedicated SID, not a second process of this user.
- Correct filesystem object: the directory that SID created and opened. A file id after a caller-supplied open is not that proof.
- Correct publication destination: a commit on that handle. A rename into a user directory is not publication.
- Correct dependency graph: `assert_dependency_graph`, and still incomplete while the target profile is incomplete.
- Correct target: unknown patch, SOABI, glibc, pip, and tags. The historical image id is not a digest.
- Correct authorisation: a recorded approval. `COMPLETE_SYNTHETIC` is not one.

## 6. RECEIVING PRINCIPAL

- Options reviewed: R1 dedicated account, R2 service, R3 guest, R4 path-only and same-user launcher.
- Proposed principal: R1, a non-administrator local account that is not the interactive user. It was not created.
- Principal ownership: that account would own the directory. Not shown.
- Principal authenticity: token SID must match. Not implemented.
- Same-user interference: still possible until a medium-integrity swap against that directory fails. A different process of this user is not a different authority.
- Required privileges: account creation needs a future elevated approval. The receiver itself must not be an administrator. This process is not elevated. Whether this account can elevate later is unknown. Administrators was deny-only on the G.14.10 token.
- Missing evidence: the account, the DACL, and the swap test.
- Classification: `RECEIVING_PRINCIPAL_UNVERIFIED`.

## 7. FILESYSTEM TRUST ANCHOR

- Proposed root anchor: the receiver's own directory handle. The sender does not supply the path.
- Parent ownership: receiver SID. Not created.
- Parent ACL: must deny this user's medium-integrity write, delete, and rename. Not written.
- Ancestor mutability: any ancestor this user can rename is still the race. Not enumerated.
- Same-user substitution: the design refuses a sender path. It does not yet prevent a swap of the receiver's own path.
- Reparse-point handling: reject the reparse attribute. Junctions were tested in G.14.8. Symlinks were not. Other tags were not.
- Handle identity: volume serial and file index of the opened object.
- Directory identity: not proof of pre-open intent.
- Initial-open protection: unverified. `lstat` then `CreateFileW` is not accepted as protection.
- Missing evidence: the directory and the failed swap.
- Classification: `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`.

## 8. ACQUISITION-TO-RECEIVER PROTOCOL

- Proposed transport: a local named pipe with explicit SID checks. The pipe was not created. Locality is not authentication.
- Sender authentication: client SID on an allowlist. Not implemented.
- Receiver authentication: server SID is the receiver. Not implemented.
- Transfer limits: count and size caps belong to a future approval. Exceeding them fails closed. No cap number was invented as a security result.
- Artifact naming: one NFC path segment. Traversal, streams, device names, and casefold collisions fail.
- Artifact hashes: receiver recomputes them from handle bytes.
- Source provenance: required and absent. Proposed hosts are not approved.
- Replay resistance: a receiver nonce. A repeated nonce fails. The nonce is not a content signature.
- Interrupted transfer: `FAILED_CLOSED`. The partial file is not published.
- Fail-closed behavior: no fallback to `open_directory` on a sender path.
- Required future tests: the 50 scenarios. None were run.

## 9. INDEPENDENT VERIFICATION

- Wheel format: `parse_wheel_filename` and wheel-only rejection.
- ZIP verification: `inspect_wheel_bytes`.
- WHEEL metadata: that inspector.
- METADATA: that inspector.
- RECORD: `_check_record`.
- Dependency graph: `assert_dependency_graph`. Completeness stays unverified.
- PEP 508 markers: unknown markers fail. They are not treated as true.
- Extras: only an approved set. None is approved.
- Target wheel tags: cannot pass while the tag set is unknown.
- Lockfile: a synthetic lock is not production evidence. `accept_verified_lock` still takes a path. A future check must use handle bytes. That change was not made.
- Package-source approval: required and not granted.
- Remaining gaps: source, digest, pip, SOABI, glibc, tags, and a real lock.

## 10. CONTROLLED PUBLICATION

- Publication states: the 13 named states, forward only, or `FAILED_CLOSED`.
- Publication trust anchor: the same directory handle. Not a user path.
- Atomicity: one commit record created with `FILE_CREATE` after re-read. A rename can be atomic and still be the attacker's directory.
- Concurrent mutation: a changed file id fails.
- Post-publication mutation: a later re-read mismatch refuses the consumer.
- Crash recovery: no commit record means not published. The record is not invented.
- Audit evidence: SIDs, hashes, and reasons. No secrets.
- Failure state: `FAILED_CLOSED`.
- Remaining gaps: the machine was not implemented, so publication is unverified. Current blockers stop the design before `PROVENANCE_VERIFIED`.

## 11. RECEIVER-TO-BUILD BOUNDARY

- Proposed consumer: an allowlisted SID that reads bytes. Not the production container. Not the 63-file staging tree.
- Consumer authentication: server SID checked by the consumer.
- Published-object identity: file id and hashes in the commit, checked by the receiver at send time.
- Consumer path substitution: a consumer that opens a path is outside the claim and is a failure if it is reported as publication.
- Independent verification: the consumer hashes and re-checks the wheel.
- Build-context isolation: a new context only, under a later approval. Wheels are not added to the existing staging directory.
- Credential exclusion: the two backup filenames and `.env` names are rejected and not read.
- Staging compatibility: staging was reverified and not modified.
- Required future tests: F, AQ, and the publication scenarios.
- Classification: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`.

## 12. ADVERSARIAL TEST PLAN

- Planned scenarios: 50.
- Fully specified scenarios: 50. Identifiers A through AX.
- Same-user substitution cases: A through F.
- Junction cases: G.
- Symlink cases: H. A creation failure stays not executed and is not a pass.
- ACL cases: K and L.
- Authentication cases: O, P, and AQ.
- Artifact-integrity cases: AD through AL.
- Publication cases: AM, AN, and AO.
- Production-isolation cases: AR, AS, AT, AU, and AV. None of them may touch live OANDA, PostgreSQL, operational state, or shadow state.
- Executed scenarios: 0.
- Remaining test-design gaps: none of the required identifiers were left unspecified. Running them is a later approval.

## 13. FAIL-CLOSED CONTRACT

- Conditions covered: 28, from an unverified principal through an unknown security state.
- Unknown-state handling: `FAILED_CLOSED` and manual approval before any retry that would publish.
- Partial artifact handling: unpublished bytes may remain. They are not a commit.
- Crash handling: absence of a valid commit is not publication.
- Cleanup policy: no automatic deletion of historical evidence or production files.
- Evidence retention: reasons, SIDs, and hashes. No secret contents.
- Recovery requirements: a new transfer. A failed session is not repaired into success.
- Classification: specified, not implemented. No less-secure path fallback. Synthetic success does not authorise a real download.

## 14. ARCHITECTURE FEASIBILITY

- Windows host evidence: reused from G.14.10. Not remeasured. Professional, AMD64, medium integrity, not elevated, hypervisor and WSL service were running then, Docker only historically.
- Required new principal: yes. Not created.
- Required ACL configuration: yes. Not performed.
- Required service configuration: no for the preferred design. R2 was not selected.
- Required IPC implementation: yes. Not created.
- Required artifact receiver: yes. Not created.
- Required guest environment: no for R1. A guest sender would be a different approval.
- Required privileges: a future elevated step to create the account. Receiver runtime is not administrator.
- Evidence gaps: DACL, elevation ability, ancestor writability, symlink kernel behaviour, current Docker context.
- Classification: designed, and implementation blocked on the missing substitution test.

## 15. ARCHITECTURE DECISION

- Preferred receiver architecture: `R1_DEDICATED_WINDOWS_PRINCIPAL_DESIGN_PREFERRED`.
- Rationale: the sender and the receiver must not share a write-capable token. A service, a guest, and a careful path do not fix the open by themselves.
- Trust assumptions: a medium-integrity user cannot rewrite the future DACL. Not tested. Administrator resistance is not claimed.
- Same-user resistance: required before acceptance. Not shown.
- Acquisition boundary: SID-checked bytes. Not built.
- Publication boundary: commit on the receiver handle. Not built.
- Build-consumer boundary: bytes and a second verification. Not built.
- Missing verification: all 50 scenarios, the principal, and the ACL.
- Implementation approved: no.

## 16. FUTURE APPROVAL PLAN

- Next recommended stage: do not create the account. A later prompt may accept or reject the contract, then a separate prompt may inspect whether any existing principal already meets it.
- Stage objective: that inspection is read-only unless its own approval says otherwise.
- Allowed operations: only what that prompt names.
- Prohibited operations: account creation, ACL writes, pipes, directories, Docker, WSL, VM, and network remain prohibited.
- Required evidence: an owner SID and a failed medium-integrity swap, or an explicit statement that none exists.
- Required approval: separate from G.14.11.
- Later approval boundaries: prototype, substitution tests, authentication, transfer limits, wheel checks, publication, consumer, optional guest, synthetic acquisition, metadata, downloads, lock verification, packaging, candidate build, runtime, and production review. Each is separate. None authorises live trading.

## 17. REMAINING BLOCKERS

- Filesystem trust boundary: unverified.
- Artifact-import trust boundary: unverified.
- Isolation boundary: none verified.
- Receiving principal: unverified.
- Receiving directory trust anchor: unverified.
- Sender authentication: unverified.
- Receiver authentication: unverified.
- Artifact publication: unverified.
- Receiver-to-build: unverified.
- Real HTTPS sender: absent.
- Package-source approval: required.
- Dependency graph: incomplete.
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

## 18. VALIDATION

- Exact commands: Git metadata, and one read-only Python process that hashed the authorised baselines and called `verify_directory`.
- Read-only checks: those, plus the G.14.10 report and the verifier function names.
- Dynamic receiver tests executed: none.
- Docker commands: none.
- WSL commands: none.
- VM commands: none.
- Network requests: none.
- Source files modified: none.
- Test files modified: none.
- Existing artifacts modified: none.
- Unexpected files: none.
- Limitations: the design was not run. No ACL was read. Elevation was not tested. Host service facts were not refreshed.

## 19. FILES CHANGED

- Production Python: none.
- Dockerfile: none.
- .dockerignore: none.
- requirements.txt: none.
- Compose: none.
- Research helpers: none.
- Test files: none.
- G.14.11 artifacts: `data/research/adaptive_ensemble/g14_11/`.
- Staging directory: unchanged.
- Running production: unchanged.

No Git commit was created. No principal, directory, service, ACL, or endpoint was created.

## 20. FINAL CLASSIFICATION

`G14_11_RECEIVER_DESIGN_COMPLETE_IMPLEMENTATION_BLOCKED`

The receiving contract is specified: a dedicated principal, a handle it opens itself, SID-checked bytes, independent verification, and publication that is not a user-path rename. Fifty adversarial tests are specified and were not run. Implementation is blocked because that principal does not exist, the ACL is unmeasured, and the same-user swap that G.14.8 demonstrated has not been shown to fail. This classification does not approve implementation or Gate B.

## 21. NEXT ACTION

The receiving design is complete as a contract. A preferred architecture was selected: R1. The receiving principal does not exist. The filesystem trust anchor is not verified. Artifact transfer is not implemented. Controlled publication is not implemented. No Windows security configuration is authorised. No receiver implementation is authorised. No environment creation is authorised. No Docker operation is authorised. No WSL operation is authorised. No VM operation is authorised. No network operation is authorised. No dependency download is authorised. Gate B remains blocked. Production deployment remains NO-GO.

GATE B APPROVAL: NOT GRANTED.
NETWORK APPROVAL: NOT GRANTED.
DEPENDENCY DOWNLOAD APPROVAL: NOT GRANTED.
DOCKER APPROVAL: NOT GRANTED.
WSL APPROVAL: NOT GRANTED.
VM APPROVAL: NOT GRANTED.
WINDOWS SECURITY MODIFICATION APPROVAL: NOT GRANTED.
RECEIVER IMPLEMENTATION APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
