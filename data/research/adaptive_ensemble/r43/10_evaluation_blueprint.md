# R.43 independent evaluation blueprint

This blueprint is not an evaluation. No backtest was run.

## Clocks already frozen

- M5, H1, and H4 candles are known at their own close. An unfinished higher-timeframe candle stays invisible.
- Swing confirmation remains `k = 2`. A swing is known three periods after the pivot open.
- Trendlines use the R.41 consecutive-swing rule and the R.42 lifecycle: one first break, then no repeated break, and no reactivation.
- Ranges use the R.42 latest-level pair and the reach-episode rule. R.42 confirmed one GBP_USD H1 range in the exposed year, and that range was replaced on the confirmation candle. H4 confirmed none. That count is a warning. The definition is not relaxed in order to create more events, and it is not relaxed after seeing a holdout.

## Execution assumptions for a later test

- A feature at time T may use only information with `available_at` at or before T.
- A decision at T is not filled on the same bar.
- The next completed bar supplies the bid and ask. Entries buy at the ask and sell at the bid, or the spread-bet equivalent once the contract check names it.
- Stops and targets are conservative: a gap through both levels in one bar is a loss at the worse side. The rule is written before the test.
- Weekend and missing-data gaps are not filled. A position that would be held across a gap uses the next available bid and ask and the financing rule, or the test abstains if financing is unknown.
- Slippage is a stated sensitivity, not a fitted residue. At least one wider-spread case is reported beside the historical bid/ask.
- Stake and margin use the verified GBP contract. Until that exists, results stay in price units and are labelled incomplete.
- GBP results are reported only when the conversion and the pip value come from the contract record. They are not inferred from the £97.15 balance figure.

## Dependence

- The six USD pairs are one correlated book. Pair-level counts are not added into an independent sample size.
- Opportunities that overlap in time are one exposure cluster.
- Confidence intervals need a dependence-aware method written in the protocol. A bar-level interval that assumes independence is not acceptable.
- Multiple rules, multiple timeframes, and multiple instruments are a multiple-testing problem. The protocol names the family of tests before the run.
- R.42's single confirmed range is below any serious minimum event count. A later test that still uses that definition must be able to return `INSUFFICIENT_EVENTS` and stop.

## Decision states

- `UNCERTAIN` and `NO_TRADE` are outcomes. They are not converted into a direction.
- A candidate range is not a confirmed range and is not an entry.
- Abstention is reported separately from wins and losses.

## Acceptance, rejection, and stopping

- Accept only if the pre-registered cost-aware result stays positive after financing, slippage sensitivity, and the dependence-aware interval, and the event count meets the minimum written in the protocol.
- Reject if the point estimate is non-positive, if the interval includes a material loss, or if the event count is below the minimum.
- Stop after the single pre-registered evaluation. Do not add a variant because the first one failed.
- A rejected rule stays rejected for that holdout.
- This blueprint does not set a numeric profit target. The later protocol must set the minimum event count and the cost assumptions before any holdout read.
