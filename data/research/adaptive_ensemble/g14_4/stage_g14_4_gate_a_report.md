# STAGE G.14.4 — CONTROLLED DEPENDENCY RESOLUTION AND VERIFIED WHEELHOUSE ACQUISITION — GATE A REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker images pulled: no
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
- Initial working-tree status: modified Dockerfile, two scheduler files, three migrated tests, and untracked G.13 through G.14.3 files
- Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore SHA-256: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 allowlist SHA-256: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- Frozen G.10 verification: archive and canonical manifest digest matched
- Frozen G.7 verification: archive and canonical manifest digest matched
- Unexpected changes: none. `test_g10_snapshot.py` was not run.

## 3. Staging context

- Staging directory: `C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`
- Expected files: 63
- Actual files: 63
- Expected bytes: 617279
- Actual bytes: 617279
- Manifest digest: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`
- Independent verification: PASS
- Unexpected files: none
- Sensitive backups excluded: yes, and they were not opened
- Staging modified: no

## 4. Target environment

- Operating system: linux
- Architecture: x86_64
- Python implementation: CPython
- Python major/minor: 3.12
- Python patch version: `UNKNOWN`
- Base-image identity: historical local ID `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. Not a registry digest. Not rechecked.
- Wheel compatibility assumptions: pure-Python `py3-none-any` wheels may fit; native wheels need a linux/x86_64 tag. The exact manylinux tag is not established.
- Unknown target details: Python patch, SOABI, glibc, pip version, and the selected packages inside `uvicorn[standard]`
- Target specification complete: the major target is documented. The ABI and glibc details are not, and `--platform` alone does not close that gap.

## 5. Direct dependencies

- Direct requirements: 9, reconciled with `requirements.txt` and the G.14.3 count
- Exactly pinned: 0
- Minimum-version ranges: 9, none with an upper bound
- Missing hashes: 9
- Extras: `uvicorn[standard]` only
- Native-extension risks: pandas, numpy, psycopg2-binary
- Unknown transitive dependencies: the full graph, including that extra
- Inventory reconciled: yes

## 6. Package source

- Proposed index: `https://pypi.org/simple`
- Explicitly approved: no
- Authentication required: no for that public index. No credential was read.
- Additional indexes: prohibited
- Redirect policy: reject any host that is not later named
- Direct URL policy: prohibited
- VCS policy: prohibited
- Source-distribution policy: prohibited
- Classification: `PACKAGE_SOURCE_APPROVAL_REQUIRED`

## 7. Wheels-only resolution

- Proposed resolver: a later target-aware wheel resolver, not the Windows host environment
- Target-platform handling: linux/x86_64 only
- Target-marker handling: evaluate markers for linux CPython 3.12
- Wheel-tag verification: reject tags outside that set
- Source-distribution rejection: yes, stop with `COMPATIBLE_WHEEL_UNAVAILABLE`
- Transitive-graph verification: required, and currently `UNKNOWN`
- Failure conditions: second index, direct URL, VCS, yanked release, conflicting versions, missing artifact, bad hash
- Procedure executable now: no
- Additional approvals required: source approval, then metadata, download, and verification as separate rows

## 8. Lockfile and verification

- Lock schema: `g14_4_lock_schema_v1`
- Canonical serialization: UTF-8 JSON, sorted keys, packages ordered by normalized name
- Hash requirements: 64 lowercase hex characters, plus file size
- Provenance requirements: recorded separately from the hash
- Independent verifier: `tests/g14_4_verify.py`
- Synthetic tests passed: the valid fixture, with provenance left unapproved
- Synthetic tests failed closed: 30 negative cases, including symlink and reparse
- Real wheel artifacts acquired: no
- Real dependency lock created: no

## 9. Wheelhouse location

- Proposed location: a new directory under the user temporary parent, named `forext-g14-4-wheelhouse-` plus a Gate B suffix
- Outside OneDrive: yes, when that parent is the local Temp directory
- Created: no
- Existing staging modified: no
- Cleanup policy: retain until a later approval names the exact directory

## 10. Base image and pip

