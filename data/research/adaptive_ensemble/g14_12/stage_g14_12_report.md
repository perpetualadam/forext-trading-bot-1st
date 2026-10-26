# STAGE G.14.12 — RECEIVER TRUST CONTRACT ACCEPTANCE AND EXISTING SECURITY PRINCIPAL ASSESSMENT REPORT

Primary classification: `G14_12_NO_SUITABLE_EXISTING_PRINCIPAL_IDENTIFIED`

The R1 design text is now specific enough to describe a boundary against the medium-integrity same-user attacker. No existing principal or directory on this machine was shown to be that boundary. Implementation stays blocked.

## 1. LIVE SAFETY

- Running container changed: no. Historical identity was not refreshed.
- Docker commands executed: 0
- Docker images built: 0
- Docker images pulled: 0
- WSL commands executed: 0
- VM commands executed: 0
- Network requests: 0
- Dependency downloads: 0
- Packages installed: 0
- Third-party package code executed: 0
- Broker API requests: 0
- Broker mutations: 0
- Live-order authorisation: BLOCKED (`operator_preflight_blocked`). Not read and not written.
- Active strategies: none of scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, swing_breakout
- Production database writes: 0
- Operational-state changes: 0
- Shadow-mount changes: 0
- Consensus Forecast modified: no

## 2. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Initial working-tree status: dirty from earlier stages. Porcelain line count 43. Nothing was committed, reset, cleaned, or stashed.
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Frozen G.10 verification: archive `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`, canonical manifest `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`
- Frozen G.7 verification: archive `0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82`, canonical manifest `ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989`
- Unexpected changes: none

## 3. STAGING CONTEXT

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Expected files: 63
- Actual files: 63
- Expected bytes: 617279
- Actual bytes: 617279
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- Independent verification: PASS via `tests/g14_1_verify.py:verify_directory` with no dockerignore import
- Unexpected files: none
- Sensitive backups excluded: yes. Neither backup was opened.
- Staging modified: no

## 4. G.14.11 FINDINGS

- Prior classification: `G14_11_RECEIVER_DESIGN_COMPLETE_IMPLEMENTATION_BLOCKED`
- Preferred receiver architecture: `R1_DEDICATED_WINDOWS_PRINCIPAL_DESIGN_PREFERRED`
- Receiving principal exists: no
- Receiving directory exists: no
- Named pipe exists: no
- Receiver implemented: no
- Adversarial scenarios planned: 50
- Adversarial scenarios executed: 0
- Remaining critical blocker: no principal and no ancestor chain has been shown to stop the G.14.8 swap

## 5. CONTRACT ACCEPTANCE

- Criteria assessed: 30
- Design satisfied: 30
- Design partial: 0
- Design unsatisfied: 0
- Empirically verified: 0
- Unknown: 0
- Unresolved critical defects: 0 in the amended text
- Unresolved high defects: 0 in the amended text
- Contract decision: the design text is internally sufficient for threats A and B. It is not empirically verified. The primary classification is still `G14_12_NO_SUITABLE_EXISTING_PRINCIPAL_IDENTIFIED` because no existing principal meets it.

G.14.11 left ancestors, executable placement, pipe order, unconfigured transfer limits, and file-index reuse incomplete. Those clauses are now written in the G.14.12 documents. `DESIGN_SATISFIED` means the sentence exists. It does not mean Windows enforces it.

## 6. EXISTING PRINCIPAL FEASIBILITY

- Current token identity: `nucbox_m5plus\brian`, SID `S-1-5-21-1451533663-3497457457-3930589332-1001`
- Current integrity level: Medium, `S-1-16-8192`
- Current elevation: not elevated. Administrators is deny-only. Ability to elevate later is unknown.
- Candidate existing principals: none
- Candidate existing protected locations: none
- Principal ownership: this SID is the interactive user and the G.14.8 adversary. It cannot be the receiver.
- Principal authenticity: LocalSystem, LocalService, NetworkService, and Administrators are rejected as inappropriate. They were not queried and are not proposed.
- Interactive-user control: a same-user process can replace directories this token can write. That was already demonstrated.
- Required future inspection: a later prompt must name one target before any further ACL read. A user-database dump was not done and is not authorised.
- Classification: `NO_SUITABLE_EXISTING_PRINCIPAL_IDENTIFIED`

