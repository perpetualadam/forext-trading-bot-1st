# Position-state model

The application already distinguishes reservation PENDING, PARTIAL, FILLED, CANCELLED, and UNRESOLVED on `exec_orders.status`. REJECTED is a terminal word in the reservation policy, not a required database status. There is no stored state for an open position, a partially closed position, or a fully closed position. `positions.py` is an in-memory slot. `trades` records a closed trade after the fact. `broker_exit_pending` is an exit table and was not reused.

R.9 adds an internal marker, `metadata.exposure_safety`, on the existing JSON column. The values are `UNCONFIRMED` and `CONFIRMED_FLAT`. They are not broker states. No new table, column, or migration was added.

The process also keeps `_process_exposure`. Recovery of a snapshot restores `UNCONFIRMED`, and a FILLED row without `CONFIRMED_FLAT` is treated as unconfirmed. A stale or unknown marker fail-closes.

What remains outside this model: the position object itself is not durable. Startup can restore the uncertainty marker only if the recovery query runs and the row carries it. That query was not executed. Historical FILLED rows written before this marker are not selected by the recovery query, so they are not converted into a permanent block and they are also not proven flat.
