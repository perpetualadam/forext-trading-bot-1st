# R.2 decision-path trace

Evidence type for this file: SOURCE-TRACED. The trading loop was not imported and was not run.

The live sequence is not the diagram in the stage prompt. Strategy selection happens before the buy/sell vote, and it only chooses a name.

## Actual order

1. Load M5 candles. `fetch_ohlcv` in `forex_bot/oanda_client.py` lines 429-449 would call OANDA. `_load_decision_candles` in `forex_bot/bot_loop.py` lines 483-516 calls it. This stage did not call it.
2. If a position is already open, manage or close it before any new entry. `bot_loop.py` `_evaluate_impl`, through about line 997. A close is not a new strategy entry.
3. If candles are missing or invalid, stop. Lines 999-1001.
4. Block a new entry when live-order authorisation is missing or blocked. `pre_trade_entry_blocked_reason` in `forex_bot/execution.py` lines 143-195, called from `bot_loop.py` lines 1013-1022.
5. Calculate routing indicators. `compute_indicators`, `bot_loop.py` lines 1024-1025.
6. Select a strategy name. `select_strategy` in `forex_bot/strategy_meta.py` lines 159-210, called at `bot_loop.py` line 1027.
7. If no name is selected, or that name is inactive, or it is not authorised, return before sizing. `bot_loop.py` lines 1066-1095.
8. Calculate the entry indicators and reject unsafe volatility. Lines 1098-1110.
9. Ask the AI ensemble for allow and direction. `ai.vote` in `forex_bot/ai_ensemble.py` lines 207-229, called at `bot_loop.py` lines 1123-1165. The default local voter is the moving-average stub in `_quant_stub_vote`, lines 33-120. External API voters are added only when keys are set, lines 245-339. No key was read and no API was called.
10. Reinforcement learning can block. It cannot replace the AI side. `RLAgent.decide` in `forex_bot/rl_agent.py` lines 28-42, used at `bot_loop.py` lines 1175-1230. SKIP stops. A BUY/SELL that disagrees with the AI side stops. An unseen state can return UNAVAILABLE when that flag is on.
11. Shared stop and target distance. `sl_tp_distance_for_entry` in `forex_bot/trading.py` lines 119-129, called at `bot_loop.py` line 1239.
12. Shared position size. `position_sizing` in `forex_bot/trading.py` lines 278-325, called at `bot_loop.py` line 1243.
13. Choose paper, window, or broker fill. `open_fill_path` in `forex_bot/execution.py` lines 205-219, called at `bot_loop.py` line 1299.
14. A broker send is `execute_oanda_market_open` in `forex_bot/oanda_exec.py`, called at `bot_loop.py` lines 1510-1519. It is reached only on the broker path after `assert_broker_order_allowed`, lines 70-91.

## B01-B18

| ID | Behaviour | Where | Risk |
|---|---|---|---|
| B01 | Market data enters through `fetch_ohlcv`. Missing API returns None. | `oanda_client.py` 429-449; `bot_loop.py` 483-516 | Not called here. |
| B02 | Indicators are `compute_indicators`, twice: once to route, once to trade. | `bot_loop.py` 1024 and 1098 | Source only. |
| B03 | External voters are optional. Default is the local moving-average stub. No votes at all means allow=False. | `ai_ensemble.py` 207-229 and 320-346 | A configured key would try the network on a real run. This run had empty tokens. |
| B04 | BUY/SELL is the ensemble direction, mostly fast average versus slow average plus a momentum check. | `_quant_stub_vote` 91-110; `bot_loop.py` 1175-1178 | If the direction is neither BUY nor SELL, line 1178 forces BUY. |
| B05 | RL can veto. It does not set a new side. | `bot_loop.py` 1175-1230 | Default RL can still pick randomly when its state flag is off. `rl_agent.py` 38-42. |
| B06 | The name is selected before the side. | `strategy_meta.py` 159-210 | Random or rotating choice among active names. |
| B07 | The name does not change BUY/SELL. Shadow rules are not called on this path. | `bot_loop.py` 1175-1178; `shadow/signals.py` is separate | The constant below is a label, not a gate. |
| B08 | An inactive name returns before sizing and before any order. | `bot_loop.py` 1076-1084 | Tested for the flag itself. The return-before-sizing line was not executed. |
| B09 | Stop and target are shared. The name only changes a paper spread label later. | `trading.py` 119-129 and 238-241 | Not six stop systems. |
| B10 | Size is equity times risk percent, divided by stop risk, default cap 1 percent. | `trading.py` 278-325 | Margin is not in this formula. |
| B11 | New entries call `pre_trade_entry_blocked_reason`, which calls `live_open_blocked_reason`. Broker sends call `assert_broker_order_allowed`. | `execution.py` 143-152; `oanda_exec.py` 70-91 | A close is not blocked by the new-order gate. `live_safety.py` 102-106. |
| B12 | The broker call is `execute_oanda_market_open`. | `bot_loop.py` 1510; `oanda_exec.py` | Not called. |
| B13 | The new-entry path cannot skip the inactive check. A protective close does not use the strategy name. | `bot_loop.py` 1076 and the earlier close block | No second entry function was found on this path. |
| B14 | A new entry cannot skip authorisation. Paper mode still hits `pre_trade_entry_blocked_reason` before sizing. | `bot_loop.py` 1013; `execution.py` 143-152 | Restart does not honour a saved ALLOWED flag. `live_safety.py` 401-404. |
| B15 | Missing candles skip the new entry. | `bot_loop.py` 499-507 and 999-1001 | Source only. |
| B16 | Unclear AI vote returns. RL SKIP or mismatch returns. A bad direction string is forced to BUY. | `bot_loop.py` 1144-1165 and 1177-1230 | The forced BUY is a real source risk if allow is true and direction is blank. |
| B17 | A timeout is classified AMBIGUOUS, then the live loop catches it as a failed outcome and marks that reservation failed. | `oanda_exec.py` 289-316 and 46-63; `bot_loop.py` 1527-1532 | The next cycle creates a new client id. That can send again after an uncertain result. Not executed. |
| B18 | Process start forces effective authorisation to BLOCKED even if the file says ALLOWED. | `live_safety.py` 401-404 | Offline tests covered the blocked and invalid files. They did not start the app. |

`STRATEGY_NAME_DOES_NOT_SET_SIDE` is defined only in `forex_bot/decision_quality/live_path.py` line 44. No runtime function reads it. The runtime agrees with it because `bot_loop.py` never calls `signal_from_indicators`.
