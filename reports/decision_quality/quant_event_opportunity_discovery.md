# Six-pair event / opportunity discovery

**Status:** COMPLETE — research only. No model was trained. Production, the quant stub, SL/TP, sessions, RL, APIs, execution, historical CSVs, Docker, and the live bot were not changed.

**Study window:** 2026-09-18T22:29:50Z – 2026-09-18T22:30:11Z (compute). Report completed after that.

**Question:** Should the future quant problem be reframed from “predict UP/DOWN on every M5 bar” to “identify infrequent events whose future path clears realistic cost”?

**Core rule:** Every event definition was declared and TRAIN quantile edges were persisted **before** VALIDATION / DISCOVERY_TEST tables were examined. Thresholds were not retuned.

---

## Final research verdict

# NO ECONOMICALLY USEFUL EVENT FOUND

Some predeclared events change the **distribution** of the next 60-minute close by a few tenths of a pip, and upside breakouts **fail** more often than they continue. None of those shifts is large enough to clear the modeled entry half-spread (~1.0 pip on five pairs, 1.5 pips on GBP_USD). Two-sided 60-minute excursion already exceeds 1 pip on almost every bar, so a 1-pip “opportunity” is not a rare event.

**Do not train a replacement model on this target set. Do not add event filters to live trading.**

---

## How to read this report

| Label | Meaning |
| --- | --- |
| VERIFIED DESCRIPTIVE RESULT | Observed on this dataset with predeclared definitions |
| STABLE CANDIDATE | Same sign in TRAIN, VALIDATION, and DISCOVERY_TEST **and** multiple symbols — still not a trading edge |
| UNSTABLE | Sign or magnitude flips across time or symbols |
| INSUFFICIENT SAMPLE | Event n too small |
| BELOW COST HURDLE | Distributional shift exists but typical close / unique path is smaller than entry cost |
| HYPOTHESIS ONLY | Interpretation, not a claim |

DISCOVERY_TEST (from 2026-06-02 05:05 UTC) **has already been inspected** in prior studies. It is exploratory. It is **not** a pristine final holdout for future model acceptance.

---

## Stage 1 — Data identity

Compatible with the previous feature study. Source CSVs were not modified.

| Symbol | Rows | First UTC | Last UTC | Dup | Monotonic | Unexpected gaps | SHA256 prefix |
| --- | ---: | --- | --- | ---: | --- | ---: | --- |
| EUR_USD | 74572 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 39 | `3ae3c4d061792353` |
| GBP_USD | 74555 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 53 | `ac3ddba51b75f493` |
| USD_JPY | 74557 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 51 | `e1b0d3491f873723` |
| AUD_USD | 74563 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 47 | `e639a1f817e4b919` |
| USD_CAD | 74560 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 48 | `a88eb2c440691bd5` |
| USD_CHF | 74514 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | yes | 82 | `3901a2d50a63ef5c` |

- Raw six-file total: **447321** M5 bars.
- Warmup-complete research rows (same cache as the feature study): **447027**.
- Gaps were classified, not interpolated. Completed MID candles only.

---

## Stage 2 — Split policy

Frozen chronological cuts, identical to the feature study:

| Split | End (inclusive) | Rows | Role |
| --- | --- | ---: | --- |
| TRAIN | 2026-03-03 12:15 | 223370 | Quantile edges and descriptive baseline |
| VALIDATION | 2026-06-02 05:05 | 111828 | Stability check |
| DISCOVERY_TEST | after 2026-06-02 05:05 | 111829 | Already inspected. Exploratory only. |

**This entire year (2025-09 through 2026-08) is now DEVELOPMENT / DISCOVERY data.** No slice of it may be cited later as pristine final out-of-sample evidence for a trained model.

No model acceptance is allowed in this task.

---

## Stage 3 — Cost hurdles (declared before events)

Cost is the **existing modeled entry half-spread**, converted to pips. These are movement hurdles, not trading thresholds.

