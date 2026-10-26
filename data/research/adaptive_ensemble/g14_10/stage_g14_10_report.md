# STAGE G.14.10 — OFFLINE ISOLATION BOUNDARY EVIDENCE AND FEASIBILITY REVIEW REPORT

## 1. LIVE SAFETY

- Running container changed: no. The G.14.2 identity was not refreshed.
- Docker commands executed: none.
- Docker images built: none.
- Docker images pulled: none.
- WSL commands executed: none. `wsl.exe` was not started. Its file presence was checked only.
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
- Initial working-tree status: dirty from earlier stages. 41 porcelain entries, including untracked G.14.9 artifacts. Those changes were not reset, cleaned, stashed, or committed.
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

## 4. G.14.9 FINDINGS

- Prior classification: `G14_9_ARCHITECTURE_REVIEW_COMPLETE_NO_OPTION_READY`.
- Prior architecture decision: `NO_OPTION_READY_FOR_IMPLEMENTATION`.
- Initial path race: still the demonstrated pre-open substitution. Not re-run.
- Trusted launcher: not a trust anchor. The race moves with `CreateFileW`.
- Isolated environment: none selected and none created.
- Constrained trust model: rejected because it trusts the demonstrated same-user attacker.
- Export/import boundary: a host path open repeats the race.
- Remaining critical blocker: `FILESYSTEM_TRUST_BOUNDARY_UNVERIFIED`.

## 5. WINDOWS HOST EVIDENCE

- Windows version: ProductName `Windows 10 Pro`. DisplayVersion `25H2`. CurrentBuild `26200`.
- Windows edition: EditionID `Professional`. InstallationType `Client`.
- Windows build: CurrentBuild `26200`. BuildLabEx `26100.1.amd64fre.ge_release.240331-1435`. Both were read. They were not reconciled. UBR is unknown.
- Windows architecture: AMD64.
- Current process elevation: not elevated.
- Current process integrity: Medium Mandatory Level, `S-1-16-8192`.
- Relevant privileges: the ten named high-impact privileges were absent from this token. Other privileges were not stored. Whether the account can elevate through UAC is unknown.
- Virtualization support: firmware virtualization enabled, observed. `HypervisorPresent` true. The hypervisor product was not named.
- Virtualization features enabled: `vmms` running and automatic. `vmcompute` and `hvhost` running. `WslService` running and automatic. `LxssManager` not present. This is service status, not a guest policy. WMI reported SLAT and VM monitor extensions false. Those raw values are not a block and not a capability proof.
- Evidence level: level 2 for this host metadata. It does not establish a security boundary.
- Unknown values: UBR, hypervisor product name, VM inventory, WSL distributions, WSL version, automount, Docker socket ACL, account elevation ability.

## 6. VM FEASIBILITY

- Existing hypervisor evidence: `vmms` is running. `HypervisorPresent` is true. No VM was listed.
- Guest filesystem isolation: unknown.
- Host filesystem exposure: unknown. Shared folders were not read.
- Network control: unknown. No switch was read.
- Credential isolation: unknown.
- Artifact export: no method identified.
- Host import: would repeat `CreateFileW` on a user-writable path unless a different receiver exists. None does.
- Target compatibility: host is AMD64. Linux runtime details were not read.
- Privilege requirements: this process is not elevated. Creation rights are unknown.
- Missing evidence: inventory, switches, shares, guest tools, disk ACLs, clipboard, snapshots.
- Classification: `VM_FEASIBILITY_PLAUSIBLE_UNVERIFIED`.

## 7. WSL FEASIBILITY

- Existing WSL evidence: `WslService` running. `wsl.exe` exists and was not executed.
- WSL version: unknown. The G.14.2 kernel string contained `WSL2` for the Docker engine. That was not refreshed and is not a distribution setting.
- Distribution availability: unknown. Distributions were not listed.
- Host filesystem automount: unknown. Config files were not read.
- Windows interoperability: unknown.
- Network behavior: unknown.
- Credential exposure: unknown.
- Artifact export: no method identified.
- Host import: unverified.
- Target compatibility: theoretical only if a Linux distribution were later inspected.
- Missing evidence: version, distro list, automount, storage path, interop, DNS.
- Classification: `WSL_FEASIBILITY_PLAUSIBLE_UNVERIFIED`.

