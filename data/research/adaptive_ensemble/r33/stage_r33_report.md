# STAGE R.33 — AI/RL DECISION-PATH AUDIT AND OFFLINE PREDICTIVE-VALUE ASSESSMENT REPORT

**Overall classification: `R33_AI_RL_AUDIT_COMPLETED`**

The reachable decision architecture, the local artifacts, the leakage risks, and the evaluability of each component were assessed. The only deterministic directional rule, the quant stub, was reproduced offline. Its pre-registered result shows no credible directional edge. The external voters, the RL policy, the sequence model, and the combined live path cannot be scored as historical policies from the files on disk.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

R.34 was not started.

## Preservation

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The dirty working tree and the R.24–R.32 evidence were left in place. This stage added files under `data/research/adaptive_ensemble/r33/` and `tests/test_r33_ai_rl_audit.py`. It did not commit, reset, clean, stash, or roll back.

`forex_bot/bot_loop.py` remains at SHA-256 `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`. AI voting, RL gating, feature definitions, risk defaults, and the six strategy flags were not changed. All six `Strategy.active` and `authorised_for_live` values stayed false. `.env`, credentials, broker sessions, PostgreSQL, and Docker were not used.

## Actual decision flow

A live cycle reaches `evaluate` → `_evaluate_impl` → `dispatch_production_iteration` → `evaluate_one_instrument_iteration`. Production dependencies set `invoke_selector`, `invoke_vote`, and `invoke_rl`, and they pass the process-wide `rl_agent`. `simulation` is false on that object.

The shared function then selects a strategy, applies `strategy_entry_block_reason`, computes indicators with the legacy windows 5, 20, and 14, checks `volatility_ok` on that frame, calls `ai.vote`, accepts only `BUY` or `SELL`, and calls `rl_agent.decide`. Account, risk, and sizing follow. The current producer does not seal `production_eligible` true.

With the six durable flags false, a production dependency object stops at the strategy gate, before the vote and before the RL call. An offline harness can pass an `IterationDependencies` object into the same shared function. That object never enters `_evaluate_impl`.

`ENSEMBLE_MODE` defaults to `hybrid`. Hybrid includes the quant stub unless `AI_DISABLE_STUB` is set, and it adds API voters only when keys are present. This audit did not read `.env`, so the voter list of a live process is unknown. The historical score forced `ENSEMBLE_MODE=quant` in the research process, removed known key names from that process, and called `_quant_stub_vote` directly.

The stub buys when `ma_fast` exceeds `ma_slow` by `1e-6` and sells on the opposite gap. It allows the vote only when the absolute one-bar return exceeds `0.0001` and ATR is positive. `HOLD` is not a stub output. `allow` false is an abstention even when a direction is attached. An empty ensemble returns `allow` false and direction `BUY`. The shared path rejects `allow` false before that direction can become an entry.

`RLAgent` starts with an empty Q-table. `persisted_ok` is false, and production code never sets it true. With `DECISION_REPAIR_RL_REQUIRE_STATE` unset, a zero-value tie is random. With the flag set, `decide` returns `UNAVAILABLE`. `SKIP`, a directional mismatch, and `UNAVAILABLE` all block. The agent does not replace the AI side. Neither `data/ops/rl_q_table.json` nor `data/research/decision_repair/rl_state.json` exists.

`SeqModel` and `compute_nn_pred` sit after the status `continue_existing_production_broker`. That status is checked once and assigned nowhere, so the tail does not run. `decision_quality/live_path.py` still lists `seq_model` and is stale. The research `model_vote` in `forex_bot/research/adaptive_ensemble/models.py` is not called by the shared path. The full call path is in `architecture.md`.

## Artifacts and provenance

No `.pkl`, `.joblib`, `.pt`, `.onnx`, scaler, encoder, label file, training config, seed, or saved prediction record belongs to this path. Nothing was deserialized. The stub is source. The RL policy has no weight file. API voter classes were not constructed.

The scored file is `data/historical/EUR_USD_M5.csv`, SHA-256 `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`, 74,572 rows, 2025-09-01 through 2026-08-31. The R.30 cleaner hash is unchanged: `fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc`. Exclusions were zero.

The protocol was hashed before the score: `01_evaluation_protocol.md` SHA-256 `d66add899d5ac9b22c773490c52c8bf973a682c0634179592d7fa43524445054`. The same hash is in `evaluation.json`. Source hashes are in `artifact_inventory.md`.

## Leakage

Confirmed: the stub features are causal rolling averages, ATR, and a one-bar return. A prefix recomputed through bar 5000 matched the full series at that bar before scoring.

Confirmed: `volatility_ok` percentiles every ATR in the frame it receives. A full-file call would use later bars. The score did not use that gate. A trailing 200-bar count would have removed 467 actionable bars. That count is diagnostic only.

Confirmed: this EUR_USD year was already used in R.30–R.32. It is research-exposed. It does not establish an independent holdout.

