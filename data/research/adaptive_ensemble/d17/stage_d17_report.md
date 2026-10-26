# STAGE D.17 — DEPENDENCY LOCKING STRATEGY AND REPRODUCIBILITY PREPARATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D17_PREPARATION_COMPLETE_TARGET_GAPS_REMAIN`
- Gate A: PASS. Protected hashes matched. The working tree was already dirty. No D.17 files existed at the start.
- Gate B: PASS. Nine production requirements and two development-only requirements were classified. Image copy-set imports map to declared packages.
- Gate C: PASS as classification. Python patch, architecture, libc version, wheel tags, and the base-image digest are MISSING.
- Gate D: PASS as a schema. No lock was produced.
- Gate E: PASS as a contract. No wheelhouse was created.
- Gate F: PASS as an unapproved plan. No resolution or download was authorised.
- Gate G: PASS. Thirty domains were classified. Overall readiness is MISSING.
- Critical findings: D17-DEPS-01, D17-DEPS-02, D17-TARGET-01, D17-WHEEL-01, D17-LOCK-01, D17-PROV-01, D17-SEC-01.
- Readiness domains verified: 1
- Readiness domains partial: 10
- Readiness domains missing: 19
- Readiness domains unverified: 0
- Production source modified: no
- Recommended next stage: a separately approved target-profile verification. It is not started here.

This classification means the locking strategy is written and the target cannot yet be specified tightly enough to resolve dependencies. It does not mean a lock exists.

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
- Network requests: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production state was not verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected source hashes: matched the expected values for `app.py`, `telegram_control.py`, `database.py`, `live_safety.py`, and `strategy_meta.py`.
- Requirements hashes: matched for `requirements.txt` and `requirements-dev.txt`.
- Dockerfile hash: matched `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`.
- .dockerignore hash: matched.
- Compose hash: matched.
- Unexpected changes: none caused by this stage. Existing dirty files were preserved.

## 4. DEPENDENCY INVENTORY

- Production requirements: 9, all lower bounds, no extras except `uvicorn[standard]`, no markers, no direct URLs.
- Development requirements: `-r requirements.txt`, `packaging>=22.0`, and `pytest>=8.3.5,<9`.
- Exact pins: 0
- Lower-bound-only requirements: 11, counting `packaging` with the nine production lines.
- Conditional requirements: 0
- Native dependency candidates: numpy, pandas, psycopg2-binary. The `standard` extra on uvicorn may pull native packages. That set is unverified.
- Potentially undeclared imports: none in the 60-file image copy set.
- Unused declarations: `tzdata` is declared and not imported by name. `packaging` was not seen in the top-level test scan. Neither was removed.
- Dynamic imports: none in the image copy set.
- Coverage limitations: the standard-library split used the host Python 3.13 name list. The research tree was not fully walked. Installed metadata was not queried.

## 5. TARGET ENVIRONMENT

- Declared Python: 3.12, from `python:3.12-slim-bookworm`.
- Exact Python patch: MISSING
- Target OS: Linux, inferred from the image name.
- Linux distribution: Debian bookworm, inferred from the tag. The image revision is MISSING.
- Architecture: MISSING. It was not assumed.
- ABI: MISSING
- libc: glibc is inferred from a Debian tag. The version is MISSING.
- Base-image digest: MISSING
- Wheel tags: MISSING
- Native library requirements: MISSING
- Host-target mismatch: the D.16 host audit interpreter was Python 3.13.5. The container tag is Python 3.12. A host lock is not acceptable.
- Remaining unknowns: patch, architecture, libc version, digest, index policy, resolver version.

## 6. LOCKING STRATEGY

- Candidate approaches: pip-tools hash output, uv compile or uv lock, Poetry, and name-only pins.
- Recommended approach: one hash-pinned production requirements lock for a later-verified Python 3.12 Linux target, installed later with hash checking and no index.
- Selection rationale: the image has no compiler, so the first milestone is wheel-only. Poetry would require a project file that is not present. Pins without hashes do not meet the integrity bar. The resolver must not run on the host interpreter.
- Resolver version: MISSING
- Lockfile format: proposed schema only. Not resolved and not installable.
- Transitive closure: required and not produced.
- Artifact hashes: required and not produced.
- Environment markers: none are declared today. Future evaluation is still required for the target.
- Multi-platform handling: one verified platform only. A second architecture needs its own artifact set.
- Repeated resolution: defined and not run.
- Remaining verification: tool version, target flags, and a repeated run against one index snapshot.

## 7. ARTIFACT PROVENANCE

- Required identity fields: distribution, version, filename, type, origin, size, tags, and Requires-Python.
- Required hashes: SHA-256 of each artifact and of the lock.
- Required origins: approved index or other approved acquisition path.
- Required compatibility metadata: Python, ABI, and platform tags.
- Required resolver metadata: name, version, input manifest hash, and timestamp.
- Trusted storage: separate from the production tree.
- Independent verification: hash check before any install.
- Missing evidence: no artifact exists. Placeholders remain MISSING, NOT_ACQUIRED, and UNVERIFIED.

## 8. OFFLINE WHEELHOUSE

