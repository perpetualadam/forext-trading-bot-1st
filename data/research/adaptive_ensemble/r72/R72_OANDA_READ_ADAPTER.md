# R.72 OANDA Read Adapter

The reader is `_request_trade` in `forex_bot/broker_protection.py` lines 202–232.

It uses the existing client:

- `forex_bot.oanda_client.get_api`
- `forex_bot.oanda_client._oanda_request`
- `oandapyV20.endpoints.trades.TradeDetails`

The account id is taken from the already-loaded `Config.OANDA_ACCOUNT_ID` and passed as the TradeDetails scope. The evidence record stores `scoped` or `missing`. It does not store the account id.

The module does not import `forex_bot.oanda_exec`. Its source does not name `OrderCreate`, `PositionClose`, `TradeClose`, `OrderCancel`, or `OrderReplace`.

## What is read

One `TradeDetails` response for the single local broker trade id. The classifier reads `trade.id`, `trade.instrument`, `trade.state`, `trade.currentUnits`, and the `stopLossOrder` and `takeProfitOrder` objects when those keys exist. Order fields used are `id`, `type`, `tradeID`, `state`, `price`, optional `units`, optional `tradeUnits`, `fillingTransactionID`, and `fillingTime` or `createTime`.

## What is not read

- Account-wide `OrdersPending`. A pending-order list can omit orders, so it is not used as proof of absence.
- `TransactionDetails`. A filling transaction id on the order is stored and is not treated as a retrieved fill.
- `OpenPositions`. Snapshot completeness remains the R.70 path.

Missing client returns `missing_client` before a request. Missing account returns `missing_account` before a request. Timeout returns `timeout`. Any other request exception returns `request_exception`. Null and non-dict bodies return `null_body` or `malformed_body`. None of those publish a confirmed state.

`R72_BROKER_READ_ADAPTER_IMPLEMENTED`

`R72_NO_ORDER_WRITES`

`R72_NO_REAL_NETWORK_EXECUTION` for this stage. Tests installed a synthetic `request` object. No practice or live host was contacted.
