# R.84 full-close evidence

Executed by `test_02_documented_buy_and_sell_full_closes` and `test_07_operational_full_and_partial_paths`.

The documented BUY shape uses fill units `"-100"` and `tradesClosed[].units="-100"`. Requested 100. Result: `CLOSE_FULLY_CONFIRMED`, confirmed 100, remaining 0, signed value `"-100"`.

A 1,000-unit BUY full close uses fill `"-1000"` and `tradesClosed` `"-1000"`. The operational path runs startup, persists the position, claims one close, sends one synthetic PositionClose, and reads synthetic TransactionDetails. The journal row is `CLOSE_FULLY_CONFIRMED` with confirmed 1,000 and remaining 0. Calling the same transaction again through `resolve_from_retrieved_transaction` leaves confirmed units at 1,000. `close_confirmed_live_position` then removes the in-memory position and finalises the journal row. A later resolve returns `CLOSE_FINALISED` and does not add the units again.

The SELL full close uses fill `"1000"` and `tradesClosed` `"1000"`. Result: `CLOSE_FULLY_CONFIRMED`, remaining 0, signed value `"1000"`. The official full-close example is the negative long-close shape. The positive SELL shape is that same sign-agreement rule applied to a short. It is not a second official example.

`tradeReduced` equal to the whole requested amount does not become `CLOSE_FULLY_CONFIRMED`. The full-close example uses `tradesClosed`. The result is `trade_reduced_is_not_full_close`.
