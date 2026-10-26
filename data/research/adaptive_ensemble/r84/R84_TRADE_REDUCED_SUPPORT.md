# R.84 tradeReduced support

Executed by `test_03_documented_partial_closes_keep_remainder` and `test_08_operational_partial_does_not_resubmit_or_publish_remainder`.

BUY partial: fill `"-400"`, `tradeReduced.units="-400"`, requested 1,000. Result: `CLOSE_PARTIALLY_CONFIRMED`, confirmed 400, remaining 600, signed `"-400"`.

The official partial example: fill `"10"`, `tradeReduced.units="10"`, USD_CAD trade `6397`, interpreted as SELL, requested 1,000. Result: partial, confirmed 10, remaining 990.

SELL 400 of 1,000 with positive `tradeReduced` remains 600.

The operational partial path uses one synthetic PositionClose and one TransactionDetails body with `tradeReduced`. The position units stay 1,000. A second `run_guarded_live_close` does not add a PositionClose. `close_confirmed_live_position` returns `None` because the state is partial. The position stays in memory and is not rewritten to 600.

A positive `tradesClosed` value of `"400"` beside a negative fill still produces the same 400/600 partial. That preserves the R.82 and R.83 fixture shape.
