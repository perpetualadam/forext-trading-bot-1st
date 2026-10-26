# Failure scenarios

## UNRESOLVED

Cycle 1 reached the inert adapter once. The adapter returned ambiguous. The result was `outcome=ambiguous`, exposure after the cycle was `exposure_unconfirmed`, and the local order stayed `PENDING` with an unresolved intent. There was no second broker call and no flat release.

Cycle 2, on the same store, blocked with `exposure_unconfirmed` before reservation. Inert calls: 0.

## PARTIAL

One focused cycle used a partial inert fill. The adapter was called once. The result status was `partial`. Exposure remained `exposure_unconfirmed`.

## Reservation failure

One focused cycle injected `persistence_failure=unavailable`. The result was `reservation_persistence_failed`. The inert adapter was not called.
