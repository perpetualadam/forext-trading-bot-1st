# Quant V2 Experiment A — historical spread and volume

**Status:** COMPLETE — research only. No model, no filters, no download, no production change.

**Authorized data:** existing six M5 CSVs (MID + BID + ASK + OANDA candle volume).  
**Period:** 2025-09-01 through 2026-08-31 UTC = **DEVELOPMENT / DISCOVERY**. Not a pristine holdout.

**V1 parent:** NO ECONOMICALLY USEFUL EVENT FOUND. This experiment tests information V1 did not use.

---

## Experiment A verdict

# A_USEFUL_CONTEXT_BUT_BELOW_G3

Contemporaneous bid/ask half-spread and OANDA activity are **real unused fields**. They change how we should talk about **cost** and **magnitude ranking**. They do **not** pass Quant V2 gate **G3** (unique favorable movement ≥ 1× contemporaneous half-spread).

- Historical half-spread is typically **below** V1’s constant 1.0 / 1.5 pip model (GBP especially).
- Higher activity **ranks** larger two-sided future excursion. That ranking is chronological and six-pair.
- Low spread improves movement/cost **ratios** mostly because the denominator is smaller, and it makes 60m **BOTH-sided** hurdles *more* common.
- No directional information.
- Frozen V1 range-bottom (~+0.31 pip) and breakout-failure (~0.37 pip) remain **below actual** median half-spread (~0.80 pip).
- Using actual cost **raises** the 60m BOTH rate from ~70% (modeled) to **~75%**. V1’s “UP/DOWN/NO-TRADE is poorly formed” conclusion is stronger, not weaker.

**This does not authorize training or live filters.**

---

## Cost semantics (frozen before later tables)

| Term | Definition | Units |
| --- | --- | --- |
| Full close spread | `ask_close − bid_close` on the **same completed bar** | price, then pips |
| Full open spread | `ask_open − bid_open` | same |
| Contemporaneous **entry cost** | **half** close spread = full / 2 | price / pips |
| V1 modeled entry cost | `simulated_half_spread` / `pip_size` | 1.0 pip; **1.5 GBP** |
| JPY pip | 0.01 | — |

**Not used:** `ask_low − bid_high`. Those extrema need not be simultaneous. Bid/ask OHLC do **not** reconstruct the tick spread path.

V1 compared future **pips** to a **half-spread** hurdle. This study does the same with historical half-spread so the comparison is like-for-like.

---

## Stage 1 — Input identity

Six approved files. MID/BID/ASK/volume/complete all present. 0 duplicates. Monotonic. Gaps classified, not repaired. Matches V1 DEV0 row counts and date range.

| Symbol | Rows | First UTC | Last UTC |
| --- | ---: | --- | --- |
| EUR_USD | 74572 | 2025-09-01 00:00 | 2026-08-31 23:50 |
| GBP_USD | 74555 | 2025-09-01 00:00 | 2026-08-31 23:50 |
| USD_JPY | 74557 | 2025-09-01 00:00 | 2026-08-31 23:50 |
| AUD_USD | 74563 | 2025-09-01 00:00 | 2026-08-31 23:50 |
| USD_CAD | 74560 | 2025-09-01 00:00 | 2026-08-31 23:50 |
| USD_CHF | 74514 | 2025-09-01 00:00 | 2026-08-31 23:50 |

Research rows here: **447321** (full CSVs; V1 feature cache dropped warmup to 447027). Source CSVs were not modified.

---

## Stages 3–4 — Historical vs modeled cost

**Impossible values:** missing 0, zero 0, negative 0. Nothing was silently cleaned.

Half-spread (pips), contemporaneous entry-cost analogue:

| Symbol | Mean | Median | p10 | p90 | p99 | Max | V1 modeled | Median − modeled |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EUR_USD | 0.86 | 0.80 | 0.75 | 0.90 | 2.65 | 5.0 | 1.00 | **−0.20** |
| GBP_USD | 1.14 | 0.95 | 0.85 | 1.10 | 6.35 | 10.0 | 1.50 | **−0.55** |
| USD_JPY | 0.92 | 0.80 | 0.70 | 1.00 | 4.75 | 5.0 | 1.00 | **−0.20** |
| AUD_USD | 0.73 | 0.65 | 0.60 | 0.75 | 2.95 | 7.5 | 1.00 | **−0.35** |
| USD_CAD | 1.04 | 0.90 | 0.85 | 1.05 | 4.80 | 7.5 | 1.00 | −0.10 |
| USD_CHF | 0.91 | 0.75 | 0.65 | 0.85 | 6.10 | 7.5 | 1.00 | **−0.25** |

