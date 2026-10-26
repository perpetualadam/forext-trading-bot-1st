# STAGE D.20 — MULTI-PLATFORM DEPLOYMENT TARGET DEFINITION AND COMPATIBILITY PREPARATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D20_AUDIT_COMPLETE_MULTI_PLATFORM_POLICY_READY_FOR_DECISION`
- Gate A: PASS. Protected hashes matched. The D.20 directory was absent at the start.
- Gate B: PASS. `linux/amd64` and the base-image reference are recorded as stated decisions. `linux/arm64` stays proposed.
- Gate C: PASS. Current deployment files declare no platform.
- Gate D: PASS. Both runtime profiles leave patch, ABI, libc, and wheel tags unknown.
- Gate E: PASS. Per-platform image digests are unverified. The historical local image ID was not reused.
- Gate F: PASS. A per-platform lock preference is documented. No lock was created.
- Gate G: PASS. The later sequence is a proposal. No step is authorised.
- Gate H: PASS. The dual policy is ready for a user decision. It is not verified.
- Production source modified: no
- Multi-platform policy approval: pending explicit confirmation
- Recommended next action: the user explicitly confirms or rejects `linux/amd64 + linux/arm64`. Until that statement, the operative approved architecture remains `linux/amd64` alone.

This classification means the policy is documented for a decision. It does not mean either platform is technically verified.

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
- Image downloads: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected hashes: matched for the five source files, both requirements files, the Dockerfile, `.dockerignore`, and Compose.
- Unexpected changes: none caused by this stage.

## 4. USER DECISIONS

- Approved platform: `linux/amd64`, as stated in the D.20 instruction.
- Proposed additional platform: `linux/arm64`.
- Multi-platform policy approval: pending.
- Approved base-image reference: `docker.io/library/python:3.12-slim-bookworm`. The digest is not approved or verified.
- Future VPS provider: not selected.
- Future VPS hardware: not verified.

D.19 still records a null platform because that stage was not allowed to infer a selection. That file was not rewritten.

## 5. CURRENT DEPLOYMENT CONFIGURATION

- Dockerfile base: line 2, `python:3.12-slim-bookworm`. The file does not name `docker.io`.
- Dockerfile platform: absent.
- Compose bot platform: absent. Result remains `TARGET_PLATFORM_UNSPECIFIED` in the file. `linux/amd64` was not written into Compose.
- Runtime command: line 81, `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`.
- Dependency installation: lines 13–14 upgrade pip and install `requirements.txt` with `--prefer-binary` and without hashes.
- Architecture assumptions: no `amd64` or `arm64` strings in the deployment files. Two research scripts call `ctypes.windll.kernel32` and are not in the image copy list. A negative search is not proof of portability.

## 6. MULTI-PLATFORM TARGET MATRIX

AMD64:

- OCI platform: `linux/amd64`, stated as the intended architecture.
- Base-image identity: the approved reference. Manifest digest unverified.
- Python patch: unknown.
- ABI: unknown.
- libc: unknown.
- Wheel compatibility: unverified.
- Native dependencies: numpy, pandas, psycopg2-binary, and uvicorn`[standard]`, unverified.
- Verification status: not verified. The selection is not a hardware proof.

ARM64:

- OCI platform: `linux/arm64`, proposed only.
- Base-image identity: same reference. Presence in the index is unverified.
- Python patch: unknown.
- ABI: unknown.
- libc: unknown.
- Wheel compatibility: unverified. Missing evidence is not a finding of incompatibility.
- Native dependencies: the same four candidates, with no artifacts.
- Verification status: not approved and not verified.

## 7. DEPENDENCY ANALYSIS

- Direct requirements: 9, revalidated by the unchanged `requirements.txt` hash.
- Exact pins: 0.
- Native candidates: numpy, pandas, psycopg2-binary, uvicorn with the `standard` extra.
- Transitive closure: absent.
- AMD64 compatibility: unverified.
- ARM64 compatibility: unverified.
- Proposed locking strategy: if dual support is later approved, separate fully resolved locks are the audit preference. A single shared resolution can accept a version that has a wheel for only one architecture. No strategy is approved.
- Lock created: no.

