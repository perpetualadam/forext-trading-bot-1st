# Production recovery trace

Status: SOURCE-REVIEWED, then CODE MODIFIED. PostgreSQL was not contacted.

`exec_orders.metadata` is JSONB (`forex_bot/database.py` lines 72–88). A missing key and SQL NULL both make `metadata->>'exposure_safety'` NULL. `COALESCE(..., '')` turns that NULL into an empty string. An empty string is not `CONFIRMED_FLAT`.

Before this stage, `fetch_exec_orders_open_for_recovery` and `read_durable_recovery` selected only `PENDING`, `PARTIAL`, `UNRESOLVED`, or `exposure_safety = UNCONFIRMED`. A historical FILLED row with NULL, missing, or empty metadata was omitted. The reservation check had the same hole: an unmarked FILLED row did not block a new insert.

Call path:

1. `initialise_application` production port calls `load_open_orders_from_db_into_memory`.
2. That calls `fetch_exec_orders_open_for_recovery` and then `ingest_recovery_snapshot`.
3. A query exception raises `OrderRecoveryUnreadable`. The loader fail-closes and returns 0.
4. `exposure_entry_block_reason` then blocks on the process fail-closed flag or on the ingested holds.
5. `read_durable_recovery` feeds `new_intent_block_reason` on the later entry path. It was not executed against PostgreSQL.
6. `finalize_order_fill` writes `exposure_safety = UNCONFIRMED` for new FILLED and PARTIAL rows. `confirm_exposure_flat` does not write that marker back to the database.

The offline startup path now filters injected rows with `select_rows_for_recovery` before `ingest_recovery_snapshot`. That Python predicate mirrors `RECOVERY_SELECTION_SQL`. It is not a PostgreSQL execution.
