# STAGE R.38 — COST-AWARE PREDICTIVE FEATURE DISCOVERY REPORT

## Overall classification

`R38_COST_AWARE_FEATURE_DISCOVERY_COMPLETED`

No feature demonstrated a credible cost-adjusted trading signal. That is the result the evidence supports.

## Branch, HEAD and preservation

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- The working tree was already dirty. Unrelated changes were left in place.
- R.24–R.37 evidence was not modified.
- All six strategies remain inactive and unauthorised for live trading.
- The quant stub still returns `quant_stub_removed`.
- An unseen reinforcement-learning state still returns `UNAVAILABLE`.
- Operational hashes are unchanged, including `ai_ensemble.py` `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa`, `rl_agent.py` `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e`, and `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`.

## Protocol and source-data hashes

The protocol was hashed before the comparisons were interpreted: `597388bf5b238ff2a866a83c2662b6a46f4f52a3fefff4ee268d770221cc8dd1`.

It freezes horizons 12 and 48, the ten R.35 features, a training cutoff of 1 March 2026, a confirmation start of 1 May 2026, and eight Bonferroni-controlled EUR/USD tests. The discovery module hash is `28812817937c206ff086a24b81b1070a665c612d6f95dbc24cc5f0f68fd2b4b8`.

All six M5 files matched the R.35 inventory hashes. EUR/USD is `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`. USD/JPY uses a pip size of 0.01. The other five pairs use 0.0001. Timestamps are unique, ordered, and UTC. Labels that cross a gap are unevaluable.

## Feature and target definitions

Features are the R.35 set: one-bar midpoint return, 20-bar volatility, 14-bar ATR, moving-average distance, 12-bar momentum, close spread, UTC hour, session bucket, 20-bar range, and volume. Each uses the current completed candle and earlier candles only.

Targets at 12 and 48 bars are the future midpoint return, its absolute value, and the bid/ask-adjusted BUY and SELL returns. The economic rule enters on the next candle’s open and exits at the close of the horizon. The decision close is not used as the entry.

## Causal and leakage-control results

A prefix check left the EUR/USD features unchanged when later rows were removed. A fixture that copies the next return into the current row was rejected. Outcome columns stay out of the feature matrix. Training outcomes finish before 1 March 2026. Confirmation decisions start after 1 May 2026, with an extra horizon embargo. Scaler statistics for the magnitude model were fit on the training rows only.

## Individual feature findings

The confirmatory family is eight numeric features against the signed 12-bar midpoint return on EUR/USD, with a block-bootstrap interval widened for eight comparisons. Block length is 20 bars, with 800 replicates and seed 3801.

| Feature | Confirmation rank correlation | Adjusted interval excludes zero | Classification |
| --- | ---: | --- | --- |
| return_1 | −0.019 | yes | `STATISTICAL_VALUE_ONLY` |
| rolling_vol_20 | −0.051 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| atr_14 | −0.047 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| ma_distance | −0.014 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| momentum_12 | −0.021 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| spread | −0.007 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| range_20 | −0.035 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| volume | −0.031 | no | `NO_DEMONSTRATED_PREDICTIVE_VALUE` |
| hour_utc | descriptive only |  | `INCONCLUSIVE` |
| session_code | descriptive only |  | `INCONCLUSIVE` |

`return_1` kept a negative sign on the training window and on all three walk-forward windows inside that window. The association is small: a rank correlation of about −0.02. The adjusted interval runs from about −0.040 to −0.002. The other numeric features have adjusted intervals that include zero. Hour and session were summarised by group and were not promoted through a numeric correlation.

## Movement-magnitude results

Recent volatility, ATR, 20-bar range, and volume are associated with the size of the later move. On the EUR/USD confirmation window their rank correlations with absolute 12-bar midpoint return are about 0.30, 0.30, 0.29, and 0.32. At 48 bars those figures are about 0.19 to 0.22. `return_1` has almost no association with size.