| Symbol | 0.5× | 1.0× | 1.5× | 2.0× | 3.0× |
| --- | ---: | ---: | ---: | ---: | ---: |
| EUR_USD | 0.50 | 1.00 | 1.50 | 2.00 | 3.00 |
| GBP_USD | 0.75 | 1.50 | 2.25 | 3.00 | 4.50 |
| USD_JPY | 0.50 | 1.00 | 1.50 | 2.00 | 3.00 |
| AUD_USD | 0.50 | 1.00 | 1.50 | 2.00 | 3.00 |
| USD_CAD | 0.50 | 1.00 | 1.50 | 2.00 | 3.00 |
| USD_CHF | 0.50 | 1.00 | 1.50 | 2.00 | 3.00 |

Path-order ATR multiples (also predeclared, not searched): 0.25 / 0.50 / 1.00 ATR. Primary path-order tables use **1.0× cost** and **0.50 ATR**.

A 0.2–0.8 pip mean close is **not** economically interesting against this cost.

---

## Stage 4 — Future path targets

For horizons 15 / 30 / 60 / 120 / 240 / 480 minutes, each completed bar received:

- future close return (pips and ATR)
- MFE-up = (future high − close) / pip
- MFE-down = (close − future low) / pip
- max absolute excursion
- bars to future high / low

Windows are `close[t+1 : t+h]` via `sliding_window_view`. The event bar is excluded. BUY/SELL was **not** assigned.

---

## Stage 5 — Path-order labels

Predeclared rule, never invented from intra-bar ticks:

- **UP_FIRST** if the +threshold high is touched on an earlier future bar than the −threshold low
- **DOWN_FIRST** if the reverse
- **NEITHER** if neither threshold is touched
- **AMBIGUOUS** if both thresholds can be touched on the **same** M5 bar (OHLC cannot order them)

Same-bar ambiguous rate at 1× cost is **~22.5%** at every horizon (15m through 480m). That is a structural limit of M5 OHLC, not a bug.

---

## Stage 6 — How often does M5 present a clear directional opportunity?

Three-way conceptual classes from future MFE vs cost, **no side chosen**:

| Horizon | Hurdle | Only UP | Only DOWN | Both sides | Neither |
| --- | --- | ---: | ---: | ---: | ---: |
| 60m | 0.5× | 8.5% | 8.1% | **83.5%** | 0.002% |
| 60m | 1.0× | 15.3% | 14.8% | **69.8%** | 0.06% |
| 60m | 1.5× | 21.1% | 20.5% | 57.9% | 0.47% |
| 60m | 2.0× | 26.3% | 25.6% | 46.2% | 1.9% |
| 60m | 3.0× | 31.7% | 31.1% | 29.3% | 8.0% |
| 240m | 1.0× | 6.9% | 6.6% | **86.5%** | 0.002% |
| 240m | 3.0× | 19.2% | 18.4% | 62.2% | 0.15% |

**VERIFIED DESCRIPTIVE RESULT:** At a realistic 1× entry-cost hurdle, almost every M5 bar already has **both** an up-path and a down-path large enough to clear cost inside 60 minutes. A one-sided “clear opportunity” is the minority. A NO-TRADE class defined as “neither side clears 1× cost” is essentially empty (~0.06%).

This is why every-bar UP/DOWN is the wrong problem: the typical path is **two-sided noise larger than spread**, not a missing 51% coin-flip.

---

## Predeclared event definitions (frozen)

Persisted in `quant_event_opportunity_data.json` under `frozen_edges` before event tables.

