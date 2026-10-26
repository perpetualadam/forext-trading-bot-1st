# Approval gates

Three gates. Passing one does not open the next. This B3 design does not mark any gate passed. Independent review of these documents is still required before Gate 1 can be accepted.

## Gate 1 — design acceptance

Required before Gate 1 can be accepted:

- This architecture and the threat model.
- Option A only: two GET patterns, instruments then pricing, `includeHomeConversions=true` on pricing only.
- Account summary remains deferred.
- The credential procedure in the design report: preview, exact confirmation, then hidden entry only in a later authorised stage, cancel before the first request, and no way to withdraw a request already sent.
- Unresolved contract facts left unresolved: home currency, stake mapping, GBP pip value, financing, token permission, executable size, profitability, and quote freshness.
- An independent review of these eight documents.

Passing Gate 1 authorises no live connection, no credential prompt, and no HTTPS implementation.

## Gate 2 — future offline HTTPS implementation

Would need a new written approval after Gate 1. Possible scope:

- A fixed-host GET-only transport.
- Local credential handling that matches the threat model.
- Enforcement of the 5-second request cap, the 15-second session deadline, and the 1 MiB cap, with tests that show those limits rather than only constants.
- The offline tests in `05_offline_security_test_spec.md`, with networking blocked.
- An independent review of that source and of the actual test counts.

Passing Gate 2 would still authorise no authenticated OANDA request. It would not authorise practice orders or a production change.

## Gate 3 — future authenticated read-only session

Would need another written approval after Gate 2. That approval would have to name:

- The exact executable hash.
- The two endpoints and the maximum of two requests.
- The credential procedure, including hidden entry outside chat, and the warning that the token may be allowed to trade.
- The allowed output fields and the ban on raw bodies, identifiers, and full URLs.
- Cancellation before the first request, and the statement that a sent request cannot be withdrawn.
- Residual risks: token permission `UNKNOWN`, memory exposure, dirty worktree, quote freshness `NOT_VERIFIED`, and the unresolved contract facts.
- Stop conditions: first failure stops the session, no third request, no order path, no account summary.

Gate 3 is not granted by a passing test, by HTTP 200, or by this document. It must be a separate user approval.

## Current closures

B1 and B2 live entries stay disabled. This design adds no command that prompts or connects. Production deployment remains NO-GO.
