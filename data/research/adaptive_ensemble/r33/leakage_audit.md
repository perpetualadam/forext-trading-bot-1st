# R.33 leakage and provenance notes

Static reading. No training code was changed.

| Finding | Location | Status | Severity | Consequence |
| --- | --- | --- | --- | --- |
| Rolling averages, ATR, and one-bar returns use current and earlier bars. | `indicators.compute_indicators`, `_true_range`, `_quant_stub_vote` | Confirmed | None for the stub features | The scored features can be aligned to the decision bar. |
| `volatility_ok` takes percentiles of every ATR in the frame it is given. A full-history frame includes later bars. The live call receives the loaded window, default 200 bars. | `session_rules.volatility_ok` | Confirmed | Medium if misused offline | The score does not use this gate. A trailing count is reported separately. |
| The stub has no training file, split, seed, or scaler. Thresholds are source defaults. Whether they were chosen against market data is not recorded. | `ai_ensemble._quant_stub_vote`, `_env_float` | Unresolved provenance | High for any claim of a holdout | This year cannot be called an independent test. |
| The EUR_USD M5 year was used in R.30–R.32. | `data/historical/EUR_USD_M5.csv` | Confirmed | High for a fresh-validation claim | The protocol marks the period research-exposed. |
| `RLAgent` starts empty and is not loaded from disk. Its default choice is random. There is no train window to leak from. The update uses realised P&L after a close, which is a delayed reward, not a decision feature. | `rl_agent.py`, close branch in `_evaluate_impl` | Confirmed | The learned gate cannot be scored | Historical RL contribution is not estimated. |
| `compute_nn_pred` adds random noise by default and is only referenced from the unreachable tail. The stub ignores `nn_pred`. | `nn_pred.py`, `_evaluate_impl` after the shared return | Confirmed | Low for the reachable vote | It is not part of the score. |
| Shared indicators use fixed 5/20/14. The unreachable tail uses the strategy lookback. | `evaluate_one_instrument_iteration`, `_evaluate_impl` | Confirmed | The two paths disagree | The score follows the reachable shared windows. |
| An empty ensemble returns direction `BUY` with `allow` false. | `AIEnsemble.vote` | Confirmed | Low if `allow` is honoured | The shared path rejects `allow` false before using the direction. |
| No local `.pkl`, `.joblib`, `.pt`, `.onnx`, or Q-table file was found for this path. | `data/` model search | Confirmed | The trained-model question has no artifact | Missing weights are not replaced. |

No scaler is fitted on a later period, because the reachable vote has no scaler. No label column is shifted into the stub. No instrument was added after a result.
