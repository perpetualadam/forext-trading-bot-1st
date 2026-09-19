# Quant V2 Experiment B — cross-pair factor / residual / dispersion

**Status:** COMPLETE — research only. No model, no residual/factor/lead-lag filters, no download, no production change.

**Authorized data:** existing six M5 CSVs only. MID for returns. Experiment A bid/ask half-spread for the economic hurdle only. OANDA activity is descriptive context using **frozen** Experiment A session-relative quintiles.

**Period:** 2025-09-01 through 2026-08-31 UTC = **DEVELOPMENT / DISCOVERY**. Not a pristine holdout.

**Parents:** V1 frozen **NO ECONOMICALLY USEFUL EVENT FOUND**. Experiment A **A_USEFUL_CONTEXT_BUT_BELOW_G3**. Experiment A did **not** unlock this study. B is independently justified by the frozen V2 plan as a different information class.

**Safety:** production, `_quant_stub_vote`, BUY/SELL, SL/TP, ATR, risk, sessions, RL, API voters, execution, reconciliation, historical CSVs, Docker, and the live bot were not changed. No OANDA or external API calls. No M1 download. No model training.

Progress: `reports/decision_quality/quant_v2_experiment_b_progress.json`  
Machine tables: `reports/decision_quality/quant_v2_experiment_b_data.json`  
Primitives: `forex_bot/decision_quality/cross_pair.py`

---

## Experiment B verdict

# B_USEFUL_CONTEXT_BUT_BELOW_G3

The six pairs share one contemporaneous USD factor. That factor is **not new** relative to V1 simple USD context. Residualization against a TRAIN-fit PCA-1 component is almost the same as V1 leave-one-out divergence. A **tiny** residual-reversal shift is statistically detectable and chronologically same-signed, but it is **~0.18 pip** at 60 minutes against a contemporaneous half-spread of **~0.80 pip**. Continuation and common-factor catch-up do not work. Predeclared 1/2/3-bar lags and extreme relative ranks do not contain usable direction.

**What is useful context:** cross-sectional USD dispersion ranks subsequent **movement magnitude** (low ~4.6 pips vs high ~9.2 pips at 60m) and then **mean-reverts** as a statistic. That is a risk/opportunity-size fact, not a unique directional path.

**Nothing here passes G3.** This does not authorize training or live pair-relative filters.

---

## Signed metrics (declared before results)

All directional tests use **USD-oriented** space unless labeled instrument.

| Hypothesis | Signed 60m metric | Instrument side |
| --- | --- | --- |
| **A. TARGET REVERSAL** | `-sign(residual_usd) × future_usd` | Fade idiosyncratic USD residual (`reversal_instrument_side`) |
| **B. TARGET CONTINUATION** | `+sign(residual_usd) × future_usd` | Opposite of A |
| **C. COMMON-FACTOR CATCH-UP** | `+sign(factor) × future_usd` | Trade the target in the common-USD direction |

**G3** requires a **unique** favorable directional close (or unique first path) that is economically relevant versus the **same-bar** historical half-spread from Experiment A. Two-sided MFE is not a directional edge.

Cost: `half_close_spread = (ask_close − bid_close) / 2`, converted with `pip_size` (JPY 0.01, others 0.0001). Same semantics as Experiment A.

---

## Orientation (never mixed silently)

| Representation | Positive means |
| --- | --- |
| **INSTRUMENT RETURN** | Quoted instrument price rises |
| **USD-ORIENTED RETURN** | USD strengthens |

| Symbol | Price UP means | USD-oriented transform |
| --- | --- | --- |
| EUR_USD, GBP_USD, AUD_USD | USD weaker | `usd = −instrument` |
| USD_JPY, USD_CAD, USD_CHF | USD stronger | `usd = +instrument` |

Tests cover all six symbols. Factor, residual, rank, dispersion, and lag features are **USD-oriented**. Economic pips and MFE/MAE use the mapped instrument side.

---

## Stage 1 — Synchronized panel

**Alignment policy:** inner join on bar-start timestamp. **No price forward-fill.** A timestamp is retained only if **all six** symbols have a completed candle. Partial rows are dropped, not imputed.

