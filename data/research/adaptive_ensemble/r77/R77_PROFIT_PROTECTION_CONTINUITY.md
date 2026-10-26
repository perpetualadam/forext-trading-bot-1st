# R.77 profit-protection continuity

`forex_bot/profit_protection.py` was not edited. SHA-256 remains `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

With the process environment left at the code defaults, the R.77 suite observed:

- `profit_protection_trigger_percent()` = 0.67
- `profit_protection_atr_period()` = 14
- `profit_giveback_atr_multiplier()` = 0.5
- `profit_giveback_pips()` = 4.0

`session_rules.flatten_for_weekend` was not edited. The R.71 suite passed 8 tests.

`commit_verified_entry` writes the initial position with MFE 0 and protection inactive. A second finalisation of the same identity returns before `_write_managed_position`. Test 12 stored exit pips 3.5 through `persist_protection_progress`, called `record_entry_response` again, and read 3.5 back from SQLite.

`persist_protection_progress` (`position_recovery.py` lines 423–442) still refuses a lower exit-pips value and refuses active-to-inactive. `_activated_without_ratchet` (lines 273–285) quarantines an active row whose ratchet fields are NULL. Test 18 nulled the stored stop and startup quarantined `missing_management_state` without reconstructing it from a price. `evaluate_durable_row` does not take a market price.

Repair updates only `recovery_runs.state` and inserts an audit row. It does not assign `max_profit_pips` or any ratchet column.
