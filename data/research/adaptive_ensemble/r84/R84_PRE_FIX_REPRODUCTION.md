# R.84 pre-fix reproduction

Executed on 26 October 2026 against the unchanged R.83 parser, before `broker_close_evidence.py` was edited. The fixtures are synthetic shapes copied from the official examples. They are not captured broker responses. The account id is the synthetic test account.

| Fixture | Result |
| --- | --- |
| BUY full close, fill `"-100"`, `tradesClosed[].units="-100"`, trade `6395`, requested 100 | `CloseReadError negative_closed_units` |
| BUY partial, fill `"-400"`, only `tradeReduced.units="400"`, requested 1000 | `CloseReadError missing_closed_trade_details` |
| Official partial shape, fill `"10"`, `tradeReduced.units="10"`, interpreted as BUY | `CloseReadError direction_mismatch` |
| Official partial shape interpreted as SELL | `CloseReadError missing_closed_trade_details` |

The full-close defect is the negative-unit rejection. The partial-close defect is that `tradeReduced` is not evidence. The official partial example also fails the BUY direction check because its fill is positive. No source was modified between this run and the recording of these four results.