This does not prove the machine has no other local accounts. It proves none was identified under the read-only limits, and the well-known high-privilege identities are not acceptable receivers.

## 7. WINDOWS METADATA EVIDENCE

- Commands executed: `whoami /user`; `whoami /groups` filtered to the integrity label and Administrators
- Targets inspected: the current process token only
- Current token: medium, not elevated, interactive SID above
- Service identity metadata: skipped
- Directory ownership metadata: skipped
- Directory DACL metadata: skipped
- Ancestor DACL metadata: skipped
- Skipped checks: `SKIPPED_UNSAFE_OR_UNVERIFIED` for the user database, service logon names, and any directory ACL walk. No authorised candidate path exists. Temp, OneDrive, the repository, staging, system directories, and production mounts were not scanned.
- Unknown values: UAC elevation ability, other local accounts, every ancestor DACL, pipe DACLs

## 8. FILESYSTEM ANCESTOR TRUST

- Proposed placement contract: every ancestor from the volume root through the receiving directory must deny the interactive SID write, delete, DELETE_CHILD, FILE_ADD_FILE, FILE_ADD_SUBDIRECTORY, reparse creation, rename, WRITE_DAC, and WRITE_OWNER
- Root anchor: not chosen. Not this user's temp, not OneDrive, not the repository, not staging, not a system directory used as a wheel dump
- Parent ownership: the receiver SID, which does not exist
- Parent ACL: not measured
- Ancestor mutability: unknown. One writable ancestor restores the G.14.8 race.
- Same-user substitution: demonstrated against a user-owned directory. Not demonstrated against a protected chain, because no chain exists.
- Reparse-point handling: an open that sees the reparse attribute fails closed. Not retested.
- Handle identity: volume serial plus file index, compared while the receiver holds the handle. The index alone is not identity after deletion.
- Initial-open protection: the sender supplies no path. The remaining requirement is that the receiver's own first open cannot be redirected. That is unverified.
- Missing evidence: a real chain and a failed rename at each level
- Classification: `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`

## 9. EXECUTABLE AND CONFIGURATION INTEGRITY

- Executable placement: on the same protected chain as the data directory. No binary exists.
- Executable owner: receiver SID. Not measured.
- Executable DACL: interactive SID denied write and control. Not measured.
- Configuration owner: same
- Configuration DACL: same
- DLL/import loading: only the receiver tree. User PATH, PYTHONPATH, PYTHONHOME, and user site-packages are not used.
- Environment inheritance: discarded. The allowlist must not contain broker, database, or Docker secrets.
- Writable code paths: forbidden. The current user Python is not an accepted receiver runtime.
- Launch authority: no method is selected. Service, task, and runas each add a replaceable configuration object. Until one method is approved and its config sits on the chain, the receiver is not started.
- Termination authority: the interactive medium token must fail to terminate the process. Not measured. Administrators are not claimed to be blocked.
- Missing evidence: the files, their DACLs, and a failed write
- Classification: `RECEIVER_EXECUTABLE_INTEGRITY_UNVERIFIED`, `RECEIVER_CONFIGURATION_INTEGRITY_UNVERIFIED`

## 10. AUTHENTICATED TRANSFER

- Proposed transport: local named pipe. It does not exist.
- Pipe creation authority: receiver SID only
- Pipe DACL: sender may connect and transfer. Sender may not create a new instance. Interactive SID, Everyone, and anonymous have no access. Not measured.
- Server authentication: client reads the server process SID and aborts unless it is the receiver. The pipe name is not identity.
- Client authentication: server reads the client SID and aborts unless it is the allowlisted sender. No file is created on failure.
- Impersonation policy: the server must not call ImpersonateNamedPipeClient
- Pipe-squatting resistance: a pipe created by this user fails the server-SID check. Unverified.
- Replay resistance: one 32-byte nonce and a session id. A repeated nonce fails. A new nonce does not approve a source.
- Transfer limits: if the approved configuration has no count maximum or byte maximum, fail closed before the first body is stored. No number was invented.
- Fail-closed behavior: short reads, collisions, non-NFC names, streams, device names, and a second concurrent session leave no commit
- Missing evidence: a pipe, its DACL, and scenarios O through AE

