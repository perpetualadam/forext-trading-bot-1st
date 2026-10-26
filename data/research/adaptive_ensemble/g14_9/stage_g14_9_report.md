# STAGE G.14.9 — OFFLINE ACQUISITION TRUST-ANCHOR ARCHITECTURE REVIEW REPORT

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
- Initial working-tree status: dirty from earlier stages. 40 porcelain entries. Those changes were not reset, cleaned, stashed, or committed.
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
- Independent verification: PASS, through `tests/g14_1_verify.py` `verify_directory`. Per-file hashes matched the G.14.1 manifest. Symlinks, reparse points, and placeholder attributes would have failed that call.
- Unexpected files: none.
- Sensitive backups excluded: yes. Their contents were not opened.
- Staging modified: no.

## 4. G.14.8 FINDINGS

- Initial trust-anchor status: the caller-supplied path is not an anchor. `open_directory` uses `CreateFileW`.
- Same-user substitution result: a replacement before the open binds the handle to the substitute. The child is created there. The test did not fail closed.
- Handle-relative operations: verified only relative to the opened object. That does not verify the filesystem boundary.
- Parent identity: volume serial and file index of the opened object. Not a pre-open identity.
- Child identity: partial, relative to that parent. Cross-volume creation was not executed.
- Junction coverage: tested. Rejected before the open. After the open, the junction target stayed empty.
- Symlink coverage: not executed. `os.symlink` returned errno 22.
- Remaining critical finding: `INITIAL_PATH_RACE_UNVERIFIED`.

## 5. OPTION A — TRUSTED HANDLE

- Proposed trust anchor: a handle supplied by a launcher. The launcher's own first open is still a pathname lookup.
- Launcher model: not created. A same-user launcher is the attacker in the G.14.8 test. A different account was not found and would need elevation this stage did not request.
- Handle transfer: inheritance or `DuplicateHandle` would require a good handle first. Neither was built. Process DACLs were not read.
- Same-user protection: none for the weak launcher.
- Initial-path problem: moved into the launcher, not removed.
- Required privileges: none for the weak design. The weak design fails. A stronger principal is unevidenced.
- Required evidence: a directory this user cannot replace, a tested transfer, and a launcher binary this user cannot replace.
- Major risks: silent success on the substitute, and a new race on the launcher executable.
- Classification: `TRUST_ANCHOR_UNVERIFIED`. Ineligible.

## 6. OPTION B — ISOLATED ENVIRONMENT

- Proposed environment: none selected.
- Trust anchor: a boundary this user cannot reconfigure. Not observed.
- Filesystem isolation: unknown for WSL, a virtual machine, and a container. A restricted process of this user is not isolation.
- Credential isolation: would require no mounted profile. Not set up.
- Production isolation: would require no production, operational, or shadow mounts and no Docker socket. Not set up. The running container was not used.
- Network policy: deny until a separate approval. Not observed as an OS control.
- Artifact export: a later host `CreateFileW` on a user-writable path repeats the race. A guest hash does not bind that open.
- Target compatibility: a Linux guest might eventually observe the production profile. No guest ran. The profile stays incomplete.
- Required privileges: a principal this user cannot drive is likely to need rights this stage did not measure and did not request.
- Required evidence: who owns the boundary, whether this user can rewrite it, the mount list, and an export that is not a raced path open.
- Major risks: treating Docker, WSL, or a restricted token as a boundary; sharing a daemon with the production container; mounting a host path.
- Classification: `TRUST_ANCHOR_DESIGNED_NOT_IMPLEMENTED`. `ENVIRONMENT_SELECTION_REQUIRES_FURTHER_EVIDENCE`. Not eligible to build.

## 7. OPTION C — CONSTRAINED TRUST MODEL

