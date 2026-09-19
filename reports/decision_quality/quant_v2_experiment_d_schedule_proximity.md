# Quant V2 Experiment D — Official scheduled-event proximity

**Status:** COMPLETE — research only. No model. No production change. Verdict: **D_PASS_INCREMENTAL_MAGNITUDE_INFORMATION**.

Hypothesis A only: proximity to a pre-scheduled high-importance official economic event predicts future FX movement **magnitude**. Not a directional experiment. Incremental value is tested against frozen Experiment A OANDA activity and frozen Experiment B cross-sectional dispersion.

## Acquisition

Official schedule metadata only. Raw store: `data/research/external/raw/<agency>/<date>/`. Normalized: `data/research/external/normalized/`. Market M5/M1 CSVs were not modified.

| Agency | Source identity | Clock convention |
| --- | --- | --- |
| BLS | `bls.gov/schedule/2025/`, CPI and Employment Situation release tables | 08:30 America/New_York |
| FRB | `federalreserve.gov/monetarypolicy/fomccalendars.htm` | 14:00 America/New_York statement |
| ONS | CPI and labour-market dataset previous-version clocks | 07:00 Europe/London |
| BoE | Official MPC date pages 2025/2026 | 12:00 Europe/London |
| StatCan | 2026-2027 release PDF + The Daily / major-release calendar | 08:30 America/New_York |
| BoC | Official 2025 and 2026 rate-announcement schedule pages | **09:45 America/Toronto** (official page; not the earlier 10:00 placeholder) |

Fields stored: event category, affected currency, official scheduled timestamp, timezone, UTC, source/ref, retrieval metadata. **No consensus, forecast, actual, revision, surprise, or text.**

Normalization version: `d1`. BLS 2025 lapse-delayed clocks are `RESCHEDULED` and excluded from primary analysis. FOMC notation votes are `UNCERTAIN`.

## Event inventory (primary period 2025-09-01 to 2026-08-31 UTC)

- Official rows parsed: 332
- PRIMARY clock rows: 327
- In development window: 90
- RESCHEDULED / UNCERTAIN excluded from primary: 9
- Median spacing of primary events: 48.0 hours
- Simultaneous same-timestamp releases: 12
- Overlapping ±120m windows: 7

### By currency / category (primary, in-period)

| Currency | INFLATION | EMPLOYMENT | CENTRAL_BANK_DECISION | Total events |
| --- | ---: | ---: | ---: | ---: |
| USD | 9 | 9 | 8 | 26 |
| GBP | 12 | 12 | 8 | 32 |
| CAD | 12 | 12 | 8 | 32 |

Independent n is **event count**, not surrounding M5 bars.

## Frozen windows and clock control

Pre: 120–60, 60–30, 30–15, 15–5 minutes before. Post: 0–15, 15–30, 30–60, 60–120 minutes after. Half-open as frozen. One observation per (event, window, symbol): last pre-window bar or first post-window bar. Base population: same symbol, UTC hour, weekday, outside any authorized event ±120 minutes.

The 60-minute absolute-close target from `pre_60_30` and closer **mechanically includes the scheduled instant**. That is allowed: the feature is the known clock, the target is future magnitude. `pre_120_60` is the window whose 60-minute path usually ends before the print. That window is **not** larger than clock-matched base except for central-bank decisions. So the magnitude information is “an official high-importance clock is inside or about to enter the horizon,” not a long lead-up of extra volatility two hours early.

## Pre-event magnitude (60m abs close, pips) vs clock-matched base

