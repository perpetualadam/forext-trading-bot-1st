# V2.6G local review decision — 2026-10-28

`TIV26G_LIVE_BRIDGE_IMPLEMENTED_OFFLINE_VERIFIED`

Baseline main: f8eabd464f766c25b81c9541df2042f4940b90a4. Local/main and
origin/main still match; existing baseline CI run 40675446522 passed all 14 jobs.
This does not constitute CI verification of the uncommitted V2.6G implementation.

Implemented locally: a disabled real credential getter, exact-host DNS/TLS
connector, worker socket policy, dormant controller hooks, shared single-attempt
exchange and synthetic tests. Normal entry, explicit reservation attempts and
direct connector/provider calls all refuse AUTHENTICATED_EXECUTION_DISABLED.
The admission gate is deliberately non-functioning; no real grant exists.

The dormant real branch reserves in the supervisor before worker creation and
retains native identity handles. Under the original archive lock, the worker
claims REQUEST_RESERVED -> REQUEST_ATTEMPTED before requesting a credential;
a second worker claim refuses. No second journal or grant issuer was added.
These real-branch ordering transitions are verified with in-memory doubles;
the existing physical HTTPS/IPC/archive lifecycle is verified with synthetic grants.
Actual admission remains deliberately unavailable and external operation untested.

Answers:

- Can the provider run only after an authorised durable reservation? Currently
  no real reservation is accepted, so real retrieval cannot run at all. The
  synthetic integration verifies getter invocation after durable claim; a future
  validator must prove reservation/session/source identity before enabling it.
- Can the worker reach only the selected destination? The dormant real branch
  fixes OANDA host:443, exact GET/path/query, one public address and verified TLS.
  Actual operation remains loopback-only. Real DNS/socket policy is tested with
  fake objects, not an API probe.
- Can timeout/crash cause a second request? All tested synthetic restart,
  timeout, crash and two-worker races refuse a second dispatch. This is not a
  runtime guarantee for a future unimplemented real-admission mechanism.
- Are real credentials inaccessible ordinarily and in tests? Yes under the
  unchanged refusing gate. Tests substitute the getter before invoking its body;
  no actual token, .env, Credential Manager or credential environment value was read.
- What must be approved? First review this exact local diff and hashes.
  Explicitly approve publication separately. Then resolve
  endpoint/account/retention questions, implement and review real admission, and
  explicitly approve one exact GET for one approved source revision/session.

All requested regressions pass; exact counts are in V26G_TEST_RESULTS.md.
Operational sources, historical test assertions, existing reports and archive
binding/security implementation retain their baseline hashes. The scheduler is
enabled and its latest checked result is 0. Its unrelated operator_attention.jsonl
change and existing ignored data/temporary directories were preserved.

Proposed commit scope: the ten source/test/CI files listed in
V26G_SOURCE_HASHES.txt and these seven reports only. No files are staged, committed
or pushed for V2.6G. A complete unified review patch is supplied as a local
delivery artifact. Per request section 12, publication of the provider/network
implementation requires explicit approval. No authenticated request, API-host
probe, real grant, trading enablement or support message occurred.

**STOP AFTER V2.6G. PRODUCTION TRADING REMAINS NO-GO.**