- Target artifact set: the future lock closure. Empty today.
- Wheel-only policy: planning preference for the first milestone.
- Source distribution policy: rejected unless a later approval records a toolchain.
- Completeness criteria: version, compatible artifact, hash, filename, origin, manifest membership, marker evaluation, and transitive closure.
- Integrity checks: hash the manifest and every file. Quarantine mismatches.
- Offline installation contract: disposable environment, no network, no extra resolution, no production writes.
- Repeatability checks: resolution repeat, hash compare, then a separate offline install.
- Remaining blockers: target profile, resolver version, and the absence of any artifact.

## 9. DEPENDENCY SECURITY

- Origin risks: an unpinned install can select a different index artifact later.
- Substitution risks: a lower bound accepts any newer release.
- Hash enforcement: absent in the Dockerfile.
- Native binary risks: numpy, pandas, and psycopg2-binary ship platform binaries whose provenance is unknown.
- Build-script risks: a source build would execute upstream build code. That path is not selected.
- Vulnerability review: not performed.
- Supply-chain limitations: no signatures, no attestations, and no yanked-release check.
- Required future controls: pinned resolver, approved index, exact lock, hash checks, and a separate vulnerability review after versions exist.

## 10. FUTURE APPROVAL PLAN

- Target verification stage: establish architecture, Python patch, digest, libc, and accepted wheel tags. Not approved now.
- Dependency resolution stage: hashed manifest in, lock and provenance template out. Not approved now.
- Artifact acquisition stage: download only names and hashes from the reviewed lock. Not approved now.
- Offline installation stage: disposable environment only, after the wheelhouse is complete. Not approved now.
- Prerequisites: the sequence in `approval_dependency_graph.json`.
- Permitted future scope: one target, one resolver version, one index allow-list, wheels only.
- Prohibited future scope: broker, Telegram, production database, production state, Docker build, source edits, deployment, and live trading.
- Stop conditions: missing target fact, missing compatible wheel, hash mismatch, or any extra package.
- Required explicit approvals: each arrow in the sequence. A finished dependency stage does not authorise an image build.

## 11. READINESS MATRIX

- Total domains: 30
- VERIFIED: 1 (R01)
- PARTIAL: 10 (R02, R03, R04, R06, R09, R11, R13, R20, R26, R27)
- MISSING: 19
- UNVERIFIED: 0
- BLOCKED_BY_SCOPE: 0 as a domain classification. R23's evidence level records that vulnerability scanning was out of scope.
- NOT_APPLICABLE: 0
- Overall dependency readiness: MISSING

## 12. FINDING REGISTER

- D17-DEPS-01. `requirements.txt` lines 1–9. Nine lower bounds and no exact pin. Current local file. Reproducibility and security impact: a later install can change every package. Future action: resolve only after the target profile exists. Approval required. Network would be required later. Production impact: UNVERIFIED.
- D17-DEPS-02. Dockerfile lines 13–14. pip is upgraded and requirements are installed without hashes. Current local file. Same impact as D17-DEPS-01. Future action: hash-checked offline install. Production impact: UNVERIFIED.
- D17-TARGET-01. Dockerfile line 2. The tag does not fix patch, architecture, libc version, or digest. Future action: target verification. Production impact: UNVERIFIED.
- D17-WHEEL-01. numpy, pandas, and psycopg2-binary have no local wheels and no verified tags. Future action: select artifacts only after the target tags exist. Production impact: UNVERIFIED.
- D17-LOCK-01. No lockfile. A host Python 3.13 lock is not the target. Future action: target-environment resolution. Production impact: UNVERIFIED.
- D17-PROV-01. No artifacts, so provenance is empty. Future action: record provenance at acquisition. Production impact: UNVERIFIED.
- D17-SEC-01. No hash enforcement and no vulnerability review. Future action: hashes first, advisory review after exact versions. Production impact: UNVERIFIED.

None of these findings were repaired.

## 13. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, SHA-256 comparison, AST scan of the 60 Dockerfile COPY Python files, AST scan of top-level `tests/*.py`, and a zoneinfo import search.
- Files read: the ten protected and packaging files, Dockerfile COPY sources as text via AST, and D.16 dependency evidence.
- Files created: the D.17 research files in `data/research/adaptive_ensemble/d17/`.
- Files modified: none outside that new directory.
- Static checks: JSON artifacts were written by a local script and the protected hashes were compared before and after.
- Runtime tests: none
- Docker commands: none
- Network requests: none
- Package-manager commands: none
- Prohibited operations: none observed
- Missing evidence: Python patch, architecture, libc version, base digest, wheel tags, resolver version, lock, hashes, wheelhouse, and vulnerability review.

A completed static analysis does not show that a lock can be generated.

## 14. FINAL CLASSIFICATION

`D17_PREPARATION_COMPLETE_TARGET_GAPS_REMAIN`

## 15. NEXT ACTION

D.17 completed. A locking strategy was defined. The target environment was not verified. Direct image imports are declared. No resolved lockfile exists. No artifact hashes exist. No offline wheelhouse exists. Offline installation was not verified. Production source remained unchanged.

The bot may not be restarted. An image may not be built. Deployment is not authorised. Live trading is not authorised. Another separately approved stage is required before any resolution.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