| Symbol | Source rows | SHA-256 prefix |
| --- | ---: | --- |
| EUR_USD | 74572 | `3ae3c4d061792353` |
| GBP_USD | 74555 | `ac3ddba51b75f493` |
| USD_JPY | 74557 | `e1b0d3491f873723` |
| AUD_USD | 74563 | `e639a1f817e4b919` |
| USD_CAD | 74560 | `a88eb2c440691bd5` |
| USD_CHF | 74514 | `3901a2d50a63ef5c` |

| Panel | Count |
| --- | ---: |
| Union timestamps | 74575 |
| Fully synchronized (inner join) | **74454** |
| Missing on at least one symbol | **121** |
| Long panel (6 × sync, including warmup NaNs) | 446724 |
| Finite PCA residuals | 446688 |

**Missing-symbol composition (121 stamps):** USD_CHF only 55; GBP 17; JPY 15; CAD 12; AUD 11; EUR 3; two-symbol combinations 8. These are feed holes, not filled.

**Gap behavior (EUR_USD as representative, already classified in V1):** 74498 adjacent 5-minute steps; 34 expected weekend gaps; 39 unexpected (mostly ~10-minute holes plus a few long gaps). Gaps are classified, not repaired. Weekend absence is expected; it is not treated as a residual event.

Source CSVs were not modified.

**VERIFIED DESCRIPTIVE RESULT.**

---

## Stage 2 — Return definitions

Predeclared causal backward-looking returns only:

| Bars | Horizon | Columns |
| ---: | --- | --- |
| 1 | 5m | `instr_ret_1`, `usd_ret_1`, ATR-normalized USD |
| 3 | 15m | same |
| 6 | 30m | **primary factor / residual window** |
| 12 | 60m | same |

No additional lookbacks. `pct_change(b)` uses only past closes. ATR-14 is the existing causal true-range mean; ATR-normalized returns are descriptive, not a second optimized family.

Primary common-factor input: **USD-oriented 30-minute return (`usd_ret_6`)** on the synchronized panel.

---

## Stage 3 — Simple common USD factor (reference)

**Definition:** for target *S*, `factor_loo_S = median(usd_ret_6 of the other five pairs)`. Target excluded.

This is the V1-12 / V1-13 reference. **Not claimed novel.**

---

## Stage 4 — TRAIN-fit common factor (one component)

**Method:** PCA first component of the 6-column TRAIN synchronized `usd_ret_6` matrix. Deterministic SVD. TRAIN means and loadings **frozen**. Applied unchanged to VALIDATION and DISCOVERY_TEST. **Not** refit later. One component only.

**Sign convention:** if TRAIN scores correlate negatively with the cross-sectional mean, loadings are flipped so **positive factor = USD strengthening**.

**Scaling:** raw (not unit-variance columns). Scores are `(X − μ_TRAIN) · w`.

TRAIN synchronized rows: **37239**.

| Symbol | PCA-1 weight | TRAIN OLS beta on the factor |
| --- | ---: | ---: |
| EUR_USD | 0.383 | 0.383 |
| GBP_USD | 0.420 | 0.420 |
| USD_JPY | 0.420 | 0.420 |
| AUD_USD | 0.505 | 0.505 |
| USD_CAD | 0.244 | 0.244 |
| USD_CHF | 0.431 | 0.431 |

Betas equal weights because the factor **is** the first PC: OLS of each column on that score recovers the loading. Fitting did not discover a second structure.

| Comparison | Correlation |
| --- | ---: |
| PCA-1 vs cross-sectional median | **0.977** |
| PCA-1 vs EUR leave-one-out median | 0.964 |

**VERIFIED:** the “formal” factor is the same one-factor USD object V1 already used, with CAD under-weight and AUD over-weight. That is pair structure, not a new signal.

---

## Stage 5 — Residual definition

Units: **USD-oriented 30-minute return** (dimensionless price return, not pips).

| Residual | Formula |
| --- | --- |
| `resid_pca6` | `usd_ret_6 − β_TRAIN(S) × PCA1` |
| `resid_loo6` | `usd_ret_6 − LOO_median` (V1-like divergence) |

Betas frozen after TRAIN. No full-sample standardization.

Correlation `resid_pca6` vs `resid_loo6`: **0.920**. Residualization against PCA is mostly a rename of V1 divergence.

