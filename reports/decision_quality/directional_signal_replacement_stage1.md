# Directional signal replacement — Stage 1

RESEARCH ONLY. Production strategy, `bot_loop`, live quant, RL, SL/TP, ATR, profit protection, sizing, USD guards, `.env`, Docker, and OANDA orders were not changed.

**Verdict:** The current stub has no stable after-cost directional edge. Simple inversion does not either. Stub magnitude, simple entry-time models, skip gates, and cross-pair USD counts all fail the out-of-sample economic test. Nothing in this stage is a deployable replacement. **BEST RESEARCH CANDIDATE: NONE.**

Machine-readable output: `data/research/directional_replacement_stage1/results.json` and `events_first_qual.csv`.

Live sample contamination: **NO.** Thresholds, quintile edges, and model weights were frozen on historical TRAIN only. The corrected live sample was scored last and was not used to change any rule.

---

## 1. Datasets (kept separate)

### A. Corrected live holdout

Same window as `reports/decision_quality/live_trade_failure_diagnosis.md`.

| Item | Value |
|---|---|
| Start | `2026-09-21T22:00:04Z` |
| Scored trades | 212 (6 MANUAL excluded) |
| Booked | mean R −0.352, PF 0.524, 154 SL / 14 TP / 44 PP |
| Role | **final untouched evaluation set** |
| Features at entry | not persisted (`ma_fast` / `ma_slow` absent) |
| Historical cache | ends `2026-08-31`; live bars were **not** downloaded |

Live inversion / forwards reuse the forensic executable-side series already computed for those 212 trades. Live was **not** used to fit models or pick thresholds.

### B. Historical research cache

| Item | Value |
|---|---|
| Files | `data/historical/{EUR,GBP,AUD,USD}_{USD,JPY,CAD,CHF}_M5.csv` |
| Range | `2025-09-01` through `2026-08-31` complete M5 bid/ask |
| Bars / pair | ~74.5k–74.6k |
| New market data downloaded | **NO** |
| Lookbacks | frozen published mapping: USD_JPY 50; other five 100 |
| Event rule (primary) | first stub-allow bar of each SMA episode (`first_qual`) |
| Events | **14,104** |
| Chrono cuts | TRAIN ≤ `2026-02-27 07:47:30Z` (n=7,052); VALID ≤ `2026-05-29 02:10:00Z` (n=3,528); TEST after (n=3,524 / 3,521 with a 60m forward) |

Sensitivity: every stub-allow bar (~236k) was scored at 60m only. Sign and economics match the first-qual set.

Production `select_strategy` names are RNG/meta and were **not** reconstructed on historical bars. Live strategy labels are used only in the live descriptive block.

---

## 2. Target construction

No look-ahead. Decision at the close of a **complete** M5 bar. Forwards use later complete bars only.

Executable round-trip (includes spread at entry and at horizon):

| Side | Forward pips |
|---|---|
| BUY | `(bid_close[t+h] − ask_close[t]) / pip` |
| SELL | `(bid_close[t] − ask_close[t+h]) / pip` |

Directional labels (independent of SL/TP):

| Label | Rule |
|---|---|
| UP | `bid[t+h] > ask[t]` (a long covers cost) |
| DOWN | `ask[t+h] < bid[t]` (a short covers cost) |
| ECONOMICALLY_FLAT | neither |

A tiny mid-only move that does not cross the opposite side is FLAT. Research R uses `pips / (2 × ATR_pips)` (same 2×ATR stop geometry as live, not booked live P/L).

Horizons: 5 / 15 / 30 / 60 / 120 / 240 minutes.

Primary economic horizon for filters/models: **60m** (predeclared).

---

## 3. Is inversion real?

### Historical first-qual, after costs, 60m

| Split | n | Orig hit | Orig mean pips | Orig mean R | Inv hit | Inv mean pips | Inv mean R |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 7052 | 0.392 | −1.77 | −0.332 | 0.385 | −1.95 | −0.335 |
| VALID | 3528 | 0.364 | −2.16 | −0.347 | 0.387 | −1.84 | −0.329 |
| TEST | 3521 | 0.352 | −1.78 | −0.424 | 0.371 | −2.00 | −0.409 |

Both sides lose in every split. VALID slightly prefers inversion; TRAIN and TEST prefer original (still negative). **Sign of the inversion advantage flips. Unstable.**

TEST, all horizons (orig vs inv mean pips): 5m −1.91 / −1.94; 15m −1.88 / −1.97; 30m −1.92 / −1.91; 60m −1.78 / −2.00; 120m −1.98 / −1.79; 240m −1.74 / −1.99. No horizon is positive either way.

