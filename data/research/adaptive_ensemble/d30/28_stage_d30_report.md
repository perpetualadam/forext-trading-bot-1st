# STAGE D.30 — CONTROLLED READ-ONLY REGISTRY HEAD RESPONSE DISCOVERY REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D30_BLOCKED_PROMPT_INTEGRITY`
- Gate A: BLOCKED
- Gate B: NOT_REACHED
- Gate C: NOT_REACHED
- Gate D: NOT_REACHED
- Gate E: NOT_REACHED
- Gate F: NOT_REACHED
- Gate G: NOT_REACHED
- Gate H: NOT_REACHED
- Gate I: NOT_REACHED
- Gate J: NOT_REACHED
- Production source modified: no
- Network requests: 0
- Layer bodies downloaded: none
- Recommended next action: supply a stage text whose requirements.txt expected digest contains exactly 64 hexadecimal characters. This stage did not choose or substitute one.

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
- Working-tree status: dirty before D.30. HEAD does not identify the working-tree bytes.
- Protected hashes: nine expected digests are 64 hexadecimal characters and match the current files. The requirements.txt expected digest in the stage text is 66 hexadecimal characters.
- Earlier evidence integrity: D.22 through D.29-R1 were not modified.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE

- Index digest and size: not revalidated. Gate B was not reached.
- AMD64 manifest digest and size: not revalidated.
- ARM64 manifest digest and size: not revalidated.
- AMD64 config digest and size: not revalidated.
- ARM64 config digest and size: not revalidated.
- Layer digest reconciliation: not performed.
- OCI integrity verdict: NOT_REACHED.

## 5. CLIENT PREFLIGHT

- Host allowlist: not implemented.
- Method allowlist: not implemented.
- Credential policy: not implemented.
- Proxy policy: not implemented.
- TLS policy: not implemented.
- Redirect policy: not implemented.
- Deadline enforcement: not implemented.
- Body-read limits: not implemented.
- Preflight verdict: NOT_REACHED. No HEAD client was written.

## 6. AUTHENTICATION

- Challenges observed: none
- Token requests: 0
- Token host: not contacted
- Token scope: not requested
- Token persistence: none
- Unexpected challenges: none
- Authentication verdict: NOT_REACHED

## 7. HEAD RESPONSE DISCOVERY

- Unique layer digests: not requested
- HEAD attempts: 0
- Direct HEAD responses: 0
- Authentication challenges: 0
- Redirects: 0
- Errors: 0
- Timeouts: 0
- Not attempted: all eight layer digests
- Per-layer response matrix: not created. No response was invented.

## 8. REDIRECT AND HOST SAFETY

- Redirects observed: 0
- Redirects followed: 0
- Storage hosts contacted: 0
- Unapproved destinations: none
- Sensitive URL retention: none
- Redirect verdict: NOT_REACHED

## 9. NETWORK BUDGET

- Total requests: 0
- Layer HEAD requests: 0
- Token GET requests: 0
- Cumulative response-body bytes: 0
- Maximum request duration: not applicable
- Total stage duration: no network clock was started
- Connection timeout: not used
- Inactivity timeout: not used
- Retries: 0
- Budget verdict: NOT_REACHED. The approved ceilings were not consumed.

## 10. EVIDENCE LIMITATIONS

- HEAD versus GET: no HEAD response exists, so no GET behaviour is known.
- Layer bytes: none were read.
- Compressed digest verification: not performed.
- Uncompressed diff IDs: not rechecked in this stage.
- Python ABI: unmeasured.
- libc: unmeasured.
- Final image: not assessed.
- VPS: not assessed.
- Publisher authenticity: not assessed.

## 11. FINDINGS

- D30-OCI-01. Evidence: Gate B was not reached. Evidence classification: NOT_ATTEMPTED. Supported conclusion: the eight layer digests were not requested. Unsupported conclusion: their registry responses are known. Impact: discovery did not start. Required next evidence: a stage text with a valid requirements.txt digest, then the preserved manifests. Required approval: a corrected stage text. Production impact: UNVERIFIED.
- D30-HEAD-01. Evidence: zero HEAD requests. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no HEAD observation was made. Unsupported conclusion: a GET response can be inferred. Impact: HEAD and GET remain uncompared. Required next evidence: an approved HEAD attempt. Required approval: yes. Production impact: UNVERIFIED.
- D30-AUTH-01. Evidence: auth.docker.io was not contacted. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no token was requested or stored. Unsupported conclusion: anonymous authentication succeeded. Impact: the authentication boundary was not exercised. Required next evidence: none until the prompt check passes. Required approval: yes. Production impact: UNVERIFIED.
- D30-REDIRECT-01. Evidence: no response was received. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no redirect was followed and no storage host was contacted. Unsupported conclusion: the registry will or will not redirect a later HEAD. Impact: the historical storage host stays unauthorised. Required next evidence: a future HEAD response. Required approval: yes. Production impact: UNVERIFIED.
- D30-TIME-01. Evidence: deadlines were not implemented. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no socket was opened, so no deadline was extended. Unsupported conclusion: the 10, 15, 30, and 180 second limits were enforced in a client. Impact: enforcement remains untested. Required next evidence: a client built only after a valid prompt. Required approval: yes. Production impact: UNVERIFIED.
- D30-BYTES-01. Evidence: zero body bytes read. Evidence classification: NOT_ATTEMPTED. Supported conclusion: no layer body was acquired. Unsupported conclusion: the blobs are present on the registry. Impact: compressed bytes remain remote. Required next evidence: none from this stop. Required approval: yes for any later request. Production impact: UNVERIFIED.
- D30-PROV-01. Evidence: no signature check and no registry response. Evidence classification: NOT_EVALUATED. Supported conclusion: this stop does not authenticate a publisher. Unsupported conclusion: digest text in the stage prompt proves authorship. Impact: trust is unchanged. Required next evidence: a separate signature review. Required approval: yes. Production impact: UNVERIFIED.
- D30-ABI-01. Evidence: no interpreter probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: a later HEAD response would measure it. Impact: wheel compatibility stays unresolved. Required next evidence: filesystem or runtime measurement under a separate approval. Required approval: yes. Production impact: UNVERIFIED.
- D30-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc family and version remain unmeasured. Unsupported conclusion: the bookworm name supplies them. Impact: manylinux and musllinux relevance stay unresolved. Required next evidence: a libc file or loader observation. Required approval: yes. Production impact: UNVERIFIED.
- D30-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this stop did not read or change trading controls. Unsupported conclusion: the registry stage makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 12. FUTURE DECISION

- Recommended next stage: no registry request until the requirements.txt expected digest in the stage text is exactly 64 hexadecimal characters.
- Evidence gap addressed: none. The malformed expected digest blocked the stage.
- Required permissions: a replacement stage text. This report does not supply a corrected digest.
- Remaining risks: using the 66-character value, or silently replacing it, would make the baseline check unreliable.
- Explicit approval required: yes.

## 13. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and a local syntax check.
- Network requests: 0
- Files created: D.30 stop artifacts under data/research/adaptive_ensemble/d30/.
- Files modified: none outside that new directory.
- Protected hashes: nine valid prompt digests match. The requirements.txt prompt digest was not compared and was not replaced.
- OCI hashes: not rechecked.
- Prior evidence hashes: D.29-R1 files were not rewritten.
- Prohibited operations: none observed.

## 14. FINAL CLASSIFICATION

`D30_BLOCKED_PROMPT_INTEGRITY`

## 15. NEXT ACTION

D.30 did not complete. No network request occurred. No image-layer body was downloaded. No redirect was followed. No storage host was contacted. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
