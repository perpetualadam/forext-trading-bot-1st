# STAGE R.42 — STRUCTURAL RANGE PAIRING AND LEVEL LIFECYCLE REPORT

Classification: `R42_STRUCTURAL_RANGE_LIFECYCLE_COMPLETED`

## Preservation

- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`
- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Working tree: dirty before this stage. Unrelated changes were left in place.
- R.24–R.41 evidence files are present and were not modified.
- All six strategies remain inactive and unauthorised.
- Quant stub: `quant_stub_removed`, allow false.
- Unverified reinforcement learning: `UNAVAILABLE`.
- `lifecycle.py` is not imported by `bot_loop.py` or `ai_ensemble.py`.
- No commit, reset, clean, stash, deploy, migration, or rollback.

## Protocol and source hashes

- Definition: `r42.structure.v1`
- Parent: `r41.structure.v1`
- Ancestor: `r40.structure.v1`
- Protocol SHA-256: `da8f53c0f8b89037ab00721f4c0a3b8d7c322d6da692e37a2b3f142a643c6b27`
- `lifecycle.py` SHA-256: `4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5`
- `structure.py` SHA-256, unchanged: `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc`
- `timeframes.py` SHA-256, unchanged: `a482ef747fb28a9d1a4409c8d67b67811147afaedd0b487c52f2e9730f734676`

The protocol was written and hashed before the descriptive counts. The descriptive script exits if either hash changes. Swing confirmation remains `k = 2` on bid candles. The absolute tolerance `1e-8` remains numerical equality.

## Support and resistance pairing

The pair is the latest `ACTIVE` confirmed swing-low support and the latest `ACTIVE` confirmed swing-high resistance. Support must be strictly below resistance. The pair is available at the later level's availability time. A missing, superseded, invalidated, or crossed pair stays `UNCERTAIN`. A crossed identity is counted once. Same-timestamp swings are applied by pivot time and then swing type, with `HIGH` before `LOW`. Older combinations are not searched.

On these twelve series the latest-level rule created no crossed candidate. The fail-closed crossed path was still exercised by a synthetic test.

## Reaction episodes

A reaction is the R.41 reach: the wick reaches the boundary and the close finishes back on the original side. Adjacent reaches are one episode. The pivot candle and the confirmation candle do not count. Only an episode that starts after the pair exists counts toward confirmation. Two support episodes and two resistance episodes confirm the candidate. A completed close outside either boundary invalidates it.

## Level lifecycle

`ACTIVE` at swing confirmation. `INVALIDATED` on a later completed close through the price. `SUPERSEDED` when a newer confirmed level of the same kind becomes the latest eligible level. Invalidated levels are not rewritten. Old levels stay in the record. No age, distance, or volatility threshold is applied. The confirmation candle does not invalidate the level it creates.

## Trendline lifecycle

R.41 consecutive-swing construction is unchanged. A line is `ACTIVE` only after its second swing is confirmed. A newer same-kind line supersedes the active line. The first completed close beyond the active line is the only break. Later candles are not extra breaks, and the line is not reactivated. Broken lines stay broken. Archived lines are retained and are not compared with every later candle.

## Range state machine

`UNCERTAIN` without an eligible uncrossed pair. `CANDIDATE` when the latest pair is valid. `CONFIRMED` at the candle that completes the second reaction episode on both sides. `INVALIDATED` on a completed close outside either boundary. A newer eligible pair replaces the old range without turning that replacement into a price invalidation and without choosing a different historical boundary.

## Distinct-event results

Counts below are descriptive. Touch episodes and range reactions can describe the same candles and are not added. Sums across the six USD instruments are arithmetic totals over one correlated, research-exposed year. They are not six independent samples. Raw retained-line continuation comparisons were not computed.

H1 candidates: 7,408. Of those, 3,126 were invalidated before confirmation, 4,276 were replaced before confirmation, 1 was confirmed and then replaced on the confirmation candle, and 5 were still candidates when the sample ended.

H4 candidates: 1,405. All 1,405 ended before confirmation. None were confirmed.

The frozen reach rule is sparse. It produced one confirmed range in the whole research year. That range did not remain the active pair through a later completed candle.

## Descriptive results

Incomplete buckets are rejected higher-timeframe groups. Gap windows are swing neighbourhoods rejected because the neighbouring candles were not exactly one period apart.

| Series | Candles | Rejected | Swings H/L | Levels | Invalidated | Superseded | Active levels | Lines | Broken | Line superseded | Line touches | Support touches | Resistance touches | Pairs | Reactions | Confirmed | Range invalidations | Range replacements | Uncertain candles | Gap windows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AUD_USD H1 | 6189 | 27 | 795/807 | 1602 | 572 | 1028 | 2 | 1600 | 673 | 925 | 386 | 251 | 211 | 1230 | 407 | 0 | 524 | 705 | 2054 | 296 |
| AUD_USD H4 | 1478 | 130 | 158/169 | 327 | 133 | 194 | 0 | 325 | 140 | 185 | 87 | 37 | 40 | 238 | 66 | 0 | 118 | 120 | 649 | 270 |
| EUR_USD H1 | 6196 | 20 | 774/787 | 1561 | 594 | 965 | 2 | 1559 | 666 | 891 | 394 | 225 | 226 | 1233 | 397 | 0 | 546 | 686 | 1975 | 275 |
| EUR_USD H4 | 1483 | 125 | 165/159 | 324 | 121 | 202 | 1 | 322 | 146 | 175 | 79 | 58 | 48 | 243 | 97 | 0 | 109 | 134 | 555 | 250 |
| GBP_USD H1 | 6184 | 32 | 774/826 | 1600 | 547 | 1051 | 2 | 1598 | 681 | 915 | 401 | 264 | 230 | 1254 | 432 | 1 | 500 | 753 | 2068 | 295 |
| GBP_USD H4 | 1478 | 130 | 168/165 | 333 | 128 | 204 | 1 | 331 | 144 | 187 | 99 | 55 | 42 | 244 | 88 | 0 | 113 | 131 | 592 | 267 |
| USD_CAD H1 | 6188 | 28 | 778/790 | 1568 | 554 | 1013 | 1 | 1566 | 684 | 880 | 349 | 239 | 229 | 1222 | 422 | 0 | 505 | 717 | 2134 | 275 |
| USD_CAD H4 | 1483 | 125 | 170/147 | 317 | 134 | 183 | 0 | 315 | 135 | 180 | 83 | 46 | 46 | 222 | 82 | 0 | 118 | 104 | 691 | 250 |
| USD_CHF H1 | 6163 | 53 | 729/781 | 1510 | 558 | 950 | 2 | 1508 | 636 | 871 | 387 | 244 | 225 | 1180 | 406 | 0 | 516 | 663 | 2127 | 367 |
| USD_CHF H4 | 1460 | 148 | 148/148 | 296 | 120 | 175 | 1 | 294 | 134 | 159 | 92 | 49 | 40 | 214 | 75 | 0 | 104 | 110 | 677 | 336 |
| USD_JPY H1 | 6185 | 31 | 815/827 | 1642 | 572 | 1068 | 2 | 1640 | 699 | 940 | 413 | 219 | 227 | 1289 | 396 | 0 | 535 | 753 | 1921 | 303 |
| USD_JPY H4 | 1476 | 132 | 165/173 | 338 | 128 | 209 | 1 | 336 | 142 | 193 | 85 | 46 | 52 | 244 | 85 | 0 | 113 | 131 | 632 | 277 |

About 31–35% of completed H1 candles ended `UNCERTAIN`. About 37–47% of completed H4 candles did. H1 has about four times as many complete candles and about five times as many levels and lines. A swing remains invisible until three periods after its pivot open: 3 hours on H1 and 12 hours on H4.

The one confirmed range is GBP_USD H1. Its support pivot is 2026-05-20 01:00 UTC and its resistance pivot is 2026-05-19 23:00 UTC. The pair became available at 2026-05-20 04:00 UTC and was confirmed at 2026-05-20 09:00 UTC. Width is 0.00261 price units, 26.1 pips at a pip size of 0.0001. The range record remains `CONFIRMED` with no price-invalidation time. A newer level replaced it on the confirmation candle, so no completed candle ended while that confirmed range was still the active pair.

EUR_USD H1 example: the first resistance was created at 2025-09-01 11:00 UTC from the 08:00 pivot and was superseded at 22:00 UTC by a newer confirmed high. Research observation rows keep decision, outcome, and confidence empty. They were not written to the production journal.

## Prefix invariance and availability

The prefix cutoff `2026-03-01T00:00:00Z` is a causality check. On all twelve series, events from the prefix matched the full-sample events known by that cutoff. Levels are hidden one second before availability and visible at availability. A higher-timeframe candle is hidden during its own open interval and visible at its close. Each side ends with at most one active level and one active line.

## Tests

Focused tests passed after the two assertion corrections described in `15_regression_results.md`. The offline R.8–R.42 suites then passed on the first run, including R.10 with 69 passed and 5 skipped. No safety assertion was weakened. R.28 PostgreSQL scripts were not run.

## Limitations

The reaction rule was not widened after seeing that confirmations are rare. Replaced ranges are not scanned again. Archived lines are not counted as repeated breaks. The six pairs remain one correlated sample. No spread, financing, profit, or model result is implied by a touch, a break, or the single confirmation.

## Recommended R.43 direction

Leave the reach tolerance unchanged. Do not backtest these labels on the exposed year. Economic questions wait for bid/ask data outside September 2025 through August 2026. Expanded pairs and an adaptive selector are separate later questions.

R.43 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
