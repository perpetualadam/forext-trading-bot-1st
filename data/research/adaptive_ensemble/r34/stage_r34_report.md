# STAGE R.34 — QUANT STUB REMOVAL AND AI/ML ARCHITECTURE HARDENING REPORT

**Overall classification: `R34_STUB_REMOVAL_AND_HARDENING_COMPLETED`**

The quant stub can no longer supply an operational BUY or SELL. Legacy quant mode fails closed. Hybrid mode does not insert another heuristic. Empty and invalid voter results abstain. An unverified RL table cannot approve a direction. Volatility at a timestamp uses only data at or before that timestamp. The prediction contract and the decision journal are research-only and were checked offline. No model was trained.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

R.35 was not started.

## Preservation

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The existing dirty tree and the R.24–R.33 evidence were left in place. This stage did not commit, reset, clean, stash, or roll back.

`forex_bot/bot_loop.py` remains SHA-256 `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`. `forex_bot/strategy_meta.py` remains `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`. All six `Strategy.active` and `authorised_for_live` flags stayed false. `.env`, credentials, brokers, PostgreSQL, and package installs were not used.

## Quant-stub removal

`_quant_stub_vote` now returns `allow` false, direction `None`, and reason `quant_stub_removed`. `LocalLLM.predict` returns that same abstention and is not registered. `ExternalLLMAPI.predict` returns `external_voter_unavailable` and does not call a network service.

`ENSEMBLE_MODE=quant` builds an empty ensemble whose vote reason is `unsupported_ensemble_mode`. `api` and `hybrid` register only the existing external voter classes, and only when the process already has the corresponding key. `AI_DISABLE_STUB` no longer inserts or removes a heuristic. If no voter returns a usable result, the ensemble abstains with direction `None`. A confidence-weighted tie also abstains. The old default direction `BUY` is gone.

Historical research modules that still import `_quant_stub_vote` receive the abstention. Their files were not rewritten and the R.33 score was not rerun. `tests/test_silent_skip_observability.py`, `tests/test_v2_shadow.py`, `tests/test_momentum_m5_dedup_research.py`, and `tests/test_decision_quality_engine.py` still assert the old directional stub. They are outside the R.8–R.33 regression set and are no longer applicable to the operational voter.

## AI voting and RL

The shared path still rejects an abstention before reservation. Focused checks covered an empty voter list, quant mode, hybrid with no voters, `HOLD`, non-finite confidence, and a BUY/SELL tie. Each blocked evaluate call kept `reservation_attempted == false`, `broker_requests == 0`, and `production_eligible == false`.

`RLAgent.decide` returns `UNAVAILABLE` when `persisted_ok` is false, when the state is missing, when every Q value is zero, or when two actions tie. It does not call `random`. Twenty repeated calls on a new agent stayed `UNAVAILABLE` and did not fill the table. `persisted_ok` is not set by `decide` or by `update`. A unique non-zero learned action is returned only after a caller has already set `persisted_ok`. Synthetic tests that inject such a row set that flag on the test agent. The process-wide agent stays unverified. An RL rejection is not turned into an AI approval.

## Causal volatility

`volatility_ok` scores one bar from at most the preceding 200 ATR values, ending at that bar. Fewer than 20 finite values, a missing column, or a non-finite latest value returns false. The percentile rule is unchanged: the latest ATR fails when it is above twice the 90th percentile or below half the 10th percentile.

A 40-bar calm series and the same series with 30 later spikes produce the same decision at bar 39. A 10-bar window fails closed. A three-candle evaluate call is blocked with `volatility_unsafe` and does not reach the broker. Short frames that used to reach `insufficient_lookback` now stop at this earlier gate. Those regression assertions accept `volatility_unsafe` and still require zero broker requests. The 49-bar lookback check still reaches `insufficient_lookback`.

## Contracts

`forex_bot/research/ml_prediction.py` validates a supplied prediction and does not invent one. Approval requires a 64-character artifact hash, a fresh timezone-aware timestamp, direction, finite confidence, and `validation_status=validated_offline`. An unvalidated, stale, or non-finite payload is rejected. Abstention cannot carry a direction. The module is not registered as a voter.

`forex_bot/research/decision_journal.py` validates one in-memory row and writes nothing. Prediction error and adverse outcome are separate fields, so a directionally correct row can still record an adverse result. An unevaluable row cannot carry an outcome. There is no collector and no retraining hook.

## Source hashes

| File | SHA-256 |
| --- | --- |
| `forex_bot/ai_ensemble.py` | `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa` |
| `forex_bot/rl_agent.py` | `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` |
| `forex_bot/session_rules.py` | `1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1` |
| `forex_bot/experiment.py` | `36eb14d5adb0a626f277a0adcc6f08b14163054273bea71e3d9679f535821356` |
| `forex_bot/research/ml_prediction.py` | `97ba722204734b480ecc610cc26756a42cabafb9d4ded81070ced146580bd7bc` |
| `forex_bot/research/decision_journal.py` | `2b11468a69b015470eb4a57bd9a3585cdb4b1721fde54e8a424c01966e1025c5` |

Pre-change hashes are in `00_pre_change_hashes.json`.

## Tests

Focused R.34 tests: 5 passed, 0 failed, 0 skipped, 0 deselected.

The first full regression failed where short frames now stop at `volatility_unsafe`, and where the R.23 synthetic agent had not been marked verified. Those assertions were updated. Broker, reservation, and eligibility checks stayed in place. The following full run exited 0. `WinError 5` did not recur. R.28 PostgreSQL scripts were not run.

| Suite | Result |
| --- | --- |
| R.34 | 5 passed |
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

## Limitations

No LightGBM, XGBoost, scikit-learn, or MLflow model was installed or trained. The live process voter list is still unknown because `.env` was not read. External voters remain in source and are constructed only when keys are already present; this stage did not call them. There is still no saved RL policy. `decision_quality/live_path.py` and `shadow/fidelity.py` still describe the old stub. They are not the registration path.

The fail-closed voting path, the unverified-RL rejection, the causal volatility gate, and the research contracts are in place for an offline R.35 learning-foundation stage. That stage was not started. Nothing here authorises a strategy or an order.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**
