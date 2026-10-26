# R.84 identity and transaction validation

Executed by `test_06_identity_rejects_false_confirmation`.

A full-close body with the correct trade, account, instrument, direction, and transaction id can confirm. The same body is rejected when the trade id, account, instrument, direction, or transaction id differs. An empty transaction id raises `missing_transaction_id`.

`orderID` on the fixture is `ORD-R84` or the example order id. `tradeID` is a different value. The parser reads `tradeID` from the TradeReduce. It does not substitute `orderID`.

`clientExtensions` containing `idempotent client order` does not change the unit decision. It is not treated as broker idempotency.

`resolve_from_retrieved_transaction` on an already finalised operation returns `CLOSE_FINALISED` and leaves the stored confirmed units at 1,000. A second application does not become 2,000.

Position instance and generation are checked by `close_confirmed_live_position` and by `_position_still` before submission. They are not fields of the OANDA fill. A stale recovery owner fails the R.83 epoch fence before those checks, which `test_12` executes.