| Family | Event | Definition (TRAIN-only edges) |
| --- | --- | --- |
| Range extreme | `range_bottom_enter` / `range_top_enter` | First bar `pos_in_range_24` enters q1 (≤ 0.191176) or q5 (≥ 0.831461). Edges copied from the prior feature study. |
| Extension | `extend_down_enter` / `extend_up_enter` | First bar `dist_rollmean24_atr` enters TRAIN q1 (≤ −1.442) or q5 (≥ 1.533). |
| Impulse | `impulse_bull_enter` / `impulse_bear_enter` | First bar `signed_body_atr` enters TRAIN q5 (≥ 0.532) or q1 (≤ −0.522). |
| Vol transition | `vol_expand_enter` | First bar `atr_pctile` enters TRAIN q5 (≥ 0.86). |
| Vol transition | `vol_exit_compress` | Previous `atr_pctile` ≤ q1 (0.135) **and** current ≥ q3 (0.64). |
| Breakout | `breakout_up/dn_{12,24,48}` | First close above/below prior rolling high/low. Rolling window **excludes the current bar**. Lookbacks not searched. |
| Rejection | `reject_upper/lower_24` | High (low) beyond prior 24-bar range, close back inside. |
| Session | `asia_to_london`, `london_to_overlap`, `overlap_to_late_ny` | Existing London session buckets only. |
| USD context | other-pairs median / agreement / dispersion | USD-up = −ret on EUR/GBP/AUD, +ret on JPY/CAD/CHF. Target pair excluded. |
| USD divergence | `usd_div_extreme_pos/neg` | `usd_own − usd_others_med` enters TRAIN q5 / q1. |
| Combos (5 only) | listed below | Predeclared. No combinatorial search. |

Predeclared combinations:

1. range bottom + lower rejection
2. range top + upper rejection
3. range bottom + USD-div extreme (either tail)
4. 24-bar upside breakout + vol expand
5. bullish impulse + other-pairs USD agreement ≥ 0.6

---

## Stage 7 — Range-extreme mean reversion as independent events

Prior study: weak bar-level mean reversion at range extremes. This stage counts **entry into** the extreme, not every bar that stays there.

| | Bottom enter | Top enter |
| --- | ---: | ---: |
| Event n | 23734 | 25044 |
| Persistent-state bars | 86661 | 87597 |
| Bars per episode (approx.) | 3.65 | 3.50 |
| 60m mean close (pips) | **+0.313** | **−0.104** |
| 60m P(close up) | 52.8% | 48.5% |
| 60m mean MFE-up / MFE-down | 6.84 / 6.75 | 6.40 / 6.71 |
| Path-order 1× cost | UP 9458 / DOWN 8485 / AMB 5786 | DOWN 9894 / UP 9103 / AMB 6037 |
| Event-bootstrap 60m close (seed 42, 200) | mean 0.313, CI [0.198, 0.417] | mean −0.104, CI [−0.208, −0.0002] |

Chronological 60m close:

| Split | Bottom n | Bottom pips | Bottom hit | Top n | Top pips | Top hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TRAIN | 12021 | +0.230 | 52.2% | 12592 | +0.010 | 49.1% |
| VALIDATION | 5788 | +0.542 | 53.4% | 6195 | −0.319 | 47.9% |
| DISCOVERY_TEST | 5925 | +0.257 | 53.5% | 6257 | −0.122 | 47.9% |

Bottom-enter by symbol (60m close): EUR +0.12 (hit 49.9%), GBP +0.51, JPY +0.49, AUD +0.38, CAD +0.30, CHF +0.11. Five of six positive; EUR is flat on hit rate.

Monthly bottom-enter 60m close is usually positive but **not every month** (2026-04 −0.15, 2026-07 −0.07, 2026-02 hit 49.9%).

Horizons for bottom enter: 15m +0.10 / 52.1%; 30m +0.17 / 52.5%; 60m +0.31 / 52.8%; 120m +0.51 / 53.5%; 240m +0.54 / 52.4%; 480m +0.82 / 52.7%. MFE-up and MFE-down stay nearly equal at every horizon.

**Answer:** The weak mean-reversion **survives event-level analysis** (bottom-enter close CI excludes 0). It does **not** become economically meaningful. Typical close is 0.3 pips versus ~1.0–1.5 pip entry cost. Favorable and adverse 60m MFE are almost the same (~6.8 pips). Adverse 1×-cost path is first on 36% of events; 24% are same-bar ambiguous.

Classification: **WEAK / BELOW COST HURDLE**. Bottom-enter is a BROAD-weak descriptive pattern. Top-enter is weaker and closer to zero.

---

## Stage 8 — Extension / displacement

Same shape as range extremes. Continuation was **not** assumed; both sides were measured.