- Requested base: `python:3.12-slim-bookworm`
- Recorded local image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`
- Registry manifest digest: `UNKNOWN`
- Base pip version: `UNKNOWN`
- Future verification: inspect patch, SOABI, glibc, and pip without starting the application
- Remaining classifications: `BASE_IMAGE_DIGEST_UNVERIFIED`, `PIP_TOOLCHAIN_VERSION_UNVERIFIED`

## 11. Network and execution boundary

- Network calls made: no
- Dependencies downloaded: no
- Packages installed: no
- Package code executed: no
- Docker commands executed: no
- Gate B permissions granted: no

## 12. Candidate packaging

- Current 63-file context preserved: yes
- New candidate context required: yes, before a locked build
- New allowlist required: yes
- Candidate Dockerfile required: yes, and it is not a substitute for the production Dockerfile
- Production Dockerfile changed: no
- Production requirements changed: no
- Build approved: no

## 13. Approval matrix

- Package metadata requests: not granted
- Wheel-only resolution: not granted
- Wheel downloads: not granted
- Artifact hashing: not granted
- Wheel metadata parsing: not granted
- Lockfile generation: not granted
- Independent verification: not granted
- Candidate packaging: not granted
- Docker build: not granted
- Image export: not granted
- Runtime test: not granted
- Production deployment: not granted
- Rollback: not granted

## 14. Remaining blockers

- Dependency lock: absent
- Verified wheelhouse: absent
- Package source approval: `PACKAGE_SOURCE_APPROVAL_REQUIRED`
- Base-image registry digest: `BASE_IMAGE_DIGEST_UNVERIFIED`
- Pip toolchain version: `PIP_TOOLCHAIN_VERSION_UNVERIFIED`
- Docker daemon context behavior: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`
- Safety-state compatibility: `SAFETY_STATE_FORWARD_COMPATIBILITY_UNVERIFIED`
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED`
- Verified rollback target: `NO_VERIFIED_ROLLBACK_TARGET`
- Production deployment readiness: NO-GO

## 15. Tests

- Exact commands: recorded in `data/research/adaptive_ensemble/g14_4/test_results.json`
- Tests passed: 86
- Tests failed: 0
- Tests skipped: 0
- Ruff: pass
- Mypy: pass
- Synthetic fixtures: pytest temporary files only; none kept
- Unexpected file changes: none in protected evidence
- Untested behavior: real index resolution, real wheel hashes, image glibc, and the base-image pip version

## 16. Files changed

- Production Python: unchanged
- Dockerfile: unchanged
- .dockerignore: unchanged
- requirements.txt: unchanged
- Compose: unchanged
- New tests: `tests/g14_4_verify.py`, `tests/g14_4_acquire.py`, `tests/g14_4_inventory.py`, `tests/test_g14_4_wheelhouse.py`
- G.14.4 artifacts: `data/research/adaptive_ensemble/g14_4/`
- Staging directory: unchanged
- Running production: unchanged

## 17. Final classification

`G14_4_GATE_A_COMPLETE_GATE_B_APPROVAL_REQUIRED`

The acquisition process is prepared for review. It has not been executed. Gate B is not authorised.

## 18. Next approval request

Gate B is not approved. If it is considered later, the operator would still have to approve the source first.

- Source that would be contacted: `https://pypi.org/simple`, only after that proposal is explicitly approved. It is not approved now.
- Metadata that would be requested: version and wheel-tag metadata for the nine direct requirements and their transitive graph on CPython 3.12, linux/x86_64. The file list is `UNKNOWN` until resolution.
- Packages that could be downloaded: only `.whl` files selected by that resolution. No names are known yet. Source distributions would stop the run.
- Target platform: linux, x86_64, CPython 3.12. Patch, ABI, and glibc remain `UNKNOWN` and must be checked before a lock is accepted.
- Where files would be written: a new empty directory under the local Temp parent, prefixed `forext-g14-4-wheelhouse-`. It was not created.
- Commands or APIs: the pip download template in `proposed_acquisition_commands.md`, only after every `UNRESOLVED` placeholder is replaced from evidence. It was not run.
- Whether downloaded code would execute: no. Download does not include install, setup scripts, hooks, or the application.
- Immediate stops: unapproved index, redirect, second index, direct URL, VCS, yanked release, source distribution, incompatible tag, nonempty destination, hash or size mismatch, conflicting versions, or a completion claim without artifacts.
- Outputs retained: the wheelhouse and lock, outside the repository and outside the 63-file context, until a separate cleanup approval.
- Still prohibited: package installation, Docker, image build or pull, application startup, broker access, database access, production packaging edits, deployment, and rollback.

Gate B approval: not granted. Docker build approval: not granted. Production deployment: NO-GO. Rollback: NO-GO.
