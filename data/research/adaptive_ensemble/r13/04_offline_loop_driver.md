# Offline loop driver

The driver is `evaluate(symbol, dependencies)` followed by `dispatch_production_iteration`.

Tests drive the coroutine with `send(None)`. They do not create an event loop, call `run_bot`, or enter the lifespan.

G01–G20 cover the blocked permission, inactive strategy, invalid direction, open position, pending, partial, unresolved, historical FILLED, missing position, simulated BUY, simulated SELL, rejection, timeout, partial fill, ambiguous result, malformed result, position-record failure, persistence failure, ignored reconciliation token, and cleanup.

Every executed case has `production_dispatch=true` and `shared_implementation=evaluate_one_instrument_iteration`.

A simulated request is not a broker order.
