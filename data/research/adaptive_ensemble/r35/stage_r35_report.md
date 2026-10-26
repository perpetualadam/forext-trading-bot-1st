# STAGE R.35 — OFFLINE AI LEARNING FOUNDATION AND DECISION JOURNAL REPORT

Classification: `R35_OFFLINE_AI_LEARNING_FOUNDATION_COMPLETED`

Completion means the offline data, journal, provenance, and leakage-control foundation is in place. It does not mean a model was trained or that a trading edge exists.

## Branch and preservation

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The dirty working tree was preserved. Nothing was committed, reset, cleaned, stashed, or rolled back. R.24–R.34 evidence was not modified.

All six strategies remain `active=false` and `authorised_for_live=false`.

`ai_ensemble.py`, `rl_agent.py`, `session_rules.py`, `experiment.py`, `bot_loop.py`, and `strategy_meta.py` match their preflight hashes. The retired quant stub still returns `quant_stub_removed`. An unverified RL agent still returns `UNAVAILABLE`. The default ensemble builder still does not register `LocalLLM`.

## Historical data

Six local M5 files were inventoried and left unchanged. Each runs from 2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC. Timestamps are UTC. Each file has bid and ask OHLC, a volume column, no duplicate timestamps, and no negative close spreads. Spread is the ask close minus the bid close, in price units.

| File | Rows | Gaps longer than 5 minutes | SHA-256 |
| --- | ---: | ---: | --- |
| AUD_USD_M5.csv | 74,563 | 81 | `e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0` |
| EUR_USD_M5.csv | 74,572 | 73 | `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091` |
| GBP_USD_M5.csv | 74,555 | 87 | `ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58` |
| USD_CAD_M5.csv | 74,560 | 82 | `a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60` |
| USD_CHF_M5.csv | 74,514 | 116 | `3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc` |
| USD_JPY_M5.csv | 74,557 | 85 | `e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c` |

The demonstration uses the existing EUR_USD file. That year was already researched in R.29–R.33. It is not an untouched final test, and a new chronological split does not make it unseen.

## Feature pipeline

Schema `r35.features.v1`, SHA-256 `7d15b98d9bfe99136f2de5e05522d9cef623539b38f7ab61e9ea722a24889946`.

Features at a decision bar use that completed candle and earlier completed candles. They do not use a later candle. An incomplete candle is dropped. Rolling statistics end at the decision bar. There is no global normalisation.

The columns are one-bar midpoint return, 20-bar return volatility, 14-bar ATR, fast/slow moving-average distance, 12-bar momentum, close spread, UTC hour, a UTC session bucket, 20-bar range, and source volume. A row is feature-valid only when every required value is finite and the spread is non-negative. The first 20 bars are warm-up.

Prefix tests confirm that adding later bars does not change earlier feature values. A synthetic fixture that copies the next return into the current row fails that check.

## Outcome labels

Protocol `r35.labels.v1`, SHA-256 `dc914245aa072f1922b656634f473cd1c641cd01fa1f4c217b21ab1decb0ed51`.

The primary horizon is 12 M5 bars. A label exists only when the later timestamp is exactly 12 times 300 seconds after the decision bar. The hypothetical BUY result enters at the decision ask close and exits at the later bid close. The hypothetical SELL result enters at the decision bid close and exits at the later ask close. The midpoint change is stored separately. These are labels, not executed trades.

This differs from the R.30 simulator, which enters on a later bar inside the scalp lifecycle. R.35 labels the decision close against a later close.

Missing prices, a broken time gap, and the end of the file are unevaluable. Adjacent labels overlap. The evaluation embargo handles that overlap later; the label table keeps the overlapping rows. Label columns are not part of the feature frame.

Abstention has no chosen side, so the journal does not store a cost-adjusted decision outcome. Both hypothetical sides remain available in the label frame for a future model.

## Journal and mistakes

Every kept bar receives a deterministic research decision id. With no trained model, every row is `prediction_unavailable`: no direction, no probabilities, and no confidence. An evaluable market outcome can be stored without a prediction error. An invented error on an unavailable prediction is rejected.

Mistake classes distinguish an incorrect direction, a correct direction with a negative cost-adjusted result, a low-confidence correct call, a high-confidence incorrect call, a correct abstention, a possible missed opportunity, insufficient information, an invalid prediction, and an unevaluable outcome. A loss is not automatically a model mistake. Log loss and Brier score run only when the caller supplies probabilities. The demonstration supplies none.

## Evaluation controls

Protocol `r35.evaluation.v1`, SHA-256 `bab4a868f1b789b795c5c124f86f7975d0b6ca9a5c0848b3323f743c2d8f81e9`.

