# STAGE D.24 — CONTROLLED OCI CONFIGURATION METADATA VERIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D24_BLOCKED_REGISTRY_RESPONSE`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: NOT_PASSED
- Gate F: NOT_PASSED
- Gate G: NOT_PASSED
- Gate H: NOT_PASSED
- Gate I: NOT_PASSED
- Gate J: PASS
- Production source modified: no
- Network requests: 3
- AMD64 config verified: no
- ARM64 config verified: no
- Recommended next action: the registry answered the authenticated AMD64 blob GET with HTTP 307. That redirect was not followed. A later attempt needs a separate approval that names any additional host before it can be contacted. D.25 was not started.

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
- Image downloads: none. Configuration JSON was not retrieved. Layers were not requested.
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.24. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files and the D.21 baseline.
- Earlier evidence integrity: D.22 remains `D22_BLOCKED_BASELINE_INTEGRITY`. The three D.22-R1 manifests were rehashed before the network requests.
- Unexpected changes: none caused by this stage.

## 4. NETWORK BOUNDARY

- Approved hosts: `registry-1.docker.io`, `auth.docker.io`
- Actual hosts: `auth.docker.io`, `registry-1.docker.io`
- Request count: 3
- Request methods: GET
- Request paths: the AMD64 config blob, the anonymous token endpoint, then the same AMD64 config blob with the anonymous token
- Redirects: the third response was HTTP 307. Its Location value was not stored and was not followed.
- Proxy use: no proxy environment entries and no proxy handler
- TLS validation: `ssl.create_default_context`
- Response-size limits: 1 MiB while reading
- Unexpected destinations: none

## 5. AUTHENTICATION

- Initial blob request: 401
- Bearer challenge: scheme Bearer, realm `auth.docker.io/token`, service `registry.docker.io`, scope `repository:library/python:pull`
- Token service: `auth.docker.io`
- Token scope: `repository:library/python:pull`
- Token persisted: no
- Credentials accessed: no
- Authentication verdict: `ANONYMOUS_TOKEN_USED`

## 6. AMD64 CONFIGURATION

- Parent manifest: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`
- Config descriptor digest: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`
- Config descriptor size: 5684
- HTTP status: 401 on the first GET, then 307 on the authenticated retry
- Raw byte count: not obtained
- Computed digest: not obtained
- Digest comparison: not verified
- Size comparison: not verified
- Raw evidence path: NOT_OBTAINED
- Config verification verdict: NOT_VERIFIED

## 7. ARM64 CONFIGURATION

- Parent manifest: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`
- Config descriptor digest: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`
- Config descriptor size: 5699
- HTTP status: not requested
- Raw byte count: not obtained
- Computed digest: not obtained
- Digest comparison: not verified
- Size comparison: not verified
- Raw evidence path: NOT_OBTAINED
- Config verification verdict: NOT_VERIFIED

## 8. CONFIGURATION METADATA

- AMD64 architecture: not obtained
- ARM64 architecture: not obtained
- OS fields: not obtained
- Variant fields: not obtained
- User declarations: not obtained
- Working directories: not obtained
- Entrypoints: not obtained
- Commands: not obtained
- Environment variable names: not obtained
- Exposed ports: not obtained
- Volume declarations: not obtained
- Rootfs diff-ID counts: not obtained
- History entry counts: not obtained
- Image labels: not obtained
- Cross-platform differences: not compared, because neither config blob was retrieved

## 9. RUNTIME EVIDENCE MATRIX

- Total entries: 0
- Verified from local bytes: 0
- Verified config content: 0
- Verified descriptor only: 0
- Declared in local source: 0
- Historical observation: 0
- Inferred: 0
- Unverified: 0
- Missing: 0
- Blocked: 0

The matrix was not populated. The config bytes required for those classifications were not retrieved.

## 10. FINDINGS

- D24-HIST-01. Evidence: D.22 remains `D22_BLOCKED_BASELINE_INTEGRITY` with zero network requests. Evidence level: preserved historical record. Impact: this stage does not erase that stop. Required action: leave the D.22 directory unchanged. Required approval: none for preservation. Production impact: UNVERIFIED.
- D24-STOP-01. Evidence: the authenticated AMD64 config-blob GET returned HTTP 307. The Location value was not stored and the redirect was not followed. The ARM64 blob was not requested. Evidence level: stop condition. Impact: neither configuration blob was retrieved. Required action: do not follow an unapproved redirect and do not retry under this approval. Required approval: a new approval that names any additional host before another attempt. Production impact: UNVERIFIED.

## 11. VALIDATION

- Commands executed: Git HEAD, branch, targeted status, and the Python standard-library registry client.
- Network requests: 3
- Files created: the D.24 evidence under `data/research/adaptive_ensemble/d24/`. Raw config files 09 and 13 were not created.
- Files modified: none outside that new directory.
- Static checks: local OCI schema before the requests. Config JSON was not parsed.
- Digest checks: protected files and the three preserved manifests. Config blob digests were not computed.
- Prohibited operations: none observed.

## 12. FINAL CLASSIFICATION

`D24_BLOCKED_REGISTRY_RESPONSE`

## 13. NEXT ACTION

D.24 stopped before both config blobs were verified. AMD64 config bytes were not verified. ARM64 config bytes were not verified. Actual Python runtime versions were not verified. Python ABI was not verified. libc versions were not verified. Wheel compatibility was not verified. Dependency resolution is not authorised. Image building is not authorised. Production deployment is not authorised. Live trading is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
