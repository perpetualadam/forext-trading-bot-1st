# Execution contract trace

SOURCE-REVIEWED. `execute_oanda_market_open` was not called.

The shared decision builds one argument mapping in `broker_open_arguments`. `production_execution_adapter` is the only function that passes that mapping to `execute_oanda_market_open`. Tests never call `production_execution_adapter`.

Existing broker signature: symbol, position units, direction, client order id, stop loss, take profit, execution kind, entry quote. Instrument names are `BASE_QUOTE` with an underscore. BUY units are positive and SELL units are negative inside the broker function, after taking the absolute magnitude. The shared path sends the positive sized magnitude and the direction. `broker_signed_units` records the sign rule and does not place an order.

The legacy tail still returns before any broker call. The continuation sentinel is never produced.

Timeout, partial, ambiguous, malformed, and rejection outcomes stay on the existing classification path. Uncertain results do not retry.
