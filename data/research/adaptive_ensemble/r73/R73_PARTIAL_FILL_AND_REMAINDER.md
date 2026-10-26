# R.73 Partial Fill and Remainder

A retrieved fill whose closed units for the local trade are greater than zero and less than the request becomes `CLOSE_PARTIALLY_CONFIRMED`.

The operation stores the confirmed quantity and the remainder. Local `Position.units` is not rewritten. `close_position` returns `None`. The same operation blocks another submission. The remainder is not sent automatically.

Zero closed units and a larger-than-requested quantity are `CLOSE_RECONCILIATION_REQUIRED`, not a full close. A transaction that also closes a different trade is reconciliation-required.

`R73_PARTIAL_FILL_NOT_TREATED_AS_FULL`
