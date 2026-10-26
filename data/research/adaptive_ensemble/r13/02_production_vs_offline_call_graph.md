# Production path and offline path

SOURCE-REVIEWED before the edit. CODE MODIFIED afterward.

## Path 1, before this stage

`run_bot` (infinite loop) called `_cycle_symbols`, which awaited `evaluate`, which awaited `_evaluate_impl`.

`_evaluate_impl` loaded real candles, managed an open position, then ran its own new-entry sequence: exposure, permission, strategy, AI vote, direction, RL, sizing, reservation, and `execute_oanda_market_open`. That broker call was not executed in any test.

## Path 2, before this stage

Tests called `evaluate_one_instrument_iteration` directly. `run_bot` and `_evaluate_impl` did not call it. The two paths could diverge.

Differences that remain visible in source:

- The old new-entry tail still contains `execute_oanda_market_open`, RL, and the live quote geometry. The shared decision does not call that broker function.
- The shared decision injects the vote and the strategy flags. It does not call `select_strategy`, `ai.vote`, or the RL gate.
- The shared decision stops a non-simulation call at the live-order gate and does not continue into the old broker tail.

## Path after this stage

`_evaluate_impl`, once position management is finished, calls `dispatch_production_iteration`.

`evaluate(symbol, dependencies)` calls the same function when a dependency object is supplied, and does not enter `_evaluate_impl` or `run_bot`.

`dispatch_production_iteration` calls `evaluate_one_instrument_iteration` and marks the result as a production dispatch.

The shared function does not return `continue_existing_production_broker`. The old broker tail therefore stays in the file and is not reached. There is no second broker dispatch.
