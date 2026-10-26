# R.76 entry journal schema

File: `forex_bot/close_journal.py`

`SCHEMA_VERSION = 3`

Connections use `isolation_level=None`. `_configure` (line 691) sets WAL and refuses a journal mode other than WAL. `synchronous=FULL` is required. The busy timeout comes from `CLOSE_JOURNAL_BUSY_MS`.

## `entry_operations`

Created in `SCHEMA_SQL` after `managed_positions`. Fields include:

- `operation_id`, `owner_token`
- `account_binding`, `instrument`, `direction`, `requested_units`
- `position_instance_id`, `position_generation`, `client_order_id`
- `strategy_name`, `stop_loss`, `take_profit`, `entry_reference`
- `initial_max_profit_pips`, `initial_protection_active`, `atr_at_entry_pips`
- `submission_intent`, `network_permit`, `submission_state`, `outcome`
- `broker_order_id`, `broker_trade_id`, `transaction_ids`
- `recovery_status`, `error_classification`
- `created_at`, `updated_at`, `schema_version`

Index: `one_unresolved_entry` on `(account_binding, client_order_id)` where `outcome != 'ENTRY_FINALISED'`.

## `managed_positions`

The R.75 table gains nullable `entry_operation_id`. `store_incomplete_position` omits that column. `persist_bot_position` writes it on insert and does not change it on a later protection update.

`one_managed_trade` remains unique on `(account_binding, trade_id)`.

## `recovery_runs`

Columns: `run_id`, `state`, `owner_token`, `created_at`, `updated_at`.

Index: `one_recovery_in_progress` on `state` where `state = 'RECOVERY_IN_PROGRESS'`. A second in-progress insert fails. There is no lease takeover. A crashed in-progress row keeps later startups at `RECOVERY_BLOCKED`.

## Close table

`close_operations` and `one_unresolved_close` are unchanged in role. `CloseSubmissionPermit` and `EntrySubmissionPermit` are different types. `claim_network_permit` is not `claim_entry_permit`.