Splits: TRAIN median 0.80; VALID 0.85; DISCOVERY_TEST 0.80. Monthly medians 0.80–0.85. Fat right tail (p99 often 3–6 pips) is the stress/news component.

**VERIFIED:** V1’s constant cost was **conservative on typical bars**, especially GBP. It was **optimistic on the p99 tail**.

---

## Stage 5 — Volume semantics

Local evidence: the field is OANDA InstrumentsCandles `volume`, persisted on the CSV, ignored by production `csv_ohlcv`. **Not** centralized FX volume. Treated as **feed activity**.

No zeros/missing. Medians differ by pair (CHF 184, JPY 673, GBP 634). Session structure is strong — hence TRAIN session-relative normalization.

---

## Stages 6–7 — Frozen TRAIN buckets

Persisted in `quant_v2_experiment_a_data.json` **before** VALIDATION/DISCOVERY_TEST tables.

| Measure | Construction | TRAIN q1 / q5 edges |
| --- | --- | --- |
| `half_close_spread_pips` | contemporaneous half close spread | 0.70 / 0.95 |
| `spread_atr` | half price spread / ATR14 | 0.164 / 0.435 |
| `volume` | raw activity | 163 / 737 |
| `vol_sess_rel` | volume / TRAIN median volume for that **symbol×session** | 0.643 / 1.561 |
| `spread_vs_lag24` | half-spread / median of **previous** 24 bars | 0.919 / 1.071 |
| `vol_vs_lag24` | volume / median of previous 24 | 0.673 / 1.472 |

LOW = q1, HIGH = q5. Not retuned.

---

## Stage 8 — Spread as tradeability

60m future mid path by frozen half-spread quintile (no side assigned):

| Bucket | n | Median cost | Mean \|exc\| | \|exc\| / cost | MFE-up | MFE-down | Close pips |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| q1 low | 72474 | 0.65 | 9.01 | **14.1** | 5.57 | 5.76 | +0.02 |
| q3 | 74974 | 0.80 | 11.13 | 13.7 | 6.91 | 7.13 | +0.10 |
| q5 high | 109204 | 1.00 | 10.76 | **9.8** | 6.75 | 6.82 | +0.04 |

Low-spread states have a **higher movement-to-cost ratio**. Absolute future excursion is **not larger** (9.0 vs 10.8). MFE-up ≈ MFE-down in every bucket. Close is ~50%.

**Mechanical part:** dividing by a smaller cost raises the ratio even if the path is unchanged.  
**Non-mechanical part:** low-spread bars have slightly *smaller* abs paths, so they are quieter, not “cheap + explosive.”

---

## Stage 9 — Activity as magnitude

Session-relative volume (TRAIN session medians):

| Bucket | n | 60m \|exc\| | TRAIN | VALID | DISCOVERY_TEST | Close |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| q1 low | 97384 | **7.68** | 7.90 | 8.07 | 7.11 | +0.11 |
| q5 high | 95455 | **13.38** | 13.58 | 13.93 | 11.78 | −0.00 |

Raw volume is more monotonic: q1 **6.08** → q5 **17.28** pips abs excursion. All six pairs show large q5 abs excursion (EUR 15.5 … JPY 19.5).

Direction stays ~50%. Raw-volume q5 close +0.20 pips fails DISCOVERY_TEST (−0.07).

**Classification:** **MAGNITUDE INFORMATION**, BROAD, chronological. Not directional.

---

## Stages 10–11 — Direction

Spread quintile closes: +0.02 to +0.10 pips, hit ~50%. **NO INFORMATION / UNSTABLE** as direction.

Activity expand vs contract: closes ~0, hits ~50%. **NO INFORMATION** as direction.

---

## Stages 12–13 — Transition events

Event n (not persistent bars). Spread q5 state = 109,204 bars; enter-high events = 34,290.