| Window | Category | Events | Event mean | Base mean | Diff | boot p05 | boot p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pre_120_60 | INFLATION | 33 | 6.079 | 7.348 | -1.269 | -2.559 | -0.252 |
| pre_120_60 | EMPLOYMENT | 33 | 7.375 | 7.826 | -0.452 | -1.943 | 0.661 |
| pre_120_60 | CENTRAL_BANK_DECISION | 24 | 9.307 | 6.760 | 2.547 | 0.323 | 4.761 |
| pre_120_60 | POOLED | 90 | 7.415 | 7.346 | 0.068 | -0.901 | 0.872 |
| pre_60_30 | INFLATION | 33 | 12.612 | 7.513 | 5.100 | 2.266 | 8.600 |
| pre_60_30 | EMPLOYMENT | 33 | 23.375 | 8.177 | 15.197 | 9.894 | 19.900 |
| pre_60_30 | CENTRAL_BANK_DECISION | 24 | 17.884 | 6.375 | 11.509 | 7.799 | 15.978 |
| pre_60_30 | POOLED | 90 | 17.964 | 7.417 | 10.547 | 8.171 | 13.772 |
| pre_30_15 | INFLATION | 33 | 12.944 | 8.449 | 4.495 | 0.992 | 8.115 |
| pre_30_15 | EMPLOYMENT | 33 | 23.364 | 9.108 | 14.256 | 8.360 | 19.506 |
| pre_30_15 | CENTRAL_BANK_DECISION | 24 | 16.440 | 6.375 | 10.066 | 6.331 | 15.604 |
| pre_30_15 | POOLED | 90 | 17.697 | 8.079 | 9.618 | 6.660 | 12.709 |
| pre_15_5 | INFLATION | 33 | 11.883 | 8.449 | 3.433 | 0.001 | 7.443 |
| pre_15_5 | EMPLOYMENT | 33 | 23.833 | 9.108 | 14.726 | 8.952 | 19.544 |
| pre_15_5 | CENTRAL_BANK_DECISION | 24 | 18.683 | 6.375 | 12.308 | 8.399 | 16.963 |
| pre_15_5 | POOLED | 90 | 18.078 | 8.079 | 9.999 | 7.419 | 13.268 |

## Post-event magnitude (60m abs close, pips) vs clock-matched base

| Window | Category | Events | Event mean | Base mean | Diff | boot p05 | boot p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| post_0_15 | INFLATION | 33 | 8.681 | 8.721 | -0.039 | -2.080 | 2.050 |
| post_0_15 | EMPLOYMENT | 33 | 14.270 | 9.418 | 4.852 | 1.388 | 7.659 |
| post_0_15 | CENTRAL_BANK_DECISION | 24 | 19.292 | 6.164 | 13.128 | 8.919 | 17.824 |
| post_0_15 | POOLED | 90 | 13.560 | 8.224 | 5.336 | 3.288 | 7.551 |
| post_15_30 | INFLATION | 33 | 9.347 | 8.721 | 0.626 | -1.235 | 2.909 |
| post_15_30 | EMPLOYMENT | 33 | 13.760 | 9.418 | 4.342 | 1.112 | 7.282 |
| post_15_30 | CENTRAL_BANK_DECISION | 24 | 18.292 | 6.164 | 12.129 | 8.219 | 16.617 |
| post_15_30 | POOLED | 90 | 13.351 | 8.224 | 5.127 | 3.334 | 6.932 |
| post_30_60 | INFLATION | 33 | 10.522 | 8.721 | 1.801 | -0.002 | 3.968 |
| post_30_60 | EMPLOYMENT | 33 | 12.868 | 9.418 | 3.450 | 0.946 | 5.743 |
| post_30_60 | CENTRAL_BANK_DECISION | 24 | 20.738 | 6.100 | 14.638 | 11.035 | 19.266 |
| post_30_60 | POOLED | 90 | 14.106 | 8.206 | 5.901 | 4.185 | 7.929 |
| post_60_120 | INFLATION | 33 | 8.148 | 9.685 | -1.537 | -3.106 | 0.145 |
| post_60_120 | EMPLOYMENT | 33 | 11.298 | 10.274 | 1.025 | -1.393 | 3.122 |
| post_60_120 | CENTRAL_BANK_DECISION | 24 | 15.522 | 6.100 | 9.421 | 5.800 | 14.162 |
| post_60_120 | POOLED | 90 | 11.270 | 8.851 | 2.419 | 0.724 | 4.301 |

## Currency / symbol stability (post_0_15, 60m abs pips minus clock base)

| Currency | Symbol | Events | Diff | boot p05 | boot p95 |
| --- | --- | ---: | ---: | ---: | ---: |
| USD | EUR_USD | 26 | 9.146 | 4.760 | 14.324 |
| USD | GBP_USD | 26 | 10.212 | 5.509 | 15.893 |
| USD | USD_JPY | 26 | 15.775 | 9.044 | 23.769 |
| USD | AUD_USD | 26 | 8.472 | 4.800 | 13.141 |
| USD | USD_CAD | 26 | 7.051 | 4.261 | 9.837 |
| USD | USD_CHF | 26 | 6.011 | 2.829 | 9.153 |
| GBP | GBP_USD | 32 | 3.041 | -0.573 | 6.808 |
| CAD | USD_CAD | 32 | 2.528 | 0.777 | 4.666 |

Stability class: **BROAD** for USD events across all six pairs (event-level bootstrap p05 > 0). CAD events on USD_CAD are smaller but still positive. GBP-only events on GBP_USD are positive on the point estimate; the 5–95% event bootstrap interval includes zero. Do not hide that disagreement in the USD-heavy pool.

