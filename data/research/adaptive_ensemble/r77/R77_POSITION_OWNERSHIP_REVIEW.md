# R.77 position ownership review

R.68 behaviour is unchanged in source.

- `classify_broker_discovery` (`forex_bot/position_recovery.py` lines 445–449) returns manageable false unless the caller is describing an existing durable `bot_managed` row. Broker visibility does not create a managed position.
- `position_management_permitted` (`forex_bot/positions.py` line 70) refuses `observation_only` and `recovery_quarantine`.
- `_write_managed_position` refuses an observation row, an unknown execution kind, and a position that does not already pass `position_management_permitted`.
- Startup publishes a durable row only when `evaluate_durable_row` returns `restored_managed`. Manual, broker-only, and unknown-kind rows stay out of `positions` (tests 71–73).

A memory slot that already holds a different position instance is not overwritten after the atomic commit. The resident object gets `recovery_quarantine = True` (`entry_capture.py` lines 106–112). The new durable row remains for the next startup, when memory starts empty.

Historical partial states are quarantined by `execute_startup_sequence` (lines 191–230) and `capture_gaps` (`entry_journal.py` lines 481–513):

- `ENTRY_CONFIRMED_SINGLE_TRADE` linked to a position: `unfinalised_capture`
- `ENTRY_FINALISED` whose trade, instance, or generation disagrees: `entry_position_identity_conflict`
- durable row whose `entry_operation_id` has no entry: `position_without_entry_history`
- `ENTRY_FINALISED` with no position row: `finalised_without_position`
- confirmed entry with no position row: `confirmed_without_position`

None of those branches insert a position. A legacy R.75 row with a null `entry_operation_id` still goes through `evaluate_durable_row` when no unresolved entry exists for that instrument.

The R.68 suite was not rewritten. Its previously classified failures remain. Test 71 in the R.77 suite rechecked broker-only discovery against the current function.
