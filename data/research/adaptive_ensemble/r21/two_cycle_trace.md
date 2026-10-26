# R.21 two-cycle trace

Synthetic offline cycles. No production order was authorised.

FILLED cycle 1 used selector result `mean_reversion` and ignored supplied `trend`.
The inert adapter was called 1 time. The order status is FILLED. Production eligibility was False.
FILLED cycle 2 read `exposure_unconfirmed` and stopped with `position_already_open` before reservation. Adapter calls: 0.

Ambiguous cycle 1 made 1 inert call and recorded status UNRESOLVED with exposure `exposure_unconfirmed`.
Ambiguous cycle 2 stopped with `exposure_unconfirmed`. Reservation attempted: False. Adapter calls: 0.

The default select_strategy path still returns null because no production strategy is active. The valid name above came from select_deterministic with an offline eligibility map. That map does not activate a production strategy.
