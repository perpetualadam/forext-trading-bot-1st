# Source continuity trace

SOURCE-REVIEWED before the repair. `run_bot` was not executed.

| Step | Function | File | Reachability |
| --- | --- | --- | --- |
| Launcher | `run_bot` | `bot_loop.py` 2982 area, function remains `while True` | Production only if the lifespan schedules it. Not entered. |
| Cycle | `_cycle_symbols` calls `evaluate(symbol)` with no dependencies | `bot_loop.py` | Not entered. |
| Offline driver | `evaluate` returns `dispatch_production_iteration` when dependencies are supplied | `bot_loop.py` 686 | Offline tests use this. It does not enter `_evaluate_impl`. |
| Production new entry | `_evaluate_impl` calls `dispatch_production_iteration` | `bot_loop.py` 706 and 1098 | The call is in source. Tests do not enter `_evaluate_impl`. |
| Continuation | status must be `continue_existing_production_broker` | `bot_loop.py` 1098 | The shared function never returns that status. |
| Shared decision | `evaluate_one_instrument_iteration` | `bot_loop.py` 2112 | Offline and the production dispatch boundary. |
| Strategy | `select_strategy` or `select_deterministic` | `strategy_meta.py` 159, `decision_repair/selection.py` | Called by the shared path when selector flags are set. Not called when the permission gate returns first. |
| AI vote | `AIEnsemble.vote` | `ai_ensemble.py` 207 | Called by the shared path when the scenario reaches the vote. Async work is driven with `send(None)`. No event loop. |
| RL veto | `RLAgent.decide` | `rl_agent.py` 28 | Called by the shared path when the scenario reaches the veto, before reservation. |
| Production adapter | `production_execution_adapter` | `bot_loop.py` 2049 | The only `execute_oanda_market_open` reference. Not called by tests. |
| Legacy tail | return at `legacy broker tail is not a dispatch path` | `bot_loop.py` 1678 | Unreachable because the sentinel is never returned. It no longer calls the broker. |

The R.13 sentinel made the old broker tail unreachable. That was confirmed in source: the comparison exists and no return produces the sentinel. The tail's direct `execute_oanda_market_open` call was then removed so the dead tail cannot become a second dispatch.