---

## Stage 6 — Residual distributions

PCA residual, USD-oriented `ret_6` units.

| Slice | n | Mean | Std | p01 | Median | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 446688 | ≈0 | 0.000352 | −0.00093 | ≈0 | 0.00095 |
| TRAIN | 223398 | ≈0 | 0.000373 | −0.00101 | ≈0 | 0.00102 |
| VALIDATION | 111630 | ≈0 | 0.000352 | −0.00092 | ≈0 | 0.00096 |
| DISCOVERY_TEST | 111660 | ≈0 | 0.000306 | −0.00074 | ≈0 | 0.00076 |

Per symbol std: EUR 0.000218 (tightest) · CAD 0.000278 · GBP 0.000287 · CHF 0.000330 · AUD 0.000436 · **JPY 0.000487 (widest)**. JPY/AUD contribute more residual events because they move more versus the common factor, not because they have a special rule.

Monthly residual std stays in a band ~0.00027–0.00043. Means remain ~0. No month is a hidden regime that would justify silent full-sample scaling.

LOO residual is slightly wider (std 0.000437) — expected, because the median is a rougher common-factor estimate.

**VERIFIED DESCRIPTIVE RESULT.** Structural pair differences exist (JPY/AUD noisier; EUR tighter). Splits are stable in location; DISCOVERY_TEST is a quieter year-end slice, as in Experiment A.

---

## Stage 7 — Residual event definitions

TRAIN-only quintile edges of `resid_pca6`, then frozen:

`[−0.00734, −0.000216, −5.82e-5, 5.90e-5, 0.000216, 0.00959]`

Primary events are **transitions into** extreme bins, not every bar that remains extreme.

| Count | n |
| --- | ---: |
| ENTER q5 (extreme +USD residual) | 26459 |
| ENTER q1 (extreme −USD residual) | 26418 |
| ENTER either | **52877** |
| Persistent q5 state bars | 81299 |
| Persistent q1 state bars | 81365 |

TRAIN / VALID / DISCOVERY_TEST event split: 28426 / 13312 / 11139.

Per-symbol enter-either: EUR 6377, GBP 7999, CAD 7846, CHF 9122, JPY 10748, AUD 10785.

Median spacing between enter-extreme events is about **6–7 M5 bars (~30–35 minutes)** per pair (p10 ≈ 2 bars, p90 ≈ 14–25). Events are dense and overlapping. Event n, not row n, is the uncertainty unit.

**VERIFIED DESCRIPTIVE RESULT.**

---

## Stage 8 — Catch-up vs reversal vs continuation

Event n = 52877 enter-extreme residual events unless noted.

### A. Target reversal

| Horizon | n | Mean signed USD | Hit | Signed instrument pips | MFE hyp | MAE | Close / cost | Frac close ≥1× |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 15m | 52877 | +1.42e-5 | 0.512 | +0.15 | 3.76 | 3.56 | 0.12 | 0.410 |
| 30m | 52877 | +1.52e-5 | 0.513 | +0.16 | 5.33 | 5.10 | 0.13 | 0.432 |
| 60m | 52875 | +1.65e-5 | 0.510 | **+0.18** | 7.54 | 7.26 | **0.12** | 0.451 |
| 120m | 52875 | +2.28e-5 | 0.509 | +0.24 | 10.59 | 10.28 | 0.19 | 0.468 |
| 240m | 52869 | +2.79e-5 | 0.507 | +0.31 | 14.95 | 14.52 | 0.27 | 0.478 |
| 480m | 52855 | +2.97e-5 | 0.503 | +0.38 | 21.10 | 20.51 | 0.34 | 0.483 |

60m by split (signed USD / hit / instrument pips): TRAIN +1.67e-5 / 0.511 / +0.12 · VALID +2.26e-5 / 0.510 / +0.16 · DISCOVERY_TEST +8.9e-6 / 0.506 / +0.09.

Positive and negative residual entries separately have the same tiny same-signed reversal (pos 60m +0.13 pip, neg +0.23 pip). Hit rates sit at 50–52%.

MFE and MAE are almost equal at every horizon. The path is **two-sided**.

### B. Target continuation

Exact opposite of A (signed USD −1.65e-5, hit 0.483 at 60m). **No continuation edge.**

