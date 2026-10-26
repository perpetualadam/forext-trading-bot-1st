# R.33 architecture inventory

Static reading of the current source. No production entry point was called.

## Reachable path

`run_bot` calls `_cycle_symbols`, which calls `evaluate(symbol)` with no dependency object. That enters `_evaluate_impl`. After an open position is managed, a new entry calls `dispatch_production_iteration` with `_production_iteration_dependencies`. Those dependencies set `invoke_selector`, `invoke_vote`, and `invoke_rl`, and they pass the process-wide `rl_agent`. `simulation` is false.

`dispatch_production_iteration` only calls `evaluate_one_instrument_iteration`. The shared order is:

1. Candle and session gates already applied by the caller.
2. Strategy selection when `invoke_selector` is true.
3. `strategy_entry_block_reason`. All six `Strategy.active` and `authorised_for_live` flags are false, so a production dependency object stops here.
4. `compute_indicators` with no lookback argument, so the legacy windows are 5, 20, and 14.
5. `volatility_ok` on that frame.
6. `ai.vote` when `invoke_vote` is true. `ai` is the ensemble built at import of `ai_ensemble.py`.
7. `direction_action_gate`. Only `BUY` and `SELL` pass. `HOLD` and any other text do not.
8. `rl_agent.decide(rl_decision_state(frame))` when `invoke_rl` is true.
9. Account, risk, sizing, and the inert-or-live order path. `production_eligible` is not sealed true by the current producer.

An offline test that supplies an `IterationDependencies` object never enters `_evaluate_impl`. It uses the same shared function.

## Vote

`ENSEMBLE_MODE` defaults to `hybrid`. In that mode the quant stub is added unless `AI_DISABLE_STUB` is set, and API voters are added only when the corresponding key is present. This audit did not read `.env`, so the live process's voter list is unknown. The reproduction forces `quant` inside the research process and calls `_quant_stub_vote`.

The stub buys when `ma_fast` exceeds `ma_slow` by `1e-6`, sells on the opposite gap, and allows the vote only when absolute one-bar return exceeds `0.0001` and ATR is positive. A failed ensemble with no voters returns `allow` false and direction `BUY`. The shared path rejects that result on `allow` before the direction is used.

`nn_pred` is not in the shared payload. The stub does not read it.

## RL gate

`RLAgent.decide` returns `BUY`, `SELL`, or `SKIP`. `SKIP` blocks. A directional action that differs from the AI side blocks. `UNAVAILABLE` blocks. The agent does not replace the AI side.

The Q-table starts empty. `persisted_ok` is set false in the constructor and production code never sets it true. With `DECISION_REPAIR_RL_REQUIRE_STATE` unset, every state is a tie at zero, so the choice is random: epsilon `0.25` explores, and a tie also chooses at random. With that flag set, `decide` returns `UNAVAILABLE` because the table was not loaded. No `data/ops/rl_q_table.json` and no `data/research/decision_repair/rl_state.json` are present. The save call exists on the close branch and is behind `DECISION_REPAIR_RL_PERSIST`.

The state string is rounded trend and ATR: four decimals and six decimals.

## Unreachable tail

`_evaluate_impl` continues into `seq_model`, `compute_nn_pred`, a second `ai.vote`, and a second RL decision only when the shared result status is `continue_existing_production_broker`. That string is checked once and assigned nowhere. The tail does not run. `decision_quality/live_path.py` still lists `seq_model` on the live path. That description is stale relative to the shared gate.

`SeqModel.predict` is a causal line fit on the last 50 prices seen by the process. It is not a saved network. `compute_nn_pred` adds uniform noise in the default live mode. Neither output is a scored prediction in this stage.

## Research models

`forex_bot/research/adaptive_ensemble/models.py` has a separate vote. `evaluate_one_instrument_iteration` does not call it.
