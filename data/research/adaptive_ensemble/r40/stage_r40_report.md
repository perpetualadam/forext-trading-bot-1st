# STAGE R.40 — HIGHER-TIMEFRAME MARKET STRUCTURE AND EXPANDED CURRENCY-PAIR FEASIBILITY REPORT

## Overall classification

`R40_MARKET_STRUCTURE_FEASIBILITY_COMPLETED`

R.40 assessed the local M5 files, documented causal swing and trendline rules, reviewed the R.39 range and breakout results as open questions, ranked a currency-pair verification list, specified a multi-timeframe clock, and set the bar for a later independent test. No model was trained, no strategy was optimised, and no trading backtest was run.

## Branch, HEAD, and preservation

- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`
- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Working tree: dirty, and the unrelated changes were left in place
- R.24–R.39 stage evidence is present
- All six strategies remain inactive and unauthorised: `scalp`, `trend`, `mean_reversion`, `swing_trend`, `swing_mean_reversion`, `swing_breakout`
- Quant stub reason: `quant_stub_removed`. The stub does not allow a trade
- Unverified reinforcement learning: `UNAVAILABLE`
- `timeframes.py` is not imported by `bot_loop.py` or `ai_ensemble.py`
- Operational hashes are unchanged: `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`, `strategy_meta.py` `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`, `ai_ensemble.py` `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa`, `rl_agent.py` `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e`, `session_rules.py` `1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1`, `regimes.py` `f3d2ffdbe77e17808e30b3d034b5b681fd631426349dbbd107c4f4c83cfdc0ea`

## Existing dataset inventory

`data/historical/` contains six M5 files and no H1 or H4 files. Each file runs from 2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC. Columns include mid prices, volume, a complete flag, and bid and ask OHLC. Duplicate timestamps, negative spreads, and incomplete source rows were zero. SHA-256 values match the R.39 inventory. Median close spreads are about 1.3 to 1.9 pips, with USD_JPY at about 0.016 price units and a local pip of 0.01. Details are in `02_data_inventory.json` and `03_h1_h4_feasibility.md`.

This year has already been examined by R.29 through R.39. Those stages did not show a cost-adjusted trading edge. R.39's range, trend, breakout, and adaptive selector all lost money. That record stands.

## H1 and H4 data feasibility

M5 bars can build a research H1 candle when all twelve UTC-aligned five-minute bars exist, and an H4 candle when all forty-eight exist. The higher-timeframe candle opens on the UTC boundary (hour, or 00/04/08/12/16/20). Open is the first constituent, high is the max, low is the min, close is the last, and volume is the sum of M5 volume. Bid and ask are aggregated separately. A missing bar, a broken 300-second step, or a constituent flagged incomplete rejects the bucket. Nothing is forward-filled. The close is known at `open + period`.

| Instrument | Complete H1 | Incomplete H1 | Complete H4 | Incomplete H4 |
| --- | ---: | ---: | ---: | ---: |
| AUD_USD | 6,189 | 27 | 1,478 | 130 |
| EUR_USD | 6,196 | 20 | 1,483 | 125 |
| GBP_USD | 6,184 | 32 | 1,478 | 130 |
| USD_CAD | 6,188 | 28 | 1,483 | 125 |
| USD_CHF | 6,163 | 53 | 1,460 | 148 |
| USD_JPY | 6,185 | 31 | 1,476 | 132 |

Each file has 51 gaps longer than 48 hours. The largest is 49.08 hours, consistent with a weekend. Each file also has 3 gaps between 1 and 48 hours. Those gaps were not named as holidays. USD_CHF has more short gaps and more rejected higher-timeframe buckets. The file ends at 23:50 UTC, so the final H1 hour and the 20:00 H4 block are unfinished and were rejected. The last complete H1 opens at 22:00 UTC on 2026-08-31. The last complete H4 opens at 16:00 UTC the same day.

## Causal trendline and swing-point design

Definition id: `r40.structure.v1`. It was written down and not applied to the stored year.

A swing high of width `k = 2` requires the pivot high to be strictly above the two candles before it and the two candles after it. It becomes available when the second later candle completes. On H1 that is three hours after the pivot hour opens. On H4 it is twelve hours after the pivot candle opens. A swing low is the mirror. Ties are not swings. A missing candle in the window yields `UNCERTAIN`.

Higher highs, higher lows, lower highs, and lower lows compare only swings that are already confirmed. `UPTREND` requires both a higher high and a higher low. `DOWNTREND` is the mirror. Anything mixed or incomplete is `TRANSITION` or `UNCERTAIN`, and a later protocol maps both to `NO_TRADE`. The state changes only at a confirmation time.

A trendline needs two confirmed swings of the same kind. It exists at the confirmation time of the later swing. A newer swing creates a new line and leaves the old line's historical value in place. A touch or a break is a later completed candle. A wick through the line is not a break. No distance buffer was selected.

Support and resistance are confirmed swing prices. A range needs both sides, at least two completed reactions on each, and no completed close outside the pair of levels before the range is declared. The range is known at the last required reaction.

## Range and breakout research findings

R.39 was not rerun and its rules were not edited. On EUR_USD confirmation, the range stream resolved 561 trades, mean fractional return about −0.000133, with 333 stop exits, 78 target exits, and 150 time exits. Trend, breakout, and the selector were also negative on that window, on the design window, and on all six pairs.

The stop-versus-target imbalance is a recorded property of that rule. It does not identify which clause caused the loss. Open questions, still hypotheses, are whether the window was a range with repeated reactions, whether the boundary was stable, how false breaks returned, how width compared with spread, where a stop would sit relative to a confirmed swing, whether the midpoint was reachable inside the hold, whether the range had already ended, and whether a completed H4 state would have said something different. R.39's five-versus-twenty-bar average, twenty-bar breakout, ATR exits, and twelve-bar hold remain short M5 tests. They do not separate continuation, pullback, trendline bounce, structural breakout, failed breakout, and range-to-trend transition. Those six labels are defined as future research categories. No classifier was trained.

## Additional currency-pair shortlist

GBP_JPY, EUR_JPY, EUR_GBP, AUD_JPY, NZD_USD, and EUR_AUD have no local candles. They are not authorised instruments. Broker availability on the GBP spread-betting account was not checked. No spread was invented.

Verification priority, which is not a profit ranking:

1. NZD_USD, because it is the only name that adds a currency absent from the six files.
2. EUR_GBP, because the cross is a different instrument from the two USD pairs and is quoted in GBP.
3. EUR_JPY, then GBP_JPY, then AUD_JPY. Each needs its own file. The local pip rule would use 0.01 for a JPY quote.
4. EUR_AUD last, because both currencies already have USD pairs.

A cross must not be synthesized by dividing two stored USD pairs. The research universe stays the six files until a later stage is authorised to acquire data and check the contract.

The supplied video URL was not opened. No local transcript of it exists. The trend, bounce, break, and abstention ideas are labelled `GENERAL_TRENDLINE_RESEARCH_CONCEPT`.

## Multi-timeframe architecture

H4 is context, H1 is structure, and M5 is a possible later timing bar. A join at time `t` may use a higher-timeframe candle only when that candle's `available_at` is at or before `t`. The H4 candle that contains `t` stays invisible to the M5 rows inside it. The same rule applies to the current hour. `visible_close` implements that read. A missing completed candle becomes `UNCERTAIN` and then `NO_TRADE`. Pip size follows the quote currency. The research module does not place an order or set a strategy flag.

## Transaction-cost and holding-period considerations

A longer hold can make a spread a smaller fraction of a larger move only if that move is predictable after costs. R.38 and R.39 did not show that. The entry spread is still paid. An H4 swing is known twelve hours after the pivot opens, so a subsequent hold can cross a financing time and can be open across the 49-hour weekend gap seen in every file.

The stored median spreads describe these CSV files. They are not the account's spread-bet prices. The test-account balance is not a cost input. Financing, margin, minimum stake, guaranteed-stop charges, GBP conversion, and the difference between practice and live contracts are unknown and were not requested from the broker. Those items need a separate verification before any operational use.

## Independent validation requirements

The stored year is research-exposed, and the files end on 2026-08-31. A few weeks of it are not an independent test. A performance claim needs new bid/ask M5 data outside this year, long enough to cover more than one regime. The counting floor proposed here is 100 pre-registered non-overlapping events per instrument after embargo, with correlated USD pairs treated as one portfolio. One hundred events is a floor for counting the test, not a claim of statistical power.

Definitions, `k`, and any buffer have to be frozen before that data is scored. Training, validation, and test stay chronological, with a purge and embargo at least as long as the confirmation delay plus the hold. Uncertainty has to respect overlapping swings. A cost-adjusted mean at or below zero, an interval that includes zero, or a count under the floor ends the line. If the fresh data is not already stored, the choices are to wait or to authorise a separate acquisition stage. This stage did not acquire it.

## AI learning design

A later authorised journal row can store context, confirmed swings, line and range state, eligibility, the decision or the abstention, data quality, and protocol hashes. A hypothetical outcome belongs only in a stage that is authorised to evaluate one. Confidence belongs only when a frozen model actually produced a probability. The journal cannot authorise trading, cannot flip a strategy flag, and cannot rewrite its own rules. Promotion still requires an offline result on fresh data and an explicit approval.

## Ranked future research priorities

A is the next piece of work: implement the frozen swing and trendline clock on the existing six pairs and test causality only. No entries and no profit score in that stage.

B comes after A. The range questions need those swing levels. Refitting the R.39 window would repeat a failed rule.

C is a separate data and contract check, led by NZD_USD. It waits for its own authorisation.

D, the adaptive H4/H1/M5 selector, waits until one structure definition has a pre-registered fresh-data result. R.39's selector already lost money.

These four are not simultaneous builds.

## Focused tests and offline regression results

`tests/test_r40_timeframes.py`: 6 passed. R.8–R.39 suites all exited 0 on the first attempt, with the same pass and skip counts as the last clean R.39 run. R.10 passed on the first attempt: 69 passed, 5 skipped. `WinError 5` did not occur. There were no retries. R.28 PostgreSQL scripts were not run. Counts are in `14_regression_results.md`.

## Remaining limitations

The swing rules were not counted on the historical year, so R.40 has no structure-event frequency and no economic result. `k = 2` was not compared with other widths, and that comparison has to stay frozen rather than searched on this year. Holiday names for the three medium gaps were not assigned. USD_CHF loses more hours than the other pairs when incomplete buckets are dropped. Volume is the sum of the source M5 volume column. Financing, margin, and account eligibility are unknown. The six pairs move together, so six negative or positive results would still be one correlated sample. The additional pairs cannot be studied until new files and a contract check exist.

## Recommended R.41 direction

Authorise, separately, a bounded offline descriptive study that applies `r40.structure.v1` with `k = 2` to the derived H1 and H4 candles of the existing six pairs. The output should be availability times, prefix checks, and counts of confirmed swings and `UNCERTAIN` gaps. It should not emit entries, tune `k`, score profit, download data, or connect a selector. Expanded-pair acquisition and the adaptive architecture stay outside that stage.

R.41 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
