# R.76 startup recovery integration

`run_bot` in `forex_bot/bot_loop.py` lines 4498–4504:

```text
execute_startup_sequence(load_startup_broker_view())
while True:
```

This stage did not execute `run_bot`. Test 38 checks that source order and checks that `live_management_permitted()` is false before a recovery call. Test 39 places a live position, stubs candle loading, and calls `_evaluate_impl`. `apply_profit_protection` is not called.

`execute_startup_sequence` (`forex_bot/startup_recovery.py` line 148):

1. `active_journal()`, which opens the configured file and runs close recovery.
2. Insert one `RECOVERY_IN_PROGRESS` row.
3. `recover_entry_operations()`.
4. Clear the in-memory book and quarantine map.
5. Refuse `INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `UNAVAILABLE`, `UNKNOWN`, `CONFLICT`, and a missing view. The report sets `empty_book_is_not_flat`. Memory stays empty. State becomes `RECOVERY_BLOCKED`.
6. Classify broker trades that have no durable row. They are observations.
7. Quarantine a durable row whose instrument has an ambiguous, partial, conflicting, or multiple-trade entry.
8. Otherwise `evaluate_durable_row` and `publish_recovered`.
9. Finish the recovery row in `finally`.

`load_startup_broker_view` (line 38) returns `REQUEST_FAILED` when `get_api()` is missing or the read throws. A successful OpenPositions body contributes a trade only when the instrument has one trade id. Test 71 restores `T-TRADE`. Test 72 keeps two trade ids out of the managed book.

Missing, corrupt, and schema-2 journals return `RECOVERY_BLOCKED` (tests 25–27, 49, and 50). Live management stays false.

`COMPLETED_WITH_QUARANTINE` allows management of positions that were actually published. Quarantined objects are not in `positions`, and `position_management_permitted` is false for them because quarantine sets `observation_only`.
