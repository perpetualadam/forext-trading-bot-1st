# STAGE D.22-R1 — CORRECTED BASELINE AND READ-ONLY OCI REGISTRY IDENTITY VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D22_R1_REGISTRY_IDENTITY_VERIFIED_BOTH_PLATFORMS`
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
- Network requests: 5
- Index verified: yes
- AMD64 manifest verified: yes
- ARM64 manifest verified: yes
- Recommended next action: a separate approval is required before runtime metadata, wheel checks, or any image build. This stage does not start that work.

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
- Image downloads: none. Configuration blobs and layers were not requested.
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected hashes: all ten expected digests are 64 hexadecimal characters and match the current files and the D.21 baseline.
- Original D.22 failure preserved: `D22_BLOCKED_BASELINE_INTEGRITY`, zero network requests. That directory was not edited.
- Unexpected changes: none caused by this stage.

## 4. NETWORK BOUNDARY

- Approved hosts: `registry-1.docker.io`, `auth.docker.io`
- Actual hosts: auth.docker.io, registry-1.docker.io
- Request count: 5
- Request methods: GET
- Request paths: /v2/library/python/manifests/3.12-slim-bookworm; /token?service=registry.docker.io&scope=repository%3Alibrary%2Fpython%3Apull; /v2/library/python/manifests/3.12-slim-bookworm; /v2/library/python/manifests/sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d; /v2/library/python/manifests/sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163
- Redirects: none followed
- Proxy use: no proxy environment entries were present, and the client installed no proxy handler.
- TLS validation: `ssl.create_default_context`
- Response-size limits: 1 MiB, enforced while reading
- Unexpected destinations: none

## 5. AUTHENTICATION

- Initial index request: HTTP 401
- Bearer challenge: {'scheme': 'Bearer', 'realm_host': 'auth.docker.io', 'realm_path': '/token', 'service': 'registry.docker.io', 'scope': 'repository:library/python:pull'}
- Token service: auth.docker.io
- Token scope: `repository:library/python:pull` when a token was required. This scope was not used to download blobs.
- Token persisted: no
- Credentials accessed: no
- Authentication verdict: ANONYMOUS_TOKEN_USED

## 6. OCI INDEX

- Reference: `docker.io/library/python:3.12-slim-bookworm`
- HTTP status: 200
- Media type: application/vnd.oci.image.index.v1+json
- Raw byte count: 6546
- Computed digest: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`
- Registry-reported digest: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`
- Digest comparison: matched
- Raw evidence path: `data/research/adaptive_ensemble/d22_r1/09_index_raw_manifest.json`
- Index verdict: verified

## 7. PLATFORM DESCRIPTORS

- AMD64 descriptor: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- ARM64 descriptor: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Duplicate candidates: none for the selected runtime platforms
- Unexpected descriptors: 8 other index entries were recorded and not retrieved
- Selection verdict: one runtime descriptor for each approved platform

## 8. AMD64 MANIFEST

- Request path: `/v2/library/python/manifests/sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- HTTP status: 200
- Media type: application/vnd.oci.image.manifest.v1+json
- Raw byte count: 1752
- Computed digest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Expected digest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Digest comparison: matched
- Size comparison: matched
- Raw evidence path: `data/research/adaptive_ensemble/d22_r1/15_amd64_raw_manifest.json`
- AMD64 verdict: verified

## 9. ARM64 MANIFEST

- Request path: `/v2/library/python/manifests/sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- HTTP status: 200
- Media type: application/vnd.oci.image.manifest.v1+json
- Raw byte count: 1754
- Computed digest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Expected digest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Digest comparison: matched
- Size comparison: matched
- Raw evidence path: `data/research/adaptive_ensemble/d22_r1/19_arm64_raw_manifest.json`
- ARM64 verdict: verified

## 10. EVIDENCE CONSISTENCY

- Index digest: matched the registry header and the preserved bytes
- AMD64 digest: matched its index descriptor and the preserved bytes
- ARM64 digest: matched its index descriptor and the preserved bytes
- Cross-reference checks: passed for hosts, paths, sizes, media types, and both descriptors
- Missing evidence: Python patch, ABI, libc, distribution revision, wheel artifacts, and provenance signatures
- Unexpected artifacts: none in the evidence set beyond this stage's files

## 11. FINDINGS

- D22R1-HIST-01. The original D.22 directory still records `D22_BLOCKED_BASELINE_INTEGRITY` and zero network requests. Impact: the corrected retry does not erase that stop. Required action: leave that directory unchanged. Production impact: UNVERIFIED.
- D22R1-LIMIT-01. The verified objects are an image index and two image manifests. Impact: Python patch, ABI, libc, native libraries, and wheel compatibility remain unverified. Required action: do not treat this result as runtime or dependency approval. Required approval: a later metadata stage. Production impact: UNVERIFIED.

## 12. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, SHA-256 comparison, and the Python standard-library registry client.
- Network requests: 5
- Files created: the D.22-R1 evidence under `data/research/adaptive_ensemble/d22_r1/`.
- Files modified: none outside that new directory. D.19, D.20, D.21, and D.22 were not edited.
- Static checks: descriptor schema, digest syntax, sizes, and media types.
- Digest checks: raw-byte SHA-256 compared with registry headers and index descriptors.
- Prohibited operations: none observed.

## 13. FINAL CLASSIFICATION

`D22_R1_REGISTRY_IDENTITY_VERIFIED_BOTH_PLATFORMS`

## 14. NEXT ACTION

D.22-R1 completed the registry identity checks. The OCI index was verified. AMD64 registry identity was verified. ARM64 registry identity was verified. Python runtime profiles were not verified. ABI and libc were not verified. Dependency wheels were not verified. Dependency resolution is not authorised. Source integrity was preserved. Additional approval is required before any runtime, wheel, or build stage. Image building is not authorised. Production deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
