# STAGE D.29-R1 — OFFLINE ACQUISITION BUDGET RECONCILIATION AND CLIENT SAFETY SPECIFICATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D29_R1_OFFLINE_ACQUISITION_SPEC_COMPLETE`
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
- Network requests: 0
- Image layers downloaded: none
- Downloader implemented: no
- Recommended next action: a future registry response discovery that stops on redirect, after a new approval supplies the missing deadlines.

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

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: dirty before D.29-R1. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match.
- Earlier evidence integrity: the inspected D.28 and D.29 files and the five OCI objects were unchanged.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Descriptor relationships: the index points at both manifests, and each manifest points at its config. AMD64 has no variant key. ARM64 variant is v8.

## 5. EXACT LAYER INVENTORY

- AMD64 layer references: 4
- ARM64 layer references: 4
- Total layer references: 8
- Unique blob digests: 8
- Shared digests: 0
- Largest unique blob: 28249323 bytes
- Declared compressed bytes: AMD64 47558478, ARM64 47168483, references 94726961, unique 94726961

## 6. REQUEST AND HOST POLICY

- Request-flow model: response-driven. A direct body, a challenge, a redirect, or an error are separate branches.
- Proposed request ceiling: 18, status PROPOSED_NOT_AUTHORISED. This is a maximum, not the D.29 sequence.
- Approved hosts: none
- Proposed hosts: registry-1.docker.io and auth.docker.io
- Storage-host status: NOT AUTHORISED. The historical CloudFront name remains an observation.
- Authentication policy: anonymous only under a future approval. No credential store and no ambient credentials.
- Redirect policy: do not follow. An unapproved target stops the stage.
- Credential policy: no token or signed URL is persisted, and a registry token is not sent to storage.
- Proxy policy: no proxy discovery and no proxy use.

## 7. TIMEOUT MODEL

- Connection timeout: MISSING
- Inactivity timeout: MISSING
- Per-request total deadline: MISSING
- Whole-stage deadline: MISSING
- Evidence basis: no registry transfer rate or handshake measurement is in the local evidence. The Dockerfile pip timeout was not used.
- Unresolved assumptions: a future approval must choose the four numbers. They are not enforced now.

## 8. BYTE AND STORAGE BUDGET

- Combined reference bytes: 94726961
- Unique blob bytes: 94726961
- Deduplication savings: 0
- Per-layer body cap: the declared size of that digest
- Non-layer response cap: 1,048,576 bytes, historical comparison value
- Cumulative body cap: 105212721 bytes
- Temporary storage: one in-progress partial, at most 28249323 logical bytes
- Retained storage: 94726961 logical bytes after verification
- Peak application-managed storage: 94726961 logical bytes if the partial is renamed into place
- Filesystem overhead: MISSING
- Available disk: MISSING
- Minimum free-space requirement: MISSING

## 9. CLIENT SAFETY SPECIFICATION

- TLS: certificate verification required for any future connection
- Redirects: manual inspection only, then stop when the host is unapproved
- Credentials: isolated from stores, helpers, and logs
- Proxies: prohibited
- Retries: prohibited
- Content encoding: identity or absent, otherwise stop
- Streaming hash: SHA-256 while counting bytes
- Partial files: one at a time, inside the future directory
- Atomic promotion: same-directory rename after an exact match
- Failure cleanup: remove that temporary file or stop
- Logging: no credentials, tokens, query strings, or signed locations
- Scope boundaries: no extraction, execution, deployment, or trading

## 10. REVIEW QUALIFICATION CLOSURE

- D29-REVIEW-01: RESOLVED. The fixed sequence is withdrawn. The request number is only a ceiling, and the live flow remains unknown.
- D29-REVIEW-02: PARTIALLY_RESOLVED. The pip-timeout rationale is withdrawn. Numeric deadlines are MISSING.
- D29-REVIEW-03: PARTIALLY_RESOLVED. Unique digests and the logical partial maximum are calculated. Available disk and filesystem overhead are MISSING.
- Remaining uncertainty: response behaviour, enforceable deadlines, storage-host approval, free disk space, publisher identity, ABI, libc, the final image, and the VPS.

## 11. FINDINGS

