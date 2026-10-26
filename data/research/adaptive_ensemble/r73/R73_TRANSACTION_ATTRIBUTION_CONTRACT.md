# R.73 Transaction Attribution Contract

`interpret_close_response` (line 319) reads the position-close body. `apply_transaction_body` (line 364) runs only after `_fetch_transaction` (line 445) returns a transaction object.

A transaction id on the close body is a reference. `transaction_body_retrieved` becomes true only after the GET returns a dict.

Full confirmation requires all of the following on that retrieved body:

- `type` is `ORDER_FILL`
- `id` equals the id named by the close response
- `accountID` equals the configured account
- `instrument` equals the local instrument
- fill `units` are negative for BUY and positive for SELL
- `tradesClosed` contains the local trade id once
- absolute closed units for that trade equal the requested units
- no other trade is closed in the same transaction

Otherwise the state is partial, reconciliation-required, confirmation-pending, or ambiguous. The local row is not deleted.

`R73_BROKER_TRANSACTION_EVIDENCE_IMPLEMENTED`

`R73_CLOSED_UNITS_MATCHED`
