# SIX-PAIR 12-MONTH QUANT/OFFLINE BASELINE

**Window:** 2025-09 through 2026-08 UTC  
**Implementation:** `impl=optimized`  
**Methodology:** production quant + routing + SL/TP (research replay)  
**This is NOT a live-bot historical replay.** Live production also applies an always-on RL agreement/veto gate (stochastic on unseen states) and downstream risk/execution. Those are excluded here.

Report written: 2026-09-18T16:22:10Z

Do not confuse this with the old EUR_USD / 450-bar / 12-trade sample.

## Scope confirmation

- Six baseline work units only: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF
- Stop-width / ATR 1.00 / 1.25 / 1.50 / 2.00: **NOT RUN IN BASELINE PHASE**
- RL historical replay: **NOT RUN IN BASELINE PHASE**
- API voter replay: **NOT RUN IN BASELINE PHASE**
- Parameter/grid/strategy optimization: **NOT RUN**
- Historical CSVs were not modified

## 1. Dataset coverage

| symbol | bars | earliest UTC | latest UTC | CSV |
| --- | ---: | --- | --- | --- |
| EUR_USD | 74572 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\EUR_USD_M5.csv` |
| GBP_USD | 74555 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\GBP_USD_M5.csv` |
| USD_JPY | 74557 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\USD_JPY_M5.csv` |
| AUD_USD | 74563 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\AUD_USD_M5.csv` |
| USD_CAD | 74560 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\USD_CAD_M5.csv` |
| USD_CHF | 74514 | 2025-09-01 00:00:00 | 2026-08-31 23:50:00 | `data\historical\USD_CHF_M5.csv` |

## 2. Overall metrics

- trade_count: **18689**
- BUY / SELL: **9538** / **9151**
- win_rate: 26.69%  (n=18689)
- expectancy R: **-0.1995**
- profit_factor: 0.7278
- total R: **-3728.5249**
- max drawdown R: 3731.2386
- median R: -1.0000
- wins / losses: 4988 / 13701
- ambiguous SL/TP bars: 39

Primary metrics are expectancy, profit factor, drawdown, and sample size — not win rate.

## 3. Per-symbol metrics

| symbol | bars | trades | BUY | SELL | win_rate | exp_R | PF | total_R | maxDD_R | median_R | runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| EUR_USD | 74572 | 3202 | 1563 | 1639 | 25.83% | -0.2250 | 0.6966 | -720.3032 | 720.3032 | -1.0000 | 3893.6s |
| GBP_USD | 74555 | 3134 | 1583 | 1551 | 26.80% | -0.1964 | 0.7317 | -615.3764 | 623.0000 | -1.0000 | 3731.2s |
| USD_JPY | 74557 | 2595 | 1357 | 1238 | 28.98% | -0.1303 | 0.8164 | -338.1585 | 347.0000 | -1.0000 | 3035.0s |
| AUD_USD | 74563 | 3255 | 1655 | 1600 | 26.14% | -0.2161 | 0.7074 | -703.3280 | 707.0000 | -1.0000 | 3977.8s |
| USD_CAD | 74560 | 3017 | 1552 | 1465 | 26.72% | -0.1989 | 0.7286 | -600.0726 | 612.0000 | -1.0000 | 3669.5s |
| USD_CHF | 74514 | 3486 | 1828 | 1658 | 26.16% | -0.2155 | 0.7081 | -751.2862 | 754.0000 | -1.0000 | 4390.9s |

## 4. BUY vs SELL

| group | n | win_rate | exp_R | PF | total_R | maxDD_R | median_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUY | 9538 | 27.01% | -0.1898 | 0.7399 | -1810.4447 | 1815.1585 | -1.0000 |
| SELL | 9151 | 26.36% | -0.2096 | 0.7153 | -1918.0801 | 1927.0801 | -1.0000 |

## 5. Strategy-label breakdown

| group | n | win_rate | exp_R | PF | total_R | maxDD_R | median_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mean_reversion | 1703 | 27.54% | -0.1746 | 0.7591 | -297.3280 | 304.3280 | -1.0000 |
| scalp | 1824 | 29.88% | -0.1045 | 0.8508 | -190.6620 | 194.3758 | -1.0000 |
| swing_breakout | 4330 | 25.77% | -0.2268 | 0.6945 | -982.0000 | 993.0000 | -1.0000 |
| swing_mean_reversion | 4527 | 25.96% | -0.2213 | 0.7011 | -1002.0000 | 1009.0000 | -1.0000 |
| swing_trend | 4580 | 25.92% | -0.2225 | 0.6997 | -1019.0000 | 1021.0000 | -1.0000 |
| trend | 1725 | 28.75% | -0.1377 | 0.8066 | -237.5349 | 270.5349 | -1.0000 |

Strategy labels route lookback/horizon; they do not set BUY/SELL. Direction is the quant stub.

## 6. Higher-timeframe context

| group | n | win_rate | exp_R | PF | total_R | maxDD_R | median_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| against_h1|against_h4|h1_h4_agree | 4173 | 25.55% | -0.2336 | 0.6862 | -975.0000 | 979.0000 | -1.0000 |
| against_h1|aligned_h4|h1_h4_conflict | 3036 | 25.72% | -0.2280 | 0.6929 | -692.1585 | 696.1585 | -1.0000 |
| against_h1|h4_uncertain | 218 | 20.18% | -0.3945 | 0.5057 | -86.0000 | 89.0000 | -1.0000 |
| aligned_h1|against_h4|h1_h4_conflict | 4281 | 26.51% | -0.2052 | 0.7208 | -878.4006 | 885.4006 | -1.0000 |
| aligned_h1|aligned_h4|h1_h4_agree | 6123 | 27.85% | -0.1647 | 0.7717 | -1008.6796 | 1021.6796 | -1.0000 |
| aligned_h1|h4_uncertain | 338 | 31.66% | -0.0503 | 0.9264 | -17.0000 | 43.0000 | -1.0000 |
| h1_uncertain|against_h4 | 238 | 26.47% | -0.2059 | 0.7200 | -49.0000 | 51.0000 | -1.0000 |
| h1_uncertain|aligned_h4 | 259 | 31.27% | -0.0667 | 0.9029 | -17.2862 | 38.0000 | -1.0000 |
| h1_uncertain|h4_uncertain | 23 | 26.09% | -0.2174 | 0.7059 | -5.0000 | 10.0000 | -1.0000 |

## 7. Regime breakdown

| group | n | win_rate | exp_R | PF | total_R | maxDD_R | median_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HIGH_VOLATILITY | 6523 | 28.28% | -0.1521 | 0.7878 | -992.3664 | 1019.0801 | -1.0000 |
| LOW_VOLATILITY | 1352 | 20.41% | -0.3876 | 0.5130 | -524.0000 | 525.0000 | -1.0000 |
| RANGING | 2729 | 26.42% | -0.2074 | 0.7181 | -566.0000 | 573.0000 | -1.0000 |
| TRENDING_DOWN | 2588 | 26.62% | -0.2013 | 0.7256 | -521.0000 | 527.0000 | -1.0000 |
| TRENDING_UP | 2632 | 26.82% | -0.1950 | 0.7334 | -513.1585 | 513.1585 | -1.0000 |
| UNCERTAIN | 2865 | 26.21% | -0.2136 | 0.7105 | -612.0000 | 615.0000 | -1.0000 |

## 8. Session breakdown

| group | n | win_rate | exp_R | PF | total_R | maxDD_R | median_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| asia | 4837 | 25.43% | -0.2371 | 0.6820 | -1147.0000 | 1152.0000 | -1.0000 |
| late_new_york | 2426 | 26.09% | -0.2177 | 0.7052 | -528.1660 | 533.1661 | -1.0000 |
| london | 5292 | 26.91% | -0.1927 | 0.7363 | -1020.0000 | 1041.0000 | -1.0000 |
| london_ny_overlap | 4872 | 28.61% | -0.1421 | 0.8009 | -692.3588 | 707.0726 | -1.0000 |
| rollover_low_liquidity | 1262 | 24.33% | -0.2702 | 0.6429 | -341.0000 | 341.0000 | -1.0000 |

## 9. Forward directional returns

- 5m: n=18689 hit_rate=0.3030 mean_pips=-1.1373 median_pips=-1.1000
- 15m: n=18689 hit_rate=0.3704 mean_pips=-1.1215 median_pips=-1.1000
- 30m: n=18689 hit_rate=0.4045 mean_pips=-1.0762 median_pips=-1.1000
- 60m: n=18689 hit_rate=0.4291 mean_pips=-1.1270 median_pips=-1.2000

## 10. Stop / MFE / MAE

- stopped_n: 13699
- later reached original TP: 0.9556
- later +0.5R: 0.9780
- later +1R: 0.9705
- later +2R: 0.9556
- median SL/ATR: 2.0000
- median MAE/ATR: 2.1707
- median MFE/ATR: 1.2654
- overall avg MFE R: 0.9900
- overall avg MAE R: 1.0852

## 11. Post-stop analysis

Derived from completed baseline trades only (no extra backtest).

- Loss categories (first matching rule): {'possible_stop_too_tight': 13295, 'mean_reversion_vs_trend_conflict': 5, 'unclear': 26, 'possible_late_entry': 189, 'higher_timeframe_conflict': 139, 'high_spread_noise': 32, 'direction_failure': 15}

## 12. Entry-timing / possible late entries

- pre_move_atr >= 1.5 ATR (possible late): n=8171 exp_R=-0.2042 PF=0.7220 wr=26.53%
- otherwise: n=10518 exp_R=-0.1959 PF=0.7324 wr=26.81%

This is a measurement, not a live filter change.

## 13. Chronological train / validation / test

Trades split by entry time: first 50% IN-SAMPLE (train), next 25% VALIDATION, last 25% TEST / OUT-OF-SAMPLE.
No parameters were tuned on the test period in this run.

| split | label | n | win_rate | exp_R | PF | total_R | maxDD_R |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | IN-SAMPLE | 9344 | 26.44% | -0.2067 | 0.7190 | -1931.0000 | 1943.0000 |
| valid | VALIDATION | 4672 | 27.65% | -0.1704 | 0.7645 | -796.0000 | 829.0000 |
| test | TEST / OUT-OF-SAMPLE | 4673 | 26.21% | -0.2143 | 0.7094 | -1001.5249 | 1005.2938 |

## 14. Existing baseline filter analyses

Each candidate filter is scored on the already-completed baseline trades (train discovery / valid / untouched test).
These are **not** additional historical backtests and were **not** applied live.

| filter | split | retained | removed | filt exp_R | base exp_R | filt PF |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| h1_direction_agreement | train | 5367 | 3977 | -0.1722 | -0.2067 | 0.7622 |
| h1_direction_agreement | valid | 2691 | 1981 | -0.1605 | -0.1704 | 0.7771 |
| h1_direction_agreement | test | 2684 | 1989 | -0.2042 | -0.2143 | 0.7218 |
| h4_severe_conflict_avoid | train | 5221 | 4123 | -0.1703 | -0.2067 | 0.7646 |
| h4_severe_conflict_avoid | valid | 2429 | 2243 | -0.1935 | -0.1704 | 0.7354 |
| h4_severe_conflict_avoid | test | 2347 | 2326 | -0.1990 | -0.2143 | 0.7282 |
| regime_match | train | 2918 | 6426 | -0.1827 | -0.2067 | 0.7489 |
| regime_match | valid | 1598 | 3074 | -0.1289 | -0.1704 | 0.8183 |
| regime_match | test | 1280 | 3393 | -0.1944 | -0.2143 | 0.7337 |
| adx_filter | train | 6213 | 3131 | -0.1960 | -0.2067 | 0.7322 |
| adx_filter | valid | 3155 | 1517 | -0.1765 | -0.1704 | 0.7567 |
| adx_filter | test | 3066 | 1607 | -0.2042 | -0.2143 | 0.7217 |
| volatility_filter | train | 5242 | 4102 | -0.2411 | -0.2067 | 0.6772 |
| volatility_filter | valid | 2605 | 2067 | -0.1996 | -0.1704 | 0.7277 |
| volatility_filter | test | 2614 | 2059 | -0.2778 | -0.2143 | 0.6340 |
| spread_atr_filter | train | 2984 | 6360 | -0.1092 | -0.2067 | 0.8446 |
| spread_atr_filter | valid | 1811 | 2861 | -0.1237 | -0.1704 | 0.8253 |
| spread_atr_filter | test | 761 | 3912 | -0.0714 | -0.2143 | 0.8961 |
| session_london_or_overlap | train | 5132 | 4212 | -0.1933 | -0.2067 | 0.7356 |
| session_london_or_overlap | valid | 2519 | 2153 | -0.1282 | -0.1704 | 0.8193 |
| session_london_or_overlap | test | 2513 | 2160 | -0.1581 | -0.2143 | 0.7801 |
| entry_extension_filter | train | 5223 | 4121 | -0.2125 | -0.2067 | 0.7118 |
| entry_extension_filter | valid | 2573 | 2099 | -0.1512 | -0.1704 | 0.7892 |
| entry_extension_filter | test | 2722 | 1951 | -0.2061 | -0.2143 | 0.7195 |

## 15. Data-quality warnings

- **EUR_USD**: bars=74572 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=21
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-09-25 21:10:00 → 2025-09-25 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-12-24 21:55:00 → 2025-12-25 22:00:00 (1 days 00:05:00)
  - unexpected: 2025-12-31 21:55:00 → 2026-01-01 22:00:00 (1 days 00:05:00)
- **GBP_USD**: bars=74555 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=35
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:00:00 → 2025-09-14 21:10:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-09-17 21:00:00 → 2025-09-17 21:10:00 (0 days 00:10:00)
  - unexpected: 2025-09-25 21:00:00 → 2025-09-25 21:10:00 (0 days 00:10:00)
- **USD_JPY**: bars=74557 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=33
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-11 21:30:00 → 2025-09-11 21:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-10-08 21:05:00 → 2025-10-08 21:15:00 (0 days 00:10:00)
  - unexpected: 2025-11-02 22:00:00 → 2025-11-02 22:10:00 (0 days 00:10:00)
- **AUD_USD**: bars=74563 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=29
  - unexpected: 2025-09-02 21:50:00 → 2025-09-02 22:00:00 (0 days 00:10:00)
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-10-06 21:20:00 → 2025-10-06 21:30:00 (0 days 00:10:00)
  - unexpected: 2025-12-08 22:10:00 → 2025-12-08 22:25:00 (0 days 00:15:00)
- **USD_CAD**: bars=74560 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=30
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-09-21 21:15:00 → 2025-09-21 21:25:00 (0 days 00:10:00)
  - unexpected: 2025-09-25 21:00:00 → 2025-09-25 21:15:00 (0 days 00:15:00)
  - unexpected: 2025-11-09 22:05:00 → 2025-11-09 22:15:00 (0 days 00:10:00)
- **USD_CHF**: bars=74514 duplicates=0 incomplete=0 unparseable_times=0 weekend/closed gaps=52 unexpected_gaps=64
  - unexpected: 2025-09-07 22:30:00 → 2025-09-07 22:40:00 (0 days 00:10:00)
  - unexpected: 2025-09-14 21:10:00 → 2025-09-14 21:20:00 (0 days 00:10:00)
  - unexpected: 2025-09-16 21:05:00 → 2025-09-16 21:15:00 (0 days 00:10:00)
  - unexpected: 2025-09-17 21:15:00 → 2025-09-17 21:25:00 (0 days 00:10:00)
  - unexpected: 2025-09-25 21:05:00 → 2025-09-25 21:15:00 (0 days 00:10:00)

No missing candles were manufactured. No interpolation. No data discarded to improve results.

## 16. Live-vs-offline limitation

This analysis is a **QUANT / OFFLINE BASELINE**.

Live path: quant direction → always-on RL agreement/veto → risk/execution.
Unseen RL states are stochastic BUY/SELL/SKIP with probability 1/3 each.
This baseline does **not** include RL or API voters and must not be described as an exact historical replay of the live bot.

## 17. Runtime per symbol

| symbol | started UTC | finished UTC | elapsed_s | status | trades | artifact |
| --- | --- | --- | ---: | --- | ---: | --- |
| EUR_USD | 2026-09-18T10:02:57Z | 2026-09-18T11:07:51Z | 3893.5530 | completed | 3202 | `reports\decision_quality\checkpoints\baseline\EUR_USD__baseline.json` |
| GBP_USD | 2026-09-18T11:07:51Z | 2026-09-18T12:10:02Z | 3731.2170 | completed | 3134 | `reports\decision_quality\checkpoints\baseline\GBP_USD__baseline.json` |
| USD_JPY | 2026-09-18T12:10:02Z | 2026-09-18T13:00:37Z | 3035.0370 | completed | 2595 | `reports\decision_quality\checkpoints\baseline\USD_JPY__baseline.json` |
| AUD_USD | 2026-09-18T13:00:37Z | 2026-09-18T14:06:55Z | 3977.7760 | completed | 3255 | `reports\decision_quality\checkpoints\baseline\AUD_USD__baseline.json` |
| USD_CAD | 2026-09-18T14:06:55Z | 2026-09-18T15:08:04Z | 3669.4840 | completed | 3017 | `reports\decision_quality\checkpoints\baseline\USD_CAD__baseline.json` |
| USD_CHF | 2026-09-18T15:08:04Z | 2026-09-18T16:21:15Z | 4390.8500 | completed | 3486 | `reports\decision_quality\checkpoints\baseline\USD_CHF__baseline.json` |

## 18. Total wall-clock runtime

- Sum of per-symbol elapsed seconds: **22697.9s** (378.3 min)
- Checkpoint created: 2026-09-18T10:02:56Z
- Checkpoint updated: 2026-09-18T16:21:15Z

## 19. Checkpoint status

- `EUR_USD|baseline`: **completed** trades=3202 sha256=3ae3c4d06179…
- `GBP_USD|baseline`: **completed** trades=3134 sha256=ac3ddba51b75…
- `USD_JPY|baseline`: **completed** trades=2595 sha256=e1b0d3491f87…
- `AUD_USD|baseline`: **completed** trades=3255 sha256=e639a1f817e4…
- `USD_CAD|baseline`: **completed** trades=3017 sha256=a88eb2c44069…
- `USD_CHF|baseline`: **completed** trades=3486 sha256=3901a2d50a63…

- mode=baseline impl=optimized warmup=80 seed=42
- sl_atr_mult=None apply_fx_week=True

## 20. Experiments not run

- ATR / stop-width alternatives: **NOT RUN IN BASELINE PHASE**
- Random-RL / RL historical gate: **NOT RUN IN BASELINE PHASE**
- API replay: **NOT RUN IN BASELINE PHASE**

No strategy, SL/TP, or filter changes are recommended or applied from this report.