All-allow 60m TEST: orig −1.77 pips, inv −1.80 pips. Same conclusion.

Pooled-by-symbol 60m originals are all negative (AUD −1.38 through GBP −2.26). Inversion does not rescue any pair.

### Live holdout (sign-flip of already-costed forensic forwards)

| Horizon | Orig hit | Orig mean R | Inv hit | Inv mean R |
|---|---:|---:|---:|---:|
| 5m | 0.269 | −0.292 | 0.726 | +0.292 |
| 60m | 0.443 | −0.180 | 0.552 | +0.180 |
| 240m | 0.415 | −0.356 | 0.585 | +0.356 |

This live “inversion” is **not** a re-entered opposite trade. It flips the signed path after the original fill has already paid spread. Historical inversion *does* re-price BUY vs SELL from the same bar and stays negative. **Do not invert the bot because the 212-trade holdout sign-flip looks green.**

Prior stub forensic (orientation audit): labels are not swapped. Both sides lose. Inversion of a two-sided loser is still a loser after costs.

---

## 4. Entry-time features (historical)

Included, all as-of the decision bar:

SMA fast/slow, SMA diff, SMA diff/ATR, SMA slope (30m), price−SMA fast/slow, RSI, MACD, MACD signal (9-span of existing MACD), MACD hist, Bollinger position, research Wilder ADX (not used live), ATR, ATR/price, returns 5/15/30/60/120m, 30m realized vol, distance to 36-bar high/low in ATR, spread, spread/ATR, volume, relative volume, hour UTC, day of week, stub side, USD dir, other-pair USD counts.

Unavailable / not invented: production ADX on the live path; historical `select_strategy` labels; live SMA values (not persisted; cache does not cover Sept 2026).

---

## 5. Stub information content (strength quintiles)

Magnitude = `|SMA_fast − SMA_slow| / ATR`. Edges from TRAIN only. Q1 = weakest, Q5 = strongest.

60m original, hit rate / mean pips:

| Q | TRAIN hit | TRAIN pips | VALID hit | VALID pips | TEST hit | TEST pips |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 0.417 | −1.50 | 0.375 | −1.64 | 0.364 | −1.70 |
| Q2 | 0.410 | −1.51 | 0.372 | −2.26 | 0.336 | −2.17 |
| Q3 | 0.401 | −1.50 | 0.383 | −1.95 | 0.340 | −2.46 |
| Q4 | 0.372 | −2.18 | 0.343 | −2.34 | 0.370 | −1.20 |
| Q5 | 0.361 | −2.16 | 0.349 | −2.57 | 0.350 | −1.53 |

Monotonic improvement: **NO** on TRAIN, VALID, or TEST. Stronger stub states are **worse** on TRAIN/VALID. Trade-only-Q5 is worse than trade-all (TEST Q5 −1.53 vs all TEST −1.78 is mixed; VALID Q5 −2.57 is worse). Strength does not predict directional quality.

Live strength: **not scored** (no entry SMA). Not used to pick a story.

---

## 6. Conditional failure analysis

A subgroup is “promising” only if TRAIN, VALID, and TEST after-cost 60m mean pips are all > 0 with adequate n. Live P/L was not used to nominate groups.

**Stable positive subgroups found: 0.**

Every predeclared slice is negative on TRAIN and VALID:

| Slice | TRAIN mean pips | VALID | TEST |
|---|---:|---:|---:|
| EUR_USD | −1.83 | −2.47 | −1.95 |
| USD_CAD | −1.73 | −2.63 | −2.36 |
| USD_CHF | −1.91 | −2.19 | −1.90 |
| USD_JPY | −1.63 | −2.25 | −1.06 |
| BUY | pooled −1.82 | (all splits negative in first-qual 60m) | |
| SELL | pooled −1.92 | | |
| LONG_USD | pooled −1.80 | | |
| SHORT_USD | pooled −1.94 | | |
| Hour 12–15 | −1.50 | −2.13 | −1.21 |
| Hour 20–23 | −3.42 | −4.05 | −3.28 |
| Tightest spread Q1 | −1.75 | −2.56 | **+0.23** |
| Strongest trend Q5 | −2.16 | −2.57 | −1.53 |

Spread Q1 TEST is a one-split flicker (n=253). TRAIN/VALID are negative. Not promising.

Hour 20–23 is a **stable bad** region (hit ~0.25, mean R ~ −0.8 to −1.0) but that is not a tradable edge.

