# STAGE R.37 — AI ERROR DIAGNOSIS AND CONTROLLED LEARNING EXPERIMENTS REPORT

## Overall classification

`R37_CONTROLLED_AI_LEARNING_COMPLETED`

## Model advancement decision

`NO_MODEL_QUALIFIES_FOR_ADVANCEMENT`

Neither pre-registered candidate met the frozen acceptance rule. No model was registered, promoted, or connected to voting, reinforcement learning, or order execution.

## Branch, HEAD and preservation

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- The working tree was already dirty and those unrelated changes were left in place.
- All six strategies remain `active=false` and `authorised_for_live=false`.
- The quant stub still returns `quant_stub_removed` and does not allow a trade.
- An unseen reinforcement-learning state still returns `UNAVAILABLE`.
- Operational file hashes match the R.34 pins: `ai_ensemble.py` `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa`, `rl_agent.py` `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e`, `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`, `strategy_meta.py` `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`.
- The R.36 trainer `supervised.py` is unchanged: `164e13853c6bbc4400dec7e4346e83b4977768fc27a0adef886b033c77660347`.

## R.36 action-count reconciliation

The reloaded R.36 logistic and XGBoost artifacts reproduced the published test prediction hashes, so the counts below are the same predictions as R.36.

| Population | Logistic | XGBoost |
| --- | ---: | ---: |
| Eligible research-exposed test rows | 14,631 | 14,631 |
| Abstentions on those rows | 14,548 | 14,631 |
| Directional calls on those rows | 83 | 0 |
| Next-bar unevaluable rows | 0 | 0 |
| Non-overlapping stride-12 opportunities | 1,220 | 1,220 |
| Stride-12 cost-adjusted actions | 5 | 0 |
| Directional calls outside the stride | 78 | 0 |

The 83 logistic mistake rows are 42 incorrect directional predictions, 36 low-confidence correct predictions, and 5 directionally correct predictions that lose after the recorded spread. Those three categories sum to 83. Together with 10,087 hindsight missed opportunities and 4,461 correct abstentions, they sum to the 14,631-row denominator.

Five of the 83 directional calls fall on a bar whose position is a multiple of 12. The other 78 sit on neighbouring bars whose 12-bar outcomes overlap. They are not 78 extra independent trades. The R.36 economic comparison counted only the five non-overlapping actions.

## Error patterns and diagnostic conclusions

On the R.36 validation slice, the median maximum class probability is 0.393. The 90th percentile is 0.447 and the 99th is 0.615. About 2.9% of validation bars have any class probability of at least 0.50, and that share includes bars whose most likely class is already `NO_TRADE`. The published R.36 policy therefore abstains on nearly every bar.

The probability scores are a separate fact from the trading result. R.36 already showed a small log-loss improvement over a class-frequency baseline, while the only threshold with a large number of validation trades lost money after the spread. This stage does not treat that association as a proven cause.

## Candidate changes investigated

The diagnostic protocol was hashed before the candidate results were produced: `1584ebf1f3e9309deac4a4d025a930a8013103c1fb1c39cfe64bb4a54be23381`.

Two candidates were frozen. A third was not run, because training and validation evidence had not identified a specific feature or hyperparameter defect.

**Candidate A — probability bins.** A logistic model with the unchanged R.36 hyperparameters was fit only on positions `[20, 15000)`. On the later estimation window `[15012, 25000)`, buy and sell probabilities were grouped at 0.35, 0.40, 0.45 and 0.50. A bin could be used only if it had at least 100 observations, a positive mean next-bar return, and a block-bootstrap lower bound above zero. Every bin with enough observations had a negative mean. The only positive buy bin, probability at least 0.50, had 13 observations, which is below the frozen sample rule. The candidate therefore abstained on both later evaluation windows (825 and 802 stride opportunities, zero actions). It was rejected.

**Candidate B — 48-bar horizon.** The same logistic specification was trained on a 48-bar target with a 48-bar embargo. The horizon was taken from the existing R.35 horizon list before any result was seen. Its log loss is for a different target, so it is not a matched comparison with the R.36 12-bar log loss. On its own target, validation log loss was 0.9793 against a frequency baseline of 0.9904, with abstention of 96.7%. The validation stride had 296 opportunities and 3 actions. The mean including abstentions was about `+0.0000005`, the bootstrap lower bound was below zero, and an extra one-pip cost made the mean negative.

