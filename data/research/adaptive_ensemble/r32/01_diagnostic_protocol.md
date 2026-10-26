# R.32 frozen diagnostic protocol

Frozen at 2026-10-20T02:21:00+01:00, before any R.32 diagnostic measurement.

This stage explains the two R.31 mean-reversion results. It does not change their rules, the R.30 lifecycle, or the R.31 screening gate. It does not choose a new strategy.

The R.30/R.31 sample has already been examined. These diagnostics are exploratory. A pass is not a fresh out-of-sample validation and is not a trading authorisation.

## Populations

Both strategies use the existing rules in `signal_from_arrays`: sell when bid close is above the upper Bollinger band, buy when it is below the lower band. `mean_reversion` uses lookback 50. `swing_mean_reversion` uses lookback 100. Those lookbacks stay as they were in R.31.

Dataset: `data/historical/EUR_USD_M5.csv` only. The same cleaned bid/ask bars as R.31. No other pair, no M1 file, and no later extract.

Trade population: the R.31 spread-only closed trades in `trades_mean_reversion.csv` and `trades_swing_mean_reversion.csv`. One position at a time, so these trades do not overlap. Totals must reconcile to `data/research/adaptive_ensemble/r31/performance.json` before any research decision.

Signal population: direction-change events from the recomputed R.31 signals. An event is a BUY or SELL whose previous bar is not the same direction. This is the R.31 `entry_events` definition. It includes events that the lifecycle did not trade.

The in-sample and out-of-sample split used to reconcile P&L is the R.31 split: in-sample is `entry_index < floor(0.70 * cleaned_rows)`. That split is a reconciliation check. It is not reused as evidence that a signal is new.

## Price and cost attribution

For each spread-only trade the recorded columns already separate the two ledgers:

- Price-movement P&L is `mid_pnl`: the direction-adjusted change from `entry_mid` to `exit_mid`, times units.
- Quoted P&L is `pnl`: the direction-adjusted change from `entry_price` to `exit_price`, times units.
- Execution difference is `pnl - mid_pnl`.

The two ledgers add as `pnl = mid_pnl + execution difference`. The spread is not subtracted a second time.

On the spread-only ledger, slippage is zero. For exits that use a market quote (`signal_reversal`, `gap_exit`, `weekend_flatten`, `market_closed`, `end_of_data`, `stop_gap`, `take_profit_gap`), the execution difference equals the entry half-spread plus the exit half-spread, times units, with a minus sign. The half-spreads are `entry_price - entry_mid` for a long and the opposite for a short, and the same construction at the exit.

For `stop`, `take_profit`, and `ambiguous_stop`, the simulator stores the order price as both the fill and the midpoint reference. The execution difference then equals the entry half-spread only. The exit spread is not observed. It is left unmeasured. It is not recorded as zero.

A per-trade residual is the execution difference minus that spread component. Reconciliation requires every absolute residual to be below `1e-6` USD, the sum of `pnl` and of `mid_pnl` to match the R.31 in-sample, out-of-sample, and whole-sample totals within `1e-4` USD, and the row counts to match. Ending cash must equal 10,000 plus the sum of `pnl`, within the same total tolerance.

The R.31 half-pip and one-pip scenario totals are a separate hypothetical cost. Their difference from the spread-only total is additional simulated slippage. It is not folded into the spread component. Commission, financing, and swap stay unmeasured and are not called zero.

If the identity fails, the discrepancy is reported and no research decision is made from a forced split.

## Forward returns

Horizons are fixed at 1, 6, 12, and 48 M5 bars: 5 minutes, 30 minutes, 1 hour, and 4 hours. The decision uses the 12-bar horizon only. The other three are descriptive. A horizon is not added or dropped after the results.

The origin is the signal bar. `P0` is the midpoint of that bar's bid and ask close. `P_h` is the midpoint of the close `h` bars later. The horizon is missing when bar `i+h` does not exist or its timestamp is not exactly `300 * h` seconds after bar `i`. Missing horizons are counted and are not interpolated.

The direction-adjusted return is `P_h - P0` for BUY and `P0 - P_h` for SELL. The signal bar's own close is the origin, so the return uses later closes only.

Two samples are reported at each horizon:

- Overlapping: every entry event with a complete horizon. Neighbouring events share future bars. This mean is descriptive.
- Non-overlapping: walk the events in time. Keep an event with a complete horizon, then ignore later events until index `i+h`. The kept events do not share the horizon window. The decision uses this sample.

BUY and SELL are reported separately on the non-overlapping sample. The decision uses the pooled direction-adjusted mean. A stronger side is not selected afterwards.

The spread comparison uses the median full bid/ask close spread on the same non-overlapping signal bars. The median next-bar open spread is reported beside it and is not the gate.

## Excursions

For each closed trade, maximum favourable excursion and maximum adverse excursion use the exit-side high and low: bid for a long, ask for a short.

