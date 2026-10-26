# STAGE D.25 — OFFLINE DUAL-ARCHITECTURE RUNTIME EVIDENCE AND DEPENDENCY READINESS PLANNING REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D25_OFFLINE_PLANNING_COMPLETE_GAPS_RECORDED`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H: PASS
- Gate I: PASS
- Production source modified: no
- Network requests: 0
- AMD64 planning completed: yes
- ARM64 planning completed: yes
- Recommended next action: record Option C for a later approval. Dependency metadata verification was not started.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Telegram network requests: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Image-layer downloads: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.25. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files and the D.21 baseline.
- Earlier evidence integrity: D.22 remains `D22_BLOCKED_BASELINE_INTEGRITY`. D.22-R1, D.23, D.24, D.24-R1, and D.24-R2 were unchanged.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE INTEGRITY

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Parent-child descriptor checks: index descriptors, manifest config descriptors, and raw config hashes agree.
- OCI validation verdict: both configs parse, and their architecture, operating system, and variant fields agree with the parent descriptors.

## 5. BASE-IMAGE CONFIGURATION

- AMD64 architecture: amd64
- ARM64 architecture: arm64
- Operating system: linux on both
- Python version declarations: both configs declare `PYTHON_VERSION=3.12.15`. Both manifests annotate `3.12.15-slim-bookworm`.
- Default commands: both configs declare ["python3"].
- Runtime user declarations: neither config declares User.
- Working directory declarations: neither config declares WorkingDir.
- Entrypoint declarations: neither config declares Entrypoint.
- Environment variable names: GPG_KEY, LANG, PATH, PYTHON_SHA256, PYTHON_VERSION. `GPG_KEY` is redacted.
- Rootfs diff-ID counts: 4 on AMD64 and 4 on ARM64.
- History entry counts: 10 on AMD64 and 10 on ARM64.
- Cross-platform differences: architecture, variant, creation timestamp, config digest, manifest digest, and the annotated Debian base digest. Raw config timestamps are AMD64 `2026-10-06T02:04:51.549801942Z` and ARM64 `2026-10-06T02:11:13.014797359Z`, matching the D.24-R2 report.
- Measured runtime properties: none. The Python version string is a declaration.

## 6. DOCKERFILE AND COMPOSE

- Base-image reference: `python:3.12-slim-bookworm` on Dockerfile line 2.
- Digest pinning: absent from the Dockerfile FROM instruction.
- Platform selection: absent from the Dockerfile and from the Compose bot service.
- Dependency installation: unpinned pip upgrade and an unhashed `pip install` of `requirements.txt`.
- Runtime user: no USER instruction and no Compose user.
- Application command: Dockerfile CMD runs uvicorn `forex_bot.app:app` on port 8000. Compose does not override it.
- Health checks: the bot service has none. The db service has one. The profile-gated ollama service has one.
- Restart behaviour: the bot and db services declare none. The ollama service declares `unless-stopped`.
- Persistent mounts: Compose bind-mounts `./data/research/v2_shadow` and `./data/ops`, and the db service uses the named `pgdata` volume.
- Unverified runtime implications: the final image, its user, its interpreter, and its running process were not built or observed.

## 7. DEPENDENCY READINESS

- Production requirement count: 9
- Exact pins: none
- Hash pins: none
- Transitive lock: absent
- Per-platform locks: absent
- Wheelhouse: absent
- Native dependency candidates: numpy, pandas, psycopg2-binary, and uvicorn[standard].
- Python ABI evidence: missing
- libc evidence: missing
- AMD64 wheel evidence: missing
- ARM64 wheel evidence: missing
- Dependency readiness verdict: not ready for reproducible installation on either architecture.

## 8. RUNTIME READINESS MATRIX

- AMD64 entries: 32
- ARM64 entries: 32
- Status totals: {"BLOCKED": 4, "DECLARED_IN_LOCAL_SOURCE": 4, "MISSING": 34, "UNVERIFIED": 4, "VERIFIED_CONFIG_DECLARATION": 6, "VERIFIED_LOCAL_BYTES": 12}
- Verified declarations: config and manifest fields listed as `VERIFIED_LOCAL_BYTES` or `VERIFIED_CONFIG_DECLARATION`.
- Unverified runtime properties: Python implementation and libc family.
- Missing evidence: measured interpreter, ABI, package revisions, wheels, startup, health, VPS identity, signatures, and reproducible build inputs.
- Blocked properties: live-safety behaviour and rollback readiness.
- Cross-platform differences: readiness statuses match. Platform identity, digests, variant, and creation timestamps differ.

## 9. SAFETY READINESS

- Historical source safety repairs: prior source changes remain historical. This stage did not re-test them.
- Historical isolated tests: not rerun.
- Current production runtime safety: UNVERIFIED.
- Trusted deployment receiver: MISSING.
- Production schema compatibility: UNVERIFIED. The database was not accessed.
- Operational-state compatibility: BLOCKED. The operational mount was not read.
- Shadow-state compatibility: BLOCKED. The shadow mount was not read.
- Verified rollback: no verified artifact or procedure.
- Live trading authorisation: NOT AUTHORISED.