A ridge regression, with median imputation and scaling fit on training rows only, reduced absolute-error versus the training-period average: 12-bar MAE 0.000291 versus 0.000334, and 48-bar MAE 0.000639 versus 0.000682. That is evidence about movement size. It does not identify whether the move will be up or down.

## Chronological stability

Inside the training year, only `return_1` kept the same sign in November 2025, December 2025, and January–February 2026. Several volatility features changed sign across those folds. The confirmation window repeated the negative `return_1` sign. These folds are earlier and later slices of the same researched year. They are not an untouched future sample.

## Multi-instrument comparisons

The same negative `return_1` sign appears on the confirmation windows of AUD/USD, GBP/USD, USD/CAD, USD/CHF, and USD/JPY. The rank correlations are about −0.016 to −0.032. Median spreads are about 1.3 to 1.9 pips. Sign agreement on the other seven features is mixed, from three of eight on AUD/USD to seven of eight on GBP/USD.

These pairs share the same months and a common dollar factor. Five matching signs are not five independent replications. No pooled model was trained.

## Transaction-cost sensitivity

The one pre-registered candidate used the training screen only. `return_1` was the only feature whose training interval excluded zero. Because the association was negative, the frozen rule bought the lowest fifth of training values and sold the highest fifth, and it abstained in between. Thresholds were the training 20th and 80th percentiles.

On the EUR/USD confirmation stride of 12 bars there were 2,053 non-overlapping opportunities and 650 actions. The mean next-bar result, including abstentions, was about −0.000035. The block-bootstrap lower bound was about −0.000054. An extra half pip and an extra one pip made the mean more negative. Always abstaining scored zero and beat this rule. Always buying scored about −0.000151.

A hindsight figure that takes the better of BUY and SELL after the outcome is known has a positive mean of about 0.000276, and about 71% of bars have one positive side. That figure is an upper bound, not a strategy, because the winning side is chosen after the move.

Recorded spreads are not a full OANDA GBP spread-betting cost, financing, slippage, or margin model.

## Feature classifications

`return_1` is `STATISTICAL_VALUE_ONLY`. The association is repeatable in sign and survives the pre-registered multiplicity adjustment, and the trading rule built from it loses money after the spread.

The other seven numeric directional tests are `NO_DEMONSTRATED_PREDICTIVE_VALUE`. Hour and session are `INCONCLUSIVE` because they were not put through the confirmatory correlation test. No feature is `POTENTIAL_ECONOMIC_SIGNAL_REQUIRES_INDEPENDENT_VALIDATION`.

## Candidate signal outcome

One research-only candidate was required by the frozen rule and was evaluated once. It failed the economic acceptance rule. It was not registered, and the retired quant stub was not reused.

## Focused tests and offline regressions

`tests/test_r38_feature_discovery.py`: 9 passed. Coverage includes dataset hashes, pip size, gap rejection, prefix invariance, a leaky fixture, embargo, quantile assignment, rank correlation, bootstrap reproducibility, multiplicity widening, next-bar entry, and the unchanged fail-closed stub.

R.8–R.37 suites exited 0. R.10 attempt 1 failed on the known `WinError 5` replacement and the separate retry passed with 69 tests and 5 skips. R.28 database scripts were not run.

## Remaining limitations

The September 2025–August 2026 files have already been used in earlier research. Overlapping 12-bar and 48-bar labels mean the row count is larger than the number of independent opportunities. The pairs move together. The detectable `return_1` effect is small enough that the spread removes it. Predicting that a volatile period will be followed by a larger absolute move does not provide a direction.

## Whether any feature merits further independent research

No feature merits a machine-learning trading experiment. `return_1` has a small statistical association and fails the cost test. Volatility, range, and volume say something about movement size and nothing usable about direction.

## Recommended R.39 direction

Do not start R.39 from this result. A later stage, if separately authorised, would need a new untouched sample and a frozen cost test before any model is trained. These features do not justify that training now.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
