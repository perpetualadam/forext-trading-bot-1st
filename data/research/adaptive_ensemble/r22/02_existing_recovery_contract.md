# Existing recovery contract

Startup recovery lives in `initialise_application`. In offline mode it does not start the trading loop. When the caller supplies recovery rows, or a provider through the existing `_CALL_RECOVERY` branch, startup calls:

1. `select_rows_for_recovery` — the same selection rule as `RECOVERY_SELECTION_SQL`. It keeps `PENDING`, `PARTIAL`, `UNRESOLVED`, and `FILLED` rows that are not marked `CONFIRMED_FLAT`. A corrupt row or an unknown status fail-closes.
2. `ingest_recovery_snapshot` — rebuilds in-memory orders and the exposure, blocking, and unresolved maps. Recovered orders are marked `source=db_recovery`. A missing client id, a duplicate id with a conflicting identity, a bad metadata marker, or an unreadable snapshot fail-closes.

`read_durable_recovery` and `fetch_exec_orders_open_for_recovery` are the PostgreSQL readers. With persistence disabled they do not treat a missing database as an empty book: the durable read is unreadable. `confirm_exposure_flat` never releases a hold from caller input.

R.22 did not call `get_connection`, `lifespan`, or `run_bot`. The offline startup branch above is the recovery boundary that was executed.
