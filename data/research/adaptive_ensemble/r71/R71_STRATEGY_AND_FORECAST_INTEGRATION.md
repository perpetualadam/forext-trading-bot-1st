# R.71 Strategy and Forecast Integration

## Reachable chain

`main.py` starts uvicorn on `forex_bot.app:app` (lines 19–25). The app lifespan can create `run_bot` (`app.py` 633). `run_bot` fetches an account summary, refreshes prices, and calls `_cycle_symbols` (`bot_loop.py` 4416–4424). Each symbol calls `evaluate`, which calls `_evaluate_impl` when no dependency object is injected (720–732).

If a permitted position exists, the chain stops in management: quote, profit protection, local or broker close. It does not select a strategy.

If no position exists, `_evaluate_impl` calls `dispatch_production_iteration` (1135). Unless the status is `continue_existing_production_broker`, it logs a block and returns (1139–1148). The producer of that decision returns `blocked` for a non-simulation call and also refuses a simulation call (3336–3348). The continuation status is not assigned. Strategy selection at line 1191, the RL gate at 1412, and `position_sizing` at 1443 are not reached.

## Components

| Component | Where it lives | Connected to an order |
| --- | --- | --- |
| `select_strategy` | `bot_loop.py` after the block | No |
| `ai_ensemble` | Imported by `app.py` line 17 | Entry use is behind the block |
| RL Q update | `bot_loop.py` 1107, after a managed close | Yes, for a close that returns. Entry RL is blocked |
| V2 shadow market persist | `bot_loop.py` 759, before the position branch | A research side write on the cycle, not an order |
| Adaptive ensemble, shadow engine, decision-quality research | `forex_bot/research` and `forex_bot/shadow` | Not the order path |
| Fundamental and forecast research | Research modules and `data/research` | Not the order path |

No forecast API result is an entry. No profitability claim follows from any of these modules. Dead or superseded entry code includes the legacy broker tail that logs "legacy broker tail is not a dispatch path" and returns (`bot_loop.py` 1719) before the later fill bookkeeping.
