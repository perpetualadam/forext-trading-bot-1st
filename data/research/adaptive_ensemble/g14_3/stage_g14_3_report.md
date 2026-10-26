# STAGE G.14.3 — CANDIDATE BUILD SUPPLY-CHAIN LOCKING AND FINAL EXECUTION GATE REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker images pulled: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: BLOCKED (`operator_preflight_blocked`), not read or written
- Active strategies: none of the six were activated
- Production database writes: no
- Operational-state changes: no
- Shadow-mount changes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Initial working-tree status: modified Dockerfile, two scheduler files, three migrated tests, and untracked G.13 through G.14.2 files
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Frozen G.10 verification: archive and canonical manifest digest matched
- Frozen G.7 verification: archive and canonical manifest digest matched
- Unexpected changes: none

## 3. Staging context

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Expected files: 63
- Actual files: 63
- Expected bytes: 617279
- Actual bytes: 617279
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- Independent verification: PASS, using `tests/g14_1_verify.py`
- Unexpected files: none
- Sensitive backups excluded: yes, and their contents were not read
- Staging modified: no

## 4. Dependency inventory

- Number of direct requirements: 9
- Exact pins: 0
- Version ranges: 9 minimum bounds with no upper bound (`>=`)
- Missing hashes: 9
- Unknown transitive dependencies: all of them, including the packages selected by `uvicorn[standard]`
- Native-extension risks: pandas, numpy, and psycopg2-binary. Transitive native risk is `UNKNOWN`.
- Source-distribution risks: `--prefer-binary` still allows a source build
- Build-time hook risks: any `pip install` may run installation hooks; source fallback increases that risk
- Inventory complete: the direct lines are complete. The transitive graph is not.

## 5. Dependency locking design

- Recommended approach: resolve on CPython 3.12 linux/amd64, freeze the full graph with SHA-256 hashes, store a verified wheelhouse, then install it offline from a candidate-specific Dockerfile
- Full transitive lock available: no
- Exact versions available: no
- Verified hashes available: no
- Verified wheelhouse available: no
- Required future changes: candidate lock, wheelhouse, and candidate Dockerfile. No production packaging edit.
- Required future approvals: download, verification, and candidate-file creation, each separate from a build
- Reproducibility status: not achieved

## 6. Pip toolchain

- Current upgrade behavior: `pip install --upgrade pip` with no exact version
- Known pip version: `UNKNOWN`
- Recommended change: drop the unpinned upgrade from a future candidate Dockerfile, or install one reviewed pip wheel after its hash exists
- Reproducibility risk: pip and the resolver can change between builds
- Classification: `PIP_TOOLCHAIN_VERSION_UNVERIFIED`

## 7. Base image

- Requested tag: `python:3.12-slim-bookworm`
- Recorded local image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`
- Registry manifest digest known: no. The recorded RepoDigests value repeats that image ID and has no registry hostname.
- Immutable FROM reference available: no
- Future identity-verification plan: compare a built image's base layer with a later-verified digest, or with this image ID after a fresh inspect. History alone is not enough.
- Classification: `BASE_IMAGE_DIGEST_UNVERIFIED`

## 8. Network and wheelhouse

- Existing build requires network: yes
- Offline wheelhouse exists: no
- Proposed acquisition method: a later download of the resolved wheels from the approved index, without installing them
- Hash-verification design: an independent directory listing and SHA-256 check, rejecting extra files, missing hashes, and source distributions by default
- Source-distribution policy: reject unless a later approval names a specific file
- Package-installation-hook policy: acquisition must not install. A later build must still disclose hooks if it installs.
- Network-isolated final build feasible now: no
- Network-isolated final build feasible after proposed work: only after the lock and wheelhouse exist. It is not feasible now.

## 9. Build cache

- Current policy: the earlier command leaves the default cache enabled
- Proposed policy: `--no-cache` only for a later locked offline build. Do not clear the existing cache.
- Cache reuse risks: an old unpinned `pip install` layer can hide the resolution
- Additional requirements: `--no-cache` does not pin versions. `BUILDKIT_PROVENANCE_UNVERIFIED`.

## 10. Previous build command

- Exact previous command: `docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"`
- Context safe: yes, the verified staging directory
- Base identity controlled: no
- Dependency versions controlled: no
- Network exposure: pip upgrade and unpinned install
- Cache exposure: default cache
- Candidate-tag collision handling: the tag was free at G.14.2 and is not reserved
- Recommendation: `REPLACE_WITH_LOCKED_OFFLINE_BUILD_PROPOSAL`

