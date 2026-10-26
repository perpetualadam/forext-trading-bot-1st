# Ambiguous order state

## What the model already said

`OrderStatus` includes `PENDING`, `PARTIAL`, `FILLED`, `CANCELLED`, and `UNRESOLVED`.

A new reservation starts as `PENDING`. Recovery treats `PENDING`, `PARTIAL`, and `UNRESOLVED` as active. `FILLED` does not release exposure unless the stored marker is exactly `CONFIRMED_FLAT`. `confirm_exposure_flat` always returns false.

`persist_unresolved_order` writes status `UNRESOLVED` only when order persistence is enabled. Offline runs set `PERSIST_EXEC_ORDERS=0`. Calling that persist path from the shared iteration would mark the process fail-closed and make the next cycle report `recovery_unreadable` instead of the exposure hold. That call is not used here.

## Repair

On timeout, connection failure, ambiguous, malformed, or unclassified outcomes, the shared iteration still notes unconfirmed exposure and restores the unresolved intent. If the local order is still `PENDING`, it now becomes `UNRESOLVED` with detail `ambiguous_broker_outcome`. No database write is made.

`PARTIAL` stays `PARTIAL`. `FILLED` stays `FILLED`. Both keep the exposure hold.

The next cycle reads that hold before reservation. A filled cycle also has a local position, so it stops with `position_already_open` after recording `exposure_read=exposure_unconfirmed`. An ambiguous cycle has no new position, so it stops with `exposure_unconfirmed`. Neither cycle retries or releases the hold.

This is in-memory state. It is not evidence that a restart would reload the same order from PostgreSQL.
