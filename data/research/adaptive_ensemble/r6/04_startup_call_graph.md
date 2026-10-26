# Startup call graph

SOURCE-REVIEWED. The process was not started. `forex_bot.app` was not imported.

```
main.py
  uvicorn forex_bot.app:app
    lifespan
      initialise_fail_closed          live orders BLOCKED
      get_connection                  schema SQL if PostgreSQL answers
      load_open_orders_from_db_into_memory
      load_reconcile_state_from_db
      build_api                       broker client object
      fetch_account_summary           network, errors logged
      run_reconciliation_once         broker read, errors logged
      mark_bot_started
      reconciliation_loop             background
      health_snapshot_loop            background
      telegram_inbound_loop           background
      run_bot                         trading loop
      start_telegram_control
```

`run_bot` calls `_cycle_symbols` then `evaluate` then `_evaluate_impl`.

Order of a new entry inside `_evaluate_impl`:

1. Session and weekend checks.
2. `pre_trade_entry_blocked_reason` (halt, kill switch, live permission, optional risk, reconcile).
3. `select_strategy`.
4. `continue_entry_after_strategy_gate`.
5. Indicators and `ai.vote`.
6. `direction_action_gate`.
7. `rl_agent.decide`.
8. `sl_tp_distance_for_entry` and `position_sizing`.
9. `broker_entry_block_reason` before a new client id.
10. `try_begin_order_submission`.
11. `execute_oanda_market_open`.

Findings:

- C01–C06: no missing import or signature break was found on this path by reading it. That is not a startup run.
- C09: `get_connection` both connects and creates tables. A failure returns None. Lifespan does not stop on that None.
- C10: startup builds a broker client and starts Telegram and the trading loop. Those are real side effects.
- C12: broker work is not optional in the current lifespan.
- C13: Telegram tasks are not optional in the current lifespan.
- C14: order reload is before `run_bot` in the source.
- C15: `initialise_fail_closed` forces BLOCKED.
- C16: strategy objects start inactive. Nothing in this startup turns them on.
- C17: a failed recovery sets the fail-closed reservation flag. SOURCE-REVIEWED.
- C18: lifespan has a finally path for tasks and the database. It was not executed.

Startup success: not claimed.
