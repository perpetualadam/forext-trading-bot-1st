# R.33 frozen evaluation protocol

Frozen at 2026-10-20T12:17:00+01:00, before any R.33 predictive measurement.

This stage audits the existing AI-vote and RL gate. It does not activate a strategy, retrain a model, or treat the R.30–R.32 EUR_USD year as an untouched holdout.

## What can be evaluated

The reachable production decision is `evaluate` → `_evaluate_impl` → `dispatch_production_iteration` → `evaluate_one_instrument_iteration`, with `invoke_vote=True` and `invoke_rl=True`.

| Component | This stage | Reason |
| --- | --- | --- |
| Quant stub `_quant_stub_vote` | Deterministic offline reproduction | Source defaults only. No weights file. |
| External LLM voters | Not evaluated | Construction depends on API keys and network calls. |
| Tabular `RLAgent` | Wiring tests only | No saved Q-table is loaded into the live agent. The default policy is stochastic. |
| `SeqModel` and `compute_nn_pred` | Not scored | They sit after a status the shared decision never returns, and the stub does not read `nn_pred`. |
| Research `model_vote` | Not the live path | It is not called by `evaluate_one_instrument_iteration`. |

The historical score uses `_quant_stub_vote` with the source defaults: SMA epsilon `1e-6`, momentum threshold `0.0001`, confidence scale `1000`. Research code sets `ENSEMBLE_MODE=quant` in its own process and does not construct API voters. It does not change production defaults.

`HOLD` is not a stub output. `allow` false is an abstention, even when a direction is still attached. Only `allow` true with BUY or SELL is actionable. Abstentions stay in the coverage count and out of the return mean.

## Data and period status

One file: `data/historical/EUR_USD_M5.csv`. Bid OHLC feeds the indicators. Bid and ask closes form the midpoint outcome and the spread. No other pair, no M1 file, and no later extract.

The file runs from 2025-09-01 through 2026-08-31. R.30, R.31, and R.32 already used it. There is no local training manifest for the stub thresholds. The period is research-exposed, and the threshold provenance is unknown. It is not an independent holdout.

Indicator windows are the shared-path defaults, because `compute_indicators` is called there without a strategy lookback: fast average 5, slow average 20, ATR 14. The decision bar's rolling values are taken from the full causal series. A prefix check at bar 5000 must match before scoring. The volatility percentile gate is counted on a trailing 200-bar causal ATR window and is not part of the scored sample. Applying that percentile to the whole file would use later bars.

## Outcomes

Horizons are 1, 6, 12, and 48 M5 bars. The decision uses 12 bars. A horizon is missing unless the later bar is exactly `300 * h` seconds after the decision bar. Missing rows are counted and not filled.

The origin is the decision bar's bid/ask close midpoint. The direction-adjusted return is the later midpoint minus that origin for BUY, and the opposite for SELL. The return uses later closes only.

Overlapping means use every actionable bar with a complete horizon. Non-overlapping means walk those bars in time and then skip `h` bars. The decision uses the non-overlapping 12-bar sample. BUY and SELL are reported separately and are not selected after the fact.

## Baselines and uncertainty

The non-overlapping paths stay fixed. Seeds use NumPy `Generator(PCG64(seed))`.

| Baseline | Seed | Draws |
| --- | ---: | ---: |
| Permutation of the observed BUY/SELL labels | 33001 | 200 |
| Fair coin, 0 = SELL and 1 = BUY | 33101 | 200 |
| Always BUY, and always SELL | none | 1 each |

The comparison point is the linear 95th percentile of the null means.

The interval is a non-wrapping block bootstrap, block length 20, 400 replicates, seed 33201, using the 2.5 and 97.5 linear percentiles. Fewer than 20 events leaves the interval uncomputed.

Calendar windows, by decision-bar time:

| Window | Start, inclusive | End, exclusive |
| --- | --- | --- |
| 2025-09_2025-11 | 2025-09-01 | 2025-12-01 |
| 2025-12_2026-02 | 2025-12-01 | 2026-03-01 |
| 2026-03_2026-05 | 2026-03-01 | 2026-06-01 |
| 2026-06_2026-08 | 2026-06-01 | 2026-09-01 |

A window with fewer than 30 events does not count. One EUR_USD pip is 0.0001. The spread gate uses the median full close spread on the same non-overlapping bars.

## Decision

These labels apply to the quant stub. The other components keep the classifications in the table above.

Let `m` be the non-overlapping 12-bar mean. Let `(lo, hi)` be its interval. Let `s95` and `r95` be the null percentiles. Let `spread` be the median full spread. Let `q+` and `qn` be the populated windows with a positive mean and the populated windows.

1. `m` missing: `INCONCLUSIVE`.
2. `m <= 0`: `EVALUABLE_NO_CREDIBLE_EDGE`.
3. The overlapping mean is missing or has the opposite sign: `INCONCLUSIVE`.
4. The interval is missing or `lo <= 0`: `INCONCLUSIVE`.
5. `m > s95`, `m > r95`, `qn >= 3`, `q+ >= 3`, and `m > spread`: `INCONCLUSIVE`, rule `exposed_period`. A pass on this file is not independent evidence.
6. Every remaining case: `EVALUABLE_NO_CREDIBLE_EDGE`.

`EVALUABLE_WITH_CREDIBLE_EVIDENCE` is not available for this file. The stub has no training record, and the year was already used. Synthetic vote and RL fixtures test wiring only. They are not model performance.

No horizon or threshold above is revised after the measurements.