Unresolved: the stub thresholds are source defaults. No local record says whether they were chosen against market data. That missing record is enough to withhold `EVALUABLE_WITH_CREDIBLE_EVIDENCE`.

Confirmed and not scored: the RL update uses realised P&L after a close, the default `nn_pred` path adds noise, and the unreachable tail uses a different lookback from the shared windows. Details are in `leakage_audit.md`.

## Offline reproduction

The research process reproduced every stub vote on the 74,572 cleaned bars. The first 200 bars repeated exactly. Features used bid OHLC and the shared windows. Outcomes used the bid/ask close midpoint at a later bar whose timestamp was exactly `300 * h` seconds ahead. Abstentions stayed out of the return mean.

| Count | Value |
| --- | ---: |
| Bars | 74,572 |
| `allow` true | 37,091 |
| Abstain | 37,481 |
| Actionable BUY | 18,251 |
| Actionable SELL | 18,840 |
| Direction attached while `allow` is false | 37,254 |
| Abstain with direction `None` | 227 |

External LLM voters, the RL policy, `SeqModel`, and the combined live path were not given synthetic stand-in predictions.

## Predictive value of the quant stub

The decision horizon was frozen at 12 M5 bars before the measurement. The decision sample is the non-overlapping walk: 5,555 events, 381 actionable bars dropped because the later timestamp was not exactly one hour ahead.

| Sample | Count | Mean return | Directional frequency |
| --- | ---: | ---: | ---: |
| 12-bar non-overlapping | 5,555 | −0.000008285 | 0.490 |
| 12-bar overlapping | 36,710 | +0.000002148 | 0.495 |
| Non-overlapping BUY | 2,758 | −0.000000861 | 0.484 |
| Non-overlapping SELL | 2,797 | −0.000015606 | 0.496 |

The non-overlapping mean is −0.083 pips. The median full close spread on the same bars is 0.00016, or 1.6 pips. The block-bootstrap interval is −0.0000309 to +0.0000148 and includes zero. The label-shuffle 95th percentile is +0.0000178 and the coin-flip 95th percentile is +0.0000161. The effect size is −0.0096.

The frozen rule stops at a non-positive primary mean, so the label is `EVALUABLE_NO_CREDIBLE_EDGE`, rule `nonpositive_mean`. The overlapping mean has the opposite sign. That dependence is recorded and does not change the pre-registered label. Calendar windows split two negative and two positive. Horizons of 1, 6, and 48 bars were reported and were not used to choose the label. The 1-bar mean is +0.000000029. The 6-bar and 48-bar non-overlapping means are negative.

This is a midpoint association. Commission, financing, swap, and slippage were not estimated. A negative midpoint result does not become a trading result after costs.

## RL contribution

No incremental RL effect was estimated. The blocker is the absence of a loaded policy. The live agent starts empty, `persisted_ok` stays false, and the default choice is stochastic. A random gate was not simulated and then described as model performance.

## Safety tests

Synthetic wiring tests in `tests/test_r33_ai_rl_audit.py` kept invalid decisions off the order path. Empty voters, `HOLD`, non-finite confidence, RL `SKIP`, RL mismatch, RL `UNAVAILABLE`, a NaN stop, and a missing NAV each finished with `broker_requests == 0`, `reservation_attempted == false`, and `production_eligible == false`. The durable strategy flags stayed false. Production fallbacks were not edited. The case table is `safety_results.md`.

## Tests and regressions

Focused R.33 tests: 4 passed, 0 failed, 0 skipped, 0 deselected.

Every offline suite exited 0. `WinError 5` did not recur. R.28 PostgreSQL scripts were not run.

| Suite | Result |
| --- | --- |
| R.33 | 4 passed |
| R.32 | 10 passed |
| R.31 | 7 passed |
| R.30 | 13 passed |
| R.29 | 8 passed |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 | 69 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

## Component classifications

| Component | Classification |
| --- | --- |
| Quant stub `_quant_stub_vote` | `EVALUABLE_NO_CREDIBLE_EDGE` |
| External LLM voters | `NOT_EVALUABLE` |
| Tabular `RLAgent` | `NOT_EVALUABLE` |
| `SeqModel` and `compute_nn_pred` | `NOT_EVALUABLE` |
| Research `model_vote` | `NOT_EVALUABLE` |
| Combined live path | `NOT_EVALUABLE` |

`EVALUABLE_WITH_CREDIBLE_EVIDENCE` was not available for this file. The protocol forbids that label when the year is research-exposed and the threshold provenance is unknown.

## Recommendation

The quant stub has no demonstrated directional predictive value on the available year. That result does not justify an independent validation study.

The external voters and the RL gate need a recorded configuration and a reproducible artifact before they can be evaluated. The live voter list is unknown because `.env` was not read. The combined path cannot be replayed as a historical policy: the durable strategy flags stop a production dependency before the vote, and the RL gate has no loaded state. Those are audit findings. They are not a reason to activate a strategy or to fill in a missing model.

No strategy is recommended for activation.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**
