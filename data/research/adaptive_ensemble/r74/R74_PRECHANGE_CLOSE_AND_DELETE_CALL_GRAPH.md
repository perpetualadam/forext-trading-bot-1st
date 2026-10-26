# R.74 Pre-change Close and Delete Call Graph

Verified against the matching R.73 tree before implementation.

## Broker close submission

- `forex_bot/bot_loop.py` live branch called `run_guarded_live_close`, then `close_position(symbol)`.
- The non-live branch still called `execute_trade`, then `close_position(symbol)`.
- `forex_bot/broker_close_evidence.py` `run_guarded_live_close` reserved in process memory and then called `oanda_exec._submit_position_close_body`.
- `forex_bot/oanda_exec.py` `_submit_position_close_body` constructed `PositionClose`. `execute_oanda_market_close` still reached that helper through `_place_market_order_sync`.
- `forex_bot/trading.py` `execute_trade` still called `execute_oanda_market_close` for a live kind. The manage path no longer used it for live rows.
- `forex_bot/backtest.py` could still call `close_position`. A live row was already refused by the R.73 symbol check unless a confirmation existed.
- `forex_bot/research/adaptive_ensemble/portfolio_v2.py` has a separate research `close_position`. It is not the operational book.

## Local deletion

- `positions.close_position` refused observation rows. For a live row it called `live_local_delete_permitted(symbol)` and then `positions.pop`. That permission was symbol-only.
- `positions.close_local_position` called `close_position`.
- `broker_exit.account_disappeared_broker_position` returned `retained` unless the symbol permission was true. After that, the old tail still popped the symbol.
- `reconciliation.py` auto-fix called that helper and did not count `retained` as a consumed fix.

## What was not protected

The reservation lived in `_operations` and `_recovered`. `declare_process_restart` only moved those maps. A new process could submit again. A confirmed EUR_USD operation could authorise deletion of a later EUR_USD row in the same symbol slot.

`broker_sl_tp_hit` remained false. Protection evidence did not authorise a close. An incomplete OpenPositions body remained incomplete. A valid empty body remained `COMPLETE_EMPTY` and, after R.73, did not by itself delete a live row.
