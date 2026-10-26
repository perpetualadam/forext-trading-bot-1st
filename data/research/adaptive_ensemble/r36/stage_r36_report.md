# STAGE R.36 — GENUINE SUPERVISED AI MODEL EXPERIMENTS REPORT

Classification: `R36_SUPERVISED_ML_EXPERIMENTS_COMPLETED`

Model advancement: `NO_MODEL_QUALIFIES_FOR_ADVANCEMENT`

The experiment trained genuine supervised models and compared them with frozen baselines. No model showed a cost-adjusted result that met the pre-registered rule. Nothing here authorises trading.

## Branch and preservation

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The dirty working tree was preserved. Nothing was committed, reset, cleaned, stashed, or rolled back. R.24–R.35 evidence was not modified.

All six strategies remain inactive and unauthorised for live trading. The operational voter, RL agent, `bot_loop.py`, and `strategy_meta.py` keep their R.35 hashes. The retired stub still returns `quant_stub_removed`. An unverified RL agent still returns `UNAVAILABLE`. No model was registered with the ensemble.

## Dependencies

| Package | Status |
| --- | --- |
| NumPy | 2.2.2 |
| pandas | 2.2.3 |
| scikit-learn | 1.7.0 |
| XGBoost | 3.0.3 |
| joblib | 1.5.1, available and unused; artifacts were saved as JSON |
| LightGBM | not installed |

LightGBM was not trained. A later install, not run in this stage, would be:

`python -m pip install lightgbm`

## Models

- Logistic regression, L2, C=1.0, `lbfgs`, max 500 iterations, seed 36. Median imputation and standard scaling were fit on training rows only.
- XGBoost, 60 trees, depth 3, learning rate 0.05, CPU, one thread, seed 36.
- LightGBM: unavailable.

Both fitted models reproduced a second fit exactly. `validation_status` remains `unvalidated`.

## Data, features, and target

EUR_USD M5, SHA-256 `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`. 74,572 rows, 2025-09-01 through 2026-08-31. Feature schema `r35.features.v1`, hash `7d15b98d9bfe99136f2de5e05522d9cef623539b38f7ab61e9ea722a24889946`. This year is research-exposed.

The target was frozen before fitting. A 12-bar close-to-close bid/ask return is BUY when it is positive and larger than the sell return, SELL in the opposite case, and NO-TRADE on a tie or when neither side is positive. Training class counts were SELL 17,080, NO-TRADE 10,221, and BUY 16,975. The three-class target was usable.

Eligible rows after warm-up, finite features, and an aligned horizon: train 44,276, validation 14,746, test 14,631. Twenty warm-up rows were feature-invalid. 875 labels were unevaluable. The two embargo gaps are 12 bars each. Seventy-three gaps are longer than five minutes.

## Leakage controls

Train indices are `[20, 44731)`, validation `[44743, 59645)`, test `[59657, 74560)`. The last training label ends before validation starts, and the last validation label ends before the test starts. Walk-forward evaluation stays inside the training region.

A prefix check at bar 1000 matched. A synthetic future-return feature failed the same check. Scalers and imputers are fit inside the training pipeline. The selection file was written before the test metrics and was not changed afterwards. No random split was used.

## Comparison

A priori policy: predict the highest-probability class, and abstain when that probability is below 0.50. Economic figures use non-overlapping 12-bar steps and include abstentions as zero. Block bootstrap: block 20, 200 draws, seed 3601.

Validation, used for the frozen decision:

| Model | Log loss | Frequency baseline | Brier | ECE | Accuracy | Abstention | Stride actions | Next-bar mean | Bootstrap low |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic | 1.0570 | 1.0911 | 0.6407 | 0.0188 | 0.269 | 0.991 | 12 | +0.0000066 | -0.0000060 |
| XGBoost | 1.0480 | 1.0911 | 0.6352 | 0.0138 | 0.266 | 1.000 | 0 | 0 | none |

Both models beat the frequency baseline on log loss and Brier, and their confidence ECE is below 0.10. That is a probability result. It is not a trading result. Accuracy is below the majority class because the 0.50 rule almost never acts. The probabilities are not high enough to call the models reliably confident.

Held-out test, scored once after the decision and not used to change it:

| Model | Log loss | Baseline | ECE | Accuracy | Abstention | Actions | Next-bar mean | Action-only mean | Midpoint hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic | 1.0645 | 1.1120 | 0.0129 | 0.308 | 0.994 | 5 | -0.00000052 | -0.000128 | 0.494 |
| XGBoost | 1.0585 | 1.1120 | 0.0229 | 0.307 | 1.000 | 0 | 0 | none | none |

Logistic's five test actions were about a coin flip on midpoint direction and lost about 1.3 pips each after the recorded spread. Adding half a pip or one pip of adverse cost made those results worse. The median test spread was 0.00016, about 1.6 pips.

The validation grid `{0.40, 0.50, 0.60}` selected 0.40 for both models, because that was the only point with at least 30 stride actions. Its validation mean was already negative. On the test slice that frozen threshold produced 309 logistic actions and 507 XGBoost actions, with action-only means of about -1.3 pips and -1.0 pip. Lowering the bar created more losing trades.

Always-SELL, the training majority, lost about 1.6 pips per test opportunity. A causal momentum rule that trades only when the 12-bar move exceeds the spread also lost. Abstaining beat both of those directional baselines and did not beat zero by a margin the bootstrap could separate from noise.

Close-to-close labels and next-bar-open entries agreed on the conclusion. Next-bar entry assumes the next candle opens exactly five minutes later and exits at the close 12 bars after the decision. Gaps are unevaluable. These figures are not OANDA spread-betting costs, slippage, financing, or margin.

## Walk-forward

Three expanding folds, hyperparameters fixed, 0.50 policy, evaluation before the validation slice:

| Fold | Logistic log loss | Baseline | XGBoost log loss |
| --- | ---: | ---: | ---: |
| wf1 | 1.0609 | 1.0905 | 1.0587 |
| wf2 | 1.0505 | 1.0725 | 1.0456 |
| wf3 | 1.0404 | 1.0552 | 1.0286 |

All three folds beat the fold's own frequency baseline on log loss. That stability is about probability score. The folds were not used to retune the models, and they were not used as a profit claim.

## Mistakes

On the test slice, at the 0.50 policy, XGBoost abstained on every row. Logistic made 83 directional calls: 42 wrong on direction, 36 right with confidence below 0.70, and 5 right on direction but negative after cost. There were no high-confidence incorrect calls, because confidence did not reach 0.70.

Most rows are labelled `missed_opportunity` only because an abstention was followed by some positive hypothetical side. That count does not identify the side in advance. The lower threshold, which acted on more of those windows, lost money. Directional mistakes that did occur sat mainly in the New York hour bucket and the high-volatility tercile, on a small count. That is not a stable regime rule.

## Artifacts

Frozen protocol SHA-256 `d3ca79a117f83471eaf2f83acd0a42982e3b1011c2c3a04e3f7d253076dc257b`.

| Model | Artifact SHA-256 | Test prediction SHA-256 |
| --- | --- | --- |
| Logistic | `6546fea6cd9e4038db6b86cb66de0cc96b6d78c3d8e806482dbe9dfb7c6492de` | `27a3eaa45b8d17482d3e70877921e536cd3a3e67bb29a44fc9cc2a07055c88b8` |
| XGBoost | `cd1547e4b4ee354ba323c5c756ff4f42a207009701fbb90ee24f9cbe30e3cdea` | `49e4d191086a2568ffc25a75534ee9c38148517394191770e0b2b211e0f58e3f` |

## Tests

R.36 focused tests: 10 passed. R.8–R.35 regressions all exited 0, with the same pass, skip, and deselect counts as R.35. Details are in `13_regression_results.md`.

New research code: `forex_bot/research/learning/supervised.py`, SHA-256 `164e13853c6bbc4400dec7e4346e83b4977768fc27a0adef886b033c77660347`.

## Limitations and R.37

The log-loss gain over a constant probability vector is real and small. It did not become a cost-adjusted edge under the frozen rule. The test period is not an untouched holdout. Overlapping labels were handled with a 12-bar stride and a block bootstrap, not with independent-trade statistics. LightGBM was not compared. No model qualifies for further advancement.

R.37 should not retrain these models on the test mistakes and should not promote them. A later research stage would need a new pre-registered hypothesis. This stage does not start that work.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
