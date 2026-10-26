# R.83 OANDA transaction semantics

Official pages read on 26 October 2026 without credentials:

- `https://developer.oanda.com/rest-live-v20/transaction-df/`
- `https://developer.oanda.com/rest-live-v20/trade-ep/`

`OrderFillTransaction.units` is "The number of units filled by the OrderFill" and the type is `DecimalNumber`. The trade-close example for a full EUR_USD close shows both the fill `units` and `tradesClosed[].units` as `"-100"`. The partial-close example uses `tradeReduced.units` of `"10"` and does not use `tradesClosed`.

`TradeReduce.units` is documented as "The number of units that the Trade was reduced by". The full-close example nevertheless stores a negative number in that field. The schema text and the example do not use the same sign convention.

`tradesClosed` is an array of `TradeReduce`. `tradeReduced` is one `TradeReduce` for a reduction. `tradeOpened` is a separate object. `orderID` and `tradeID` are different fields. `clientOrderID` and `clientExtensions` are client labels. The transaction definition includes `requestID`. None of these pages state that `clientExtensions.id` or the request comment `"idempotent client order"` makes OrderCreate or PositionClose exactly-once.

The bot's close classifier reads `tradesClosed` and rejects a negative unit. An official full-close example would therefore raise `negative_closed_units` and would not be marked fully confirmed. The bot does not read `tradeReduced`, which is the object in the official partial-close example. That is a contract conflict. The R.82 correction was not reversed and no execution code was changed from this documentation.

`BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains. A client label is not broker idempotency.