### C. Common-factor catch-up

| Horizon | Mean signed USD | Hit | Signed instrument pips | Close / cost |
| ---: | ---: | ---: | ---: | ---: |
| 15m | −3.5e-6 | 0.485 | −0.04 | −0.04 |
| 60m | −1.2e-5 | 0.487 | −0.15 | −0.14 |
| 240m | −3.4e-5 | 0.489 | −0.37 | −0.40 |

Catch-up is slightly **wrong-way** and stable in that direction across VALID and DISCOVERY_TEST. After an idiosyncratic residual, the target does **not** subsequently follow the common factor.

**STABLE CANDIDATE (statistical only):** residual reversal, same sign in all three splits, hit barely above 50%.  
**BELOW COST HURDLE.**  
**NO INFORMATION** for continuation and catch-up as trading hypotheses.

---

## Stage 9 — Economic cost

Contemporaneous historical half-spread (Experiment A). Typical median ~0.65–0.95 pip; study-wide reference **~0.80**.

60m ENTER-extreme residual events:

| Hypothesis | Close / cost | MFE / cost | Frac close ≥1× | ≥1.5× | ≥2× | Frac MFE ≥1× |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reversal | **0.12** | 8.98 | 0.451 | 0.424 | 0.400 | 0.896 |
| Continuation | −0.12 | 8.79 | 0.433 | 0.408 | 0.386 | 0.869 |
| Catch-up | −0.14 | 8.76 | 0.434 | 0.409 | 0.386 | 0.874 |

MFE / cost ≈ 9 is the usual two-sided 60-minute range (already documented in V1). It is **not** unique favorable movement. Unique close is **0.12× cost**. Fraction of unique closes clearing 1× cost is **below half**.

LOO residual events (V1-like) are the same story: close / cost **0.03**, unique 1× fraction 0.449.

**VERIFIED: no unique favorable path clears contemporaneous cost.**

---

## Stage 10 — Cross-sectional dispersion

**Primary measure:** cross-sectional standard deviation of synchronized `usd_ret_6` (USD-oriented). Also computed IQR; std is the reported classifier.

TRAIN-only std quintile edges, frozen:

`[1.65e-5, 1.57e-4, 2.24e-4, 3.02e-4, 4.24e-4, 4.64e-3]`

LOW = q1, NORMAL = q2–q4, HIGH = q5.

| State | Sync times | 60m mean \|instrument pips\| | 240m mean \|pips\| |
| --- | ---: | ---: | ---: |
| LOW (q1) | 18541 | **4.58** | 10.25 |
| HIGH (q5) | 12487 | **9.23** | 16.66 |

60m |pips| by split:

| State | TRAIN | VALID | DISCOVERY_TEST |
| --- | ---: | ---: | ---: |
| LOW | 4.89 | 4.79 | 4.09 |
| HIGH | 8.97 | 10.06 | 8.72 |

Every symbol is larger in HIGH than LOW (EUR 8.46 vs 4.09; GBP 11.18 vs 5.31; JPY 13.32 vs 6.76; AUD 7.67 vs 3.85; CAD 7.72 vs 3.97; CHF 7.05 vs 3.52).

**Future dispersion (convergence of the statistic):**

| Now bin | Mean disp now | Mean disp +60m | Mean disp +240m |
| --- | ---: | ---: | ---: |
| LOW q1 | 0.000112 | 0.000219 | 0.000254 |
| HIGH q5 | 0.000646 | 0.000408 | 0.000336 |

HIGH dispersion **compresses** toward the center; LOW **expands**. That is ordinary mean-reversion of a positive cross-sectional scale, not a unique pair-convergence trade.

**STABLE CANDIDATE** for **magnitude ranking**. **NO unique directional information.** Same information class as Experiment A activity → magnitude.

---

## Stage 11 — Dispersion transition events

Persistent HIGH bars: 12487 times. Independent transitions:

| Transition | Event times | 60m mean \|pips\| | TRAIN / VALID / TEST 60m \|pips\| |
| --- | ---: | ---: | ---: |
| NORMAL → HIGH | 3743 | 8.42 | 8.31 / 8.87 / 8.07 |
| HIGH → NORMAL | 3743 | 7.99 | 8.01 / 8.30 / 7.34 |