Live EUR_USD booked +0.14R is **not** treated as evidence. Historical EUR_USD is negative in all three splits. Live USD_CAD / USD_CHF / `swing_breakout` weakness is **not** used to disable those slices.

---

## 7. Simple predictive baselines

Referenced prior work: L2 logistic on 14 features, VALID AUC **0.523**, DISCOVERY_TEST 0.522, accuracy ~51% vs always-UP (`quant_feature_target_discovery.md`). That model did not clear spread.

This stage, TRAIN-only L2 logistic (fixed l2=1, 250 steps) and a greedy depth-2 stump (quintile split candidates only). Target = economic UP at 60m. Live not used.

| Split | Logreg AUC | Logreg bal-acc | Tree AUC | Always-UP acc |
|---|---:|---:|---:|---:|
| TRAIN | 0.570 | 0.500 | 0.542 | 0.596 |
| VALID | 0.585 | 0.502 | 0.551 | 0.608 |
| TEST | 0.561 | 0.501 | 0.537 | 0.629 |

Accuracy is high because UP is the minority class (~37–40%). Balanced accuracy is a coin flip. Predicted `P(UP)` sits in a narrow band ~0.38–0.42, so the 0.5 decision rule becomes **almost always SELL** (TEST: 3517 SELL / 4 BUY).

After-cost 60m economics of “always follow the model”:

| Split | Stub mean pips | Invert | Logreg-always | Tree-always |
|---|---:|---:|---:|---:|
| TRAIN | −1.77 | −1.95 | −2.09 | −2.06 |
| VALID | −2.16 | −1.84 | −1.89 | −1.94 |
| TEST | −1.78 | −2.00 | −1.59 | −1.64 |

TEST logreg is slightly less bad than the stub by collapsing to short-the-USD-pair drift, not by ranking direction. It is still **negative after costs**. Calibration is weak (two occupied bins; mean p 0.38 vs realized UP 0.33 in the lower bin).

This does **not** beat the stub as a tradeable replacement. It reproduces the earlier ~0.52–0.56 AUC ceiling.

---

## 8. Selective BUY / SELL / SKIP

Predeclared grid (not searched): BUY if `P(UP) ≥ t`, SELL if `P(UP) ≤ 1−t`, else SKIP. `t ∈ {0.55, 0.60, 0.65}`.

| t | TEST n | Coverage | Hit | Mean pips | Mean R | PF |
|---|---:|---:|---:|---:|---:|---:|
| 0.55 | 3507 | 0.996 | 0.353 | −1.57 | −0.391 | 0.60 |
| 0.60 | 1658 | 0.471 | 0.298 | −2.34 | −0.581 | 0.35 |
| 0.65 | 83 | 0.024 | 0.084 | −6.20 | −1.79 | 0.07 |

Stricter thresholds **destroy** economics (they select the most confident SELL-into-cost cases). VALID matches TEST. Compare: trade every stub TEST −1.78; invert every stub TEST −2.00. No threshold is after-cost positive.

---

## 9. Current RL gate (audit only)

Live filled trades are, by construction, stub candidates that the same-side RL gate did **not** veto. `trades` / `exec_orders` persist no `rl_action` and no veto list. Historical QUANT/OFFLINE baseline never applied RL.

| Quantity | Result |
|---|---|
| Stub candidates in dump | unknown (not logged) |
| RL-approved | 212 scored fills (lower bound) |
| RL-vetoed with forwards | **0 recorded** |

Did RL improve directional expectancy? **Cannot measure.** Not modified, not trained, not removed.

---

## 10. Cross-pair USD information

Point-in-time counts of other pairs’ contemporaneous stub USD direction. No future bars.

Follow net other-pair USD (skip when net=0), 60m after costs:

| Split | n | Hit | Mean pips | Mean R |
|---|---:|---:|---:|---:|
| TRAIN | 7030 | 0.384 | −2.23 | −0.362 |
| VALID | 3516 | 0.383 | −1.86 | −0.318 |
| TEST | 3515 | 0.380 | −1.04 | −0.311 |

Agree-with-others vs disagree: both negative in all splits. TEST agree −1.09 pips, disagree −2.74. Agreement is less bad, not profitable. Adding `xusd_net` to the logistic did not produce a tradeable gate.

---

## 11. Economic gate

STATISTICAL vs TRADEABLE:

| Candidate | AUC / hit sometimes > 0.5? | After-cost OOS expectancy > 0? |
|---|---|---|
| Current stub | No | No |
| Inverted stub | Live sign-flip only | Historical no |
| Strength Q5 | No | No |
| Logreg / tree | AUC 0.54–0.58 | No |
| Skip t=0.55–0.65 | No | No |
| Cross-USD follow | No | No |

No candidate advances.

---

## 12. Decision table

After-cost expectancy is 60m mean pips unless noted. Live stub row uses forensic booked / uncensored R as already published. Live inversion is the sign-flip caveat above.

| Candidate | TRAIN | VALID | TEST | Corrected live | Coverage | After-cost expectancy | Stability | Verdict |
|---|---|---|---|---|---|---|---|---|
| CURRENT STUB | hit 0.39, −1.77 pips | 0.36, −2.16 | 0.35, −1.78 | booked −0.35R; 60m fwd −0.18R | 1.0 of stub events | Negative all sets | Stable **loser** | **NO EVIDENCE** of edge |
| INVERTED STUB | −1.95 | −1.84 | −2.00 | sign-flip +0.18R (not re-entry) | 1.0 | Historical negative; live flip unstable | Sign of advantage flips | **NO EVIDENCE** |
| STUB STRENGTH FILTER | Q5 −2.16 | Q5 −2.57 | Q5 −1.53 | not scored | ~0.20–0.25 | Worse or equal | Anti-monotonic | **NO EVIDENCE** |
| CONDITIONAL STUB FILTER | all predeclared slices ≤ 0 | all ≤ 0 | one flicker (tight spread +0.23) | EUR_USD booked + ignored | varies | No slice +/+/+ | None stable | **NO EVIDENCE** |
| SIMPLE PREDICTIVE MODEL | AUC 0.57; −2.09 pips | 0.58; −1.89 | 0.56; −1.59 | not scored (no features) | ~1.0 (always SELL) | Still negative | Matches prior ~0.52–0.56 AUC | **WEAK / INSUFFICIENT** |
| SELECTIVE BUY/SELL/SKIP | t=0.60 −2.49 | −2.16 | −2.34 | not scored | 0.37–0.47 | Worse as t rises | Stable failure | **NO EVIDENCE** |
| CROSS-PAIR USD FILTER | −2.23 | −1.86 | −1.04 | not used to fit | ~0.99 | Negative | Same sign, not profitable | **WEAK / INSUFFICIENT** |
| CURRENT RL FILTER | n/a | n/a | n/a | vetoes not persisted | unknown | Unknown | Unknown | **WEAK / INSUFFICIENT** |

No verdict is “production ready.”

---

## 13. Anti-overfit record

| Rule | Status |
|---|---|
| Live used to fit weights | NO |
| Live used to choose thresholds | NO |
| Live used to pick quintile edges | NO |
| Live used to declare a winning subgroup | NO |
| Live still an untouched holdout | **YES** |
| If a later task refits after seeing live numbers | that live sample is contaminated |

---

## 14. What this means for replacement

The stub is a lagged SMA-state plus a `|ret|>0.0001` allow gate. It is not a coin flip on mid returns; after bid/ask costs it is a **persistent negative**. There is no conditional pocket that stays positive through TRAIN/VALID/TEST. Inversion, strength filters, and a small logistic/tree do not create after-cost expectancy.

The directional layer should be treated as **uninformative for trading**, not as a slightly-wrong signal to invert or tighten. Replacement research (Stage 2+) must start from a different hypothesis than “preserve the stub and filter it.” That is a research conclusion, not a production change.

---

## 15. Exact answers

CURRENT STUB HAS STABLE DIRECTIONAL EDGE: **NO**  
SIMPLE INVERSION HAS STABLE DIRECTIONAL EDGE: **NO**  
STUB STRENGTH PREDICTS DIRECTIONAL QUALITY: **NO**  
STABLE POSITIVE SUBGROUP EXISTS: **NO**  
CURRENT RL FILTER ADDS VALUE: **INSUFFICIENT**  
CROSS-PAIR USD INFORMATION ADDS VALUE: **NO**  
SIMPLE ENTRY-TIME FEATURE MODEL BEATS STUB OUT OF SAMPLE: **NO**  
POSITIVE AFTER-COST SELECTIVE SIGNAL FOUND: **NO**  
BEST RESEARCH CANDIDATE: **NONE**  
SHOULD ANYTHING BE DEPLOYED: **NO**  
PRODUCTION CODE CHANGED: **NO**  
LIVE STRATEGY CHANGED: **NO**  
OANDA ORDERS SENT: **NO**  
DOCKER RESTARTED: **NO**

STOP.
