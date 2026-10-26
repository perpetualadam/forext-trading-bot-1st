# STAGE D.30-R1 — CORRECTED CONTROLLED REGISTRY HEAD RESPONSE DISCOVERY REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D30_R1_BLOCKED_CLIENT_SAFETY`
- Gate A: PASS
- Gate B: PASS
- Gate C: BLOCKED
- Gate D: NOT_REACHED
- Gate E: NOT_REACHED
- Gate F: NOT_REACHED
- Gate G: NOT_REACHED
- Gate H: NOT_REACHED
- Gate I: NOT_REACHED
- Gate J: PASS for stop integrity only
- Production source modified: no
- Network requests: 0
- Layer bodies downloaded: none
- Recommended next action: no registry request until a client can cancel name resolution inside the approved deadline.

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
- Image-layer extraction: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. ORIGINAL D.30 STOP

- Historical classification: `D30_BLOCKED_PROMPT_INTEGRITY`
- Malformed digest: the D.30 requirements.txt expected value was 66 hexadecimal characters. It remains recorded in D.30 and was not reused.
- Corrected digest: the D.30-R1 expected value is 64 hexadecimal characters and matches the current requirements.txt bytes.
- Historical network requests: 0
- Historical artifact preservation: the 16 D.30 files were read and not modified.

## 4. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.30-R1. HEAD does not identify the working-tree bytes.
- Protected hashes: all ten expected digests are 64 hexadecimal characters and match the current files.
- Earlier evidence integrity: inspected D.29-R1 and D.30 files match their pre-stage hashes.
- Unexpected changes: none.

## 5. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Layer digest reconciliation: 4 AMD64 references, 4 ARM64 references, 8 unique digests, 0 shared digests, 94,726,961 declared compressed bytes, largest blob 28,249,323 bytes. The D.29-R1 digest set matches.
- OCI integrity verdict: PASS.

## 6. CLIENT PREFLIGHT

- Host allowlist: registry-1.docker.io and auth.docker.io only.
- Method allowlist: HEAD for the registry and GET for the token host.
- Credential policy: no credential store, helper, or ambient credential read.
- Proxy policy: proxy settings are not discovered and are not used.
- TLS policy: not exercised, because no connection was opened.
- Redirect policy: automatic following is rejected.
- DNS deadline enforcement: not achieved. A synthetic resolver was still running when the 0.05 second wait returned, and it could not be cancelled.
- Request deadline enforcement: not claimed. Waiting for a thread to finish does not bound the blocking call.
- Stage deadline enforcement: not claimed for the same reason.
- Body-read limits: the client has no layer-body read path and no registry GET path.
- Preflight verdict: BLOCKED. No external host was contacted.

## 7. AUTHENTICATION

- Challenges observed: 0
- Token requests: 0
- Token host: not contacted
- Token scope: not requested
- Token persistence: none
- Unexpected challenges: none
- Authentication verdict: NOT_REACHED

## 8. HEAD RESPONSE DISCOVERY

- Unique layer digests: 8, derived from the local manifests
- HEAD attempts: 0
- Direct HEAD responses: 0
- Authentication challenges: 0
- Redirects: 0
- Errors: 0
- Timeouts: 0
- Not attempted: all 8 digests
- Per-layer response matrix: every digest is NOT_ATTEMPTED. No response was invented.

## 9. REDIRECT AND HOST SAFETY

- Redirects observed: 0
- Redirects followed: 0
- Storage hosts contacted: 0
- Unapproved destinations: none
- Sensitive URL retention: none
- Redirect verdict: NOT_REACHED

## 10. NETWORK BUDGET

- Total requests: 0
- Layer HEAD requests: 0
- Token GET requests: 0
- Cumulative response-body bytes: 0
- Maximum request duration: not applicable
- Total stage duration: no network clock was started
- Connection timeout: 10 seconds approved, not used
- Inactivity timeout: 15 seconds approved, not used
- Retries: 0
- Budget verdict: NOT_REACHED. The ceilings were not consumed.

## 11. EVIDENCE LIMITATIONS

- HEAD versus GET: no HEAD response exists.
- Layer bytes: none were read.
- Compressed digest verification: descriptors were checked locally. Blob bytes were not.
- Uncompressed diff IDs: not remeasured.
- Python ABI: unmeasured.
- libc: unmeasured.
- Final image: not assessed.
- VPS: not assessed.
- Publisher authenticity: not assessed.

