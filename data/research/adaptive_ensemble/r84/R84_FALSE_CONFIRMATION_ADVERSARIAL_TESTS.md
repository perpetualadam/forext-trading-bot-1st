# R.84 false-confirmation adversarial tests

`test_05` and `test_06` try to reach `CLOSE_FULLY_CONFIRMED` with bad evidence.

| Attempt | Result |
| --- | --- |
| Correct units, wrong trade | `CloseReadError("trade_id_mismatch")` |
| Correct trade, wrong account | `CloseReadError("account_mismatch")` |
| Correct trade, wrong instrument | `CloseReadError("instrument_mismatch")` |
| Correct trade, wrong direction | `CloseReadError("direction_mismatch")` |
| Transaction id different from the requested id | `CloseReadError("transaction_id_mismatch")` |
| Empty transaction id | `CloseReadError("missing_transaction_id")` |
| Duplicate trade id in `tradesClosed` | `CloseReadError("duplicate_transaction_id")` |
| Reduction of another trade in the same fill | `CLOSE_RECONCILIATION_REQUIRED` |
| `tradeReduced` for the entire 1,000 units | Not full. `trade_reduced_is_not_full_close` |
| Negative TradeReduce beside a positive fill | `CloseReadError("negative_closed_units")` |
| Fill with no reduction fields | `CloseReadError("missing_closed_trade_details")` |
| `tradeOpened` plus a reduction | `mixed_open_and_reduce` |
| Conflicting quantities on the same trade | `contradictory_reduction` |
| 1,200 of 1,000 | `unit_mismatch` |
| Zero closed units | `zero_confirmed_units` |

None of these return `CLOSE_FULLY_CONFIRMED`.