- D29R1-BASE-01. Evidence: rehashed source and OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the ten protected files and five OCI objects match their expected digests. Unsupported conclusion: HEAD identifies the dirty working tree. Impact: planning continued. Required next evidence: none for this baseline. Required approval: none for the completed check. Production impact: UNVERIFIED.
- D29R1-LAYER-01. Evidence: manifest layer arrays and config diff IDs. Evidence classification: VERIFIED_OCI_DESCRIPTOR. Supported conclusion: each reference has a parent manifest, order, media type, declared size, compressed digest, and a different diff ID. Unsupported conclusion: the compressed bytes are local. Impact: acquisition targets are identified only as descriptors. Required next evidence: response bodies under a later approval. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-DEDUP-01. Evidence: exact digest equality. Evidence classification: VERIFIED_OCI_DESCRIPTOR. Supported conclusion: the unique count, shared set, and byte savings are the calculated values above. Unsupported conclusion: similar sizes imply shared blobs. Impact: retention is based on unique digests. Required next evidence: none for this arithmetic. Required approval: none for the completed calculation. Production impact: UNVERIFIED.
- D29R1-REQUEST-01. Evidence: D.29 sequence compared with the new state machine. Evidence classification: PROPOSED_NOT_AUTHORISED. Supported conclusion: registry, token, redirect, and storage steps are conditional. Unsupported conclusion: eighteen particular requests will occur. Impact: a future client must branch on responses. Required next evidence: actual status codes. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-TIME-01. Evidence: no transfer measurement. Evidence classification: MISSING. Supported conclusion: connection, inactivity, request, and stage limits are different controls. Unsupported conclusion: 120 seconds or 2160 seconds is a justified registry deadline. Impact: no network stage can enforce a number chosen here. Required next evidence: user-selected limits or a later authorised measurement. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-BYTES-01. Evidence: declared sizes and the historical 1,048,576 byte cap. Evidence classification: VERIFIED_OCI_DESCRIPTOR for layer sizes and HISTORICAL_OBSERVATION for the non-layer cap. Supported conclusion: the cumulative ceiling counts failed and non-layer bodies. Unsupported conclusion: Content-Length can replace the streaming counter. Impact: an overrun stops the read. Required next evidence: actual response sizes. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-STORAGE-01. Evidence: unique sizes and the largest blob. Evidence classification: VERIFIED_OCI_DESCRIPTOR for logical totals and MISSING for disk. Supported conclusion: one partial is bounded by the largest blob, and retained logical bytes are the unique total. Unsupported conclusion: logical bytes equal filesystem allocation or available space. Impact: a writer must check free space later. Required next evidence: a filesystem check during an approved stage. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-AUTH-01. Evidence: policy specification. Evidence classification: PLANNED_NOT_EXECUTED. Supported conclusion: anonymous authentication needs a separate approval and no credential store is consulted now. Unsupported conclusion: a token already exists or one token will serve every blob. Impact: credentials stay untouched. Required next evidence: a challenge response, if a later approval allows it. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-REDIRECT-01. Evidence: D.24-R2 historical 307 and the current allowlist. Evidence classification: HISTORICAL_OBSERVATION. Supported conclusion: an unapproved storage redirect stops the stage. Unsupported conclusion: the historical CloudFront host is approved. Impact: layer bytes are not fetched through an unnamed host. Required next evidence: a sanitised redirect record or a direct response. Required approval: yes, including any storage host. Production impact: UNVERIFIED.
- D29R1-HASH-01. Evidence: descriptor digests and the streaming rule. Evidence classification: PLANNED_NOT_EXECUTED. Supported conclusion: promotion requires the streamed size and SHA-256 to match. Unsupported conclusion: a descriptor digest proves the publisher or that verification already happened. Impact: partial files are not promoted. Required next evidence: a future streamed hash. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-PROV-01. Evidence: local digest checks without signatures. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the preserved OCI files match their expected hashes. Unsupported conclusion: digest equality authenticates the publisher. Impact: trust remains at descriptor level. Required next evidence: signatures only under a separate approval. Required approval: yes. Production impact: UNVERIFIED.
- D29R1-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this specification does not read or change trading controls. Unsupported conclusion: acquisition planning makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 12. FUTURE DECISION

- Recommended next stage: controlled read-only registry response discovery.
- Evidence gap addressed: whether each layer descriptor receives a direct body, a challenge, or a redirect.
- Required permissions: named registry and token hosts, user-supplied deadlines, the unique digests, a 1,048,576 byte discovery cap, and a stop on every unapproved redirect.
- Remaining risks: discovery can still receive a challenge or a redirect, and it does not produce ABI or libc evidence.
- Explicit approval required: yes. Storage contact, extraction, and execution are not included.

## 13. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and standard-library reconciliation.
- Network requests: 0
- Files created: D.29-R1 artifacts under data/research/adaptive_ensemble/d29_r1/.
- Files modified: none outside that new directory.
- Protected source hashes: ten files matched.
- OCI hashes: five objects matched.
- Prior evidence hashes: inspected D.28 and D.29 files matched before and after.
- Prohibited operations: none observed. No downloader was written.

## 14. FINAL CLASSIFICATION

`D29_R1_OFFLINE_ACQUISITION_SPEC_COMPLETE`

## 15. NEXT ACTION

D.29-R1 planning completed. A downloader was not implemented. No network request occurred. No layer was downloaded. No layer was extracted. No interpreter was executed. Python ABI was not measured. libc was not measured. Docker was not executed. Production was not accessed. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