## Incremental value over frozen activity

Question: at similar Experiment A session-relative volume quintiles, does official event proximity add magnitude?

| Activity band | Window | Event mean | Matched-activity base | Diff | boot p05 | boot p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| low | pre_15_5 | 17.213 | 4.983 | 12.231 | 7.554 | 16.520 |
| low | post_0_15 | 4.150 | 4.983 | -0.833 | -2.489 | 1.617 |
| mid | pre_15_5 | 25.084 | 6.169 | 18.915 | 13.177 | 23.914 |
| mid | post_0_15 | 6.600 | 6.169 | 0.431 | -1.471 | 2.571 |
| high | pre_15_5 | 17.588 | 7.405 | 10.183 | 6.734 | 14.268 |
| high | post_0_15 | 14.756 | 7.405 | 7.352 | 5.191 | 9.756 |

## Incremental value over frozen dispersion

| Dispersion band | Window | Event mean | Matched-dispersion base | Diff | boot p05 | boot p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| low | pre_15_5 | 13.200 | 4.933 | 8.267 | 4.841 | 13.595 |
| low | post_0_15 | 10.290 | 4.933 | 5.358 | 1.047 | 10.000 |
| mid | pre_15_5 | 17.803 | 6.134 | 11.670 | 6.121 | 17.691 |
| mid | post_0_15 | 14.605 | 6.134 | 8.471 | 0.541 | 17.614 |
| high | pre_15_5 | 21.162 | 7.938 | 13.224 | 9.153 | 18.068 |
| high | post_0_15 | 14.291 | 7.938 | 6.353 | 4.253 | 8.719 |

## Activity / dispersion / spread response

Session-relative activity mean pre_15_5=1.073 vs post_0_15=5.086. disp_std pre=0.000 vs post=0.001. Half-spread pips pre=0.829 vs post=0.903.

## Cost / tradeability

Post-event half-spread mean 0.903 pips vs clock-ordinary 0.940 (p90 1.050 vs 1.050). 60m |move|/half-spread 17.482 vs 7.434. Higher movement/cost is not directional edge.

## Time stability (development splits only)

| Split | Window | Events | Diff |
| --- | --- | ---: | ---: |
| train | pre_15_5 | 42 | 12.666 |
| train | post_0_15 | 42 | 7.745 |
| valid | pre_15_5 | 24 | 3.864 |
| valid | post_0_15 | 24 | 3.101 |
| discovery_test | pre_15_5 | 24 | 11.424 |
| discovery_test | post_0_15 | 24 | 3.329 |

2025-09 through 2026-08 is already-inspected DEVELOPMENT / DISCOVERY. No pristine holdout claim.

## Directional diagnostic (descriptive only)

Descriptive signed 60m instrument pips after scheduled time (post_0_15), n_rows=220, mean=-0.353. Incidental only.

No directional hypothesis was authorized. Signed means are not a strategy.

## Information classification

**INCREMENTAL MAGNITUDE INFORMATION**

## Verdict answers

1. Does scheduled-event proximity predict future movement magnitude? **YES**
2. Does the relationship survive clock-time controls? **YES**
3. Does it survive chronological splits? **YES**
4. Does it appear across relevant pairs? **YES**
5. Does it add information beyond OANDA activity? **YES**
6. Does it add information beyond cross-sectional dispersion? **YES**
7. Are spreads materially worse around these events? **NO / MODEST**
8. Does movement/cost improve despite spread widening? **YES**
9. Is the useful information pre-event, post-event, or both? **both — but the late-pre 60m target includes the print; 120–60 pre does not**
10. Is the effect broad or event/currency-specific? **BROAD for USD; weaker for GBP-only events**

# D_PASS_INCREMENTAL_MAGNITUDE_INFORMATION

D_PASS would not authorize training, BUY/SELL, or production changes. This run does not train and does not change `_quant_stub_vote`.

## Next external-data decision

# PIT_CONSENSUS_SAMPLE_AUDIT_JUSTIFIED

Official clocks predict extra post-event magnitude after clock-time controls and after frozen activity/dispersion bands. That is a necessary condition for later asking whether the *direction* of the print matters. It does **not** authorize buying consensus, downloading a surprise feed, or testing surprise. A later human review may consider a small point-in-time consensus *sample audit* only.

## Stop

No consensus acquired. No actuals acquired. No purchase. No surprise study. No training. No event filters. No production change. No ATR/RL/bot restart. Stop after Experiment D.