Enter-HIGH then +60m dispersion falls (0.00053 → 0.00037). Exit-HIGH is already near normal and stays there.

Subsequent absolute movement after enter-HIGH is large, as expected from Stage 10. It is **not** a directional residual correction. Directional residual reversal after these timestamps is the same sub-pip Stage 8 effect.

**VERIFIED DESCRIPTIVE RESULT.** Transitions are the correct event unit (state bars are 3.3× more common than enters).

---

## Stage 12 — Relative rank

At each sync time, rank the six USD-oriented `usd_ret_6` values. 1 = strongest USD, 6 = weakest. Ties: `method=first`. **No threshold search.** Events: **enter** rank 1 / enter rank 6.

| Enter rank | n | Raw future USD 60m | Continuation signed USD 60m | Hit | Close / cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Strongest | 28762 | −1.5e-6 | ≈0 | 0.492 | 0.09 |
| Weakest | 29024 | +9.1e-6 | −9.8e-6 | 0.477 | −0.07 |

Per-symbol strongest → future USD 60m: mixed signs (JPY +.000020, AUD −.000019, others ~0). **No structural leader.**

**NO INFORMATION** for continuation or reversal-toward-group as a unique directional rule. Extreme rank is a restatement of a large recent residual, already tested in Stage 8.

---

## Stage 13 — Lead / lag diagnostic

Predeclared lags only: **1, 2, 3** M5 bars. Feature = PCA factor at `t−k`. Label = target **USD-oriented 60m return after t**. Strictly causal. Not a trading rule.

Lag-1 correlation of lagged factor vs future 60m USD:

| Symbol | TRAIN | VALID | DISCOVERY_TEST |
| --- | ---: | ---: | ---: |
| EUR_USD | +0.003 | −0.046 | −0.009 |
| GBP_USD | +0.000 | −0.024 | −0.002 |
| USD_JPY | +0.006 | −0.018 | −0.030 |
| AUD_USD | −0.024 | −0.043 | −0.021 |
| USD_CAD | +0.004 | −0.052 | +0.007 |
| USD_CHF | +0.011 | −0.013 | +0.003 |

Lags 2 and 3 are the same picture: TRAIN ≈ 0, VALID often slightly negative, DISCOVERY_TEST mixed. AUD is the only pair with a persistent small **negative** TRAIN correlation; it does not become a six-pair lead/lag law.

**NO INFORMATION** that survives chronological validation as a causal lead. **UNSTABLE** where a split correlation exceeds ~0.03.

---

## Stage 14 — Leave-one-pair-out robustness

PCA-1 refit on TRAIN after dropping each column in turn. Remaining weights stay the same shape: AUD largest, CAD smallest, others ~0.40–0.47. Dropping AUD raises JPY/CHF; dropping CAD barely changes the others.

The common factor is **broad**, not a one-pair artifact. CAD’s low loading is structural (this sample), not a hidden driver of the residual-reversal number: that reversal is tiny on every pair.

---

## Stage 15 — Pair-specific structure

60m residual-event reversal and catch-up, and HIGH-dispersion 60m |pips|:

| Symbol | Reversal signed USD | Hit | Class (direction) | HIGH-disp 60m \|pips\| |
| --- | ---: | ---: | --- | ---: |
| EUR_USD | +2.00e-5 | 0.515 | WEAK / BROAD statistical | 8.46 |
| GBP_USD | +3.02e-5 | 0.521 | WEAK / BROAD statistical | 11.18 |
| USD_JPY | +0.28e-5 | 0.499 | **NO INFORMATION** | 13.32 |
| AUD_USD | +0.43e-5 | 0.508 | WEAK | 7.67 |
| USD_CAD | +1.18e-5 | 0.513 | WEAK / BROAD statistical | 7.72 |
| USD_CHF | +3.68e-5 | 0.506 | WEAK / BROAD statistical | 7.05 |

Catch-up signed USD is **≤ 0** on every symbol (GBP/JPY/AUD more negative). Dispersion→magnitude is **BROAD**. Residual reversal is **BROAD but economically empty**; JPY does not participate. Do not hide that disagreement in the pooled +0.18 pip figure.

---

## Stage 16 — Time stability