## 8. CONTAINER FEASIBILITY

- Historical Docker evidence: Desktop `4.57.0`, Engine `29.1.3`, API `1.52`, linux/amd64, kernel `6.6.87.2-microsoft-standard-WSL2`. Not refreshed.
- Shared daemon risk: historical. The production container was running on the daemon that answered `docker version`. Current daemon context remains unverified.
- Host mounts: not read.
- Docker socket: not opened.
- Network control: unknown.
- Credential isolation: unknown. G.14.2 did not collect environment values.
- Production isolation: not demonstrated.
- Artifact export: unknown.
- Host import: unverified.
- Target compatibility: historical image id is not a registry digest.
- Missing evidence: current socket ACL, mounts, rootless mode, network deny, separation from the production container.
- Classification: `CONTAINER_FEASIBILITY_PLAUSIBLE_UNVERIFIED`.

## 9. WINDOWS EXECUTION FEASIBILITY

- Restricted token: not created. No evidence it stops the same user.
- Low-integrity process: not created. This token is medium. No evidence low integrity stops a medium same-user writer.
- AppContainer: not created. Unknown.
- Separate user: not created. Would need a later approval. This token is not elevated.
- Protected directory: not created.
- ACL controls: same-user owner control remains the G.14.8 finding. DACL bytes were not read.
- Same-user substitution: demonstrated in G.14.8. Not fixed.
- Artifact export: no separate boundary.
- Host import: unverified.
- Required privileges: a different principal needs rights this token does not show. Account elevation was not tested.
- Missing evidence: any tested protected process.
- Classification: `WINDOWS_BOUNDARY_FEASIBILITY_PLAUSIBLE_UNVERIFIED`.

## 10. SECURITY COMPARISON

- Threats evaluated: 25, from same-user substitution through unverified rollback.
- Evidence levels: level 1 for the path race and junctions. Level 2 for this host token and services. Level 3 for the helper and the denylist. Level 4 for Docker and G.14.9. No level 6 claim was used as a finding.
- VM result: service present, isolation unknown.
- WSL result: service present, mounts unknown.
- Container result: historical engine only, production daemon overlap not cleared.
- Windows execution result: normal user token, substitution still the level 1 result.
- Candidate identified: no.
- Critical unknowns: who controls each possible anchor, whether this user can replace its disk or export path, and every guest mount and network setting.

## 11. ARTIFACT EXPORT/IMPORT

- Acquisition-side verification: handle-read checks exist in the helper and were not run in a new guest.
- Export mechanism: none that avoids a host path open.
- Receiving trust anchor: none.
- Host path substitution: still the G.14.8 result.
- Reparse-point handling: junction tested earlier. Symlink not executed. Other tags not enumerated.
- Independent host verification: a hash of bytes actually read is possible. It does not prove directory intent.
- Atomic publication: not available against this user.
- Remaining blockers: `ARTIFACT_IMPORT_TRUST_BOUNDARY_UNVERIFIED`.

## 12. PRODUCTION ISOLATION

- Production mounts excluded: required, not demonstrated.
- Operational-state mounts excluded: not accessed, not demonstrated as an OS policy.
- Shadow-state mounts excluded: same.
- Broker credentials excluded: not read. Not shown to be unreachable from a guest.
- Database credentials excluded: same.
- Docker socket excluded: not opened. Not shown to be unreachable.
- Repository-wide mount excluded: required. The code denylist is not a guest mount policy.
- OANDA access excluded: no request was made. No guest firewall was observed.
- Production interaction risk: a second container on the historical daemon is not known to be harmless.
- Classification: `PRODUCTION_ISOLATION_UNVERIFIED`.

