# First request remains unapproved

```text
Environment: LIVE
Host: api-fxtrade.oanda.com:443
Method: GET
Path: /v3/instruments/EUR_USD/candles
granularity: M5
price: MBA
smooth: false
includeFirst: true
from: 2026-09-02T10:00:00Z
to: 2026-09-02T10:49:59Z
count: omitted
Attempts: 1; retries: 0; redirects: disabled; pagination: disabled
Total budget: 15 seconds including fencing/publication
Storage: C:\TradingResearchData\OANDA
```

No change from V2.6F. No account ID belongs in this route, report or grant metadata.
This previously examined interval is for connectivity verification; timestamp-boundary
ambiguity remains, so neither exactly ten candles nor complete coverage is assumed.

Retain V2.6F findings:

`ENDPOINT_SUPPORT_NOT_RUNTIME_VERIFIED`

`USAGE_PERMISSION_NOT_FULLY_ESTABLISHED`

The existing client and official specification describe the non-account route;
current public pricing documentation describes an account-specific alternative.
Do not substitute it. The reviewed April 2026 OEL terms support internal research
conditionally; this account's applicable agreement and historical retention rights
remain unresolved. Implementation approval supplies neither entitlement nor data-use
permission. See ../v26f/V26F_ENDPOINT_AND_PERMISSIONS.md for official sources.

Unsent OANDA questions: does the applicable OEL LIVE account support this exact
non-account route; may one private research response be securely retained locally,
for how long and subject to which copy/deletion obligations; what separate
permission applies to later multi-year archival retrieval? No support message sent.

Before one real GET:

1. Review local source diff/hashes/tests and explicitly approve publishing the
   security-sensitive change.
2. Resolve endpoint, account entitlement and limited-use/retention conditions.
3. Separately review/authorise the exact real admission mechanism;
   no real approval is accepted or created in this stage.
4. Recheck native archive binding/ACLs and approve **one authenticated GET of this
   exact specification**, tied to that approved source revision, hashes and unique
   durable session. Failure/ambiguity consumes the attempt; no automatic retry.

No request or API-host probe was sent; actual tokens were not read. No grant exists.
**STOP AFTER V2.6G. PRODUCTION TRADING REMAINS NO-GO.**