All of 2025-09 through 2026-08 is DEVELOPMENT / DISCOVERY. DISCOVERY_TEST has already been inspected.

| Finding | TRAIN | VALID | DISCOVERY_TEST | Call |
| --- | ---: | ---: | ---: | --- |
| Residual reversal signed USD 60m | +1.67e-5 | +2.26e-5 | +0.89e-5 | Same sign, shrinking |
| Residual reversal hit | 0.511 | 0.510 | 0.506 | Barely > 0.5 |
| Catch-up signed USD 60m | −0.33e-5 | −2.40e-5 | −2.13e-5 | Wrong-way, stable |
| HIGH-disp 60m \|pips\| | 8.97 | 10.06 | 8.72 | Stable magnitude rank |
| LOW-disp 60m \|pips\| | 4.89 | 4.79 | 4.09 | Stable magnitude rank |
| Lag-1 factor→future USD | ~0 | often − | mixed | UNSTABLE / none |

Monthly residual std (Stage 6) does not identify a month that would flip the verdict.

---

## Stage 17 — Dependence-aware uncertainty

Event-level bootstrap, seed **42**, 200 reps. Overlapping M5 rows are **not** treated as independent experiments.

| Quantity | n | Mean | 5% | 95% |
| --- | ---: | ---: | ---: | ---: |
| Reversal signed USD 60m | 52875 | +1.65e-5 | +0.88e-5 | +2.38e-5 |
| Reversal signed instrument pips 60m | 52875 | **+0.18** | **+0.09** | **+0.26** |
| HIGH-disp \|pips\| 60m | 74922 | 9.23 | 9.17 | 9.29 |
| LOW-disp \|pips\| 60m | 111186 | 4.58 | 4.56 | 4.61 |

The reversal CI **excludes zero**. That is **statistical information**. The entire CI sits **below 0.3 pip**, versus ~0.80 pip contemporaneous cost. Dispersion CIs do not overlap: magnitude ranking is real.

---

## Stage 18 — Compare against failed V1 USD context (mandatory)

V1-12 / V1-13 already tested: other-pairs median USD `ret_6`, agreement counts, and TRAIN-extreme `usd_own − median`. Verdict: **NO INFORMATION / UNSTABLE**, ~0 to +0.15 pip, no cost clearance.

| Construct | Genuine new information? |
| --- | --- |
| Simple LOO median factor | **No.** Same object as V1-12. |
| TRAIN-fit PCA-1 | **No.** Correlation 0.977 vs median. CAD/AUD weights are descriptive, not an edge. |
| Residual vs fitted factor | **Almost no.** Correlation 0.920 vs LOO residual. 60m reversal close/cost 0.12 (PCA) vs 0.03 (LOO). Still far below 1×. |
| Dispersion std / IQR + transitions | **Yes, as magnitude context.** V1 studied pairs largely in isolation and did not publish this six-pair scale ranking. Same *class* as Experiment A activity → |move|. Not directional. |
| Relative rank strongest/weakest | **No.** Restates the residual. |
| Lags 1/2/3 of the factor | **No.** Does not survive validation. |

**Experiment B did not discover a new directional USD relationship.** It re-measured V1-12/V1-13 with orientation hygiene, leave-one-out, and a frozen PCA, and it added a **dispersion magnitude** fact. Residualization and factor fitting did **not** unlock G3.

---

## Stage 19 — Activity context (descriptive only)

Frozen Experiment A `vol_sess_rel` quintiles. **No combination search.** Applied only because residual reversal already existed as a weak full-sample statistical finding.

Residual enter-extreme events at 60m reversal:

| Activity | n | Signed USD | Hit | Signed pips | Close / cost | Frac close ≥1× |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LOW | 8718 | +2.24e-5 | 0.521 | +0.23 | −0.06 | 0.413 |
| NORMAL | 9824 | +0.48e-5 | 0.502 | +0.08 | +0.07 | 0.457 |
| HIGH | 14268 | +3.38e-5 | 0.517 | +0.42 | +0.43 | 0.467 |

High activity raises **absolute** MFE/MAE (9.37 / 8.85) and the close/cost ratio, as Experiment A already said: activity ranks magnitude. The unique close is still **0.43× cost**. This slice is **not** promoted. A relationship that is still below G3 after an explanatory cut is still below G3.

