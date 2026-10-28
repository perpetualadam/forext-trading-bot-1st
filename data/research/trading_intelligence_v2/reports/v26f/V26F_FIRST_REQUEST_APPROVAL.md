# Exact first request — proposal, not authorisation

```text
Environment: LIVE
Host: api-fxtrade.oanda.com
Port: 443
Method: GET
Path: /v3/instruments/EUR_USD/candles
Instrument: EUR_USD
granularity: M5
price: MBA
smooth: false
includeFirst: true
from: 2026-09-02T10:00:00Z
to: 2026-09-02T10:49:59Z
count: OMITTED
Maximum attempts: 1
Automatic retries: 0
Redirects: disabled
Pagination: disabled
Total deadline: 15 seconds
Storage: C:\TradingResearchData\OANDA
```

No change from oneshot.py:21 SPEC. Accept-Datetime-Format: RFC3339;
Accept: application/json; Accept-Encoding: identity. Authorization would be added
only in memory by a separately reviewed provider. No account ID is required by
this path. No alternate host/route/parameter is authorised.

This previously examined interval is for connectivity verification, not fresh
strategy evaluation. Timestamp-boundary ambiguity remains unresolved: do not
assume exactly ten complete candles. Record actual count, coverage, incompleteness
or refusal using the existing validator; do not adjust dates to force a count.

Before asking for execution approval:

1. Establish current non-account support, applicable account entitlement and
   permission for this limited research retrieval and specified local retention.
2. Separately authorise, implement and synthetically review the minimal real
   provider, literal-host DNS/TLS boundary and one-use real-grant mechanism.
   Those implementations are absent and are not authorised by V2.6F.
3. Recheck the held native archive binding/ACLs and exact source/spec hashes.
4. Obtain explicit human approval for **one authenticated GET of this exact
   specification**, with the total budget and external storage above, in that
   reviewed build and single durable session.

Failure, timeout or ambiguity consumes the attempt; no retry follows automatically.
No grant is written by this report. No token should be pasted into chat or Git.
No API probe or support contact has been sent. Stop after V2.6F.

**PRODUCTION TRADING REMAINS NO-GO.**