## 12. FINDINGS

- D30R1-PROMPT-01. Evidence: ten local file hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the corrected requirements.txt digest is 64 hexadecimal characters and matches the file. Unsupported conclusion: the original D.30 66-character value was valid. Impact: the prompt block is cleared. Required next evidence: none for this file. Required approval: none for the completed comparison. Production impact: UNVERIFIED.
- D30R1-BASE-01. Evidence: ten protected hashes and git HEAD. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the working-tree bytes match the corrected prompt. Unsupported conclusion: HEAD identifies the dirty tree. Impact: baseline passed. Required next evidence: none. Required approval: none for this check. Production impact: UNVERIFIED.
- D30R1-OCI-01. Evidence: five OCI objects and both manifest layer arrays. Evidence classification: VERIFIED_OCI_DESCRIPTOR. Supported conclusion: eight unique compressed digests were derived locally. Unsupported conclusion: those blobs were fetched. Impact: the allowlist is local only. Required next evidence: a later response, if a safe client exists. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-CLIENT-01. Evidence: offline preflight. Evidence classification: BLOCKED. Supported conclusion: host, method, redirect, proxy, and body restrictions can be expressed, and the network path was not opened. Unsupported conclusion: the client is safe to use against the registry. Impact: discovery did not start. Required next evidence: a cancellable resolver. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-DNS-01. Evidence: synthetic resolver still running at the deadline. Evidence classification: BLOCKED. Supported conclusion: a socket timeout and a thread join do not cancel name resolution. Unsupported conclusion: the 10 second connection timeout bounds DNS. Impact: the hard request deadline cannot be guaranteed. Required next evidence: an implementation that can cancel resolution. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-AUTH-01. Evidence: no token request. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no credential store was read and no token was stored. Unsupported conclusion: anonymous authentication succeeded. Impact: the auth host was not contacted. Required next evidence: a challenge, only after DNS can be bounded. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-HEAD-01. Evidence: zero HEAD requests. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no registry response was observed. Unsupported conclusion: HEAD behaviour predicts GET behaviour. Impact: all eight digests remain unattempted. Required next evidence: a future HEAD attempt. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-REDIRECT-01. Evidence: no response. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no redirect was followed and the historical storage host was not contacted. Unsupported conclusion: a later HEAD will or will not redirect. Impact: storage remains unauthorised. Required next evidence: a sanitised response. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-BYTES-01. Evidence: zero body bytes. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no layer body was read or saved. Unsupported conclusion: the blobs are present remotely. Impact: compressed bytes remain remote. Required next evidence: none from this stop. Required approval: yes for any later read. Production impact: UNVERIFIED.
- D30R1-PROV-01. Evidence: local digest checks without signatures or registry responses. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the preserved files match their expected hashes. Unsupported conclusion: that match authenticates the publisher. Impact: trust stays local. Required next evidence: a signature review. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-ABI-01. Evidence: no interpreter probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: a HEAD response would measure it. Impact: wheel compatibility stays unresolved. Required next evidence: filesystem or runtime measurement. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc family and version remain unmeasured. Unsupported conclusion: the bookworm name supplies them. Impact: native-wheel relevance stays unresolved. Required next evidence: a libc file or loader observation. Required approval: yes. Production impact: UNVERIFIED.
- D30R1-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this stop did not read or change trading controls. Unsupported conclusion: registry discovery makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 13. FUTURE DECISION

- Recommended next stage: no further network action.
- Evidence gap addressed: the corrected digest and the local layer allowlist. Registry behaviour remains unknown.
- Required permissions: a later approval would still need the same host limits, plus a client that can cancel DNS.
- Remaining risks: an unbounded resolver can outlive the 30 second request deadline.
- Explicit approval required: yes. This stop does not authorise a retry.

## 14. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and local preflight.
- Network requests: 0
- Files created: D.30-R1 artifacts under data/research/adaptive_ensemble/d30_r1/.
- Files modified: none outside that new directory.
- Protected hashes: ten files matched before and after.
- OCI hashes: five objects matched.
- Prior evidence hashes: inspected D.29-R1 and D.30 files matched.
- Prohibited operations: none observed.

## 15. FINAL CLASSIFICATION

`D30_R1_BLOCKED_CLIENT_SAFETY`

## 16. NEXT ACTION

D.30-R1 did not complete discovery. No network request occurred. No layer body was downloaded. No redirect was followed. No storage host was contacted. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
