# Offline end-to-end results

All scenarios used `evaluate_one_instrument_iteration` and `FakeBroker`. Real broker call count is 0 in every row. Selector, AI vote wrapper, and RL veto ran on the paths that reach them. Account and market gates that return earlier did not dispatch the adapter.

| ID | Scenario | Result | Adapter calls | Notes |
|---|---|---|---|---|
| G01 / I106 | BUY inside enabled test caps | PASS | 1 | selector, vote, RL ran |
| G02 / I107 | SELL inside enabled test caps | PASS | 1 | |
| G03 / I108 | Gross-notional breach | BLOCKED_AS_DESIGNED | 0 | cap enabled in the test only |
| G04 / I109 | Unit-cap breach | BLOCKED_AS_DESIGNED | 0 | cap enabled in the test only |
| G05 / I110 | Missing pending exposure | BLOCKED_AS_DESIGNED | 0 | `notional_exposure_unreadable` |
| G06 / I111 | Daily-loss breach | BLOCKED_AS_DESIGNED | 0 | flag enabled in the test only |
| G07 / I112 | Drawdown breach | BLOCKED_AS_DESIGNED | 0 | flag enabled in the test only |
| G08 / I113 | Later entry after halt | BLOCKED_AS_DESIGNED | 0 | same process |
| G09 / I114 | Fabricated reset | BLOCKED_AS_DESIGNED | 0 | halt remains |
| G10 / I115 | Wide numeric spread | PARTIAL | 1 | `spread_limit=not_approved`; no approved threshold |
| G11 / I116 | Missing bid | BLOCKED_AS_DESIGNED | 0 | |
| G12 / I117 | Crossed quote | BLOCKED_AS_DESIGNED | 0 | |
| G13 / I118 | Stale supplied quote | BLOCKED_AS_DESIGNED | 0 | existing 90-second window |
| G14 / I119 | Short lookback | BLOCKED_AS_DESIGNED | 0 | required 50 |
| G15 / I120 | Malformed candle | BLOCKED_AS_DESIGNED | 0 | |
| G16 / I121 | Missing provenance | PASS | 1 | synthetic harness, not broker-verified |
| G17 / I122 | Missing account | BLOCKED_AS_DESIGNED | 0 | |
| G18 / I123 | Unverified account | BLOCKED_AS_DESIGNED | 0 | |
| G19 / I124 | Conflicting equity | PASS | 1 | balance 5000 accepted |
| G20 / I125 | Missing margin | PARTIAL | 1 | `not_implemented` |
| G21–G25 | Position and reservation holds | BLOCKED_AS_DESIGNED | 0 | |
| G26–G29 | RL veto, invalid vote, inactive strategy, reservation failure | BLOCKED_AS_DESIGNED | 0 | |
| G30–G33 | Timeout, ambiguous, partial, record failure | PASS | 1 | exposure held; no retry |
| G34 | Duplicate client id | BLOCKED_AS_DESIGNED | 0 | |
| G35 | Cleanup | PASS | 0 | no PostgreSQL connection |

Production account provenance, production market provenance, PostgreSQL, the broker, and profitability stay NOT_EVALUATED.