| Event | n | 60m close | Hit up | TRAIN | VALID | TEST |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| extend_down_enter | 18234 | +0.308 | 53.0% | +0.282 / 52.6% | +0.496 / 52.9% | +0.177 / 53.9% |
| extend_up_enter | 18150 | −0.153 | 48.3% | (same family) |  |  |

Mean-reversion of the extension, not continuation. Effect size again ~0.3 pips. **WEAK / BELOW COST HURDLE.**

---

## Stage 9 — Large-candle / impulse

Each large signed body is already a 1-bar event (median gap 5 minutes), so event n ≈ raw qualifying bars.

| Event | n | 60m close | Hit up | Path-order 1× |
| --- | ---: | ---: | ---: | --- |
| impulse_bull_enter | 70751 | **−0.052** | 49.3% | DOWN_FIRST 27673 > UP_FIRST 26355 |
| impulse_bear_enter | 70306 | **+0.169** | 51.6% | UP_FIRST 27472 > DOWN_FIRST 25915 |

Splits: bullish impulse TRAIN +0.043, VALID −0.209, TEST −0.090 (UNSTABLE sign). Bearish impulse stays slightly positive in all three splits but ≤ 0.30 pips.

**Answer:** Large impulses **slightly revert**, they do not continue. The tilt is tiny and, for bullish impulses, not time-stable. **WEAK / BELOW COST HURDLE.**

---

## Stage 10 — Volatility transitions (not levels)

| Event | n | 60m close | Hit up | 60m mean \|exc\| | Bootstrap close CI |
| --- | ---: | ---: | ---: | ---: | --- |
| vol_expand_enter | 8285 | +0.266 | 50.5% | **13.52** | [−0.005, +0.515] includes 0 |
| vol_exit_compress | 30 | — | — | — | **INSUFFICIENT SAMPLE** |

Range-bottom events have 60m mean |exc| 10.81. Vol-expand is larger (13.52; MFE both sides ~8.5 vs ~6.8). Direction is a coin flip. Path-order is most often AMBIGUOUS.

Monthly vol-expand hit rates sit in 47–53%. GBP close +1.12 pips; CAD/CHF negative. Direction **UNSTABLE**. Magnitude lift is real but modest and two-sided.

Classification: **WEAK magnitude / NO directional information.** Not “PROMISING MAGNITUDE” — the lift does not create a one-sided or economically unique path.

`vol_exit_compress` (predeclared jump from q1 to ≥ q3) almost never occurs because `atr_pctile` is a slow rank. Left as predeclared. **INSUFFICIENT SAMPLE.** The definition was not widened after seeing n=30.

---

## Stage 11 — Breakouts

Prior rolling high/low **excludes the current bar**. Lookbacks 12 / 24 / 48 were all predeclared and are reported equally. 24 is not “the winner.”

| Event | n | 60m close | Hit up | TRAIN | VALID | TEST |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| breakout_up_12 | 23201 | −0.236 | 48.5% | −0.021 | −0.597 | −0.320 |
| breakout_up_24 | 16292 | **−0.378** | 47.9% | −0.169 | −0.892 | −0.304 |
| breakout_up_48 | 11298 | −0.507 | 47.1% |  |  |  |
| breakout_dn_12 | 22260 | +0.291 | 53.0% | +0.153 | +0.594 | +0.279 |
| breakout_dn_24 | 15146 | **+0.360** | 53.2% | +0.185 | +0.643 | +0.445 |
| breakout_dn_48 | 10184 | +0.360 | 53.4% |  |  |  |

`breakout_up_24` event-bootstrap 60m close: mean −0.378, CI **[−0.486, −0.269]** (excludes 0). Path-order: DOWN_FIRST 6276 > UP_FIRST 5745, AMBIGUOUS 4266.

All six symbols have **negative** 60m close after upside 24-bar breakouts (EUR −0.29, GBP −0.66, JPY −0.21, AUD −0.26, CAD −0.47, CHF −0.39). Monthly close is negative in most months (exceptions Oct/Jan/Feb/Jun, all small).

