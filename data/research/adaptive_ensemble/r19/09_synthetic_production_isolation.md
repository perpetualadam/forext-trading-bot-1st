# Gate H — synthetic and production isolation

SHARED INERT ADAPTER DISPATCH remains the synthetic path. PRODUCTION ELIGIBILITY DENIED.

- H01/H02: synthetic BUY and SELL each reach FakeBroker once (K119, K120, K190, K191).
- H03: `synthetic_contract=completed` while `production_eligible` is false (K121).
- H04/H05: account and market payloads cannot set trusted test context or production provenance (K122, K132, K133).
- H06/H07: `verified=True` and forged `production_eligible=True` are ignored (K123–K126). `verified_ignored` is recorded.
- H08/H09: forged and copied synthetic decisions are rejected at the production adapter (K127, K180).
- H10: the shared path uses FakeBroker and does not call `production_execution_adapter`.
- H11: the production adapter rejects synthetic decisions before the broker import.
- H12/H13: `production_authorised` and `trading_ready` stay false; the six strategies stay inactive.
- H14–H17: account, market, and margin provenance are not fabricated; numeric spread stays `POLICY_UNAPPROVED`.
- H18: a diagnostic record does not dispatch (K136).
- H19/H20: exposure holds and timeout uncertainty still stop a second synthetic request.

No environment variable, payload flag, or caller override bypasses the adapter.
