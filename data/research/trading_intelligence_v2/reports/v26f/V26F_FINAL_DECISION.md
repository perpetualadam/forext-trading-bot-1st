# V2.6F readiness decision — 2026-10-28

`TIV26F_READINESS_PARTIALLY_VERIFIED`

Baseline: main, `5061ad42de3d46fd90b4c26e0d90f1194b0b5dff`.
The pre-existing modification to scheduler/operator_attention.jsonl is unrelated
and preserved. Existing reports, protected data, scheduler and runtime code are
unchanged by this review. Only these five requested reports are added.

The exact schema and synthetic one-shot controls pass focused checks. The real
provider remains disabled, real grants remain unsupported, and the worker still
permits only fixture loopback connections. No real credentials, .env, credential
manager or environment values were read. No API-host probe or authenticated
OANDA request occurred. Production trading remains **NO-GO**.

Explicit answers:

- Is the existing candle API suitable? Its existing non-account GET contract is
  suitable in schema for one historical read. Current account support remains
  `ENDPOINT_SUPPORT_NOT_RUNTIME_VERIFIED`; no account-specific substitution.
- Are permissions sufficient? Not established for this account and exact local
  retention scope. Public internal-research provisions are supporting evidence,
  not proof of applicable account entitlement or unlimited storage rights.
- Can a token be delivered safely? The reviewed future design confines it to
  post-reservation anonymous IPC and worker memory, without importing trading.
  A usable loader has deliberately not been implemented or tested with a real token.
- Can the worker connect only to the approved endpoint? Today it cannot connect
  to OANDA at all. The proposed future network change is restricted to one exact
  host/port and guarded request; it still needs implementation and synthetic review.
- What needs approval? Resolve endpoint/account/retention conditions, then
  separately authorise the narrowly scoped provider/network/grant implementation
  and its review. Only after that, explicitly approve one attempt of the exact
  request in V26F_FIRST_REQUEST_APPROVAL.md. This report creates no grant.

Results: 50 native synthetic HTTPS tests, 11 native storage checks and 2 focused
proxy/archive tests passed, all exit 0, no failures/errors/skips. See
V26F_TEST_RESULTS.md for coverage and source references. Full historical suites
were not rerun locally because runtime code did not change. Hosted CI and the
exact published SHA are reported in the delivery message after push.

Recommended next action: resolve the concise OANDA questions in
V26F_ENDPOINT_AND_PERMISSIONS.md without transmitting a token or account identifier
in this repository. No support contact is sent by this stage. Stop after V2.6F.
