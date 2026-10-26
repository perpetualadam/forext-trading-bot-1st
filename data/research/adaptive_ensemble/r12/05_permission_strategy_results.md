# Permission and strategy gates

J01–J12 passed.

- The real `pre_trade_entry_blocked_reason` returns a live-order block. Without `simulation=True`, the fake broker receives nothing.
- An inactive, unknown, or missing strategy stops before sizing and before reservation.
- `HOLD`, a blank direction, and `NO_TRADE` stop at `direction_action_gate`.
- A simulated BUY and a simulated SELL reach `FakeBroker.submit` once. `production_authorised` stays false and `trading_ready` stays false.
- The six strategy objects remain inactive and unauthorised.
- The production live-safety file was not written. The synthetic state path is under this r12 directory.

A simulated request is not production authorisation and is not a broker order.