## 11. Candidate image verification

- Image metadata plan: inspect the candidate tag only, without environment values
- Layer verification plan: a new export outside OneDrive, not the deleted G.12 archive
- Application inventory plan: 61 application files, reject anything else
- Dependency verification plan: compare image metadata with a future lock. History does not prove versions.
- Secret exclusion plan: reject credentials, operational state, research files, and both backup filenames
- Runtime execution required: no
- Future image export approval required: yes

## 12. Approval matrix

- Read-only metadata research: not granted
- Dependency downloads: not granted
- Artifact verification: not granted
- Candidate packaging modifications: not granted
- Docker build: not granted
- Image export: not granted
- Isolated runtime test: not granted
- Production deployment: not granted

## 13. Remaining blockers

- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`
- Docker daemon context behavior: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- Candidate runtime validation: unverified
- Production deployment readiness: NO-GO
- Rollback readiness: NO-GO

## 14. Tests

- Exact commands: recorded in `data/research/adaptive_ensemble/g14_3/test_results.json`
- Tests passed: 76
- Tests failed: 0
- Tests skipped: 0
- Ruff: pass
- Mypy: pass
- Untested behavior: index resolution, wheel hashes, the registry digest, the base-image pip version, and any Docker action. `test_g10_snapshot.py` was not run because it can rewrite G.5 and G.6 files. Those frozen archives were hashed directly.

## 15. Files changed

- Production Python: unchanged
- Dockerfile: unchanged
- .dockerignore: unchanged
- requirements.txt: unchanged
- Compose: unchanged
- New tests: `tests/g14_3_supply.py`, `tests/test_g14_3_supply.py`
- G.14.3 artifacts: `data/research/adaptive_ensemble/g14_3/`
- Staging directory: unchanged
- Running production: unchanged

## 16. Final classification

`SUPPLY_CHAIN_LOCKING_DESIGN_COMPLETE_APPROVAL_REQUIRED`

This does not mean dependencies are locked, a wheelhouse exists, or a reproducible image can be built. Build approval is not granted.

## 17. Next approval request

Additional evidence required:

- A registry manifest digest for `python:3.12-slim-bookworm`, or an explicit decision to bind only to the historical local image ID. An immutable `FROM` reference cannot be established from the current evidence.
- Exact versions and the transitive graph for CPython 3.12 on linux/amd64.
- Wheel filenames and SHA-256 hashes. All of those values are `UNKNOWN`.
- The pip version inside the base image, if the unpinned upgrade is to be removed rather than replaced.

Dependency acquisition is necessary before a locked build can be specified. Read-only index metadata is not enough to verify artifact bytes.

A candidate-specific Dockerfile is necessary if the production file keeps the unpinned pip upgrade. It must not be written until the hashes exist, and it is not a substitute for the verified production Dockerfile.

A locked offline build is not currently feasible.

Future actions that still require their own approval, and which were not performed:

1. Download the resolved wheels.
2. Verify those downloads with an independent hash check.
3. Add the candidate lock, wheelhouse manifest, and candidate Dockerfile.
4. Build, export, run, or deploy. Those remain separate and are not requested.

Build approval: not granted. Production deployment: NO-GO. Rollback: NO-GO.