The first walk-forward window had 49 actions and a positive point estimate of about `+0.000073`. Its bootstrap lower bound was still below zero. The next two windows had negative means. The positive window does not meet the rule that every evaluation window must clear the cost and uncertainty bars.

## Training and evaluation periods

- Candidate A training: positions `[20, 15000)`. Estimation: `[15012, 25000)`. Evaluation: `[25012, 35000)` and `[35012, 44731)`.
- Candidate B training: `[20, 44695)`. Validation: `[44743, 59609)`. Walk-forward evaluation ends at position 36000.
- No candidate was fit on the R.36 test period, which starts at position 59657. Test outcomes were not used as training labels.

## Predictive metrics

Candidate A made no evaluation trades, so it has no new hit rate. Candidate B’s validation probabilities remain research-only: log loss 0.9793, Brier 0.6014, expected calibration error 0.034, abstention 96.7%. All three walk-forward folds had log loss at or below their own frequency baselines. That probability result does not authorise a trade.

## Cost-adjusted economic results

Candidate A matched an always-abstain result of zero on its evaluation strides because the frozen bin rule found no usable bin.

Candidate B’s validation mean was positive by a fraction of a pip on three actions and failed the bootstrap and sample-size rules. One later window was positive at the point estimate and two were negative. No window passed the full frozen economic rule.

## Transaction-cost sensitivity

Candidate B was scored with the recorded bid/ask, then with an extra half pip and an extra one pip. The validation one-pip mean was negative. The first walk-forward window stayed positive at the point estimate under an extra pip, and its bootstrap lower bound stayed below zero. These recorded spreads are not a full OANDA GBP spread-betting cost, financing, slippage, or margin model.

## Multi-instrument feasibility

The six local M5 files cover the same September 2025 to August 2026 window, use the same bid/ask columns, and have no duplicate timestamps. Median spreads are about 1.3 to 1.9 pips. USD/JPY uses a pip size of 0.01. On the training period, one-bar returns are strongly related across pairs: EUR/USD with GBP/USD is about 0.79, and EUR/USD with USD/CHF is about −0.79. A pooled model was not in the frozen protocol and was not trained. Six pairs on one clock are not six independent tests.

## Learning-history findings

Both completed experiments are retained as rejections. The probability bins did not contain a defensible expected edge on the estimation fold. The longer horizon improved its own log loss slightly and still failed the cost, sample-size, and uncertainty rules. The R.36 baseline artifacts were not overwritten.

## Artifact and protocol hashes

- Diagnostic protocol: `1584ebf1f3e9309deac4a4d025a930a8013103c1fb1c39cfe64bb4a54be23381`
- Diagnosis module: `07c0acf894fa7418b1469b68cd82a680a9e3972b06f96aaafff2660105150680`
- Candidate B coefficient record: `dc613ff49e41c9b600d0b76c0325697055c59046ccbb156aae001bf95204e871`
- Candidate B validation prediction digest: `47cadc507498c79b41bdada297b6bd470131fd769cf8cabe853ba821b1f8534a`
- R.36 logistic and XGBoost test prediction hashes were reproduced before the count table was accepted.

## Focused tests and regression results

`tests/test_r37_learning.py`: 7 passed. The tests cover the stride reconciliation, exclusion of the R.36 test slice, embargo rejection, a leaky feature fixture, a negative probability bin that must not become a trade, and the unchanged fail-closed stub and reinforcement-learning behaviour.

R.8–R.36 offline suites exited 0. R.10 attempt 1 failed on the known `WinError 5` file replacement and the separate retry passed with 69 tests and 5 skips. R.28 database scripts were not run.

## Remaining limitations

The EUR/USD year remains research-exposed. These walk-forward windows are earlier slices of that same year, so they are not a fresh untouched market period. Overlapping labels mean the row count is larger than the number of independent opportunities. Class probabilities still do not provide a price-move magnitude, and the estimation fold did not support a substitute expected-value rule. A single positive walk-forward window is too small, and too uncertain, to carry a trading claim.

## Recommended next research direction

The next useful question is whether any causal feature, on training data only, is associated with a move that reliably exceeds the spread. That question needs its own frozen protocol. This stage does not start that work.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
