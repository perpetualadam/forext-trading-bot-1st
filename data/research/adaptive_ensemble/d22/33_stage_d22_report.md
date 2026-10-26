# STAGE D.22 — READ-ONLY OCI REGISTRY IDENTITY VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D22_BLOCKED_BASELINE_INTEGRITY`
- Gate A: BLOCKED. The `requirements.txt` digest in the D.22 instruction does not match the D.21 baseline.
- Gate B: NOT RUN
- Gate C: NOT RUN
- Gate D: NOT RUN
- Gate E: NOT RUN
- Gate F: NOT RUN
- Gate G: NOT RUN
- Gate H: NOT RUN
- Gate I: NOT RUN
- Production source modified: no
- Network requests: 0
- Index verified: no
- AMD64 manifest verified: no
- ARM64 manifest verified: no
- Recommended next action: issue a separate instruction whose expected `requirements.txt` digest matches the D.21 baseline. This stage did not repair that value and did not contact the registry.

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
- Image downloads: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten files checked, including `requirements.txt`, still match the D.21 baseline.
- Unexpected changes: none in those files. The discrepancy is in the D.22 instruction text.

The D.21 digest is 64 hexadecimal characters:

`45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a`

The D.22 instruction digest is 77 characters and is not equal to that value. The file on disk matches D.21. The expected value was not rewritten, and `requirements.txt` was not edited.

## 4. NETWORK BOUNDARY

- Approved hosts: `registry-1.docker.io` and `auth.docker.io`, not contacted
- Actual hosts contacted: none
- Approved methods: not used
- Actual methods: none
- Request count: 0
- Redirects: none
- Proxy use: none
- TLS validation: not exercised
- Timeouts: not exercised
- Response-size limits: not exercised
- Unexpected destinations: none

## 5. AUTHENTICATION

- Anonymous index request: not sent
- Bearer challenge: not obtained
- Token service: not contacted
- Token scope: not used
- Token retained on disk: no
- Credential access: no
- Authentication verdict: not attempted

## 6. OCI INDEX

- Reference: `docker.io/library/python:3.12-slim-bookworm`, not requested
- HTTP status: not obtained
- Media type: not obtained
- Raw byte count: not obtained
- Computed SHA-256: not obtained
- Registry-reported digest: not obtained
- Digest comparison: not performed
- Raw evidence path: not created
- Index verification verdict: not verified

## 7. PLATFORM DESCRIPTORS

- AMD64 descriptor: not obtained
- ARM64 descriptor: not obtained
- Duplicate candidates: not assessed
- Unexpected descriptors: not assessed
- Descriptor validation verdict: not performed

## 8. AMD64 MANIFEST

- Request path: not sent
- HTTP status: not obtained
- Media type: not obtained
- Raw byte count: not obtained
- Computed SHA-256: not obtained
- Expected descriptor digest: not obtained
- Digest comparison: not performed
- Size comparison: not performed
- Raw evidence path: not created
- AMD64 verdict: not verified

## 9. ARM64 MANIFEST

- Request path: not sent
- HTTP status: not obtained
- Media type: not obtained
- Raw byte count: not obtained
- Computed SHA-256: not obtained
- Expected descriptor digest: not obtained
- Digest comparison: not performed
- Size comparison: not performed
- Raw evidence path: not created
- ARM64 verdict: not verified

## 10. EVIDENCE CONSISTENCY

- Index digest: not obtained
- AMD64 manifest digest: not obtained
- ARM64 manifest digest: not obtained
- Cross-reference integrity: not performed
- Missing evidence: the index and both platform manifests
- Unexpected artifacts: raw manifest files `08`, `14`, and `18` were not created, because no response bytes exist

## 11. FINDINGS

- D22-BASE-01. The D.22 instruction digest for `requirements.txt` is 77 characters. The D.21 baseline digest is 64 characters and identifies the current file. Impact: registry verification did not start. Required action: do not treat the instruction string as the file digest and do not edit `requirements.txt`. Required approval: a separate instruction whose expected digest matches D.21. Production impact: UNVERIFIED.

## 12. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, and SHA-256 comparison of the protected files with the D.21 records. Exit code 0.
- Network requests: none
- Files created: D.22 evidence of the stop under `data/research/adaptive_ensemble/d22/`. Raw manifest files were not created.
- Files modified: none outside that new directory
- Static checks: the instruction digest, the D.21 digest, and the file digest were compared
- Digest checks: registry digests were not calculated
- Prohibited operations: none observed

## 13. FINAL CLASSIFICATION

`D22_BLOCKED_BASELINE_INTEGRITY`

## 14. NEXT ACTION

D.22 did not complete registry verification. The index was not verified. AMD64 was not verified. ARM64 was not verified. Runtime profiles were not verified. Python ABI and libc were not verified. Dependency wheels were not verified. Dependency resolution is not authorised. Source integrity was preserved. Another instruction is required before a registry read. Image building is not authorised. Production deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