| Event | n | 60m close | \|exc\| | Direction |
| --- | ---: | ---: | ---: | --- |
| spread enter high | 34290 | +0.04 | 12.1 | none; TEST close −0.05 |
| spread expand | 46500 | +0.05 | 11.1 | none |
| vol enter high | 30936 | −0.02 | 11.2 | none |
| vol expand | 34244 | +0.03 | 11.1 | none |
| vol contract | 39722 | +0.06 | 8.4 | none (smaller paths) |

Transitions confirm **level** stories: high/expanding activity → larger two-sided paths; contraction → smaller. No unique side.

---

## Stage 14 — Predeclared 2×2 (LOW=q1, HIGH=q5)

| Cell | n | Median cost | 60m \|exc\| | \|exc\|/cost | Close | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| LOW spread + LOW activity | 14806 | 0.65 | 6.72 | 10.5 | −0.08 | quiet + cheap |
| LOW spread + HIGH activity | 16619 | 0.65 | **12.07** | **18.9** | +0.06 | TRAIN/VALID magnitude yes; TEST close **−0.50** |
| HIGH spread + LOW activity | 26598 | 1.05 | 7.87 | 6.0 | +0.23 | expensive + quiet |
| HIGH spread + HIGH activity | 26388 | 1.00 | 13.83 | 12.6 | −0.11 | large two-sided, costly |

LOW+HIGH looks like “cheap + large path” **in aggregate**, but:

- GBP n=0, CAD n=0 (pooled spread q1 almost never includes those wider pairs)
- AUD supplies 12,401 of 16,619 rows
- MFE-up 7.49 ≈ MFE-down 7.70
- Bootstrap close CI **includes 0** [−0.09, +0.21]

**PAIR-SPECIFIC / not a production state.** Magnitude lift is real where the cell exists; it is not a six-pair tradeable regime.

---

## Stages 15–17 — Frozen V1 events vs actual cost

Definitions unchanged (`pos_in_range_24` q1/q5 edges; 24-bar prior high/low excluding current; TRAIN impulse/vol-expand edges from V1).

| Frozen event | n | 60m close | Median actual half-spread | Close / cost | MFE-up vs MFE-down |
| --- | ---: | ---: | ---: | ---: | --- |
| range-bottom enter | 23743 | **+0.312** | 0.80 | **0.29** | 6.84 vs 6.75 |
| range-top enter | 25054 | −0.104 | 0.80 | −0.05 | 6.40 vs 6.71 |
| breakout up 24 | 16301 | **−0.375** | 0.80 | −0.41 | 6.56 vs 7.22 |
| breakout down 24 | 15155 | +0.358 | 0.80 | 0.37 | 7.45 vs 7.35 |
| impulse bull / bear | ~70k | −0.05 / +0.17 | 0.80 | ~0 | two-sided |
| V1 vol-expand | 8285 | +0.27 | 0.80 | 0.25 | 8.45 vs 8.57 |

Range-bottom bootstrap close CI [0.21, 0.43]; close/cost CI [0.17, 0.43] — **entirely below 1.0**.  
Breakout-up close CI [−0.51, −0.27] — fade exists, still below 1× cost.

**V1 did not reject these because modeled cost was too high.** Actual typical cost is *lower* (~0.80 vs 1.08 mean modeled) and the effects still fail G3. GBP’s modeled 1.5 was the most overstated; even against GBP’s actual ~0.95 median, +0.50 pip range-bottom on GBP is still below 1×.

---

## Stage 18 — Two-sided path with contemporaneous cost

60m MFE vs **this bar’s** half-spread:

| Hurdle | BOTH | UP only | DOWN only | NEITHER |
| --- | ---: | ---: | ---: | ---: |
| V1 modeled 1.0 / 1.5 | 69.8% | 15.3% | 14.8% | 0.05% |
| **Actual half-spread** | **75.2%** | 12.2% | 11.7% | **0.82%** |

Low-spread q1 BOTH **79.4%**. High-spread q5 BOTH 65.5%, NEITHER 3.4%.

Same-bar path-order AMBIGUOUS vs actual half-spread: **~30%** (higher than V1’s 22.5% at the larger modeled hurdle).

**Actual cost does not rescue a three-way UP/DOWN/NO-TRADE label.** Typical bars are even *more* two-sided once the hurdle shrinks to the real ~0.8 pip half-spread.