- Trusted actors: this user and every process that runs as this user.
- Untrusted actors: other local users, remote clients, and package authors. Administrators and a compromised host stay outside the claim.
- Same-user attacker treatment: defined as trusted. The G.14.8 swap is the excluded case, and the code still behaves as that test recorded.
- Assumptions: the path stays stable until `CreateFileW`, and no same-user process will replace it during a later download.
- Residual risk: a substitute receives the wheelhouse and the success marker.
- Required operator acceptance: an explicit statement that the demonstrated vulnerability is accepted. This stage does not recommend that statement and does not record it.
- Classification: `TRUST_ANCHOR_ASSUMPTION_ONLY`. Ineligible.

## 8. SECURITY COMPARISON

- Criteria: 17. Anchor, same-user resistance, and residual risk are weighted 10. Files, credentials, and production isolation are weighted 8. Export is 7. Network, verification, and Docker risk are 6. The remaining weights are 5 or less so a smaller build cannot hide a failed boundary. Weight sum 104. Maximum weighted score 520.
- Weights: published in `security_comparison_matrix.json`.
- Option A score: 190. Ineligible.
- Option B score: not computed. The isolation scores are unknown, and filling them would invent a winner.
- Option C score: 178. Ineligible.
- Ineligible options: A, B, and C.
- Mandatory safety conditions: pre-open same-user substitution is prevented or contained, and the import open does not recreate it.
- Uncertainty: launcher process DACLs, other-user DACLs, directory symlinks, and every hypervisor, WSL, and Docker property. Those were not inspected.

## 9. ARTIFACT EXPORT/IMPORT

- Acquisition-side verification: handle-relative create, read-back, hash, wheel checks, and a manifest that is only a claim.
- Export boundary: not solved. Option A has no separate boundary. Option B's exit is unspecified. Option C publishes on a declared-trusted path.
- Receiving-side verification: the receiver hashes bytes it reads and builds its own inventory.
- Manifest handling: the receiver does not trust the producer manifest alone.
- Hash handling: a match proves byte equality. It does not prove source approval or directory intent.
- File ownership: not read in G.14.8. Not a same-user control by itself.
- Link handling: reparse attribute and link count are checked at create. Symlink kernel behaviour remains unexecuted.
- Atomic publication: a rename between user-writable directories is not atomic against this user.
- Remaining risks: the receiver's first path open is the G.14.8 race unless an anchor outside this user's write set exists. None does.

## 10. TARGET COMPATIBILITY

- Target OS: Linux.
- Target architecture: x86_64 / AMD64.
- Python implementation: CPython.
- Python major/minor: 3.12.
- Python patch: unknown.
- SOABI: unknown.
- glibc: unknown.
- Pip version: unknown.
- Native wheel tags: unknown.
- Base-image registry digest: unknown. Historical local id `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` was not refreshed.
- Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`. Also `BASE_IMAGE_DIGEST_UNVERIFIED`, `PIP_TOOLCHAIN_VERSION_UNVERIFIED`, and `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`.

## 11. FUTURE NETWORK POLICY

- Proposed index: `https://pypi.org/simple`. Not approved.
- Proposed artifact host: `files.pythonhosted.org`. Not approved.
- HTTPS requirements: scheme HTTPS only, certificate validation left on.
- Redirect policy: fail closed unless the next URL stays on the same approved host and stays HTTPS.
- DNS policy: no IP literals. Resolution only under a future approval. No lookup was made.
- Credential policy: no credentials, cookies, or broker tokens on acquisition requests.
- Proxy policy: no implicit environment proxy.
- Timeout policy: bounded, with the bound left to the approval that creates a sender.
- Size limits: response and body bounds before storage. Live numbers were not chosen.
- Source-build prohibition: no source distributions, no setup hooks, no PEP 517, no install during acquisition.
- Network approval: not granted.

## 12. PREFERRED ARCHITECTURE

