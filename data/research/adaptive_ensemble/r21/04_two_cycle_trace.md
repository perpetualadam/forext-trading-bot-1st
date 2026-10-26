# R.21 two-cycle trace

Synthetic offline cycles through `evaluate` -> `dispatch_production_iteration` -> `evaluate_one_instrument_iteration`. No production order was authorised. The observed record is `two_cycle_trace.json`.

## Scenario 1 — valid selection, FILLED hold

Cycle 1 called the real `select_deterministic` with an offline eligibility map of `scalp`. It selected `scalp` and used `scalp`. The supplied name `trend` was ignored. The inert adapter was called once. The order status is `FILLED`. Production eligibility was false.

Cycle 2 used the same in-memory store. It read `exposure_unconfirmed` and stopped with `position_already_open` before reservation. Adapter calls: 0.

## Scenario 2 — null selector

`select_strategy` with every strategy inactive returned null. The iteration blocked with `NO_STRATEGY_SELECTED`. The supplied name `scalp` was recorded as ignored. Reservation attempts: 0. Adapter calls: 0. The AI vote and RL veto were not called.

A hybrid `select_strategy` result returned one of the six names and blocked with `STRATEGY_INACTIVE` because that strategy is not active. Unknown and malformed results were supplied through the selector function under test and blocked before sizing.

## Scenario 3 — ambiguous outcome

Cycle 1 made one inert call and received `ambiguous`. The local order status is `UNRESOLVED`. Exposure is `exposure_unconfirmed`. The unresolved-intent marker is set. Those three facts describe the same attempt.

Cycle 2 read that hold and stopped with `exposure_unconfirmed`. Reservation attempted: false. Adapter calls: 0. The hold was not released.

The default `select_strategy` path still returns null because no production strategy is active. The valid name in scenario 1 came from `select_deterministic` and did not activate a production strategy.
