# STAGE R.41 — CAUSAL SWING AND TRENDLINE IMPLEMENTATION REPORT

## Overall classification

`R41_CAUSAL_MARKET_STRUCTURE_COMPLETED`

The frozen `k = 2` rules now run on completed H1 and H4 candles for the six local pairs. Swings, trend states, trendlines, touches, and breaks carry availability times. Support and resistance levels are recorded. Ranges stay uncertain because the pairing rule was never defined. No buy or sell decision, entry, exit, or profit figure was produced.

## Branch, HEAD, and preservation

- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`
- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Working tree: dirty, and the unrelated changes were left in place
- R.24–R.40 evidence is present
- All six strategies remain inactive and unauthorised
- Quant stub: `quant_stub_removed`, and it does not allow a trade
- Unverified reinforcement learning: `UNAVAILABLE`
- `structure.py` is not imported by `bot_loop.py` or `ai_ensemble.py`
- Operational hashes are unchanged, including `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` and `strategy_meta.py` `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`

## Source-data and protocol hashes

Implementation `r41.structure.v1`, parent `r40.structure.v1`.

- Protocol SHA-256, written before the counts: `8880d210ca38e783c1a2615c50a90688ed75825adf1652e525a5bfe55b60e1d0`
- `structure.py` SHA-256: `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc`

The six M5 hashes match the R.35–R.40 inventory. Complete-candle counts match R.40, from 6,163 to 6,196 H1 candles and 1,460 to 1,483 H4 candles. Incomplete buckets were rejected again, including 20 H1 and 125 H4 buckets on EUR_USD. USD_CHF still has the most rejected buckets.

## Implemented swing rules

A swing high uses bid high and must be strictly above the two earlier and two later completed candles. A swing low uses bid low and strict inequality. Ties are counted and are not swings. The four neighbours must sit exactly one period apart. A weekend or a missing hour rejects that window. The pivot is stored at its own candle, and it becomes usable only when the second later candle closes. That confirmation time is three hours after an H1 pivot opens and twelve hours after an H4 pivot opens. Every confirmed swing in the run matched that delay. The final candles of the file cannot confirm a pivot that still needs later bars.

## Confirmation timing and trend states

The first swing of each type is `UNCERTAIN` because it has no prior confirmed partner. A later swing is a higher or lower high, or a higher or lower low, only against the previous confirmed swing of the same type. Equal prices stay `UNCERTAIN`.

`UPTREND` requires the latest high to be a higher high and the latest low to be a higher low. `DOWNTREND` is the lower-high and lower-low pair. Mixed relations are `TRANSITION`. The state is written on each completed candle and changes only when a swing that has just become available changes a relation. The run checks that every change has a supporting swing.

On EUR_USD H1 the candle counts are 69 `UNCERTAIN`, 1,670 `UPTREND`, 1,895 `DOWNTREND`, and 2,562 `TRANSITION`. The median run is 5 to 6 H1 candles, about 4 to 6 clock hours. On EUR_USD H4 the counts are 30, 410, 484, and 559, with median runs of about 6 to 8 four-hour candles. The other pairs are in the same range. `TRANSITION` is the largest H1 share on every pair. That is a description of this definition, not a trading instruction. Elapsed-hour medians include weekends when a run crosses one.

| Pair | H1 highs | H1 lows | H1 gap windows | H4 highs | H4 lows | H4 gap windows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AUD_USD | 795 | 807 | 296 | 158 | 169 | 270 |
| EUR_USD | 774 | 787 | 275 | 165 | 159 | 250 |
| GBP_USD | 774 | 826 | 295 | 168 | 165 | 267 |
| USD_CAD | 778 | 790 | 275 | 170 | 147 | 250 |
| USD_CHF | 729 | 781 | 367 | 148 | 148 | 336 |
| USD_JPY | 815 | 827 | 303 | 165 | 173 | 277 |

Tied H1 candidates are a few dozen per pair. Tied H4 candidates are in the single digits.

## Trendline construction and events

Each new swing forms one line with the immediately previous swing of the same type. Older pairings are not searched. The line exists at the later confirmation, and a newer line does not rewrite the earlier version. Slope uses actual UTC seconds between the pivot opens.

EUR_USD produces 1,559 H1 lines and 322 H4 lines. Across the six pairs, H1 reach-touches are about 7,600 to 8,700, of which only about 35 to 58 are exact numerical contact. H1 first-cross breaks are about 4,300 to 4,900. H4 reach-touches are about 1,000 to 1,400 and H4 breaks about 610 to 790.

`BEYOND_CONTINUATION` is much larger, on the order of 2.3 million to 2.6 million H1 candle-line pairs. It counts later candles that remain beyond a line that has already broken, across every retained line version. It is not a count of separate breaks.

## Support and resistance

Every confirmed swing is a level from its confirmation time. EUR_USD H1 has 1,561 levels. Later reaches and the first close beyond each level are counted. Levels are not retired, because R.40 did not define that step. `invalidation_time` is null.

## Range implementation

Ranges are `UNCERTAIN`, with zero confirmed range objects. A reaction to one level can be described. Which support should be paired with which resistance cannot. The run does not choose a pair by later price behaviour.

## Prefix invariance and the multi-timeframe clock

Cutting every series at 2026-03-01 00:00 UTC reproduces the swings, lines, states, and event counts that the full file marks as known by that time. On each pair, an H1 or H4 swing is hidden one second before confirmation and visible at confirmation. A timestamp 30 minutes into an H1 candle does not see that hour. A timestamp five minutes into an H4 candle does not see that four-hour close. The H4 candle appears at its own boundary. No swing is dated after the last completed candle.

## Focused tests and offline regressions

R.41 focused tests: 6 passed. R.8–R.40 suites all exited 0 on the first attempt, including R.10 with 69 passed and 5 skipped. `WinError 5` did not occur. R.28 PostgreSQL scripts were not run. Counts are in `15_regression_results.md`.

The existing trading journal was not given these rows. That journal expects a decision and can carry a direction. The structure observations are separate records. Their decision, outcome, and confidence fields are null. Examples for EUR_USD are in `14_journal_examples.json`.

## Remaining limitations

`k` was not varied. Geometry uses bid prices only. Lines connect consecutive swings only. The `1e-8` band is float equality, not a market tolerance. Continuation counts must not be read as separate events. Range pairing and level retirement remain unspecified. Median clock hours include weekends. A five-candle fractal marks many local turns, and the resulting trend label usually lasts only a handful of candles. The year is the same research-exposed sample used in R.29 through R.40. This stage has no economic result.

## Recommended R.42 direction

Do not backtest these labels on this year. If another stage is authorised, the one open specification is the range pairing. A later stage can freeze one deterministic pairing, such as the latest confirmed support and the latest confirmed resistance, before counting how often a range becomes available. That stage should still emit no entries and no profit. It should not search pairings against later prices. Economic evaluation stays blocked until there is bid/ask data outside September 2025–August 2026. Expanded pairs and an adaptive selector stay outside that stage.

R.42 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
