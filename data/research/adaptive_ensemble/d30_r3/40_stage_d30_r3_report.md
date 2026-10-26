# STAGE D.30-R3 — OFFLINE WINDOWS PROCESS-TREE CONTAINMENT AND DEADLINE-CLEANUP VALIDATION REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D30_R3_OFFLINE_PROCESS_TREE_VALIDATED`
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
- Synthetic tests run: 73
- Synthetic tests passed: 73
- Synthetic tests failed: 0
- Synthetic tests not evaluated: 0
- Recommended next action: no registry contact. Real DNS, TLS, and HTTP remain unverified.

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
- H05 historical status: `NOT_EVALUATED`
- Earlier artifacts unchanged: yes

## 5. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- OCI integrity verdict: PASS

## 6. WINDOWS CONTAINMENT ARCHITECTURE

- Job Object design: an unnamed job with kill-on-close and an active-process limit.
- API signatures: kernel32 through ctypes, with explicit argument and return types.
- Containment-before-execution: CreateProcess suspended, assign, IsProcessInJob, then ResumeThread.
- Worker assignment: membership is required before resume. The resume count is recorded.
- Descendant membership: creation FILETIME must match, and IsProcessInJob must be true, before resume.
- Breakaway controls: breakaway limit bits are not set.
- Handle ownership: the inherited list is NUL and the worker output writes. The job handle is not inherited.
- Nested-job limitations: supervisor_in_job=True.

## 7. HARNESS PREFLIGHT

- Fixed fixture allowlist: worker and descendant modes are closed sets.
- Socket prohibition: no socket import in the supervisor, worker, or descendant.
- DNS prohibition: no getaddrinfo call.
- Network prohibition: no HTTP client and no D.30-R1 client execution.
- Credential prohibition: no credential helper and no environment values in the ledger.
- Production prohibition: no application import.
- Process creation bounds: one session at a time, with a hard creation cap.
- Preflight verdict: PASS

## 8. PROCESS-TREE TESTS

- Tests run: 16
- Tests passed: 16
- Tests failed: 0
- Tests not evaluated: 0
- Worker membership: recorded from IsProcessInJob on the CreateProcess handle.
- Descendant membership: recorded only after creation-time verification.
- Worker exit verification: GetExitCodeProcess on the retained handle.
- Descendant exit verification: GetExitCodeProcess on the verified descendant handle.
- Unexpected processes: a live descendant fixture also showed two in-job conhost.exe members. They were inside the job, and the fixture count stayed at two python.exe processes.

## 9. DEADLINE AND CLEANUP TESTS

- Tests run: 15
- Tests passed: 15
- Tests failed: 0
- Operation deadline evidence: the block fixture stops on the operation clock.
- Termination initiation evidence: TerminateJobObject is requested after that stop.
- Cleanup duration: measured from cleanup start until the waits finish.
- Worker exit evidence: a non-active exit code on the worker handle.
- Descendant exit evidence: a non-active exit code on the descendant handle.
- Stage-budget evidence: later sessions keep the original monotonic origin.
- D.30-R2 comparison: deadline 0.35 seconds, total elapsed 0.534 seconds, without a descendant.

## 10. FAILURE INJECTION

- Tests run: 20
- Tests passed: 20
- Tests failed: 0
- Cleanup failures: 0
- Unexpected processes: no second fixture descendant was launched. In-job conhost.exe members were identified by file name and ended with the job.
- Unverified exits: recorded only if a handle stayed active.

## 11. BUDGET AND LOGGING SAFETY

- Supervisor-owned request counters: reserve rejects the twenty-first request, a second token, registry GET, storage, and retry.
- Supervisor-owned byte counters: excess synthetic bytes are rejected and the prior total remains.
- Worker budget isolation: a worker message does not change the snapshot.
- Descendant budget isolation: a descendant message does not change the snapshot.
- Synthetic sanitisation: unlisted fields are dropped. The ledger stores a disposition, not the payload.
- Persisted secret leakage: the written artifacts were refused if the marker fragment was present.

## 12. PROCESS AND HANDLE CLEANUP

- Worker exit: confirmed on the retained process handle.
- Descendant exit: confirmed on a separate verified handle when a descendant existed.
- Job Object closure: the job handle is closed after the wait.
- Process-handle closure: worker, descendant, and pipe handles are closed once.
- Unexpected survivors: 0
- Cleanup limitations: an active-process limit was configured. A rejected third CreateProcess was not attempted.

## 13. RESIDUAL RISKS

- Real DNS: UNVERIFIED.
- Real TLS: UNVERIFIED.
- Real HTTP: UNVERIFIED.
- Registry behaviour: UNVERIFIED.
- Windows portability: this session only.
- Job Object limitations: nested-job state was recorded. Breakaway was not enabled. A third child was not launched.
- Deadline enforcement: operation time, termination, and cleanup are separate. This does not bound a real resolver.
- Cleanup guarantees: verified for the handles this stage retained.
- Python ABI: unmeasured.
- libc: unmeasured.
- Production readiness: not established.