---

## Stage 20 — G3 economic gate

| Claim | Result |
| --- | --- |
| Bootstrap CI excludes zero | Yes, for residual reversal pips |
| Hit rate > 50% | Yes, 50.95% — economically meaningless |
| Stable across splits | Weakly, shrinking |
| MFE large | Yes, **both** ways (MAE ≈ MFE) |
| Unique favorable directional path | **No** |
| Unique close ≥ 1× contemporaneous half-spread | **No** (mean 0.12×; fraction 45%) |

**STATISTICAL INFORMATION:** tiny residual mean-reversion; dispersion ranks future |move|; dispersion statistic mean-reverts.

**ECONOMICALLY ACTIONABLE INFORMATION:** **none.**

G3 is **not** passed.

---

## Stage 21 — Experiment B answers

| # | Question | Answer |
| ---: | --- | --- |
| 1 | Does a common USD factor contain information beyond V1? | **No.** PCA-1 ≈ V1 median (corr 0.977). |
| 2 | Do target residuals predict reversal? | **Statistically yes, economically no** (~0.18 pip vs ~0.80 cost). |
| 3 | Do they predict continuation? | **No.** |
| 4 | Do lagging pairs / lagged factor predict subsequent target movement? | **No** at lags 1/2/3. |
| 5 | Does dispersion predict future convergence? | **The statistic mean-reverts.** That is not a unique pair-convergence trade. |
| 6 | Does dispersion predict movement magnitude? | **Yes**, broadly and chronologically (4.6 vs 9.2 pips at 60m). |
| 7 | Does relative rank contain information? | **No** unique direction. |
| 8 | Are effects stable in VALIDATION? | Reversal: same sign, still tiny. Dispersion magnitude: yes. Lags: no. |
| 9 | Are effects stable across symbols? | Dispersion magnitude: **BROAD**. Reversal: weak/broad except JPY **NO INFORMATION**. |
| 10 | Does any unique directional effect clear contemporaneous cost? | **No.** |
| 11 | Does any result pass G3? | **No.** |

**Exact verdict:** `B_USEFUL_CONTEXT_BUT_BELOW_G3`

`B_PASS` would not have authorized model training. This result does not either.

---

## Stage 22 — Next data decision (Experiment C)

**Decision: JUSTIFIED NEXT**

Not because B passed G3. B did **not** unlock a residual rule that needs a finer clock. C is justified as the **next predeclared V2 information class**: M1 path **order**.

**Question M1 can answer that these M5 data cannot:**

On already-defined M5 events (frozen V1 range-bottom / breakout-failure, and the residual-extreme transitions measured here), **which side of the contemporaneous half-spread is touched first** on the subsequent M1 MBA path? M5 OHLC leaves **~22.5% AMBIGUOUS** same-bar order (V1). Experiment B already shows 15-minute MFE ≈ MAE (~3.76 vs 3.56 pips) with a unique close of +0.15 pip. M1 is the only way to test whether the hypothesized side ever posts a **unique first-touch** before the opposite excursion, or whether the two-sidedness is already complete inside the decision bar.

M1 is **not** justified as a search for new events, new lags, new pair subsets, or a residual model. It does **not** create a pristine holdout. The year remains DEVELOPMENT / DISCOVERY.

**DO NOT DOWNLOAD M1 in this task.** Human review first.

---

## What was not done

- No production / stub / BUY/SELL / SL/TP / ATR / risk / session / RL / API / execution change
- No residual, factor, rank, or lead/lag filter implemented
- No model trained
- No M1 or other download; no OANDA; no Docker/bot restart
- No historical CSV modification
- No threshold optimization for PnL; no pair-subset or lag search beyond the predeclared family

---

## Tests

Focused tests in `tests/test_quant_v2_experiment_b.py`: six-symbol sync, no price forward-fill, USD orientation on all six, leave-one-out excludes target, TRAIN-only PCA + frozen transform, residual math, residual transitions, dispersion uses the current row, ranks, lag alignment / no lookahead, Experiment A half-spread reuse, fixed-seed bootstrap, source CSV immutability.

`python -m pytest -q --tb=line`: **381 passed**, **0 failed**, **0 skipped**, **26.11s**.