## 13. TARGET COMPATIBILITY

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
- Classification: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`.

## 14. FUTURE NETWORK POLICY

- Proposed index: `https://pypi.org/simple`. Not approved.
- Proposed artifact host: `files.pythonhosted.org`. Not approved.
- HTTPS policy: required later. Not implemented.
- Redirect policy: fail closed off-host. Not implemented.
- DNS policy: no lookup was made.
- Proxy policy: no implicit proxy accepted.
- Credential policy: no credentials on acquisition requests.
- Timeout policy: bounds belong to a future sender approval.
- Size policy: bounds belong to that same approval.
- Source-build prohibition: no source distributions, hooks, or install during acquisition.
- Network approval: not granted.

## 15. FEASIBILITY DECISION

- Candidate architecture: none.
- Supporting evidence: services are running and a path-substitution result exists. Neither selects a guest.
- Evidence gaps: mounts, principals, export paths, current Docker context, WSL version, VM inventory.
- Trust-anchor status: `NO_ISOLATION_BOUNDARY_CURRENTLY_VERIFIED`.
- Same-user resistance: not shown for any category.
- Export/import status: unverified.
- Future validation required: a new prompt before any Docker, WSL, or VM command.
- Implementation approved: no.

## 16. FUTURE APPROVAL PLAN

- Next recommended stage: do not create an environment. A later stage may design a boundary only after new evidence identifies one. This review did not produce that evidence.
- Stage objective: if pursued, identify a principal and an import path this user cannot replace, under a new approval.
- Allowed operations: only what that approval names.
- Prohibited operations: Docker, WSL, and VM commands remain prohibited until a prompt allows a specific one. The running container stays out of scope.
- Required evidence: principal, mount list, and a substitution attempt that fails.
- Required approval: separate from G.14.10.
- Later approval boundaries: creation, synthetic acquisition, metadata, downloads, lock verification, export, packaging, candidate build, runtime, and production review are each separate. None carries forward. None authorises live trading.

## 17. REMAINING BLOCKERS

- Filesystem trust boundary: unverified.
- Artifact-import trust boundary: unverified.
- Isolation boundary: none verified.
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

- Exact commands: Git metadata, read-only hashing and `verify_directory`, registry version fields, filtered `whoami`, two CIM properties, `Get-Service` for the named Hyper-V and WSL services, and `Test-Path` for five executables.
- Read-only checks: those commands query status or file presence. They do not start services.
- Dynamic isolation tests executed: none.
- Docker commands: none.
- WSL commands: none.
- VM commands: none.
- Network requests: none.
- Source files modified: none.
- Test files modified: none.
- Existing artifacts modified: none.
- Unexpected files: none.
- Limitations: races and Docker were not remeasured. No distribution or VM inventory. SLAT's raw WMI false is not a conclusion. VirtualBox and VMware were checked only at default paths.

## 19. FILES CHANGED

- Production Python: none.
- Dockerfile: none.
- .dockerignore: none.
- requirements.txt: none.
- Compose: none.
- Research helpers: none.
- Test files: none.
- G.14.10 artifacts: `data/research/adaptive_ensemble/g14_10/`.
- Staging directory: unchanged.
- Running production: unchanged.

No Git commit was created. No environment was created.

## 20. FINAL CLASSIFICATION

`G14_10_FEASIBILITY_REVIEW_COMPLETE_NO_BOUNDARY_VERIFIED`

The review is complete. All four categories were evaluated. Hyper-V and WSL services are running, and Docker was observed historically. None of that is a verified isolation boundary, a trust anchor, or a safe import path. No candidate is selected. This classification does not approve Gate B or environment creation.

## 21. NEXT ACTION

The feasibility review is complete. A candidate architecture was not identified. No isolation boundary was verified. No environment creation is authorised. No Docker operation is authorised. No WSL operation is authorised. No VM operation is authorised. No network operation is authorised. No dependency download is authorised. Gate B remains blocked. Production deployment remains NO-GO.

GATE B APPROVAL: NOT GRANTED.
NETWORK APPROVAL: NOT GRANTED.
DEPENDENCY DOWNLOAD APPROVAL: NOT GRANTED.
DOCKER APPROVAL: NOT GRANTED.
WSL APPROVAL: NOT GRANTED.
VM APPROVAL: NOT GRANTED.
PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
