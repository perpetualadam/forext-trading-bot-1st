# Application call graph

SOURCE-REVIEWED. The application was not imported and was not started.

When the bot is later turned on, `forex_bot/app.py` `lifespan` (about lines 333–412) does this:

1. `initialise_fail_closed()` forces effective live-order permission to BLOCKED.
2. `get_connection()` opens PostgreSQL if it can. A failure returns None and does not by itself abort startup.
3. `load_open_orders_from_db_into_memory()` reloads pending, partial, and unresolved orders.
4. Reconciliation, account summary, and Telegram tasks are created. Those steps were not run.
5. `run_bot()` is scheduled. `run_bot` calls `_cycle_symbols`, which calls `evaluate`.

Inside `_evaluate_impl`:

| Item | Location | Behaviour |
| --- | --- | --- |
| A02 Live permission | `bot_loop.py` about 1045, `pre_trade_entry_blocked_reason` | Blocks a new entry before strategy selection |
| A03 Strategy gate | `bot_loop.py` about 1154–1212, `continue_entry_after_strategy_gate` | Inactive, unknown, or unauthorised strategy returns before indicators and sizing |
| A04 Direction | `bot_loop.py` `direction_action_gate` after the vote allow check | Missing or invalid direction returns before sizing |
| A05 Sizing | `bot_loop.py` about 1367, `position_sizing` | Reached only after the earlier returns |
| A06–A08 Intent and reservation | `broker_entry_block_reason`, then `generate_client_order_id`, then `try_begin_order_submission` | A new id is refused while the symbol is unresolved or recovery is unreadable |
| A09 Broker boundary | `execute_oanda_market_open` | Not called by these tests |
| A10 Classification | `oanda_exec.classify_order_create_transport_error` | Timeout and connection loss stay ambiguous |
| A11 Unresolved save | `remember_ambiguous_outcome` and `update_order(..., UNRESOLVED)` | Process map, and the database when persistence is available |
| A12 New-order block | `insert_exec_order_pending_if_absent` under the process lock | Same symbol cannot reserve another id |
| A13 Startup recovery | `load_open_orders_from_db_into_memory` | Calls `ingest_recovery_snapshot` |
| A15 Confirmed result | Cancelled and rejected handlers call `release_resolved_intent` and `mark_order_failed_or_cancelled` | An unresolved row is not cancelled by that mark |
| A16 Missing database | `fetch_exec_orders_open_for_recovery` raises `OrderRecoveryUnreadable`; the loader sets the fail-closed flag | New broker reservations stay blocked. Startup itself is not aborted, because `app.py` was not edited |
| A17 Alternate path | `forex_bot/backtest.py` still contains the old BUY fallback | It is not on the startup path. Editing it was outside this stage |
| A18 Permission | `initialise_fail_closed` | A saved ALLOWED value does not become effective permission |

No second live broker-entry path was found in the approved modules. `try_begin_order_submission` is reached from the broker branch in `bot_loop.py`.
