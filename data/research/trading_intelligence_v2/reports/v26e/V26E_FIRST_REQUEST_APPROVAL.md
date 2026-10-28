# First historical request — proposal only, not approval

**DO NOT EXECUTE IN V2.6E. PRODUCTION TRADING REMAINS NO-GO.**

Exact logical request:

```text
Environment: LIVE
Host: api-fxtrade.oanda.com
Method: GET
Path: /v3/instruments/EUR_USD/candles
from: 2026-09-02T10:00:00Z
to: 2026-09-02T10:49:59Z
granularity: M5
price: MBA
smooth: false
includeFirst: true
count: OMITTED
Accept-Datetime-Format: RFC3339
Accept: application/json
Accept-Encoding: identity
```

Authorization would be supplied only in memory by a separately reviewed provider;
no token or account ID belongs in this document, URL, argv, environment packet or
manifest. The endpoint has no account identifier. No account-specific alternative
is approved. Physical connections in this stage remain loopback fixtures only.

Limits: one attempt per explicit durable grant; no retry, pagination, polling,
fallback host, redirect, automatic reauthorisation or second attempt after
ambiguity. The existing controller caps the total session budget at 15 seconds,
including preparation, validation, publication and worker fencing. Cleanup time
is reserved inside that budget; OS scheduling is not a hard real-time guarantee.

Future storage: `C:\TradingResearchData\OANDA`, requiring the existing owner/SYSTEM
NTFS policy and matching held identity binding. No fallback to OneDrive or Git.
Do not assume ten candles: preserve the actual validated complete count and
coverage limitations, including a possible refusal or incomplete result.

Required separate decisions before any real attempt:

1. Confirm current non-account OEL LIVE support and the applicable account's
   entitlement; do not infer these from the configured variable names.
2. Resolve applicable private research, retention and disclosure permissions.
3. Review/authorise the inactive real credential-provider implementation, exact
   LIVE-only worker network boundary and non-reusable real-grant activation.
   No such executable grant/loader/network activation is present in this stage.
4. Recheck protected native storage and approve this exact request specification
   and total budget for one disposable session. A failure or ambiguity consumes
   that approval; it cannot be retried without a new reviewed decision.

Recommended next action: review these boundaries and unresolved public evidence.
This proposal is not consent to send the request and does not enable trading.
