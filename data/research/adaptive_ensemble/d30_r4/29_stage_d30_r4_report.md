# STAGE D.30-R4 — OFFLINE NETWORK-CLIENT INTEGRATION AND SYNTHETIC SAFETY PREFLIGHT REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED`
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
- Real DNS lookups: 0
- Sockets opened: 0
- Synthetic tests run: 22
- Synthetic tests passed: 22
- Synthetic tests failed: 0
- Recommended next action: no registry contact. The client path stays closed.

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
- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.
- Protected hashes: matched
- Earlier evidence integrity: unchanged
- Unexpected changes: none observed.

## 4. HISTORICAL EVIDENCE PRESERVATION

- D.30 classification: `D30_BLOCKED_PROMPT_INTEGRITY`
- D.30-R1 classification: `D30_R1_BLOCKED_CLIENT_SAFETY`
- D.30-R2 classification: `D30_R2_OFFLINE_SUPERVISOR_VALIDATED`
- D.30-R2 H05: `NOT_EVALUATED`
- D.30-R3 classification: `D30_R3_OFFLINE_PROCESS_TREE_VALIDATED`
- Earlier artifacts unchanged: yes

## 5. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- OCI integrity verdict: PASS

## 6. INTEGRATED CLIENT

- Policy owner: the supervisor process.
- Transport: not constructed.
- Discover: raises `D30_R4_NETWORK_PATH_CLOSED` because name lookup is not hard-bounded.
- Historical discover: the D.30-R1 function still raises `D30_R1_BLOCKED_CLIENT_SAFETY`.
- A policy-only HEAD check does not send a request.
- Redirects are recorded and not followed.
- Dispatch count: 0.

## 7. PREFLIGHT

- Preflight verdict: PASS
- Socket import: absent from the integrated client and synthetic worker.
- DNS call: absent.
- HTTP client: absent.
- Application import: absent.
- Output directory: `d30_r4`.

## 8. CONTAINMENT WRAPPER

- Synthetic worker launched: True
- Worker in job: True
- Resume previous count: 1
- Worker exit confirmed: True
- Exit code: 0
- The worker wrote a status line. That line is not an HTTP response.
- Process containment does not establish that a resolver call can be cancelled.

## 9. BUDGETS

- Request ceiling: 20
- HEAD ceiling: 16
- Token ceiling: 1
- Body ceiling: 1,048,576
- Redirects followed: 0
- Retries: 0
- These counters were exercised with simulated events.

## 10. SANITISATION

- Ledger fields: event, host, method, disposition.
- An unlisted synthetic field was not stored.
- Persisted marker leakage: no

## 11. RESIDUAL RISKS

- Real DNS: UNVERIFIED.
- Real TLS: UNVERIFIED.
- Real HTTP: UNVERIFIED.
- Whether job termination cancels an in-flight name lookup: UNVERIFIED.
- Python ABI: unmeasured.
- libc: unmeasured.
- Production readiness: not established.

## 12. FINDINGS

- D30R4-BASE-01. Evidence: ten local hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the protected files match. Unsupported conclusion: HEAD identifies the dirty tree. Impact: the preflight was allowed to start. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.
- D30R4-OCI-01. Evidence: five OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the preserved objects match. Unsupported conclusion: layer bytes are local. Impact: the registry was not contacted. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.
- D30R4-CLIENT-01. Evidence: discover and propose results. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the integrated client records policy and does not dispatch. Unsupported conclusion: a HEAD request was sent. Impact: the network path stays closed. Required next evidence: a cancellable resolver before any socket. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-DNS-01. Evidence: D.30-R1 discover still raises, and the new client returns false for a hard bound. Evidence classification: HISTORICAL_OBSERVATION. Supported conclusion: standard-library name lookup is still not treated as cancellable. Unsupported conclusion: the Job Object cancelled a resolver. Impact: DNS remains the reason the path is closed. Required next evidence: a tested cancellation mechanism. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-PROC-01. Evidence: one synthetic worker under the D.30-R3 supervisor. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: the wrapper assigned the worker before resume and confirmed its exit. Unsupported conclusion: that worker performed HTTP. Impact: the process boundary is wired to a non-network fixture. Required next evidence: the same wrapper around a real transport, after DNS cancellation exists. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-BUDGET-01. Evidence: simulated reserve calls. Evidence classification: SYNTHETIC_BUDGET_VERIFIED. Supported conclusion: the ceilings reject excess simulated requests and bytes. Unsupported conclusion: a registry enforced them. Impact: budgets remain local. Required next evidence: none until a network stage exists. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-LOG-01. Evidence: filtered ledger. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: unlisted fields were not stored. Unsupported conclusion: every future header is safe. Impact: logging stays on an allowlist. Required next evidence: review of any new field. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-NET-01. Evidence: source scan and this process. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: no socket, DNS, or HTTP client ran. Unsupported conclusion: registry behaviour is known. Impact: discovery remains unattempted. Required next evidence: an approved network stage. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-ABI-01. Evidence: no interpreter tag probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: this preflight measured it. Impact: wheel selection stays unresolved. Required next evidence: a dedicated measurement. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc remains unmeasured. Unsupported conclusion: Windows version supplies a Linux libc. Impact: native wheels stay unresolved. Required next evidence: a libc observation. Required approval: yes. Production impact: UNVERIFIED.
- D30R4-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this preflight did not read or change trading controls. Unsupported conclusion: a closed client makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 13. FUTURE DECISION

- Recommended next stage: no registry contact.
- Evidence gap addressed: the safety policy and the process wrapper now meet in one offline client, and that client still refuses to create a transport.
- Permissions required: a later network stage needs a fresh approval and a cancellable name lookup.
- Remaining risks: real DNS, TLS, HTTP, ABI, and libc.
- Explicit approval required: yes.

## 14. VALIDATION

- Commands executed: git HEAD, branch, targeted status, the historical discover refusal, and one synthetic worker.
- Network requests: 0
- DNS lookups: 0
- Sockets opened: 0
- Files created: D.30-R4 artifacts under data/research/adaptive_ensemble/d30_r4/.
- Files modified: none outside that new directory.
- Protected hashes: matched
- OCI hashes: matched
- Prior evidence hashes: matched
- Prohibited operations: none observed.

## 15. FINAL CLASSIFICATION

`D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED`

## 16. NEXT ACTION

D.30-R4 completed the offline integration and synthetic preflight when the classification is validated. The network path stayed closed. No real network request occurred. No DNS lookup occurred. No socket opened. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. A future network stage is not authorised. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