## 10. FINDINGS

- D25-BASE-01. Evidence: Dockerfile FROM instruction and docker-compose.yml image instructions. Evidence level: DECLARED_IN_LOCAL_SOURCE. Impact: The verified OCI index is a historical snapshot. Current tag resolution was not rechecked. Required action: A separately approved registry recheck, or an explicit digest pin. Required approval: yes. Production impact: UNVERIFIED.
- D25-CONFIG-01. Evidence: rehashed AMD64 and ARM64 config bytes. Evidence level: VERIFIED_CONFIG_DECLARATION. Impact: These are declarations in the base-image config. They do not measure the interpreter or describe the final bot image. Required action: Final-image metadata or an isolated runtime measurement. Required approval: yes. Production impact: UNVERIFIED.
- D25-ABI-01. Evidence: verified config bytes and local requirement files. Evidence level: MISSING. Impact: A Python 3.12 declaration does not select a wheel tag. Required action: Interpreter ABI measurement or an explicitly labelled assumption in a later stage. Required approval: yes. Production impact: UNVERIFIED.
- D25-LIBC-01. Evidence: verified manifests and configs; layer bytes absent. Evidence level: MISSING. Impact: manylinux compatibility remains unknown for both architectures. Required action: Approved image-layer or package-list inspection. Required approval: yes. Production impact: UNVERIFIED.
- D25-WHEEL-01. Evidence: requirements.txt and the absence of wheel records. Evidence level: MISSING. Impact: Neither linux/amd64 nor linux/arm64/v8 has demonstrated wheel compatibility. Required action: Approved per-platform wheel metadata, hashes, and provenance. Required approval: yes. Production impact: UNVERIFIED.
- D25-LOCK-01. Evidence: requirements.txt, requirements-dev.txt, and Dockerfile RUN instructions. Evidence level: DECLARED_IN_LOCAL_SOURCE. Impact: The dependency install is not reproducible from the current files. Required action: An approved lock and artifact-hash design. Required approval: yes. Production impact: UNVERIFIED.
- D25-PROV-01. Evidence: rehashed OCI objects and local project files. Evidence level: MISSING. Impact: Byte identity against earlier descriptors is not publisher authentication. Required action: Approved signature or attestation verification. Required approval: yes. Production impact: UNVERIFIED.
- D25-VPS-01. Evidence: approved intended-target record; no receiver inventory in this stage. Evidence level: MISSING. Impact: An intended architecture is not a verified production host. Required action: Approved deployment-receiver inventory. Required approval: yes. Production impact: UNVERIFIED.
- D25-RUNTIME-01. Evidence: Dockerfile and docker-compose.yml. Evidence level: MISSING. Impact: Startup and health remain untested on both architectures. Required action: An approved isolated runtime test after image and dependency evidence exists. Required approval: yes. Production impact: UNVERIFIED.
- D25-SAFETY-01. Evidence: historical stage boundary and local source hashes. Evidence level: HISTORICAL_OBSERVATION. Impact: Source-level safety work remains separate from production runtime safety. Required action: A separately authorised production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 11. FUTURE EVIDENCE OPTIONS

- Offline analysis: Option A. Available local evidence was used in this stage. A further offline stage needs a new named gap.
- Controlled layer metadata: Option B. It can inspect base-image filesystem metadata and requires a new host and blob approval.
- Controlled dependency metadata: Option C. It can record per-platform wheel metadata and requires a new package-index approval.
- Candidate build: Option D. It is not justified until base-image and dependency inputs are pinned.
- Isolated runtime testing: Option E. It remains dependent on a candidate image and isolated fixtures.
- Trusted receiver and rollback: Option F. VPS identity and rollback evidence are absent.
- Recommended next stage: Option C.
- Why this stage comes first: it is the least invasive step that can reduce the shared unpinned-dependency blocker without Docker or layer downloads.
- Required explicit approval: a future approval naming the index, platform tags, request limits, and a prohibition on installation.

## 12. VALIDATION

- Commands executed: git rev-parse HEAD, git branch --show-current, git status --short for the ten protected paths, and Python standard-library hashing and JSON parsing.
- Network requests: 0
- Files created: D.25 artifacts under `data/research/adaptive_ensemble/d25/`.
- Files modified: none outside that new directory.
- OCI digest checks: five preserved objects rehashed and matched.
- Protected source hash checks: ten files matched D.21 and the expected digests before and after writing.
- Static checks: OCI schema, Dockerfile instructions, Compose declarations, and requirement lines.
- Prohibited operations: none observed.

## 13. FINAL CLASSIFICATION

`D25_OFFLINE_PLANNING_COMPLETE_GAPS_RECORDED`

## 14. NEXT ACTION

D.25 planning completed. Both architecture matrices completed. Actual interpreter versions were not measured. Python ABI was not measured. libc was not measured. Native wheels were not verified. Dependency resolution did not occur. Image layers were not downloaded. Docker was not executed. A candidate image was not built. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
