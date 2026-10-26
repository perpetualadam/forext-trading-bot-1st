# R.84 test matrix

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1 | R.83 baseline integrity | PASS | Hashes and archive matched before the edit |
| 2 | Official full-close fixture pre-fix failure | PASS | `negative_closed_units` recorded before the edit |
| 3 | Official partial-close fixture pre-fix failure | PASS | `missing_closed_trade_details` and, as BUY, `direction_mismatch` |
| 4 | BUY full close corrected | PASS | `test_02`, `test_07` |
| 5 | SELL full close under the sign-agreement rule | PASS | `test_02`. The official example itself is the negative long-close shape |
| 6 | BUY partial via `tradeReduced` | PASS | `test_03`, `test_08` |
| 7 | SELL partial via `tradeReduced` | PASS | Official 10-unit shape and the 400-unit shape in `test_03` |
| 8 | Signed quantity retained | PASS | `signed_reduction_units` is `"-100"` for the documented full close |
| 9 | Wrong-sign rejection | PASS | Positive fill with negative `tradeReduced` raises `negative_closed_units` |
| 10 | Fill and reduction consistency | PASS | A mismatched magnitude is `fill_reduction_mismatch` |
| 11 | 400 of 1,000 | PASS | Remaining 600 |
| 12 | 999 of 1,000 | PASS | Remaining 1 |
| 13 | 1,000 of 1,000 | PASS | Remaining 0 through `tradesClosed` |
| 14 | Zero units | PASS | Reconciliation, not full |
| 15 | Overfill 1,200 | PASS | Reconciliation, remaining none |
| 16 | Decimal 400.5 | PASS | Remaining 599.5 |
| 17 | NaN | PASS | `nonfinite_units` |
| 18 | Infinity | PASS | `nonfinite_units` |
| 19 | Non-numeric and empty units | PASS | `CloseReadError` |
| 20 | Duplicate trade id | PASS | `duplicate_transaction_id` |
| 21 | Duplicate reduction evidence | PASS | Same signed value in both fields counts as 400, not 800 |
| 22 | Wrong account | PASS | `account_mismatch` |
| 23 | Wrong instrument | PASS | `instrument_mismatch` |
| 24 | Wrong trade id | PASS | `trade_id_mismatch` |
| 25 | Wrong direction | PASS | `direction_mismatch` |
| 26 | Missing transaction id | PASS | `missing_transaction_id` |
| 27 | Conflicting transaction id | PASS | `transaction_id_mismatch` |
| 28 | Mixed `tradesClosed` and `tradeReduced` | PASS | Agreement counts once. Disagreement is reconciliation |
| 29 | Unrelated trade reduction | PASS | Reconciliation |
| 30 | Open plus reduce | PASS | `mixed_open_and_reduce` |
| 31 | Operational full close | PASS | `test_07`, one PositionClose |
| 32 | Operational partial close | PASS | `test_08`, one PositionClose |
| 33 | Full close then process kill | PASS | `test_09` |
| 34 | Partial close then process kill | PASS | `test_10` |
| 35 | Ambiguous evidence then restart | PASS | `test_11`, recorder stays 1 |
| 36 | Conflicting snapshot | PASS | `test_12`, `manageable=0` |
| 37 | Stale-owner removal | PASS | `test_12` returns `None` and leaves `CLOSE_FULLY_CONFIRMED` |
| 38 | No second PositionClose | PASS | Full, partial, ambiguous, and stale cases |
| 39 | Profit-protection preservation | PASS | Hash unchanged and `ratchet=40` |
| 40 | R.83–R.78 regression preservation | PARTIAL | R.81–R.78 unchanged. R.83 and R.82 each have one obsolete negative-unit assertion |

Rows 2 and 3 record the pre-fix defect. They are not claims that the current parser still fails.
