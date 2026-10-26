# Actual trading call graph

SOURCE-REVIEWED. `run_bot` was not executed.

## Production loop

`main.py` starts uvicorn. The lifespan calls `initialise_application`. The production scheduler, and only that scheduler, creates the `run_bot` task.

`run_bot` (`forex_bot/bot_loop.py` 2595) is `while True`: account summary, pricing refresh, `_cycle_symbols`, `evolve`, `daily_report`, then `asyncio.sleep`. It was not called.

`_cycle_symbols` (666) awaits `evaluate` per symbol. `evaluate` (686) awaits `_evaluate_impl` (700).

## New-entry order inside `_evaluate_impl`

1. Load candles through `_load_decision_candles` (570), which calls the real OANDA fetch. Not used by the offline seam.
2. Read the in-memory position. An open position is managed at line 755 and returns before a new entry.
3. Session and weekend checks skip a new entry only. Open risk is managed first.
4. `exposure_entry_block_reason` at line 1090.
5. Empty candles return.
6. `broker_exit_open_blocked_reason`.
7. `pre_trade_entry_blocked_reason` at line 1115. Live authorisation blocked this process.
8. Indicators, `select_strategy`, then `strategy_entry_block_reason` at line 1176.
9. `ai.vote`, then `direction_action_gate` at line 1298.
10. RL veto, then `position_sizing`.
11. Notional, portfolio stop-risk, and USD-direction checks.
12. On the broker fill path, `decision_frame_rejection`, then `broker_entry_block_reason`, then `try_begin_order_submission` at line 1577.
13. `execute_oanda_market_open` at line 1657. The offline seam does not call this.
14. Fill handling records the order and, for a fill, leaves exposure unconfirmed.

## Offline seam

`evaluate_one_instrument_iteration` starts at line 2002. It calls the same gate functions in that order with injected inputs. It does not sleep, schedule, or call `run_bot`.
