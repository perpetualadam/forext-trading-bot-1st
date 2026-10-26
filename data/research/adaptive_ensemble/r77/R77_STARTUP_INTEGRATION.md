# R.77 startup integration

`run_bot` (`forex_bot/bot_loop.py` lines 4535–4543) calls `run_startup_and_one_iteration(Config.SYMBOLS)` once, then loops on `_execute_bot_cycle`. The first call and each later cycle keep their own exception log. This stage did not call `run_bot`.

`run_startup_and_one_iteration` (lines 4523–4532) calls `execute_startup_sequence(load_startup_broker_view())` when no view is injected, then awaits one `_execute_bot_cycle`. The harness passes a synthetic `broker_view`, so the read-only loader is not required for that test. The production branch still contains the exact call `execute_startup_sequence(load_startup_broker_view())`.

`execute_startup_sequence` (`forex_bot/startup_recovery.py` lines 148–247) order:

1. `active_journal`, which validates the file and runs close-operation recovery.
2. Claim `RECOVERY_IN_PROGRESS`. A second claim returns `recovery_already_in_progress` and does not publish.
3. `recover_entry_operations`.
4. Clear in-memory `positions`.
5. Refuse incomplete, malformed, failed, stale, unavailable, or missing snapshots with `empty_book_is_not_flat`. A missing API client becomes `REQUEST_FAILED` in `load_startup_broker_view` (lines 38–49).
6. Classify broker trades that have no durable row. `classify_broker_discovery` returns manageable false for `broker_only`, `manual`, and any other non-`bot_managed` provenance.
7. `evaluate_durable_row` checks protection fields, ratchet completeness, and trade identity.
8. Quarantine partial entry states before that evaluation.
9. `publish_recovered` puts only a manageable decision into `positions`.
10. `capture_gaps` records finalised or confirmed entries that have no position row.
11. Finish the recovery run. `live_management_permitted` is true only for `RECOVERY_COMPLETED` and `RECOVERY_COMPLETED_WITH_QUARANTINE` (lines 106–108).

`_evaluate_impl` checks that gate before `apply_profit_protection` (bot_loop lines 796–802). There is no boolean argument that overrides it.

A blocked recovery leaves durable rows in SQLite and out of `positions` (test 68). `COMPLETE_EMPTY` does not delete a durable live row (test 65).