- A quote exit at the open uses bars from the entry index inclusive to the exit index exclusive. The exit bar's high and low are after the fill.
- `stop`, `take_profit`, and `ambiguous_stop` include the exit bar. The high and low of that bar have no known order, so both extremes are reported and neither is treated as having happened first.
- `end_of_data` includes the final bar because the fill is that bar's close.
- A timestamp jump inside the observed span is flagged. The missing interval is not filled in. Extremes use the observed bars only.

Favourable excursion is the best exit-side price relative to the entry fill, floored at zero. Adverse excursion is the worst, floored at zero. Realised price movement remains `mid_pnl / units`. Entry spread is the entry bar's ask open minus bid open. Exit spread is the bid/ask spread of the quote used for a market exit, and is null when the exit reference is an order price.

These measurements do not define a new stop, target, or exit.

## Turnover

Trades are counted by entry timestamp. Months are UTC `YYYY-MM`. Weeks are ISO weeks. Holding time is the recorded `holding_seconds`. Reversal frequency is the share of exits whose reason is `signal_reversal`.

Median entry spread is stated in pips, with one EUR_USD pip equal to 0.0001. Spread relative to favourable movement is the median entry spread divided by the median favourable excursion, when that excursion is positive.

Midpoint expectancy is the mean of `mid_pnl`. Bid/ask expectancy is the mean of `pnl`. If the midpoint mean is positive, the break-even extra price is that mean divided by the mean units: the additional adverse price that would zero the midpoint mean. If the midpoint mean is not positive, that tolerance is not meaningful.

## Baselines

All baselines use the primary non-overlapping event indices. Paths stay fixed. Only the direction labels change. Seeds use NumPy `Generator(PCG64(seed))`.

| Baseline | Seed, mean reversion | Seed, swing mean reversion | Draws |
| --- | ---: | ---: | ---: |
| Permutation of the observed BUY/SELL labels | 32001 | 32002 | 200 |
| Independent fair coin, 0 = SELL and 1 = BUY | 32101 | 32102 | 200 |
| Always BUY, and always SELL | none | none | 1 each |

The shuffle keeps the same number of buys and sells. The coin toss does not. Always-BUY is the drift at those timestamps. The null statistic is the mean direction-adjusted 12-bar return. The full list of null means is retained. The comparison point is the linear 95th percentile of that list.

## Uncertainty and subperiods

Inference uses the non-overlapping 12-bar returns. A circular-free block bootstrap draws contiguous blocks of 20 events with replacement, rebuilds a sample of the original length, and repeats 400 times.

| Strategy | Bootstrap seed |
| --- | ---: |
| mean_reversion | 32201 |
| swing_mean_reversion | 32202 |

The interval is the 2.5 and 97.5 linear percentiles of the bootstrap means. If fewer than 20 events are available, the interval is not computed.

The interval assumes that blocks of 20 consecutive non-overlapping events are exchangeable. That is an approximation for volatility regimes, not a claim that the blocks are independent of each other.

Subperiods are fixed calendar windows, by the signal-bar timestamp:

| Window | Start, inclusive | End, exclusive |
| --- | --- | --- |
| 2025-09_2025-11 | 2025-09-01 | 2025-12-01 |
| 2025-12_2026-02 | 2025-12-01 | 2026-03-01 |
| 2026-03_2026-05 | 2026-03-01 | 2026-06-01 |
| 2026-06_2026-08 | 2026-06-01 | 2026-09-01 |

A window with fewer than 30 non-overlapping events does not count as favourable or unfavourable.

Effect size is the non-overlapping mean divided by the sample standard deviation of those returns. It is descriptive.

## Decision

Each strategy is judged on its own. The better of the two is not chosen after the fact. The labels are `CONTINUE_RESEARCH`, `STOP_RESEARCH`, and `INCONCLUSIVE`.

Let `m` be the non-overlapping 12-bar mean direction-adjusted return. Let `(lo, hi)` be its bootstrap interval. Let `s95` and `r95` be the shuffle and coin-toss 95th percentiles. Let `spread` be the median signal-bar full spread on that same sample. Let `q+` be the number of windows with at least 30 events and a positive mean, and `qn` the number of windows with at least 30 events.

Apply the first matching line:

1. `m <= 0`: `STOP_RESEARCH`.
2. The overlapping 12-bar mean has the opposite sign to `m`, or it is missing: `INCONCLUSIVE`.
3. The interval is missing, or `lo <= 0`: `INCONCLUSIVE`.
4. `m > s95`, `m > r95`, `qn >= 3`, `q+ >= 3`, and `m > spread`: `CONTINUE_RESEARCH`.
5. Every remaining case: `STOP_RESEARCH`.

`CONTINUE_RESEARCH` means the pre-registered checks found a direction-adjusted midpoint association that cleared this uncertainty, baseline, stability, and one-spread screen. It does not mean the R.31 lifecycle is profitable, and it does not authorise an order. `STOP_RESEARCH` and `INCONCLUSIVE` both end further work on that current configuration in this program. `INCONCLUSIVE` means the checks do not agree; this stage does not open another study to break the tie.

No threshold above is revised after the measurements.
