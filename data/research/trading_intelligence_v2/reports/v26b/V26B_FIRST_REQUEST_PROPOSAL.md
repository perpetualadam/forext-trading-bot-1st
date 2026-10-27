# V2.6B First Request Proposal

PROPOSED ONLY — NOT APPROVED, NOT EXECUTED.

LIVE host api-fxtrade.oanda.com; GET /v3/instruments/EUR_USD/candles.
Fixed previously examined period chosen to avoid consuming a new holdout.
The existing local archive contains all10 completed starts in this interval;
that does not guarantee future service availability.

Exact proposed query:
```
granularity=M5&price=MBA&smooth=false&includeFirst=true&from=2026-09-02T10%3A00%3A00%2B00%3A00&to=2026-09-02T10%3A49%3A59%2B00%3A00
```
Boundary semantics remain unresolved: start-filter models retain ten, while a
completion-filter model returns nine. The query below requires confirmation.

Logical range[2026-09-02T10:00:00Z,2026-09-02T10:50:00Z). Ten possible M5
starts; count is omitted with both bounds. Validate at most10 unique, completed,
in-range candles. Unknown/missing bars remain unknown; do not manufacture10.

One authenticated attempt total; attempts=1; no redirect, pagination, polling,
account/order endpoint, trading loop, fallback host or retry after any result.
No token in URL/CLI/subprocess. Do not call the multi-batch acquire orchestration.

Before approval: exact non-account contract and UK usage confirmation, secure
credential method, reviewed external archive bridge, single-use call budget and
short strict timeout design. Existing15s socket/30s body-loop settings are not a
proved total wall-clock bound. This proposal is not executable authorisation.
No HTTP request to this API URL was made.

No authenticated requests. Production remains NO-GO.
