# SIX-PAIR 12-MONTH QUANT BASELINE DIAGNOSIS

**Scope:** Read-only diagnosis of the completed QUANT/OFFLINE baseline.  
**Window:** 2025-09-01 through 2026-08-31 UTC  
**Not included:** RL gate, API voters, ATR stop-width experiments.  
**This is not a live-bot historical replay.**

Started: 2026-09-18T21:32:20Z  
Finished: 2026-09-18T21:37:10Z

Required sections:
- [EXECUTIVE DIAGNOSIS](#executive-diagnosis)
- [DATA / ARTIFACT AVAILABILITY](#item-1--artifact-inventory)
- [BUY VS SELL](#item-2--buy-vs-sell-diagnosis)
- [DIRECTIONAL FORWARD RETURNS](#item-3--directional-predictive-edge-ignoring-sltp)
- [MFE / MAE](#item-4--mfe--mae-path-diagnosis)
- [STOP-OUT AFTERMATH](#item-5--stop-out-aftermath)
- [ENTRY TIMING](#item-6--entry-timing--late-entry)
- [STRATEGY LABELS](#item-7--strategy-label-decomposition)
- [HIGHER-TIMEFRAME CONTEXT](#item-8--higher-timeframe-context)
- [MARKET REGIMES](#item-9--market-regime)
- [SESSIONS / TIME OF DAY](#item-10--session--time-of-day)
- [COST / SPREAD CONTRIBUTION](#item-11--cost--spread-contribution)
- [TRAIN / VALIDATION / TEST STABILITY](#item-12--chronological-and-cross-symbol-stability)
- [CROSS-SYMBOL STABILITY](#item-12--chronological-and-cross-symbol-stability)
- [ROOT-CAUSE HYPOTHESIS TABLE](#item-13--root-cause-synthesis)
- [WHAT THE DATA SUPPORTS](#what-the-data-supports)
- [WHAT THE DATA DOES NOT SUPPORT](#what-the-data-does-not-support)
- [LIMITATIONS](#limitations)
- [NEXT EXPERIMENTS WORTH CONSIDERING — NOT RUN](#next-experiments-worth-considering--not-run)

---

## ITEM 1 — Artifact inventory

**Status:** COMPLETED  
**Started:** 2026-09-18T21:32:20Z  
**Finished:** 2026-09-18T21:32:22Z  
**Elapsed:** 2s

Persisted trade count from six `checkpoints/baseline/{symbol}__baseline.json` artifacts: **18689**. Matches the known baseline total. Checkpoint `trade_count` equals artifact length for every symbol.

### Field availability

| Field | Classification | Notes |
| --- | --- | --- |
| symbol | AVAILABLE DIRECTLY | snapshot.symbol |
| direction (BUY/SELL) | AVAILABLE DIRECTLY | snapshot.side |
| strategy label | AVAILABLE DIRECTLY | snapshot.strategy |
| horizon | AVAILABLE DIRECTLY | snapshot.horizon |
| entry timestamp | AVAILABLE DIRECTLY | entry_time |
| entry price | AVAILABLE DIRECTLY | snapshot.entry_price (spread-adjusted) |
| SL / TP | AVAILABLE DIRECTLY | snapshot.stop_loss / take_profit |
| exit timestamp / price / reason | AVAILABLE DIRECTLY | reasons: sl, tp, eod, ambiguous_sl_tp |
| realized pips / R | AVAILABLE DIRECTLY | realised_pips, realised_r |
| MFE / MAE pips, R, ATR | AVAILABLE DIRECTLY | mfe_pips/r/atr, mae_pips/r/atr |
| ATR at entry | AVAILABLE DIRECTLY | snapshot.atr |
| spread (price, pips, /ATR) | AVAILABLE DIRECTLY | snapshot.spread* |
| H1 / H4 / htf_agreement | AVAILABLE DIRECTLY | snapshot.h1_trend, h4_trend, htf_agreement |
| regime / session / hour_utc / hour_london | AVAILABLE DIRECTLY | |
| pre-entry movement | AVAILABLE DIRECTLY | snapshot.pre_move_atr |
| forward returns 5/15/30/60m | AVAILABLE DIRECTLY | forward[`Nm_pips`], [`Nm_hit`] (signed, signal direction) |
| forward returns 120/240m | DERIVABLE FROM HISTORICAL CANDLES | not persisted; can join entry_time to M5 CSV |
| post-stop +0.5R / +1R / +2R / original TP | AVAILABLE DIRECTLY | post_stop.plus_0_5r, plus_1r, plus_2r, reached_original_tp |
| post-stop 5/15/30/60m pips | AVAILABLE DIRECTLY | post_stop[`Nm_pips`] |
| post-stop 120/240m | DERIVABLE FROM HISTORICAL CANDLES | not persisted |
| minutes_to_original_tp | AVAILABLE DIRECTLY | may be hours later; uses remaining history |
| train / validation / test | DERIVABLE FROM PERSISTED TRADES | chronological 50/25/25 by entry_time; not stored on each row |
| non-trade decision snapshots | NOT AVAILABLE WITHOUT SIGNAL REPLAY | artifacts store trades only (snapshot_count=0 on reload) |
| bid/ask candle path at entry/exit | DERIVABLE FROM HISTORICAL CANDLES | CSVs have bid/ask OHLC; baseline used mid + simulated half-spread |
| indicator series at every bar | NOT AVAILABLE WITHOUT SIGNAL REPLAY | only entry-bar snapshot fields persisted |

No signal-generation replay was launched.

---

## ITEM 2 — BUY vs SELL diagnosis

**Status:** COMPLETED  
**Started:** 2026-09-18T21:33:05Z  
**Finished:** 2026-09-18T21:33:06Z  
**Elapsed:** 1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

### Overall

| side | n | win_rate | exp_R | PF | total_R | median_R | median MFE R | median MAE R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BUY | 9538 | 27.01% | -0.1898 | 0.7399 | -1810.44 | -1.0000 | 0.650 | 1.088 |
| SELL | 9151 | 26.36% | -0.2096 | 0.7153 | -1918.08 | -1.0000 | 0.618 | 1.084 |

### Per symbol

| group | n | exp_R | PF | wr | total_R |
| --- | ---: | ---: | ---: | ---: | ---: |
| EUR_USD BUY | 1563 | -0.2284 | 0.6925 | 25.72% | -357.00 |
| EUR_USD SELL | 1639 | -0.2217 | 0.7006 | 25.93% | -363.30 |
| GBP_USD BUY | 1583 | -0.2097 | 0.7153 | 26.34% | -332.00 |
| GBP_USD SELL | 1551 | -0.1827 | 0.7488 | 27.27% | -283.38 |
| USD_JPY BUY | 1357 | -0.0841 | 0.8788 | 30.51% | -114.16 |
| USD_JPY SELL | 1238 | -0.1809 | 0.7511 | 27.30% | -224.00 |
| AUD_USD BUY | 1655 | -0.2097 | 0.7153 | 26.34% | -347.00 |
| AUD_USD SELL | 1600 | -0.2227 | 0.6993 | 25.94% | -356.33 |
| USD_CAD BUY | 1552 | -0.1939 | 0.7348 | 26.87% | -301.00 |
| USD_CAD SELL | 1465 | -0.2041 | 0.7221 | 26.55% | -299.07 |
| USD_CHF BUY | 1828 | -0.1965 | 0.7315 | 26.81% | -359.29 |
| USD_CHF SELL | 1658 | -0.2364 | 0.6828 | 25.45% | -392.00 |

### Chronological (all symbols)

| split | side | n | exp_R | PF | wr |
| --- | --- | ---: | ---: | ---: | ---: |
| IN-SAMPLE | BUY | 4741 | -0.2071 | 0.7185 | 26.43% |
| IN-SAMPLE | SELL | 4603 | -0.2062 | 0.7196 | 26.46% |
| VALIDATION | BUY | 2382 | -0.1461 | 0.7958 | 28.46% |
| VALIDATION | SELL | 2290 | -0.1956 | 0.7327 | 26.81% |
| TEST/OOS | BUY | 2415 | -0.1989 | 0.7284 | 26.71% |
| TEST/OOS | SELL | 2258 | -0.2308 | 0.6893 | 25.69% |

**Answers:**
- BOTH directions are negative overall, on every symbol, and in every chronological partition.
- Neither direction accounts for most losses. Total R is similar (BUY -1810, SELL -1918).
- SELL is slightly worse overall and in OOS, but the gap is small. USD_JPY BUY is the least negative cell (-0.084 R) and is still negative.
- Median R is -1.0 on both sides (typical loser is a full stop). Median MAE ≈ 1.08 R (stop is routinely reached).
- Do **not** disable a direction. This is a descriptive result, not a trading rule.

---

## ITEM 3 — Directional predictive edge ignoring SL/TP

**Status:** COMPLETED  
**Started:** 2026-09-18T21:34:19Z  
**Finished:** 2026-09-18T21:34:27Z  
**Elapsed:** 8s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Forward returns are signed in the signal direction (BUY: future−entry, SELL: entry−future). Horizons 5/15/30/60m are persisted. 120/240m were joined from historical M5 closes to the same spread-adjusted entry used by the baseline. **No signal replay.**

### Overall (n=18689 at all listed horizons)

| horizon | n | mean pips | median pips | % positive | mean ATR | median ATR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5m | 18689 | -1.14 | -1.10 | 30.30% | -0.372 | -0.351 |
| 15m | 18689 | -1.12 | -1.10 | 37.04% | -0.370 | -0.362 |
| 30m | 18689 | -1.08 | -1.10 | 40.45% | -0.363 | -0.358 |
| 60m | 18689 | -1.13 | -1.20 | 42.91% | -0.360 | -0.372 |
| 120m | 18689 | -1.11 | -1.30 | 44.78% | -0.365 | -0.402 |
| 240m | 18689 | -1.02 | -1.30 | 45.85% | -0.355 | -0.416 |

Overall 5m quantiles (pips): p10=-4.60 p25=-2.60 p75=+0.40 p90=+2.30.

### BUY vs SELL (mean pips / % positive)

| horizon | BUY mean | BUY %pos | SELL mean | SELL %pos |
| ---: | ---: | ---: | ---: | ---: |
| 5m | -1.14 | 30.56% | -1.13 | 30.03% |
| 60m | -1.08 | 43.87% | -1.18 | 41.92% |
| 240m | -0.68 | 47.53% | -1.37 | 44.09% |

### Per symbol 60m (persisted)

| symbol | n | mean pips | %pos | mean ATR |
| --- | ---: | ---: | ---: | ---: |
| EUR_USD | 3202 | -1.26 | 41.35% | -0.418 |
| GBP_USD | 3134 | -1.85 | 41.93% | -0.421 |
| USD_JPY | 2595 | -0.78 | 45.97% | -0.182 |
| AUD_USD | 3255 | -0.99 | 43.63% | -0.377 |
| USD_CAD | 3017 | -1.03 | 42.56% | -0.370 |
| USD_CHF | 3486 | -0.82 | 42.60% | -0.361 |

### Chronological 60m

| split | n | mean pips | %pos |
| --- | ---: | ---: | ---: |
| IN-SAMPLE | 9344 | -1.39 | 42.25% |
| VALIDATION | 4672 | -1.06 | 44.29% |
| TEST/OOS | 4673 | -0.67 | 42.86% |

**Key question:** Does quant direction predict the sign of future price movement at any useful horizon before SL/TP? **No.** Mean and median are negative at every requested horizon. Hit rate stays below 50% everywhere (30% at 5m, 46% at 240m). The pattern is the same for BUY and SELL, all six symbols, and all three chronological partitions.

The ~−1.1 pip 5m median is about one typical simulated half-spread (1.0 pip on majors). Cost vs directional miss is separated in Item 11.

All requested horizons are reported; no horizon was selected as “best.”

---

## ITEM 4 — MFE / MAE path diagnosis

**Status:** COMPLETED  
**Started:** 2026-09-18T21:35:03Z  
**Finished:** 2026-09-18T21:35:04Z  
**Elapsed:** 1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Baseline SL distance is **2.0 ATR** on every trade (`sl_over_atr` median=2.0). TP is 2R.

### Quantiles

| group | n | MFE R p10/p25/med/p75/p90 | MAE R p10/p25/med/p75/p90 | MFE pips med | MAE pips med |
| --- | ---: | --- | --- | ---: | ---: |
| ALL | 18689 | 0.00 / 0.08 / **0.63** / 2.02 / 2.26 | 0.42 / 0.93 / **1.09** / 1.25 / 1.51 | 4.4 | 6.6 |
| WINNERS | 4988 | 2.03 / 2.07 / **2.18** / 2.38 / 2.70 | 0.20 / 0.32 / **0.52** / 0.74 / 0.89 | 15.6 | 3.2 |
| LOSERS | 13701 | 0.00 / 0.00 / **0.29** / 0.82 / 1.40 | 1.02 / 1.06 / **1.16** / 1.33 / 1.61 | 1.9 | 7.8 |
| BUY | 9538 | med MFE R 0.65 | med MAE R 1.09 | 4.4 | 6.6 |
| SELL | 9151 | med MFE R 0.62 | med MAE R 1.08 | 4.4 | 6.7 |

Symbol median MFE R is 0.57–0.78; median MAE R is 1.08–1.09 everywhere.

### Answers

- **Do losers move adverse almost immediately?** Often yes: **3669 / 13701 (26.8%)** losers have MFE pips = 0. Loser median MFE is only **0.29 R**.
- **Do losers first achieve meaningful favorable excursion?** Sometimes: **5175 / 13701 (37.8%)** losers reach MFE ≥ 0.5 R; **2680 / 13701 (19.6%)** reach MFE ≥ 1.0 R before losing. Most do not.
- **Do winners take large adverse movement first?** Moderate: winner median MAE = **0.52 R**. **2634 / 4988 (52.8%)** winners have MAE ≥ 0.5 R. **0 / 4988** have MAE ≥ 1.0 R (they would have been stopped).
- **Is typical MAE near/above the stop?** For the book, median MAE = **1.09 R** (stop is 1 R). 14168 / 18689 trades have MAE ≥ 0.9 R. Losers’ MAE sits on/through the stop by construction.
- **Is typical MFE large enough that profit existed but was surrendered?** For the median trade, no (0.63 R vs 2 R TP). A minority of losers did have ≥1 R of open profit (19.6%). Hypothesis E is only **partially** descriptive, not the main path.

BUY/SELL MFE/MAE distributions are nearly identical.

---

## ITEM 5 — Stop-out aftermath

**Status:** COMPLETED  
**Started:** 2026-09-18T21:35:37Z  
**Finished:** 2026-09-18T21:35:39Z  
**Elapsed:** 2s  
**Classification:** VERIFIED DESCRIPTIVE RESULT (with methodology caveat)

Stopped trades: **13699** (`sl` 13660 + `ambiguous_sl_tp` 39). TP exits 4984. EOD 6.

Existing `post_stop.plus_*` / `reached_original_tp` scan **all remaining bars after the stop** until the end of the 12-month file. That is the already-implemented research methodology. It is **not** a same-session continuation.

### Unlimited remaining-history flags (existing methodology)

| group | n stopped | % later +0.5R | % later +1R | % later orig TP / +2R | median minutes to TP |
| --- | ---: | ---: | ---: | ---: | ---: |
| OVERALL | 13699 | 97.80% | 97.05% | 95.56% | 865 (~14.4h) |
| BUY | 6961 | 98.52% | 98.07% | 96.90% | 850 |
| SELL | 6738 | 97.05% | 95.99% | 94.18% | 880 |
| train | 6873 | 98.59% | 98.02% | 97.28% | 912 |
| valid | 3380 | 98.99% | 98.58% | 97.22% | 892 |
| test | 3446 | 95.04% | 93.62% | 90.51% | 785 |

Time-to-TP among those who eventually touch it (n=13091): p25=**240 min**, median=**865 min**, p75=4678 min (~3.2 days), p90=19755 min (~13.7 days).

Every symbol shows ≥94% eventual TP touch on this unlimited window.

### Fixed short horizons after stop (persisted 5/15/30/60m pips)

| horizon after SL | n | mean pips | median pips | % positive |
| ---: | ---: | ---: | ---: | ---: |
| 5m | 13699 | -7.66 | -6.30 | 3.3% |
| 15m | 13699 | -7.50 | -6.20 | 9.0% |
| 30m | 13699 | -7.46 | -6.20 | 13.9% |
| 60m | 13699 | -7.47 | -6.30 | 20.2% |

**Key question:** Are stops cutting off trades that would commonly have worked later?

- **If “later” means the rest of the year:** most stopped trades eventually see original TP, but typically many hours later. That is FX drift, not evidence the stop was “too tight” for the intended hold.
- **If “later” means 30–60 minutes:** **No.** Price is still adverse on average (−7.5 pips) and only 14–20% are even positive.

Do **not** change stop width from this item. Short-horizon aftermath does **not** support a too-tight-stop story. Unlimited-horizon “reached TP” must not be read as a same-trade recovery.

120/240m post-stop were not persisted; short-horizon evidence is already decisive, so they were not candle-joined.

---

## ITEM 6 — Entry timing / late entry

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:16Z  
**Finished:** 2026-09-18T21:36:17Z  
**Elapsed:** 1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Existing late-entry definition: `pre_move_atr >= 1.5` (`filters._not_late_entry` / `possible_late_entry`). Buckets use that threshold plus a descriptive small/moderate split. No cutoff search.

`pre_move_atr` is present on all 18689 trades. Distribution: p10=−3.22, p25=−1.52, median=**0.96**, p75=2.98, p90=4.50, mean=0.78.

| bucket | n | exp_R | PF | wr | 60m fwd mean pips | 60m %pos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small <0.5 | 8394 | -0.1947 | 0.7338 | 26.85% | -1.03 | 43.53% |
| moderate 0.5–1.5 | 2124 | -0.2002 | 0.7269 | 26.65% | -1.46 | 42.18% |
| large ≥1.5 (existing late) | 8171 | -0.2042 | 0.7220 | 26.53% | -1.14 | 42.47% |

Chronological: every bucket is negative in train, valid, and test. Test moderate is worst (−0.245, n=545) but still the same sign.

Loser median pre_move=0.97 vs winner 0.93. **Losses do not cluster after extended pre-entry moves.** Late entries are common (43.7% of trades) but expectancy is almost the same as small-pre-move trades.

Do not invent a new late-entry threshold.

---

## ITEM 7 — Strategy-label decomposition

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:17Z  
**Finished:** 2026-09-18T21:36:18Z  
**Elapsed:** 1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Labels do not choose BUY/SELL. BUY/SELL counts are roughly balanced in every label.

| label | n | BUY/SELL | exp_R | PF | wr | total_R | med MFE R | med MAE R | 60m %pos |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp | 1824 | 900/924 | -0.1045 | 0.8508 | 29.88% | -190.7 | 0.79 | 1.06 | 44.4% |
| trend | 1725 | 869/856 | -0.1377 | 0.8066 | 28.75% | -237.5 | 0.74 | 1.07 | 44.5% |
| mean_reversion | 1703 | 891/812 | -0.1746 | 0.7591 | 27.54% | -297.3 | 0.71 | 1.07 | 44.2% |
| swing_mean_reversion | 4527 | 2307/2220 | -0.2213 | 0.7011 | 25.96% | -1002.0 | 0.59 | 1.10 | 41.9% |
| swing_trend | 4580 | 2341/2239 | -0.2225 | 0.6997 | 25.92% | -1019.0 | 0.57 | 1.10 | 42.0% |
| swing_breakout | 4330 | 2230/2100 | -0.2268 | 0.6945 | 25.77% | -982.0 | 0.60 | 1.09 | 43.2% |

Every label is negative in train, valid, and test except no label flips positive in a large split. `scalp` and `trend` are less bad but still negative in all three partitions (`trend` test −0.058 n=270; `scalp` test −0.070 n=279).

One small positive cell exists: USD_CHF `trend` +0.0415 R, n=265, 60m hit 48.7%. **INSUFFICIENT / not an edge.**

Do **not** remove any strategy.

---

## ITEM 8 — Higher-timeframe context

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:18Z  
**Finished:** 2026-09-18T21:36:18Z  
**Elapsed:** <1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Existing `htf_agreement` tokens: `aligned_h1` / `against_h1` / `h1_uncertain` and the H4 analogues.

| group | n | exp_R | PF | wr | 60m %pos |
| --- | ---: | ---: | ---: | ---: | ---: |
| H1 aligned | 10742 | -0.1773 | 0.7557 | 27.43% | 43.72% |
| H1 against | 7427 | -0.2361 | 0.6833 | 25.46% | 41.89% |
| H1 uncertain | 520 | -0.1371 | 0.8073 | 28.85% | 40.96% |
| H4 aligned | 9418 | -0.1824 | 0.7492 | 27.26% | 43.33% |
| H4 against | 8692 | -0.2189 | 0.7040 | 26.05% | 42.51% |
| H4 uncertain | 579 | -0.1865 | 0.7441 | 27.12% | 42.14% |

H1-aligned is better than H1-against in train (−0.172 vs −0.260), valid (−0.161 vs −0.194), and test (−0.204 vs −0.231). Both remain negative. The old tiny-sample story that H1-against looked better is **not** reproduced. HTF agreement shifts the distribution modestly; it does not create a positive book.

H1 uncertain valid +0.032 (n=93) is **INSUFFICIENT SAMPLE**.

---

## ITEM 9 — Market regime

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:18Z  
**Finished:** 2026-09-18T21:36:18Z  
**Elapsed:** <1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Existing `classify_regime` labels only.

| regime | n | exp_R | PF | wr | total_R | BUY/SELL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HIGH_VOLATILITY | 6523 | -0.1521 | 0.7878 | 28.28% | -992.4 | 3240/3283 |
| TRENDING_UP | 2632 | -0.1950 | 0.7334 | 26.82% | -513.2 | 2051/581 |
| TRENDING_DOWN | 2588 | -0.2013 | 0.7256 | 26.62% | -521.0 | 624/1964 |
| RANGING | 2729 | -0.2074 | 0.7181 | 26.42% | -566.0 | 1429/1300 |
| UNCERTAIN | 2865 | -0.2136 | 0.7105 | 26.21% | -612.0 | 1492/1373 |
| LOW_VOLATILITY | 1352 | **-0.3876** | 0.5130 | 20.41% | -524.0 | 702/650 |

LOW_VOLATILITY is worse in train (−0.293), valid (−0.426), and test (−0.529), and on every symbol. Still negative — a consistently worse subgroup, not a tradable positive regime.

HIGH_VOLATILITY is the least bad large group and remains negative in all splits (test −0.125).

Losses are **broadly distributed**. Do not create a new regime filter.

---

## ITEM 10 — Session / time of day

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:18Z  
**Finished:** 2026-09-18T21:36:19Z  
**Elapsed:** 1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Existing session labels only. Hours are descriptive; no window search.

| session | n | exp_R | PF | wr | train exp | valid exp | test exp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| london_ny_overlap | 4872 | -0.1421 | 0.8009 | 28.61% | -0.148 | -0.109 | -0.161 |
| london | 5292 | -0.1927 | 0.7363 | 26.91% | -0.238 | -0.144 | -0.155 |
| late_new_york | 2426 | -0.2177 | 0.7052 | 26.09% | -0.212 | -0.144 | -0.300 |
| asia | 4837 | -0.2371 | 0.6820 | 25.43% | -0.217 | -0.249 | -0.267 |
| rollover_low_liquidity | 1262 | -0.2702 | 0.6429 | 24.33% | -0.266 | -0.264 | -0.285 |

All sessions negative in all three partitions. Overlap is least bad; rollover/Asia worse. UTC hour 03 is near flat (−0.015, n=457) and is **not** treated as an optimized window.

Do not propose a new live session rule.

---

## ITEM 11 — Cost / spread contribution

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:19Z  
**Finished:** 2026-09-18T21:36:19Z  
**Elapsed:** <1s  
**Classification:** VERIFIED DESCRIPTIVE RESULT

Baseline execution (from engine / `execution_sim`):
- Signals use **mid** OHLC.
- **Entry pays** production `simulated_half_spread` (BUY +half, SELL −half).
- **Exit does not pay a second spread** (SL/TP/eod at those prices / last mid).
- No modelled slippage.
- No commissions.

Half-spread: 1.0 pip on EUR/JPY/AUD/CAD/CHF; 1.5 pip on GBP.

| metric | value |
| --- | --- |
| mean entry spread | 1.084 pips |
| median entry spread | 1.000 pip |
| mean entry cost in R | **0.179 R** |
| median entry cost in R | 0.167 R |
| sum of entry costs | 3340 R |
| after-cost expectancy (actual) | **-0.1995 R** |
| approx expectancy after adding entry spread back | **-0.0208 R** |

**Can costs explain a large portion of −0.1995 R?** **Yes, most of the R gap vs zero** (~0.179 of 0.200). The residual after adding entry cost back is still slightly negative. Combined with Item 3 (hit rate <50% at every horizon), costs are not hiding a strong directional edge — they are amplifying a near-zero / slightly negative raw direction.

Do not remove costs.

---

## ITEM 12 — Chronological and cross-symbol stability

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:19Z  
**Finished:** 2026-09-18T21:36:40Z  
**Elapsed:** 21s  

Uses only categories already analyzed. No new thresholds.

| FACTOR | SUBGROUP | TRAIN n/exp | VALID n/exp | TEST n/exp | SYMBOL CONSISTENCY | CLASSIFICATION |
| --- | --- | --- | --- | --- | --- | --- |
| side | BUY | 4741 / -0.207 | 2382 / -0.146 | 2415 / -0.199 | 6/6 negative | CONSISTENTLY NEGATIVE |
| side | SELL | 4603 / -0.206 | 2290 / -0.196 | 2258 / -0.231 | 6/6 negative | CONSISTENTLY NEGATIVE |
| 60m direction | all | 9344 / −1.39 pips | 4672 / −1.06 | 4673 / −0.67 | 6/6 mean<0 | CONSISTENTLY NEGATIVE |
| pre_move | large ≥1.5 | 4121 / -0.199 | 2099 / -0.194 | 1951 / -0.226 | same as small | NO MATERIAL DIFFERENCE |
| pre_move | small <0.5 | 4161 / -0.219 | 2056 / -0.143 | 2177 / -0.196 | same as large | NO MATERIAL DIFFERENCE |
| strategy | scalp | 956 / -0.115 | 589 / -0.104 | 279 / -0.070 | 6/6 negative | CONSISTENTLY NEGATIVE (least bad) |
| strategy | swing_* | ~2.1k / ≈-0.22 | ~1.0k / ≈-0.18 | ~1.3k / ≈-0.24 | 6/6 negative | CONSISTENTLY NEGATIVE |
| H1 | aligned | 5367 / -0.172 | 2691 / -0.161 | 2684 / -0.204 | better than against, still − | STABLE CANDIDATE (relative only) |
| H1 | against | 3681 / -0.260 | 1888 / -0.194 | 1858 / -0.231 | worse, still − | CONSISTENTLY NEGATIVE |
| regime | LOW_VOLATILITY | 670 / -0.293 | 319 / -0.426 | 363 / -0.529 | 6/6 worst-ish | STABLE CANDIDATE (worse subgroup) |
| regime | HIGH_VOLATILITY | 3227 / -0.187 | 1631 / -0.110 | 1665 / -0.125 | 6/6 negative | CONSISTENTLY NEGATIVE (least bad large) |
| session | overlap | 2542 / -0.148 | 1145 / -0.109 | 1185 / -0.161 | least bad | STABLE CANDIDATE (relative only) |
| session | asia / rollover | 2475+617 / -0.217/-0.266 | -0.249/-0.264 | -0.267/-0.285 | worse | CONSISTENTLY NEGATIVE |
| symbol | USD_JPY | — | — | — | least bad (−0.130) still − | CONSISTENTLY NEGATIVE |
| symbol | others | — | — | — | −0.20 to −0.23 | CONSISTENTLY NEGATIVE |
| USD_CHF trend | n=265 +0.042 | not split further | — | 1 cell | INSUFFICIENT SAMPLE |  |
| H1 uncertain valid | n=93 +0.032 | — | — | tiny | INSUFFICIENT SAMPLE |  |

No subgroup with adequate n is a positive STABLE CANDIDATE for an edge. Relative differences (H1 aligned, overlap, high-vol, scalp, USD_JPY) are **less negative**, not profitable.

---

## ITEM 13 — Root-cause synthesis

**Status:** COMPLETED  
**Started:** 2026-09-18T21:36:40Z  
**Finished:** 2026-09-18T21:37:10Z  
**Elapsed:** 30s

| ID | Hypothesis | Verdict | Evidence |
| --- | --- | --- | --- |
| A | Directional signal has little/negative edge | **SUPPORTED** | Item 3: mean/median forward <0 and %positive <50% at 5–240m, all splits, both sides, all symbols. |
| B | Entry timing is too late | **NOT SUPPORTED** | Item 6: large vs small pre_move expectancy almost identical; loser vs winner pre_move medians 0.97 vs 0.93. |
| C | Stops too tight vs normal noise | **NOT SUPPORTED** | Item 5 short-horizon: 30–60m after SL still −7.5 pips, 14–20% positive. Item 4: most losers never had ≥1R MFE. Unlimited “reached TP” is hours-later drift. |
| D | Target/stop geometry is poor | **PARTIALLY SUPPORTED** | 2R TP with ~27% wins is consistent with a no-edge process plus costs (win rate ≈ 1/(1+2)=33% even with zero edge before costs). Geometry does not create the missing directional edge (Item 3). |
| E | Trades move favorably then give back | **PARTIALLY SUPPORTED** | 19.6% of losers had MFE ≥1R; 26.8% had MFE=0. Not the main path. |
| F | Losses concentrated in particular strategy labels | **NOT SUPPORTED** | All six labels negative in all chronological splits. Swing labels worse; scalp/trend less bad. |
| G | Losses concentrated in particular regimes | **PARTIALLY SUPPORTED** | LOW_VOLATILITY is stably worse (−0.39, worse OOS). Other regimes still negative. Not the sole cause. |
| H | HTF conflict is important | **PARTIALLY SUPPORTED** | H1-against worse than aligned in all splits; both negative. Not a live filter. |
| I | Session/time of day is important | **PARTIALLY SUPPORTED** | Overlap least bad, Asia/rollover worse; all negative in all splits. |
| J | Transaction costs are the primary problem | **PARTIALLY SUPPORTED** | Entry spread ≈0.179 R vs book −0.1995 R. Residual after adding cost back ≈ −0.021 R. Costs explain most of the R hole but do not hide a positive signal (Item 3). |
| K | Performance is symbol-specific | **NOT SUPPORTED** as the cause | USD_JPY least bad; all six negative with similar win rates. |
| L | Quant system is broadly negative across conditions | **SUPPORTED** | Items 2–10: sign is negative in essentially every large cell. |

Multiple mechanisms are supported. The core is **A + L**, with **J** explaining most of the realized-R magnitude once SL/TP converts a no-edge signed path into a ~27% win-rate, 2R-target book.

---

# EXECUTIVE DIAGNOSIS

The six-pair 12-month QUANT/OFFLINE book loses because the **quant direction does not predict subsequent mid-price movement** at 5–240 minutes (hit rate 30–46%, mean always negative), while **entries pay ~0.18 R of simulated spread**. SL/TP geometry (stop 2 ATR / TP 2R) then produces a ~26.7% win rate and −0.20 R expectancy that is **negative in both directions, all six symbols, and train/valid/test**.

This is **not** primarily late-entry, **not** primarily too-tight stops on a 30–60 minute horizon, and **not** one bad strategy/symbol. Relative differences (H1 aligned, London–NY overlap, high-vol, scalp, USD_JPY) are smaller losses, not edges.

**Do not change live trading from this diagnosis.**

---

# WHAT THE DATA SUPPORTS

- Broad, stable negative expectancy of the quant+spread+SL/TP system.
- No usable directional hit rate before geometry.
- Costs account for most of the R expectancy gap vs zero.
- LOW_VOLATILITY, H1-against, Asia/rollover, and swing labels are relatively worse.

# WHAT THE DATA DOES NOT SUPPORT

- A BUY-only or SELL-only problem.
- Late-entry as the loss cluster.
- Stops that commonly “just miss” a recovery inside 60 minutes.
- A positive HTF, session, regime, or strategy edge with adequate n.
- Treating unlimited post-stop TP-touch as evidence stops are too tight.

# LIMITATIONS

- Offline QUANT only; live RL/API not applied.
- Forward 120/240m used mid close vs spread-adjusted entry (same as persisted 5–60m).
- Post-stop +R flags use the rest of the file; short-horizon pips are the honest “later” measure.
- Multiple subgroups inspected; relative “least bad” cells are not edges.
- `hash(symbol)` bar seeds are process-hash-randomized (pre-existing).

# NEXT EXPERIMENTS WORTH CONSIDERING — NOT RUN

1. **Quant-only vs current live RL gate (measurement)**  
   - Hypothesis: the random/unseen RL veto changes fill rate and maybe expectancy vs this quant baseline.  
   - Evidence: this baseline is quant-only; live always has RL.  
   - Variable: include the current RL gate (no retraining) on a bounded or checkpointed replay.  
   - Fixed: quant, SL/TP, symbols, dates.  
   - OOS required: same chronological test window; do not tune RL.

2. **Cost-attribution / mid-entry sensitivity (research only)**  
   - Hypothesis: most of −0.20 R is entry spread on a no-edge signal.  
   - Evidence: Item 11 + Item 3.  
   - Variable: report mid-to-mid vs spread-in books on already-persisted entries (or a thin replay of exits only).  
   - Fixed: signals.  
   - Not a live “remove spread” change.

3. **LOW_VOLATILITY exclusion (research filter experiment on persisted trades)**  
   - Hypothesis: dropping LOW_VOLATILITY improves expectancy but may stay negative.  
   - Evidence: Item 9 stability.  
   - Variable: existing regime label only.  
   - Fixed: everything else.  
   - OOS: test split must remain negative-or-not before any live discussion.

Do **not** run ATR grids, strategy deletion, or session-window searches from this list.

---

# TESTING

Focused diagnostic tests added in `tests/test_decision_quality_diagnostic.py` (forward signs, pip conversion, R normalization, MFE/MAE signs, post-stop R thresholds, chronological isolation). No historical replay.

```
python -m pytest -q --tb=line
321 passed, 0 failed, 0 skipped, 26.22s
```

---