Downside breakouts reverse upward on all six pairs (CAD nearly flat, +0.04).

**Answer:** Breakouts **fail / mean-revert** more often than they continue. The failure is BROAD and time-persistent in sign. The economic size is still ~0.4 pips versus ~1 pip cost, and the adverse path is only modestly more common than the continuation path once 1×-cost and same-bar ambiguity are counted.

Classification: **WEAK directional (failure) / BELOW COST HURDLE / BROAD.**

---

## Stage 12 — Failed-breakout / rejection

| Event | n | 60m close | Hit | TRAIN | VALID | TEST |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reject_lower_24 | 17871 | +0.256 | 51.9% | +0.051 / 51.3% | +0.634 / 52.4% | +0.311 / 52.8% |
| reject_upper_24 | 19339 | −0.128 | 48.9% | +0.075 / 49.4% | −0.581 / 48.0% | −0.096 / 49.1% |

Lower rejection is a weak bounce (CHF −0.07). Upper rejection is unstable in TRAIN (wrong sign). **WEAK / UNSTABLE / BELOW COST.**

---

## Stage 13 — Session transitions

Existing buckets only. n = 1554 each (6 pairs × ~259 session days).

| Event | 60m close | Hit | TRAIN | VALID | TEST |
| --- | ---: | ---: | ---: | ---: | ---: |
| asia → london | +0.112 | 51.7% | +0.321 | −0.420 | +0.215 |
| london → overlap | +0.256 | 50.9% |  |  |  |
| overlap → late NY | +0.288 | 50.5% |  |  |  |

MFE both sides ~7.3–8.0 pips (slightly above quiet range events). Path-order is balanced. Asia→London direction flips in VALIDATION.

**Answer:** Session transitions do **not** predict direction. They are at most a weak magnitude clock. **NO INFORMATION (direction) / WEAK magnitude.**

---

## Stage 14 — Cross-pair USD context

USD-direction return:

- EUR_USD, GBP_USD, AUD_USD: `−ret_6`
- USD_JPY, USD_CAD, USD_CHF: `+ret_6`

For each target, median / agreement / dispersion use the **other** synchronized pairs only. Incomplete alignment is left missing (no interpolation).

This context is used in Stage 15 events and in two predeclared combos. By itself it is a contemporaneous feature, not an event.

---

## Stage 15 — Cross-pair divergence events

| Event | n | 60m close | Hit | Notes |
| --- | ---: | ---: | ---: | --- |
| usd_div_extreme_pos | 28456 | +0.150 | 51.4% | EUR/CAD/CHF negative or flat |
| usd_div_extreme_neg | 28136 | −0.009 | 50.1% | near zero |

No stable catch-up, reversion, or continued-divergence story that is common to all six pairs.

Classification: **NO INFORMATION / UNSTABLE.**

---

## Stage 16 — Predeclared combinations (5 only)

| Combo | n | 60m close | Hit | TRAIN | VALID | TEST |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| range_bottom + lower reject | 2012 | +0.280 | 51.3% | +0.445 | **−0.330** | +0.602 |
| range_top + upper reject | 2367 | +0.264 | 49.1% |  |  |  |
| **range_bottom + USD-div** | 4117 | **+0.780** | 54.9% | +0.902 / 54.8% | +0.925 / 54.8% | +0.303 / 55.4% |
| breakout_up_24 + vol expand | 755 | −0.039 | 46.8% |  |  |  |
| impulse_bull + USD agree | 53433 | −0.053 | 49.2% |  |  |  |

`range_bottom_and_usd_div` is the largest close in the study. Hit rate is stable (~55%) across the three splits, but **TEST magnitude collapses** (0.30 vs 0.90) and symbols disagree (EUR 47.3% / +0.14, CAD −0.11, JPY +1.80, GBP +1.43). Still **below 1× cost** on average close (0.78 < 1.00–1.50). Path-order remains heavily two-sided (UP 1518 / DOWN 1293 / AMB 1306).

This combo was predeclared, not mined. It is **not** a license to search neighboring definitions.

