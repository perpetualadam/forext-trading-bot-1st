# STAGE D.21 — MULTI-PLATFORM POLICY RECORDING AND REGISTRY VERIFICATION PLANNING REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D21_PLANNING_COMPLETE_POLICY_RECORDED`
- Gate A: PASS. Protected hashes matched. The D.21 directory was absent at the start.
- Gate B: PASS. Both architectures, the dual policy, and the base-image reference are recorded as intended approvals.
- Gate C: PASS. Dockerfile and Compose still declare no platform. They were not edited.
- Gate D: PASS. The registry procedure is designed. No request was sent.
- Gate E: PASS. Index and both platform-manifest checks are specified and were not executed.
- Gate F: PASS. The evidence schema and stop conditions contain no fabricated registry bytes.
- Gate G: PASS. Later stages remain separate proposals.
- Gate H: PASS. Technical verification did not occur.
- Production source modified: no
- Approved architectures: `linux/amd64` and `linux/arm64`, as intended targets.
- Approved base-image reference: `docker.io/library/python:3.12-slim-bookworm`.
- Registry verification performed: no
- Recommended next action: a separately approved read-only registry stage. It is not started here.

This classification records the policy. It does not verify either architecture or the image bytes.

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
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected hashes: matched for the five source files, both requirements files, the Dockerfile, `.dockerignore`, and Compose.
- Unexpected changes: none caused by this stage.

## 4. APPROVED MULTI-PLATFORM POLICY

- Policy identifier: `D21-MULTI-PLATFORM-01`
- AMD64 approval: explicit intended target, decision `D21-PLATFORM-01`.
- ARM64 approval: explicit intended target, decision `D21-PLATFORM-02`.
- Policy scope: future Linux VPS deployment compatibility. Production architecture, VPS hardware, image compatibility, dependency compatibility, candidate images, and deployment are outside that scope.
- Approval evidence: the D.21 stage instruction following the D.20 report. No timestamp, signature, or cryptographic provenance was invented.
- Future VPS status: not selected and not verified.
- Technical verification status: not verified. D.19 and D.20 were left as they were. D.19 recorded a pending selection. D.20 recorded ARM64 as proposed. Those reports were accurate for their own stages.

## 5. APPROVED BASE-IMAGE REFERENCE

- Registry: `docker.io`
- Repository: `library/python`
- Tag: `3.12-slim-bookworm`
- Index digest: unverified
- AMD64 manifest digest: unverified
- ARM64 manifest digest: unverified
- Provenance: unverified
- Registry response: not obtained

The reference approval does not approve the current mutable tag content.

## 6. CURRENT CONFIGURATION

- Dockerfile base: line 2, `python:3.12-slim-bookworm`. The file does not name `docker.io`.
- Dockerfile platform: absent. One stage. Working directory `/app`. No user and no entrypoint. Command at line 81. Install at lines 13–14, without hashes.
- Compose bot platform: absent. Build context `.` at line 17. No bot image, restart policy, or health check. Mounts are the ops and v2_shadow paths. Environment values were not read.
- Policy alignment: partial. The files do not pin one architecture, and they also do not record the dual policy. A future build for each platform needs its own build input. No platform field and no Buildx configuration were added.
- Runtime command: `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`
- Dependency installation: unpinned `pip install -r requirements.txt` after an unpinned pip upgrade.

## 7. REGISTRY VERIFICATION PLAN

- Intended registry: `docker.io`
- Intended repository: `library/python`
- Intended reference: `docker.io/library/python:3.12-slim-bookworm`
- Proposed network boundary: one later-approved manifest endpoint. Redirects to an unnamed host stop the stage. Size cap proposed at 1 MiB per document. Timeout proposed at 30 seconds. These numbers are not approved.
- Proposed authentication policy: anonymous read if a later stage finds that it works. An unexpected credential demand stops the stage. No token was created.
- Proposed request methods: `GET` for the index and, under a further approval, each platform manifest. No blob download.
- Proposed response limits: OCI index or Docker manifest list only.
- Proposed TLS requirements: certificate verification required.
- Proposed digest validation: hash the raw bytes and compare them with the registry-reported digest, then compare each fetched manifest with its descriptor.
- Proposed evidence capture: the schema in `17_future_evidence_schema.json`. Every field is `NOT_OBTAINED`.
- Proposed stop conditions: F01 through F20. No retries were performed. Digest, authentication, TLS, size, and schema failures do not retry.
- Current network authorisation: none.

## 8. OCI VERIFICATION REQUIREMENTS

- Index verification: preserve bytes, hash them, check media type and schema, and require exactly one runtime descriptor for each approved platform. Duplicates and gaps stop the stage.
- AMD64 manifest verification: specified and not performed.
- ARM64 manifest verification: specified and not performed. Approval of ARM64 does not prove the index contains that descriptor.
- Runtime metadata limitations: a manifest does not prove the Python patch, ABI, libc, Debian revision, native libraries, dependency compatibility, runtime user, health behaviour, or trading safety.
- Missing evidence: both digests, provenance, Python patch, ABI, libc, and wheels.

## 9. READINESS MATRIX

- Total domains: 28
- Explicitly approved: 4 (R01, R02, R03, R04)
- Declared: 0
- Proposed: 1 (R21)
- Partial: 2 (R05, R06)
- Missing: 9
- Unverified: 8
- Blocked: 4 (R07, R26, R27, R28)

## 10. FINDINGS

- D21-POLICY-01. The instruction approves both architectures as intended targets. Explicit user decision. Impact: the policy is recorded and neither architecture is verified. Required action: leave D.19 and D.20 unchanged. Production impact: UNVERIFIED.
- D21-BASE-01. The reference is approved and the digests are not. Explicit user decision. Impact: the tag can still move. Required action: a separate registry stage. Required approval: a registry read, which is not granted. Production impact: UNVERIFIED.
- D21-CONFIG-01. Dockerfile line 2 and the Compose bot service declare no platform. Current static declaration. Impact: the policy is not in the deployment files, and a default build can follow the builder. Required action: leave the files unchanged. Required approval: any future platform or Buildx change. Production impact: UNVERIFIED.
- D21-REG-01. The registry procedure is a design. Proposal. Impact: no digests exist. Required action: do not query the registry. Required approval: the checklist in the future-approval document. Production impact: UNVERIFIED.
- D21-DEP-01. Nine lower bounds remain, with no lock and no wheels. Current static declaration. Impact: dependency compatibility is unverified on both platforms. Required action: do not resolve or install. Production impact: UNVERIFIED.

None of these findings were repaired.

## 11. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, SHA-256 comparison, and static Dockerfile and Compose checks. Exit code 0.
- Files read: Dockerfile, Compose, and the D.19 and D.20 decision records cited above.
- Files created: the D.21 research files under `data/research/adaptive_ensemble/d21/`.
- Files modified: none outside that new directory.
- Static checks: JSON artifacts parse. Protected hashes were compared before the write and again after it.
- Runtime tests: none
- Docker commands: none
- Network requests: none
- Prohibited operations: none observed

## 12. FINAL CLASSIFICATION

`D21_PLANNING_COMPLETE_POLICY_RECORDED`

## 13. NEXT ACTION

D.21 completed. The multi-platform policy is recorded. Both architectures are approved as intended targets. The base-image reference is approved. Registry access did not occur. Registry access is not authorised. Image digests are not verified. Python runtime profiles are not verified. Wheel compatibility is not verified. Dependency resolution is not authorised. Production source remained unchanged. Another approval is required before any registry read. An image may not be built. The bot may not be restarted. Deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