## 14. FINDINGS

- D30R3-BASE-01. Evidence: ten local hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the protected files match. Unsupported conclusion: HEAD identifies the dirty tree. Impact: process tests were allowed to start. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.
- D30R3-OCI-01. Evidence: five OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: preserved objects match size and digest. Unsupported conclusion: layer bytes are local. Impact: the registry was not contacted. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.
- D30R3-TREE-01. Evidence: Job Object limit readback and membership tests. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the tested worker and its one descendant were members of the supervisor job when those tests passed. Unsupported conclusion: every Windows configuration behaves the same. Impact: descendant containment is no longer the D.30-R2 unevaluated gap for this session. Required next evidence: none for this local mechanism. Required approval: yes before any network use. Production impact: UNVERIFIED.
- D30R3-RACE-01. Evidence: ResumeThread previous count. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the worker thread was still suspended when assignment finished. Unsupported conclusion: a running worker was assigned after the fact. Impact: fixture code did not run before membership. Required next evidence: the same sequence for any future real worker. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-CHILD-01. Evidence: descendant creation FILETIME and IsProcessInJob. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the descendant handle was tied to the published creation time and the intended job before resume. Unsupported conclusion: a process id alone proves identity. Impact: PID reuse was not accepted as proof. Required next evidence: the same check for any future child. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-TERM-01. Evidence: TerminateJobObject runs. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: job termination ended the worker and the descendant in the tests that passed. Unsupported conclusion: terminating the parent handle alone would have done so. Impact: descendant exit was not inferred from the parent. Required next evidence: the same split for any future real worker. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-EXIT-01. Evidence: GetExitCodeProcess on retained handles. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: exit was read from the verified handles. Unsupported conclusion: closing a handle by itself was the proof. Impact: cleanup and exit are distinct. Required next evidence: retained handles for any future child. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-TIME-01. Evidence: deadline rows. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: operation elapsed, termination, cleanup duration, and total elapsed are separate fields. Unsupported conclusion: the 10, 15, 30, and 180 second network ceilings were exercised. Impact: D.30-R2's 0.534 second total is not reused as a cleanup proof. Required next evidence: a real operation if one is ever approved. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-BUDGET-01. Evidence: simulated reserve calls. Evidence classification: SYNTHETIC_BUDGET_VERIFIED. Supported conclusion: counters stay with the supervisor across ignored worker and descendant messages. Unsupported conclusion: a registry enforced them. Impact: budgets remain local. Required next evidence: none until a network stage exists. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-LOG-01. Evidence: disposition records. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: unlisted synthetic fields were not stored. Unsupported conclusion: every future field is safe. Impact: logging is an allowlist. Required next evidence: review of any new field. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-NET-01. Evidence: source scan and this process. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: no socket, DNS, or HTTP client ran. Unsupported conclusion: registry HEAD behaviour is known. Impact: discovery remains unattempted. Required next evidence: an approved network stage. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-ABI-01. Evidence: no interpreter tag probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: pointer width is an ABI tag. Impact: wheel selection stays unresolved. Required next evidence: a dedicated measurement. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc remains unmeasured. Unsupported conclusion: the Windows version supplies a Linux libc. Impact: native wheels stay unresolved. Required next evidence: a libc observation. Required approval: yes. Production impact: UNVERIFIED.
- D30R3-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: these fixtures did not read or change trading controls. Unsupported conclusion: containment makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 15. FUTURE DECISION

- Recommended next stage: no registry contact.
- Evidence gap addressed: one contained synthetic descendant on this Windows session, with separate exit and cleanup times.
- Permissions required: any network stage still needs a fresh approval and a cancellable DNS design.
- Remaining risks: real DNS, TLS, HTTP, ABI, libc, and portability beyond this session.
- Explicit approval required: yes.

## 16. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and local synthetic workers.
- Network requests: 0
- DNS lookups: 0
- Sockets opened: 0
- Files created: D.30-R3 artifacts under data/research/adaptive_ensemble/d30_r3/.
- Files modified: none outside that new directory.
- Protected hashes: matched
- OCI hashes: matched
- Prior evidence hashes: matched
- Processes still alive after cleanup: 0
- Prohibited operations: none observed.

## 17. FINAL CLASSIFICATION

`D30_R3_OFFLINE_PROCESS_TREE_VALIDATED`

## 18. NEXT ACTION

D.30-R3 completed its offline process-tree programme when the classification is validated. Worker exit and descendant exit are verified only where the test rows say so. Deadline cleanup is recorded separately from the operation deadline. No real network request occurred. No DNS lookup occurred. No socket opened. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. A future network stage is not authorised. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