Classification: **WEAK / UNSTABLE (symbols + TEST magnitude) / BELOW COST HURDLE.** Not PROMISING.

---

## Stage 17 — Event independence

Primary sample size is **event n** (first bar of a True run, reset at symbol boundaries).

| Family | Persistent / raw bars | Independent events | Approx. bars / event |
| --- | ---: | ---: | ---: |
| range bottom state | 86661 | 23734 | 3.65 |
| range top state | 87597 | 25044 | 3.50 |
| impulse (1-bar feature) | 70751 | 70751 | 1 |
| vol expand | 8285 | 8285 | 1 |
| breakout up 24 | 16292 | 16292 | 1 |

Pooled “median minutes between events” is **not** used: six symbols share timestamps, so the pooled gap is downward-biased. Independence is the transition count.

---

## Stage 18 — Dependence-aware uncertainty

Event-level bootstrap, seed **42**, 200 resamples of event outcomes (not naive bar SEs).

| Event | 60m close mean | 5–95% CI | 60m \|exc\| |
| --- | ---: | --- | ---: |
| range_bottom_enter | +0.313 | [+0.198, +0.417] | 10.81 |
| range_top_enter | −0.104 | [−0.208, −0.0002] | 10.38 |
| breakout_up_24 | −0.378 | [−0.486, −0.269] | 10.95 |
| reject_lower_24 | +0.256 | [+0.126, +0.391] | 11.33 |
| vol_expand_enter | +0.266 | [−0.005, +0.515] **includes 0** | 13.52 |

Statistical detectability ≠ economic usefulness. The tightest CIs are still inside one spread.

---

## Stage 19 — Cross-time stability

| Event | TRAIN | VALID | DISCOVERY_TEST | Monthly | Time label |
| --- | --- | --- | --- | --- | --- |
| range_bottom_enter | + | + | + | 10/12 months + | STABLE CANDIDATE (tiny) |
| range_top_enter | ~0 | − | − | mixed | UNSTABLE / weak |
| breakout_up_24 | − | − | − | mostly − | STABLE CANDIDATE (failure, tiny) |
| breakout_dn_24 | + | + | + | (symmetric) | STABLE CANDIDATE (failure, tiny) |
| impulse_bull | + | − | − |  | UNSTABLE |
| vol_expand direction | ~0 | + | ~0 | 47–53% hit | NO direction |
| session asia→london | + | − | + |  | UNSTABLE |
| range_bottom + USD-div | +0.90 | +0.93 | +0.30 |  | hit stable; **magnitude UNSTABLE** |

DISCOVERY_TEST remains exploratory.

---

## Stage 20 — Cross-symbol stability

| Event | EUR | GBP | JPY | AUD | CAD | CHF | Label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| range_bottom 60m pips | +0.12 | +0.51 | +0.49 | +0.38 | +0.30 | +0.11 | BROAD-weak (EUR hit 49.9%) |
| breakout_up_24 | −0.29 | −0.66 | −0.21 | −0.26 | −0.47 | −0.39 | **BROAD** failure |
| breakout_dn_24 | +0.44 | +0.56 | +0.30 | +0.69 | +0.04 | +0.11 | BROAD-weak (CAD flat) |
| vol_expand close | +0.31 | +1.12 | +0.15 | +0.37 | −0.15 | −0.25 | UNSTABLE direction |
| usd_div_pos | −0.11 | +0.58 | +0.43 | +0.25 | −0.15 | −0.19 | UNSTABLE |
| range_bottom + USD-div | +0.14 | +1.43 | +1.80 | +0.65 | −0.11 | +0.52 | PAIR-SPECIFIC / UNSTABLE |

Losing symbols are not hidden in the aggregates.

---

## Stage 21 — Cost-hurdle analysis

MFE-up ≥ 1× cost is **~85% of all bars** at 60m (15.3% only-up + 69.8% both). Event hurdle rates of 84–89% are therefore **not special**.