- Decision: `NO_OPTION_READY_FOR_IMPLEMENTATION`.
- Rationale: A relocates the open. B has no evidenced subtype and would still need a safe import. C accepts the demonstrated attacker. Scores were not allowed to choose between ineligible options.
- Mandatory conditions: a boundary this user cannot swap, two-sided byte verification, no production mounts, network still denied, staging and the running container untouched.
- Assumptions: none of the assumptions in the decision document are granted.
- Alternative: a future read-only evidence stage to see whether any such boundary already exists. That stage is not started here. If it needs Docker, WSL, or a new guest, it needs its own approval.
- Rejected options: A as an implementation, C as a boundary, and every B subtype as a selection.
- Remaining blockers: the filesystem anchor, the absent sender, source approval, lock, wheelhouse, target profile, image digest, and the production NO-GO list.

## 13. FUTURE STAGES

- Next recommended stage: evidence sufficient to select a boundary, or an explicit finding that no boundary is known. Not environment creation.
- Stage objective: measure whether any existing boundary is outside this user's write set.
- Permitted operations: only what that future prompt allows. Read-only inspection that does not create a guest.
- Prohibited operations: Docker against the running bot, downloads, network, production edits, and creating the environment inside the evidence stage.
- Required evidence: principal, this user's access, mounts, and an export path that is not a raced `CreateFileW`.
- Approval required: a new prompt. G.14.9 does not grant it.
- Later approval boundaries: implementation design, environment creation, synthetic validation, metadata access, wheel downloads, lock verification, export, candidate packaging, candidate build, isolated runtime, and production readiness are each a separate approval. None carries forward. None authorises live trading.

## 14. REMAINING PRODUCTION BLOCKERS

- Filesystem trust boundary: `FILESYSTEM_TRUST_BOUNDARY_UNVERIFIED`.
- Real HTTPS sender: absent.
- Package-source approval: required.
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

## 15. VALIDATION

- Exact commands: `git rev-parse HEAD`, `git branch --show-current`, `git status --porcelain`, and one read-only Python process with `PYTHONDONTWRITEBYTECODE=1` that hashed the authorised baseline files and called `verify_directory`.
- Static checks: `open_directory`, `_validate_destination`, `assert_destination_boundary`, the G.14.1 verifier, and the G.14.8 report and race file.
- Dynamic tests executed: none. G.14.8's 225 passed, 0 failed, and 3 skipped results were not re-run and are not a new G.14.9 test result.
- Source files modified: none.
- Test files modified: none.
- Existing artifacts modified: none.
- Unexpected files: none. No `__pycache__` entry for the verifier was created.
- Limitations: no security API, junction, symlink, ACL, Docker, WSL, or hypervisor operation was performed. Ruff and Mypy were not run, so this stage claims no new lint result.

## 16. FILES CHANGED

- Production Python: none.
- Dockerfile: none.
- .dockerignore: none.
- requirements.txt: none.
- Compose: none.
- Research helpers: none.
- Test files: none.
- G.14.9 artifacts: `data/research/adaptive_ensemble/g14_9/`.
- Staging directory: unchanged.
- Running production: unchanged.

No Git commit was created. No acquisition directory was created.

## 17. FINAL CLASSIFICATION

`G14_9_ARCHITECTURE_REVIEW_COMPLETE_NO_OPTION_READY`

The review is complete. Baseline and staging matched. The three options were compared under one threat model. No option prevents the demonstrated same-user substitution with evidence, so none is ready to implement. This classification does not approve Gate B.

## 18. NEXT ACTION

The architecture review is complete. A preferred architecture was not identified. No architecture from this stage is implemented. The filesystem trust boundary is not verified. No environment creation is authorised. No network operation is authorised. No dependency download is authorised. No Docker operation is authorised. Gate B remains blocked. Production deployment remains NO-GO.

GATE B APPROVAL: NOT GRANTED.
NETWORK APPROVAL: NOT GRANTED.
DEPENDENCY DOWNLOAD APPROVAL: NOT GRANTED.
DOCKER APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