The prepared split is chronological: 60% train, 20% validation, 20% test, with a 12-bar embargo and a 20-bar warm-up. On the EUR_USD file the index ranges are train `[20, 44731)`, validation `[44743, 59645)`, and test `[59657, 74560)`. Model selection, scalers, and imputers are specified to use the training prefix only. The held-out slice is not a licence to tune. Baselines named for later work are always-abstain and the majority training direction. The EUR_USD year remains research-exposed.

## Demonstration

Two identical runs produced the same summary hash and the same journal-id hash.

| Item | Value |
| --- | --- |
| Rows read | 74,572 |
| Valid feature rows | 74,552 |
| Warm-up exclusions | 20 |
| Labelled observations | 73,697 |
| Unevaluable observations | 875 |
| Journal entries | 74,572 |
| Missing predictions | 74,572 |
| Feature-schema hash | `7d15b98d9bfe99136f2de5e05522d9cef623539b38f7ab61e9ea722a24889946` |
| Labelling-protocol hash | `dc914245aa072f1922b656634f473cd1c641cd01fa1f4c217b21ab1decb0ed51` |
| Reproducible | yes |

No accuracy is reported. The labels are not trading signals and are not a profitability result.

## Legacy cleanup

Directional expectations of `_quant_stub_vote` were retired in the silent-skip, momentum, and mapping tests. The shadow and decision-quality comparisons still hold because both sides now abstain. Three old `evaluate()` patches targeted `bot_loop.fetch_ohlcv`, which is no longer on that module. Those tests were retired rather than calling the live candle path. Operational descriptions in `live_path.py`, `reports.py`, and `shadow/fidelity.py` now say the stub abstains and an unverified RL agent does not sample an action. The historical shadow copy was left in place.

## Source hashes

Unchanged operational files:

| File | SHA-256 |
| --- | --- |
| `forex_bot/ai_ensemble.py` | `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa` |
| `forex_bot/rl_agent.py` | `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` |
| `forex_bot/session_rules.py` | `1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1` |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/strategy_meta.py` | `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` |
| `forex_bot/research/ml_prediction.py` | `97ba722204734b480ecc610cc26756a42cabafb9d4ded81070ced146580bd7bc` |

Changed in R.35:

| File | SHA-256 |
| --- | --- |
| `forex_bot/research/decision_journal.py` | `793b92f35d2c2a7565ff3a6cbbe3229cbfabfcc2828250c6a3f2016eef5cd3c0` |
| `forex_bot/research/learning/protocol.py` | `5c1038ca6e11f79820f2063f81f83fbf58cb87f617fc3d9ec2f412f32534b0fc` |
| `forex_bot/research/learning/data_validation.py` | `9b1c781543a876cca89c663bc7d25337b0716ba24a243c739f18ebc8cb173856` |
| `forex_bot/research/learning/features.py` | `4e532e5ee9e8c3445e5f10c2c978bf57fe67fdaef2672439a609b8acfee3f03e` |
| `forex_bot/research/learning/labels.py` | `9d3ba22145481d6aaab4c0d32c34d18579dc2c5647f8b715da0bc406074a3390` |
| `forex_bot/research/learning/journal.py` | `4eaf943204c8ce2996fe98342b39838710f3acdfefa28fcb561dc458740886a7` |
| `forex_bot/research/learning/mistakes.py` | `406970c5b6cf21a4d6070fa4456d93cdc47fef1267f96d9b8c426c74c71224c5` |
| `forex_bot/research/learning/splits.py` | `e6521f807d02d0bf08e88449f23ac193910c96a78c57367ea74c02464bd3b035` |
| `forex_bot/research/learning/dataset.py` | `7334130d2fe4c983ac4b65039d30f287a2372d272a37b10faf4d82cf2c1af9eb` |
| `forex_bot/decision_quality/live_path.py` | `46135876e455565328ef74c429dc862de691977216062f2e0487ff169eb78900` |
| `forex_bot/decision_quality/reports.py` | `b5eed0a5ccf7523704543f0fa5482ee1fc1caa2abc9c27c1c675870f17c20528` |
| `forex_bot/shadow/fidelity.py` | `198d7326153daae72ebef439be0153c1ed8acc1aca8123396fb14379aff30e7f` |

## Tests

R.35 focused tests: 10 passed. Legacy files: 55 passed. R.8–R.34 offline regressions all exited 0, with the same pass, skip, and deselect counts as the R.34 run. Details are in `13_regression_results.md`.

## Limitations and R.36 readiness

The foundation can support a later supervised experiment: causal features, separate labels, a journal that can hold a real prediction, an explicit mistake taxonomy, and a chronological embargo. It is not ready as a profitability claim. No model exists. The EUR_USD year must not be treated as unseen. Probability scores stay uncomputed until a real model emits probabilities.

R.36 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