| Event | Typical 60m close | vs 1× cost | Favorable MFE vs adverse MFE | Adverse path first? |
| --- | ---: | --- | --- | --- |
| range_bottom_enter | +0.31 | no | 6.84 vs 6.75 | 36% DOWN_FIRST vs 40% UP_FIRST |
| breakout_up_24 | −0.38 | no | 6.56 vs 7.23 | yes, modestly (failure) |
| vol_expand | +0.27 (unsigned) | no | 8.45 vs 8.57 | coin flip / ambiguous |
| range_bottom + USD-div | +0.78 | no (GBP 1.5) | 7.96 vs 7.47 | still ~31% DOWN_FIRST + 32% AMB |

No event has a typical **unique** favorable path that exceeds 1×, 1.5×, 2×, or 3× cost after same-bar ambiguity is acknowledged.

---

## Stage 22 — Direction vs magnitude

| Event | Information |
| --- | --- |
| range_bottom_enter | DIRECTIONAL (tiny MR) |
| range_top_enter | DIRECTIONAL (tinier / weaker) |
| extend_* | DIRECTIONAL (tiny MR) |
| impulse_* | DIRECTIONAL (tiny reversal), UNSTABLE for bull |
| vol_expand_enter | MAGNITUDE-ONLY (weak) |
| vol_exit_compress | NEITHER (n=30) |
| breakout_* | DIRECTIONAL (failure / MR) |
| reject_* | DIRECTIONAL (tiny / unstable) |
| session transitions | MAGNITUDE-ONLY (weak clock) or NEITHER |
| usd_div_* | NEITHER |
| range_bottom + USD-div | DIRECTIONAL (largest close; unstable) |
| other combos | NEITHER / WEAK |

A future “opportunity detector + direction model” is **architecturally plausible** but **not supported** by these events: the opportunity class at 1× cost is almost all bars, and no event isolates a one-sided large path.

---

## Stage 23 — Event-family classification

A PROMISING label required: reasonable n, VALIDATION support, DISCOVERY_TEST descriptive support, multi-symbol support, and effect size relevant to cost.

| Family | Class |
| --- | --- |
| range_bottom_enter | WEAK / BELOW COST HURDLE |
| range_top_enter | WEAK / BELOW COST HURDLE |
| extension enter | WEAK / BELOW COST HURDLE |
| impulse enter | WEAK / BELOW COST HURDLE |
| vol_expand_enter | WEAK (magnitude) / NO INFORMATION (direction) |
| vol_exit_compress | INSUFFICIENT SAMPLE |
| breakout 12/24/48 | WEAK directional (failure) / BELOW COST HURDLE |
| rejection 24 | WEAK / UNSTABLE |
| session transitions | NO INFORMATION (direction) / WEAK magnitude |
| USD divergence | NO INFORMATION / UNSTABLE |
| range_bottom + USD-div | WEAK / UNSTABLE / BELOW COST HURDLE |
| other combos | WEAK / UNSTABLE / NO INFORMATION |

**No family is PROMISING DIRECTIONAL or PROMISING MAGNITUDE.**

---

## Stage 24 — Target-design recommendation (research only)

| Option | Recommendation |
| --- | --- |
| A. binary UP/DOWN every bar | Reject. Two-sided 60m noise already exceeds cost. Prior L2 probe was ~51.3% vs 51.1% always-UP. |
| B. three-way UP/DOWN/NO-TRADE | Conceptually right, **not supported** at 1× cost (NO-TRADE ≈ 0.06%). At 3×/60m, neither is only 8% and 29% of bars still move 3 pips both ways. |
| C. opportunity/magnitude then direction | Architecturally attractive. Vol-expand is only a weak magnitude cue. **Do not train this.** |
| D. path-order classifier | Same-bar ambiguity is 22.5%. Remaining UP_FIRST vs DOWN_FIRST tilts are a few percentage points. Insufficient. |
| E. mean-reversion event classifier | The only recurring directional motif (range / extension / breakout-failure). Effect << spread. **Do not train.** |
| F. continuation event classifier | Breakouts and impulses do **not** continue. Reject. |
| **G. no current target is sufficiently supported** | **SELECT.** |

This is not a production change.

---

## Stage 25 — Future data / holdout plan

