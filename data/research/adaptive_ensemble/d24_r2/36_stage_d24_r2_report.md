# STAGE D.24-R2 — CONTROLLED OCI CONFIGURATION VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D24_R2_CONFIG_VERIFIED_BOTH_PLATFORMS`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H: PASS
- Gate I: PASS
- Gate J: PASS
- Production source modified: no
- Network requests: 6
- AMD64 config verified: yes
- ARM64 config verified: yes
- Recommended next action: config byte identity does not authorise layer inspection, wheel review, an image build, or deployment. D.25 was not started.

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
- Working-tree status: dirty before D.24-R2. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files and the D.21 baseline.
- Earlier evidence integrity: D.22 remains `D22_BLOCKED_BASELINE_INTEGRITY`. D.22-R1, D.23, D.24, and D.24-R1 were unchanged.
- Unexpected changes: none caused by this stage.

## 4. NETWORK BOUNDARY

- Approved hosts: `registry-1.docker.io`, `auth.docker.io`, `production.cloudfront.docker.com`
- Actual hosts: `auth.docker.io`, `production.cloudfront.docker.com`, `registry-1.docker.io`
- Request count: 6
- Request methods: GET
- Sanitised request paths: the AMD64 registry blob, the anonymous token endpoint, the authenticated AMD64 registry blob, a redacted AMD64 storage URL, the authenticated ARM64 registry blob, and a redacted ARM64 storage URL
- Redirects: each registry blob returned HTTP 307. Both redirects were validated manually and followed once. Storage did not return another redirect.
- Proxy use: no proxy environment entries and no proxy handler
- TLS validation: `ssl.create_default_context`
- Response-size limits: 1 MiB while reading
- Unexpected destinations: none

## 5. AUTHENTICATION

- Initial registry request: 401
- Bearer challenge: scheme Bearer, realm `auth.docker.io/token`, service `registry.docker.io`, scope `repository:library/python:pull`
- Token service: `auth.docker.io`
- Token scope: `repository:library/python:pull`
- Token persisted: no
- Registry token forwarded to storage: no
- Credentials accessed: no
- Authentication verdict: `ANONYMOUS_TOKEN_USED`

## 6. AMD64 CONFIGURATION

- Parent manifest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Config descriptor digest: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`
- Config descriptor size: 5684
- Registry HTTP status: 307 on the authenticated request, after an initial 401
- Redirect hostname: `production.cloudfront.docker.com`
- Redirect validation: PASS
- Storage contacted: yes
- Storage HTTP status: 200
- Raw byte count: 5684
- Computed SHA-256: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`
- Digest comparison: matched
- Size comparison: matched
- Raw evidence path: `data/research/adaptive_ensemble/d24_r2/11_amd64_config_raw.json`
- Verification verdict: AMD64_CONFIG_BLOB_VERIFIED

## 7. ARM64 CONFIGURATION

- Parent manifest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Config descriptor digest: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`
- Config descriptor size: 5699
- Registry HTTP status: 307
- Redirect hostname: `production.cloudfront.docker.com`
- Redirect validation: PASS
- Storage contacted: yes
- Storage HTTP status: 200
- Raw byte count: 5699
- Computed SHA-256: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`
- Digest comparison: matched
- Size comparison: matched
- Raw evidence path: `data/research/adaptive_ensemble/d24_r2/16_arm64_config_raw.json`
- Verification verdict: ARM64_CONFIG_BLOB_VERIFIED

The ARM64 redirect was validated on its own response. The signed URL was not reused from the AMD64 redirect and was not stored.

## 8. STATIC CONFIGURATION METADATA

- AMD64 architecture: amd64
- ARM64 architecture: arm64
- Operating system: linux on both
- Variant: AMD64 has no variant. ARM64 variant is `v8`.
- Runtime user: neither config declares User
- Working directory: neither config declares WorkingDir
- Entrypoint: neither config declares Entrypoint
- Command: both declare `["python3"]`
- Environment variable names: `PATH`, `LANG`, `GPG_KEY`, `PYTHON_VERSION`, `PYTHON_SHA256` on both. `GPG_KEY` was redacted.
- Exposed ports: neither config declares ExposedPorts
- Volumes: neither config declares Volumes
- Rootfs diff-ID counts: 4 on both
- History entry counts: 10 on both
- Cross-platform differences: architecture and variant. Creation timestamps also differ: AMD64 `2026-10-06T02:04:51.549801942Z`, ARM64 `2026-10-06T02:11:13.014797359Z`. Neither config contains image labels.

Both configs declare `PYTHON_VERSION=3.12.15`. That is a configuration declaration. It is not a measured interpreter patch, ABI, or libc version.

## 9. RUNTIME EVIDENCE MATRIX

- Total entries: 48
- Verified from local bytes: 8
- Verified config content: 6
- Verified descriptor only: 0
- Declared in local source: 0
- Historical observation: 0
- Inferred: 0
- Unverified: 16
- Missing: 16
- Blocked: 2

Verified config content covers the declared command and environment names, plus schema validity. Python implementation, patch measurement, Debian release, libc family, CPU compatibility, application compatibility, VPS compatibility, and provenance remain unverified. ABI, package revision, libc version, shared libraries, wheels, user, entrypoint, and health behaviour are missing. Live-safety behaviour remains blocked.

## 10. FINDINGS

- D24R2-HIST-01. Evidence: D.22 through D.24-R1 were left unchanged. Evidence level: preserved historical record. Impact: D.24 remains `D24_BLOCKED_REGISTRY_RESPONSE`. Required action: leave those directories unchanged. Required approval: none for preservation. Production impact: UNVERIFIED.
- D24R2-TOKEN-01. Evidence: both storage requests were sent without an Authorization header. Evidence level: client control. Impact: the registry bearer token was not forwarded to `production.cloudfront.docker.com`. Required action: keep that isolation. Required approval: none for this control. Production impact: UNVERIFIED.
- D24R2-PY-01. Evidence: both verified configs declare `PYTHON_VERSION=3.12.15` and `Cmd ["python3"]`. Evidence level: config content. Impact: the declaration is not a measured interpreter, ABI, libc, or wheel result. Required action: do not treat config verification as runtime approval. Required approval: a later filesystem or runtime stage. Production impact: UNVERIFIED.
- D24R2-LIMIT-01. Evidence: the verified objects are two image config documents. Evidence level: exact config bytes. Impact: layers, signatures, wheels, bot startup, and production rollback remain outside this result. Required action: do not build or deploy from this result. Required approval: each later stage needs its own approval. Production impact: UNVERIFIED.

## 11. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, and the Python standard-library HTTPS client.
- Network requests: 6
- Files created: the D.24-R2 evidence under `data/research/adaptive_ensemble/d24_r2/`, including the two raw config files.
- Files modified: none outside that new directory.
- Static checks: local OCI schema before the requests, manual redirect validation, and config schema after each digest match.
- Digest checks: protected files, three preserved manifests, and both config blobs. Both raw files match their descriptor digests and sizes.
- Prohibited operations: none observed. Signed URLs and the bearer token were not written to evidence.

## 12. FINAL CLASSIFICATION

`D24_R2_CONFIG_VERIFIED_BOTH_PLATFORMS`

## 13. NEXT ACTION

D.24-R2 completed both config verifications. AMD64 config bytes were verified. ARM64 config bytes were verified. Actual Python runtime versions were not verified. Python ABI was not verified. libc versions were not verified. Wheel compatibility was not verified. Dependency resolution is not authorised. Image building is not authorised. Production deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
