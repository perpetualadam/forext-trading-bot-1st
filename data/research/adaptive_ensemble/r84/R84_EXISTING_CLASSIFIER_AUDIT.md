# R.84 existing classifier audit

Source inspection of `forex_bot/broker_close_evidence.py` before the R.84 edit. The pre-fix hash was `3c879729a0c70138f6a317473767e8dfec8d2417c2d38d236478a3a8a190e9db`.

`interpret_close_response` accepts one fill section and records its transaction id. It does not read `tradesClosed` or `tradeReduced`. Unit confirmation happens in `apply_transaction_body` after TransactionDetails.

The pre-fix `apply_transaction_body` required:

- Transaction type `ORDER_FILL`.
- Transaction id equal to the fill id.
- Account and instrument equality.
- BUY fill units strictly negative, and SELL fill units strictly positive.
- `tradesClosed` present as a list.
- Every `tradesClosed[].units` value greater than or equal to zero. A negative value raised `CloseReadError("negative_closed_units")`.
- The matching trade's positive units summed once. A repeated trade id raised `CloseReadError("duplicate_transaction_id")`.

`tradeReduced` was not read. A documented partial close therefore never became `CLOSE_PARTIALLY_CONFIRMED` through that object.

The assumptions that conflict with the official examples:

1. `tradesClosed[].units` was treated as an unsigned magnitude, so the full-close example value `"-100"` was rejected.
2. Absence of `tradesClosed` was `missing_closed_trade_details`, so `tradeReduced` was ignored.
3. A positive fill was a direction mismatch for BUY. The official partial example has a positive fill, so it cannot be a BUY close under the existing direction rule.

Positive `tradesClosed` beside a negative BUY fill was the R.82 and R.83 fixture shape. That shape is the schema sentence read as a magnitude. It is not the full-close example. The R.84 parser keeps that shape working and also accepts the example's matching negative signs.

Identity checks for account, instrument, trade id, and transaction id were already strict. Those checks remain. `orderID` is not used as `tradeID`.
