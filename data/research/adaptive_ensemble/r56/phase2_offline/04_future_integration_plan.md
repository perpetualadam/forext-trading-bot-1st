# Future integration plan

This document does not authorise the integration. No production file was changed.

## Where the raw documents exist

| Need | Function | Response becomes available | What the caller receives today |
| --- | --- | --- | --- |
| Account | `forex_bot/oanda_client.py` `fetch_account_summary` lines 140–194 | Local name `data` at line 156, immediately after `_oanda_request` | A reduced snapshot at lines 172–181. The raw document is not returned. `id` is inside that snapshot and must not be logged |
| Pricing | `forex_bot/oanda_client.py` `fetch_pricing_snapshot` lines 503–584 | Local name `data` at line 544 | `instrument -> ManageQuote`. Home conversions are not read. The request at line 542 is only `instruments` |
| Sizing notes | `forex_bot/bot_loop.py` `_evaluate_impl` lines 1428–1432 | After `position_sizing` and `cap_position_units`, before `open_fill_path` | Local Python numbers. They are bot-calculated approximate USD risk, not a broker pip value |

`account_core` in `forex_bot/oanda_account_adapter.py` lines 24–69 is the parser `fetch_account_summary` already calls. A future hook should pass a copy of `data` from line 156 into `account_diagnostics.build`. It should not pass the reduced snapshot if the goal is to see fields the snapshot drops.

A future pricing hook should pass a copy of `data` from line 544 into `pricing_diagnostics.build`. That copy still will not contain home conversions until a separately authorised change adds `includeHomeConversions=true` to the existing `PricingInfo` parameters. That query change is not part of a log-only patch.

## Smallest later connection

1. Keep this adapter as the only logger. Do not add a second OANDA connector.
2. In a new process entry, import only the read functions required for the authorised calls. Do not import `forex_bot.app`, `forex_bot.bot_loop`, `forex_bot.trading`, `forex_bot.execution`, or `forex_bot.oanda_exec`.
3. After each read returns, `copy.deepcopy` the raw dictionary and call the matching `build` function in this directory. Write the result with `diagnostic_writer.write_record`.
4. Do not start that entry through `main.py`.

## Why the current client is not an isolated read API

`build_api` (`oanda_client.py` lines 104–126) constructs `oandapyV20.API` with `Config.OANDA_ACCESS_TOKEN`. Importing `oanda_client.py` also imports `forex_bot.config`, and that module calls `load_dotenv()` at import. This phase did not import it.

The same module does not define `OrderCreate` or `PositionClose`. Those calls are in `oanda_exec.py` `_place_market_order_open_sync` line 504 and `_place_market_order_sync` line 423. They use `get_api()` from `oanda_client.py`. The client object is therefore shared between reads and account-changing calls.

`main.py` lines 19–25 starts `forex_bot.app:app`. The lifespan starts `run_bot`, reconciliation, and the mode-switch routes. `run_bot` calls `fetch_account_summary` and then `_evaluate_impl`. The open tail at `bot_loop.py` lines 1704–1706 returns before `OrderCreate`. `trading.execute_trade` lines 391–398 still calls `execute_oanda_market_close` when the position kind is `live`. `paper_broker` and `live_broker` enable those broker calls. The host still follows `TRADING_MODE`.

Because the read client and the write helpers share one API object inside one process, a copy of the response cannot by itself make `main.py` data-only. A future data-only collector needs both of these, and neither is authorised now:

- An entry point that never imports the write modules.
- A guard inside `execute_oanda_market_open` and `execute_oanda_market_close` that raises before `api.request` when that entry is the process being started.

Until both exist, the production classification remains `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