## 8. BASE-IMAGE IDENTITY

- Approved proposed reference: `docker.io/library/python:3.12-slim-bookworm`.
- AMD64 manifest digest: unverified.
- ARM64 manifest digest: unverified.
- Index digest: unverified.
- Historical local image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. Classified as a historical local ID, not a registry digest and not a rollback artifact.
- Provenance: unverified.
- Registry requests: none.

## 9. MULTI-PLATFORM POLICY OPTIONS

- Single AMD64: matches the stated selection. Digest, wheels, and VPS remain unverified.
- Dual AMD64/ARM64: documented and not approved.
- Portable source, target undecided: not the stated decision. It would still need architecture checks after a host is chosen.
- Recommended option: keep Option 1 as the operative approved architecture. Place Option 2 in front of an explicit confirm-or-reject decision. This stage does not adopt Option 2.
- Approval still required: the dual policy, any registry read, any lock, any image build, and any deployment.

## 10. READINESS MATRIX

- Total domains: 26
- Explicitly approved: 2 (R01, R04)
- Proposed: 3 (R02, R03, R16)
- Declared: 0
- Inferred: 0
- Historical only: 0
- Partial: 0
- Unverified: 6 (R05, R06, R11, R12, R18, R23)
- Missing: 12
- Blocked: 3 (R24, R25, R26)

## 11. FINDINGS

- D20-POLICY-01. `linux/arm64` and the dual policy are proposed and not approved. Explicit user decision. Impact: ARM64 must stay out of the deployment configuration. Required action: wait for confirm or reject. Required approval: a statement that approves or rejects the pair. Production impact: UNVERIFIED.
- D20-BASE-01. The reference is approved. Neither platform manifest is verified, and the tag does not prove both platforms exist. Explicit user decision plus current file. Impact: image identity is open. Required action: a later read-only registry stage. Required approval: a separate registry-read approval. Production impact: UNVERIFIED.
- D20-WHEEL-01. The four native candidates have no verified wheels on either architecture. Current declaration. Impact: dependency compatibility is unverified. Required action: artifact checks after image identity. Required approval: package-metadata and artifact approvals. Production impact: UNVERIFIED.
- D20-LOCK-01. Nine lower bounds and no lock. Current declaration. Impact: an unpinned install can differ by platform. Required action: keep resolution unauthorised. Required approval: resolver, hash policy, and platform scope. Production impact: UNVERIFIED.
- D20-VPS-01. No provider and no hardware check. Missing. Impact: the AMD64 selection does not prove VPS hardware. Required action: independent VPS validation. Required approval: not granted. Production impact: UNVERIFIED.
- D20-SOURCE-01. Two research scripts call `ctypes.windll.kernel32` and are outside the image copy list. Current declaration. Impact: those scripts are Windows-specific. Their exclusion is not portability proof. Required action: leave them unchanged. Production impact: UNVERIFIED.

None of these findings were repaired.

## 12. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, SHA-256 comparison, and a static architecture-string search. Exit code 0 on those checks.
- Files read: Dockerfile, Compose, requirements, D.19 decision record, and the cited historical image notes.
- Files created: the D.20 research files under `data/research/adaptive_ensemble/d20/`.
- Files modified: none outside that new directory. Deployment configuration was not edited.
- Static checks: JSON artifacts parse. Protected hashes were compared before the write and again after it.
- Runtime tests: none
- Docker commands: none
- Network requests: none
- Prohibited operations: none observed
- Missing evidence: both platform manifests, Python patch, ABI, libc, wheels, transitive closure, VPS identity, and dual-policy approval.

## 13. FINAL CLASSIFICATION

`D20_AUDIT_COMPLETE_MULTI_PLATFORM_POLICY_READY_FOR_DECISION`

## 14. NEXT ACTION

D.20 completed. Multi-platform support is not approved. AMD64 remains the existing stated selection. ARM64 is still proposed. Both base-image manifests are unverified. Python ABI and libc are unverified. Wheel compatibility is unverified. Dependency resolution is not authorised. Production source remained unchanged. Another user decision is required before ARM64 is in scope. Registry access requires a separate approval. Image builds are not authorised. The bot may not be restarted. Deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