## 11. PUBLICATION AND MUTATION

- Publication invariant: no artifact is consumable unless a `FILE_CREATE` record on the still-open receiver directory handle binds the bytes just re-read, their SHA-256 and size, approved provenance, lock identity, and target profile, and the consumer verifies those bytes again before use
- Commit authenticity: only a record produced in the legal state order by the receiver counts. Empty provenance or unknown target tags mean no commit.
- Commit immutability: exclusive create. The interactive SID must lack DELETE. Not measured.
- Artifact immutability: re-read on the open handle before commit and before send. A file index can be reused after deletion, so the index is not enough after the handle closes.
- Consumer verification: on the bytes received over the pipe
- Concurrent mutation: a second session fails while one is active
- Crash recovery: no commit means incomplete. A surviving commit is served only after a fresh ancestor check and a matching re-read. Unknown checks do not serve.
- Audit integrity: records stay on the receiver handle. They are not copied into the repository.
- Missing evidence: the directory and scenarios AK through AN
- Classification: `ARTIFACT_PUBLICATION_BOUNDARY_UNVERIFIED`, `POST_VERIFICATION_MUTATION_PROTECTION_UNVERIFIED`

The invariant is not enforced.

## 12. RECEIVER-TO-BUILD TRUST

- Consumer principal: an allowlisted SID that is not the interactive user. None is identified.
- Consumer code integrity: same ancestor contract. Unverified.
- Consumer configuration integrity: same. Unverified.
- Consumer filesystem anchor: not a user-writable path. No concrete anchor.
- Consumer path substitution: the consumer has no path parameter
- Independent verification: hash, wheel checks, provenance, lock identity, target profile. A synthetic lock fails.
- Build-context isolation: the 63-file staging tree is not a wheelhouse and was not modified. A future context needs its own approval.
- Credential exclusion: backup names and `.env` names fail unread
- Production isolation: no production mount, no operational mount, no shadow mount, no Docker socket, no repository-root context
- Missing evidence: the consumer process
- Classification: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`

## 13. CONTRACT DEFECTS

- Critical defects: 1 found in G.14.11 (ancestors unspecified). Specified in this stage's ancestor contract. Still unverified.
- High defects: 5 found in G.14.11 (executable and imports, pipe order, unconfigured limits, file-index reuse, consumer launch). Specified in this stage's text. Still unverified.
- Medium defects: 1 (receiver privilege set). Specified. The token does not exist.
- Low defects: 0
- Remediation required: no further design sentence is required for those items. Empirical tests remain required.
- Design-only remediation possible: yes, and it is what this stage did
- Empirical verification required: yes for every control

Protection is claimed, as a future test requirement, only against the observed medium-integrity same-user attacker and against other unprivileged users who are actually denied by the DACL. Elevated administrators, a compromised host, and a compromised receiver are not claimed. The receiver owner can change its own DACL. This account might be able to elevate. That was not tested.

## 14. IMPLEMENTATION READINESS

- Contract accepted: as design text only
- Principal identified: no
- Trust anchor identified: no
- Executable integrity specified: yes. Not verified.
- Configuration integrity specified: yes. Not verified.
- Authentication specified: yes. Not verified.
- Publication specified: yes. Not verified.
- Consumer boundary specified: yes. Not verified.
- Production isolation specified: yes
- Implementation approved: no
- Remaining prerequisites: a named creation authority (prerequisite 4) and a separate implementation approval (prerequisite 22). The design gate is not passed.

The gate is not approval to create an account, change an ACL, install a service, create a receiver, download dependencies, or build an image.

## 15. FUTURE APPROVAL PLAN

- Next recommended stage: operator acceptance of this text, if an operator wants that decision. Not account creation. Not a receiver.
- Stage objective: record acceptance of the design, including the limit to threats A and B
- Allowed operations: a decision record
- Prohibited operations: accounts, ACLs, pipes, directories, Docker, WSL, VM commands, network, downloads
- Required evidence: the decision names the limits
- Required approval: a later prompt
- Later approval boundaries: read-only inspection only of a path a later prompt names; account creation only under its own approval; substitution tests only on nonproduction resources; network and Docker each need their own approval. No row authorises live trading.

## 16. REMAINING BLOCKERS

- Filesystem trust boundary: `FILESYSTEM_TRUST_BOUNDARY_UNVERIFIED`
- Artifact-import trust boundary: `ARTIFACT_IMPORT_TRUST_BOUNDARY_UNVERIFIED`
- Isolation boundary: `NO_ISOLATION_BOUNDARY_CURRENTLY_VERIFIED`
- Receiving principal: `RECEIVING_PRINCIPAL_UNVERIFIED`
- Receiving directory trust anchor: `RECEIVING_DIRECTORY_TRUST_ANCHOR_UNVERIFIED`
- Receiver executable integrity: `RECEIVER_EXECUTABLE_INTEGRITY_UNVERIFIED`
- Receiver configuration integrity: `RECEIVER_CONFIGURATION_INTEGRITY_UNVERIFIED`
- Receiver authentication: `RECEIVER_AUTHENTICATION_UNVERIFIED`
- Sender authentication: `SENDER_AUTHENTICATION_UNVERIFIED`
- Pipe-squatting resistance: `PIPE_SQUATTING_RESISTANCE_UNVERIFIED`
- Artifact publication: `ARTIFACT_PUBLICATION_BOUNDARY_UNVERIFIED`
- Post-verification mutation: `POST_VERIFICATION_MUTATION_PROTECTION_UNVERIFIED`
- Receiver-to-build: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`
- Real HTTPS sender: `REAL_HTTPS_SENDER_ABSENT`
- Package-source approval: `PACKAGE_SOURCE_APPROVAL_REQUIRED`
- Dependency graph: `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`
- Dependency lock: none approved
- Verified wheelhouse: none
- Target compatibility: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`
- Base-image registry digest: `BASE_IMAGE_DIGEST_UNVERIFIED`
- Pip toolchain version: `PIP_TOOLCHAIN_VERSION_UNVERIFIED`
- Docker daemon context behavior: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`. Historical container `forexttradingbot1st-bot-1` (`5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`, image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`) was not inspected. It remains `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`.
- Production deployment readiness: NO-GO
- Rollback: NO-GO

## 17. VALIDATION

- Exact commands: Git HEAD, branch, and porcelain status; SHA-256 of the Dockerfile, dockerignore, allowlist, and frozen archives; canonical manifest digests; `verify_directory` on the existing staging tree; `whoami /user`; filtered `whoami /groups`
- Read-only checks: yes
- Dynamic security tests executed: 0
- Docker commands: 0
- WSL commands: 0
- VM commands: 0
- Network requests: 0
- Source files modified: no
- Test files modified: no
- Existing artifacts modified: no
- Unexpected files: none beyond the authorised G.14.12 documents
- Limitations: the running container was not inspected; no DACL was read; other accounts were not listed; design text is not enforcement

## 18. FILES CHANGED

- Production Python: unchanged
- Dockerfile: unchanged
- .dockerignore: unchanged
- requirements.txt: unchanged
- Compose: unchanged
- Research helpers: unchanged
- Test files: unchanged
- G.14.12 artifacts: created under `data/research/adaptive_ensemble/g14_12/`
- Staging directory: unchanged
- Running production: unchanged

## 19. FINAL CLASSIFICATION

`G14_12_NO_SUITABLE_EXISTING_PRINCIPAL_IDENTIFIED`

The design contract is internally specified. All 30 criteria are `DESIGN_SATISFIED` and none are `EMPIRICALLY_VERIFIED`. No suitable existing Windows principal or protected location was identified. The interactive SID is the adversary. High-privilege well-known identities are not acceptable receivers. Implementation remains blocked.

## 20. NEXT ACTION

- The contract was accepted as design text only.
- No existing principal was found suitable.
- The receiving trust anchor was not verified.
- Implementation is not authorised.
- Windows security modifications are not authorised.
- A receiver may not be created.
- An account may not be created.
- ACLs may not be modified.
- Docker may not be used.
- WSL may not be used.
- VM commands may not be used.
- Network requests may not be made.
- Dependencies may not be downloaded.
- Gate B remains blocked.
- Production deployment remains NO-GO.

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
