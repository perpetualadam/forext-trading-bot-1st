# Remaining blockers

The missing-position entry path is blocked in source and in synthetic tests. These limits remain:

1. There is no open-position table. Restoring the position object itself would need a schema change. That change was not made. Recovery restores an uncertainty marker, not the position.
2. PostgreSQL did not execute the metadata update or the recovery query. I55 is NOT_EVALUATED.
3. `confirm_exposure_flat` does not delete a durable `UNCONFIRMED` marker. A later successful read of that row blocks again. The in-memory token is not broker proof.
4. Historical FILLED rows that have no marker are not selected by recovery. They are not treated as flat, and they are not automatically converted into a permanent block.
5. Startup calls `load_open_orders_from_db_into_memory` and then broker reconciliation. Neither was run. I56, I57, and I58 are NOT_EVALUATED.
6. The broker close path can still pop a position object without an authoritative flat token. The exposure hold stays, so the pop does not by itself allow a new entry.
