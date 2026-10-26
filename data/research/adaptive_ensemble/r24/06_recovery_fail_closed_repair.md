# Recovery fail-closed repair

`read_durable_recovery` and `fetch_exec_orders_open_for_recovery` now call `force_order_recovery_fail_closed` when the PostgreSQL connection is unavailable or the recovery query raises. They still return `[], False` or raise `OrderRecoveryUnreadable`, so the failure is not turned into a successful empty book.

A completed readable recovery, including a successful query that returns no rows, calls `note_order_recovery_readable`. That clears only `_process_fail_closed`. Exposure, unresolved, and reservation holds stay. `confirm_exposure_flat` does not call it.

`evaluate` already stops on `exposure_entry_block_reason`. Once startup recovery sets the flag, the shared path returns `recovery_unreadable` before reservation and dispatch.

Persistence disabled is unchanged: `read_durable_recovery` still returns `[], False` without touching the flag, so the offline suites do not latch a database failure they did not attempt.

`orders.py` and `app.py` were not modified. `load_open_orders_from_db_into_memory` still fail-closes when `fetch_exec_orders_open_for_recovery` raises, and a later successful ingest keeps the exposure notes.