---

## Stages 19–22 — Independence, uncertainty, stability

- Persistent high-spread bars 109,204 vs 34,290 enter events.
- Bootstrap seed 42, 200 event/level resamples (overlapping bars still in level buckets — event tables are primary for transitions).
- Activity magnitude ranking: TRAIN, VALID, DISCOVERY_TEST all show q5 \|exc\| > q1. Six symbols agree on **larger abs path**, not on sign.
- DISCOVERY_TEST is exploratory development data.

---

## Stage 23 — Information classification

| Object | Class |
| --- | --- |
| Spread level | **TRADEABILITY / COST** + **REDUNDANT/TRIVIAL** ratio effect; **NO** direction. Low spread → *more* BOTH |
| Spread change / transitions | **NO INFORMATION** (direction); weak magnitude |
| Raw / session-relative activity | **MAGNITUDE INFORMATION** (BROAD). **NO** direction |
| Activity transitions | Same as level, weaker |
| Spread × activity 2×2 | Magnitude in LOW+HIGH; **PAIR-SPECIFIC** (AUD-heavy; GBP/CAD empty) |
| V1 events × actual cost | Unchanged **WEAK / BELOW COST** |

“Low spread has lower cost” is mechanical. The predictive question — does low cost coincide with a **unique** favorable future path? — **No.**

---

## Stage 24 — Gate G3

| Claim | Economic class |
| --- | --- |
| Activity ranks \|excursion\| | Context. q1 still ~7–8 pips two-sided vs ~0.8 cost — not a no-trade desert |
| Low spread / cost ratio | **AROUND/ABOVE** as a *ratio*, **not unique**. Adverse MFE ≈ favorable |
| Range-bottom +0.31 vs 0.80 | **BELOW COST** |
| Breakout fade 0.37 vs 0.80 | **BELOW COST** |
| Any signed close | **BELOW COST** |

**No finding passes G3.** A +0.2–0.3 pip close is not promising against ~0.8 pip actual half-spread.

---

## Stage 25 — Answers

1. **Historical spread?** Typical half-spread 0.65–0.95 pips; fat tails to 5–10. No invalid prints in this cache.
2. **Vs V1 model?** V1 was conservative on the median (GBP 1.50 vs 0.95). Optimistic on p99 tails.
3. **Spread beyond being the cost?** Little. Ratios move with the denominator. Paths stay two-sided.
4. **Activity → magnitude?** **Yes**, monotonically, validated, six pairs.
5. **Activity → direction?** **No.**
6. **Spread transitions → movement?** Weak / none unique.
7. **Activity transitions → movement?** Yes as magnitude, same as level.
8. **LOW spread + HIGH activity unusually tradeable?** Larger two-sided path at lower cost **in AUD-heavy rows**. Not six-pair. Direction fails TEST.
9. **VALIDATION?** Magnitude yes; direction no.
10. **Symbols?** Magnitude BROAD. 2×2 PAIR-SPECIFIC.
11. **Range-bottom vs actual cost?** **No.** +0.31 / 0.80.
12. **Breakout failure vs actual cost?** **No.** ~0.37 / 0.80.
13. **Two-sided conclusion changes?** **No — it strengthens** (BOTH 75%).
14. **Any G3 pass?** **No.**

---

## Stage 26 — Experiment B

**NOT JUSTIFIED BY A BUT STILL INDEPENDENTLY JUSTIFIED BY V2 PLAN**

A did not produce a G3-passing spread/volume edge, so B is not “the next step because A passed.” B is a **different** information class (cross-pair residual / dispersion), already specified in the V2 plan, and is not blocked by A.

**Do not run B in this task.**

---

## What was not done

No Experiment B, no M1 download, no training, no production/stub/filter/SL/TP/RL changes, no Docker/bot restart, no CSV writes.

---

## Tests

`python -m pytest -q --tb=line`

**367 passed, 0 failed, 0 skipped, 27.33s**

New tests in `tests/test_quant_v2_experiment_a.py`: full vs half-spread, JPY pips, negative spreads not cleaned, TRAIN-only frozen buckets, lagged volume baseline, event transitions, cost-normalized movement, two-sided contemporaneous labels, no lookahead across symbols, source CSV immutability.

---

Wait for human review.
