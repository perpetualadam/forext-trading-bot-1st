# R.84 coverage equivalence

| Area | Class | Basis |
| --- | --- | --- |
| Documented full close with negative `tradesClosed` | STRONGER_COVERAGE | Previously rejected. Now confirmed on the operational path and after a process kill |
| Documented partial close with `tradeReduced` | STRONGER_COVERAGE | Previously ignored. Now partial, with remainder and quarantine |
| Positive `tradesClosed` beside a negative fill | EQUIVALENT_COVERAGE | R.82 and R.83 fixture shape still classifies 400, 999, and 1,000 |
| Universal TradeReduce sign rule | PARTIAL_COVERAGE | Schema wording and the full-close example disagree. Both tested shapes are accepted. The unsupported negative-beside-positive pair is rejected |
| Duplicate reduction counting | STRONGER_COVERAGE | Same trade in both fields is counted once |
| False full confirmation | EQUIVALENT_COVERAGE | Identity, overfill, zero, mixed open, and `tradeReduced` of the whole amount stay unconfirmed |
| R.81–R.78 | EQUIVALENT_COVERAGE | Same pass counts |
| R.82 and R.83 negative-rejection assertion | MISSING_COVERAGE as a preserved pass | The assertion is obsolete. The replacement is the R.84 signed-close tests |
| Broker idempotency and live OANDA | MISSING_COVERAGE | Synthetic fixtures and public docs only |