**2025-09-01 through 2026-08-31 UTC is DEVELOPMENT / DISCOVERY data.** It has been used for:

- 12-month QUANT/OFFLINE baseline
- baseline diagnosis
- stub forensics and component study
- feature/target discovery
- this event/opportunity study

Do **not** call TRAIN, VALIDATION, or DISCOVERY_TEST from this year “pristine final OOS” in any future model claim.

Proposed later protocol (do **not** download in this task):

1. Keep the current year as a frozen development archive. Never overwrite `data/historical/*_M5.csv`.
2. Accumulate **new later MID M5** (from 2026-09-01 UTC onward) with the existing read-only downloader into a **separate dated directory** (for example `data/historical/holdout_YYYYMM/`).
3. Research on development may use walk-forward / rolling validation **inside** the development year only, labeled as such.
4. A future trained candidate, if one is ever justified, must be accepted only on **later unseen** data after a freeze date, plus walk-forward on development.
5. Do not use live production, Docker, or broker writes to harvest holdout data.
6. Do not inspect the future holdout to retune events.

---

## Stage 26 — Synthesis

1. **Independent events with directional information?** Yes, weak: range-bottom entry and breakout **failure**. Detectable by event-bootstrap; not economic.
2. **Events that predict magnitude?** Vol-expand slightly raises two-sided excursion (13.5 vs ~10.8 pips). Session opens are a mild clock. Not promising.
3. **Does range-extreme MR survive event-level analysis?** Yes for bottom-enter (CI excludes 0; VALIDATION and DISCOVERY_TEST agree in sign).
4. **Does it clear spread?** No. ~0.3 pip close vs ~1.0–1.5 pip half-spread. MFE-up ≈ MFE-down.
5. **Do breakouts continue or fail?** Fail / revert. Broad across six pairs and three lookbacks. Still ~0.4 pips.
6. **Do large impulses continue or revert?** Slightly revert. Bullish side is time-unstable.
7. **Do vol transitions predict magnitude?** Mildly, two-sided. Not direction. Compression-exit n=30.
8. **Does cross-pair USD context add information?** Not as a standalone directional event. One predeclared combo looks larger then fails symbol and TEST-magnitude checks.
9. **Does cross-pair divergence add information?** No stable six-pair effect.
10. **Are session transitions informative?** Not for direction.
11. **Stable across time?** Only the tiny MR / breakout-failure signs. Magnitudes move. Combo magnitude is not stable.
12. **Stable across symbols?** Breakout-up failure is the most uniform. Range-bottom is broad-weak. USD and vol direction are not.
13. **Economically meaningful margin above cost?** **No.**
14. **Should the future model predict every bar?** **No.** Most bars are two-sided noise above cost.
15. **Should NO-TRADE be first-class?** Conceptually yes; **not with a 1×-cost “neither” label** (empty class). No event yet defines a useful no-trade set.
16. **Enough evidence to proceed to model training?** **No.**

### Verdict

**NO ECONOMICALLY USEFUL EVENT FOUND**

Not “proceed to event-based model design.” Not “promising magnitude model only.” Further feature families or later-period data could be researched later; **this predeclared set does not justify training.**

---

## What was not done (required stop)

- No replacement quant model
- No change to `_quant_stub_vote`, BUY/SELL, SL/TP, ATR, sessions, risk, RL, API voters, execution, reconciliation
- No live filters, no no-trade logic in production
- No historical CSV modification, no download, no Docker/live restart, no broker writes
- No old trade-engine run, no threshold grid, no parameter optimization

---

## Tests

`python -m pytest -q --tb=line`

**357 passed, 0 failed, 0 skipped, 26.25s**

New focused tests in `tests/test_quant_event_discovery.py` cover: event transition detection, grouped symbol reset, rolling range excludes current bar, future-path alignment, MFE-up/down, path-order labels, same-bar AMBIGUOUS, cost hurdles, USD orientation, other-pairs-only context, chronological alignment, no lookahead, event independence, and fixed-seed bootstrap reproducibility.

---

Wait for human review.
