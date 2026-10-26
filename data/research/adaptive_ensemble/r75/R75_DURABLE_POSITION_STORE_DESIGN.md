# R.75 Durable Position Store Design

The position store is the `managed_positions` table in the same SQLite file as the close journal. `SCHEMA_VERSION` is 2 (`close_journal.py` line 31). The table is created with the journal (lines 69–107). Unique index `one_managed_trade` is on `(account_binding, trade_id)`. The primary key is `position_instance_id`.

## Why the same file

A close operation and the position it refers to need one lock and one schema version. `open_journal` still refuses a missing, corrupt, or wrong-version file. Recovery calls `active_journal()`, which runs close-operation `recover()` before any row is published.

## Columns required for identity

`position_instance_id`, `position_generation`, `account_binding`, `instrument`, `trade_id`, `direction`, `units`, `execution_kind`, `provenance`, `entry_price`, `stop_loss`, `take_profit`, `open_time`, `strategy_name`, `rl_state`, `client_order_id`, `broker_order_id`, `broker_order`, `management_status`, and `close_operation_id`.

Protection columns are stored when `persist_bot_position` (`position_recovery.py` lines 52–181) is called with a real `Position`: MFE, activation, seeded flag, exit pips, close-attempt timestamp, ATR at entry, activated MFE/ATR/giveback/exit, ATR fallback, minimum profit, and maximum adverse excursion. NULL is written when the value is absent. NULL is not replaced with the current price.

## Write order

`persist_bot_position` takes the journal lock, uses `BEGIN IMMEDIATE`, and commits before `run_guarded_live_close` reserves. An update is allowed only when the same instance id keeps the same trade id and account binding. A different trade or account on that instance is `journal_position_disagreement`. A second instance for the same trade id hits `one_managed_trade` and becomes `duplicate_position_identity`.

## Not one transaction with memory

The SQLite commit and the later `positions[symbol] = ...` publish are separate. Crash ordering is in `R75_CRASH_WINDOW_ANALYSIS.md`.

## Entry gap

`bot_loop.py` `open_position` (around lines 1921–1936) stores `broker_order_id` but does not assign `broker_trade_ids`, and it does not call `persist_bot_position`. A broker order id is not treated as a verified trade id. No trade id is invented. A restart before a later `persist_bot_position` call has no durable managed row.
