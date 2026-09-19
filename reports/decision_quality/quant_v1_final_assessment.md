# Quant V1 — final assessment and freeze

**Status:** FROZEN. This closes the Quant V1 research branch.

**Verdict carried forward:** **NO ECONOMICALLY USEFUL EVENT FOUND** on the 2025-09-01 through 2026-08-31 six-pair M5 development dataset.

This document does not train a model, change production, or authorize another technical-indicator search on the same data.

**Sources (do not invent beyond these):**

- `reports/decision_quality/baseline_12m_quant_offline.md`
- `reports/decision_quality/baseline_12m_diagnostic.md`
- `reports/decision_quality/quant_stub_forensic_audit.md`
- `reports/decision_quality/quant_stub_component_study.md`
- `reports/decision_quality/quant_feature_target_discovery.md`
- `reports/decision_quality/quant_event_opportunity_discovery.md`

---

## Freeze statement

1. Quant V1 is a **hand-written SMA-state heuristic**, not a trained model.
2. On the inspected year it has **no economically useful directional edge**.
3. Broader M5 mid technical features and predeclared events change some return **distributions** by tenths of a pip. That is **statistically detectable** in a few cases and **not economically useful** versus modeled entry cost.
4. The year **2025-09-01 through 2026-08-31 UTC is DEVELOPMENT / DISCOVERY data**. It must never again be described as a pristine unused final holdout.
5. Future work must add **genuinely new causal information** or **later chronological data**. It must not rediscover the same mid-OHLC technical relationships on this year and call them novel.

---

## 1. Original quant architecture

Production direction originates in `forex_bot/ai_ensemble.py` → `_quant_stub_vote`.

| Piece | What it actually is |
| --- | --- |
| Input | Completed M5 **mid** candles |
| Features used for side | `ma_fast` vs `ma_slow` (lookback-scaled SMAs) |
| Allow gate | `abs(returns) > STUB_MOMENTUM_THRESHOLD` (default 0.0001) and `ATR > 0` |
| Side rule | BUY if fast > slow + eps; SELL if fast < slow − eps |
| Momentum | **Magnitude only.** Sign is discarded |
| State vs event | **Persistent SMA state**, not a crossover event. Docstring “MA cross” is wrong |
| Training | **None.** No weights, no fit, no model artifact. Defaults are hand-written (`eps=1e-6`, `mom_thr=0.0001`) |
| Strategy names | Route lookback (50/100/200). **Do not set BUY/SELL** |
| Live extras not in QUANT/OFFLINE | RL same-side/SKIP gate; optional API voters |

Git origin of this stub: `bd24462` (2026-03-31) replaced earlier random LocalLLM behavior. Workspace `ENSEMBLE_MODE=quant`.

---

## 2. Baseline performance (QUANT/OFFLINE)

Window: 2025-09 through 2026-08 UTC. Six pairs. Production quant + routing + SL/TP research replay. **Not** a live-bot replay (RL and API voters excluded).

| Metric | Value |
| --- | ---: |
| Trades | 18689 |
| BUY / SELL | 9538 / 9151 |
| Win rate | 26.69% |
| Expectancy | **−0.1995 R** |
| Profit factor | 0.7278 |
| Total R | −3728.5 |
| Chronological train / valid / test exp | −0.2067 / −0.1704 / −0.2143 |

All six symbols negative. BUY and SELL both negative. Strategy-label groups all negative. HTF-aligned and HTF-conflict both negative.

---

## 3. Directional forward-return findings

From the baseline diagnostic (signed in the stub’s direction, mid-to-mid):

- Hit rate **below 50%** at 5, 15, 30, 60, 120, and 240 minutes.
- Means and medians negative at those horizons.
- Pattern holds in train / valid / test, both sides, all six symbols.

**STATISTICALLY DETECTABLE:** the book loses; forwards are not a coin-flip in the stub’s favor.

**ECONOMICALLY USEFUL:** no. The signal does not predict subsequent mid movement well enough to pay spread.

---

## 4. Stub forensic findings

| Claim | Status |
| --- | --- |
| Trained model | **False** — hand-written fallback stub |
| BUY/SELL inversion bug | **Not found** |
| Lookahead in the stub | **Not found** |
| Live vs QUANT/OFFLINE function | **Same** `_quant_stub_vote` |
| Votes the same SMA state for hours | **True** — direction on >99.8% of bars; allow 36–64%; median direction run 12–35 bars on 4000-bar windows |

Negative expectancy is the heuristic plus costs, not a sign-flip implementation error.

---

## 5. Component / event findings (SMA family)

447,052 warmup bars; 14,769 SMA episodes.

| Label | Result | Status |
| --- | --- | --- |
| A / J persistent SMA state + stub allow | 236,828 bars / 14,104 episodes; 60m **−0.10 pips**, 48.8% hit | REJECTED |
| B first crossover | ~0; does not survive chronological splits | UNSTABLE / NO INFORMATION |
| H first qualifying bar | ~0; does not survive splits | UNSTABLE / NO INFORMATION |
| I repeated votes after first | **Worse** than first bar (−0.11 pips at 60m). 94% of stub bars | REJECTED (worsens) |
| C state age | 13–24 most negative in-sample; magnitude UNSTABLE | UNSTABLE |
| F momentum-sign agreement + stub | **−0.21 pips**, negative in all three partitions | REJECTED |
| G disagreement + stub | Near zero, sign UNSTABLE | UNSTABLE |
| K exact inverse | Arithmetic negation of J. Not an edge | REJECTED |

---

## 6. Broader feature findings

Leakage-safe 47-feature study; 447,027 rows; TRAIN-only quintiles; L2 logistic probe (no search).

| Finding | Evidence |
| --- | --- |
| Only stable pattern | Weak mean reversion at `pos_in_range_24` extremes (and short negative `ret_1`) |
| SMA continuation | Hit ≤ 50% OOS |
| Last-bar continuation | Hit ≤ 50% OOS |
| HTF quintiles | No stable directional information |
| Volatility **level** quintiles | Unstable |
| L2 logreg | VALID AUC 0.523 acc 51.60%; DISCOVERY_TEST AUC 0.522 acc 51.31% vs always-UP 51.11% |
| Ablation | No family load-bearing (ΔAUC ≤ 0.005) |
| Extreme-bucket magnitude | ~0.1–0.65 pips vs ~1.08 pip mean half-spread |

Verdict of that study: **FEATURE SET NOT YET SUFFICIENT.**

---

## 7. Event / opportunity findings

Reframe: infrequent events and future **paths** (MFE, path-order, cost hurdles), not every-bar UP/DOWN.

| Finding | Evidence |
| --- | --- |
| 60m 1×-cost opportunity | 69.8% of bars have **both** up and down MFE ≥ cost. Neither-side class 0.06% |
| Same-bar path-order | **AMBIGUOUS ~22.5%** (M5 OHLC cannot order) |
| Range-bottom **entry** | n=23,734; 60m close **+0.313 pips** (52.8%); bootstrap CI [0.198, 0.417]. Survives as an event. MFE-up ≈ MFE-down (~6.8) |
| Breakout 12/24/48 | **Fail / revert**, not continue. `breakout_up_24` 60m **−0.378**, CI [−0.486, −0.269]; all six pairs negative |
| Impulse | Slight reversal; bullish side time-unstable |
| Vol **transition** (expand) | Two-sided magnitude lift (abs ~13.5 vs ~10.8); direction CI includes 0 |
| Session transitions | No useful direction |
| Simple USD context / divergence | No stable six-pair economic effect |
| Best predeclared combo (range-bottom + USD-div) | +0.78 pips / 54.9% hit; TEST magnitude collapses to +0.30; EUR/CAD disagree; still below cost |

Verdict: **NO ECONOMICALLY USEFUL EVENT FOUND.** Target recommendation **G** (no current target sufficiently supported).

---

## 8. Transaction-cost hurdle

Modeled **entry half-spread** (production `simulated_half_spread`):

| Symbol | Half-spread (pips) |
| --- | ---: |
| EUR_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF | 1.0 |
| GBP_USD | 1.5 |
| Six-pair mean used in feature study | **~1.08** |

Baseline book: mean entry cost **0.179 R**; after adding that cost back, residual expectancy **≈ −0.021 R**. Costs explain most of the R hole and do **not** hide a positive directional signal.

**Permanent rule for this branch:** a +0.2 to +0.8 pip mean close is **STATISTICALLY** interesting at most and **ECONOMICALLY** irrelevant against ~1–1.5 pip entry cost, especially when the adverse MFE is similar and ~22% of path-orders are same-bar ambiguous.

---

## 9. Independence / overlapping observations

| Object | Why n is not “independent experiments” |
| --- | --- |
| Adjacent M5 bars | A 60m forward from t shares 11/12 of the path with t+1 |
| Persistent SMA state | 14,104 episodes → 236,828 stub votes (~17 bars/episode) |
| Persistent range-extreme state | 86,661 bottom-state bars → 23,734 entries (~3.65 bars/episode) |
| Pooled six-symbol timestamps | Shared clocks; pooled “minutes between events” is downward-biased |

V1 already required event-level n and event-level / block bootstrap. Future work must not treat overlapping M5 rows as independent samples.

---

## 10. Holdout contamination / repeated inspection

This year has been used for: 12-month QUANT/OFFLINE baseline, baseline diagnosis, stub forensics, component study, feature/target discovery, and event/opportunity discovery.

Frozen discovery cuts (feature/event studies):

| Split | Rule | Role now |
| --- | --- | --- |
| TRAIN | ≤ 2026-03-03 12:15 | Development |
| VALIDATION | ≤ 2026-06-02 05:05 | Development |
| DISCOVERY_TEST | after 2026-06-02 05:05 | **Already inspected.** Exploratory only |

**The entire interval 2025-09-01 through 2026-08-31 UTC is DEVELOPMENT / DISCOVERY.** No slice may be cited as pristine final out-of-sample proof for a future trained model.

---

## Hypothesis register (V1 results)

Statuses: **REJECTED** / **WEAK / BELOW COST** / **UNSTABLE** / **NO INFORMATION**.

| Hypothesis | Evidence | Stability | Approx effect | Cost relevance | Final status |
| --- | --- | --- | --- | --- | --- |
| SMA continuation (persistent state) | Component J; feature SMA quintiles; stub forwards | Negative or ≤50% hit across splits | 60m −0.10 pips; stub hit 48.8% | Far below / wrong sign | **REJECTED** |
| SMA crossover (first bar) | Component B / H | Fails chronological splits | ~0 to +0.03 pips at 60m | None | **UNSTABLE** / **NO INFORMATION** |
| Momentum agreement with SMA | Component F | Negative in train/valid/test | 60m −0.21 pips | Wrong sign | **REJECTED** |
| Range mean reversion (bar-level and entry event) | Feature `pos_in_range_24`; event `range_bottom_enter` | Sign mostly stable; EUR hit ~50%; some months flip | Event 60m +0.31 pips; bar extremes 0.1–0.65 | Below ~1.08 pip cost; MFE both sides ~6.8 | **WEAK / BELOW COST** |
| Breakout continuation | Event first close beyond prior 12/24/48 high/low | Opposite of continuation | Upside 24: −0.38 pips | Below cost | **REJECTED** (as continuation) |
| Breakout failure | Same events | Broad (6/6 pairs); 3 lookbacks; most months | ~0.4 pips toward fade | Below cost; path-order only modestly tilted | **WEAK / BELOW COST** |
| Impulse continuation | Large `signed_body_atr` enter | Bullish side flips across splits | ~0 | None | **REJECTED** |
| Impulse reversal | Same | Weak; bullish UNSTABLE | Bearish 60m +0.17 pips | Below cost | **WEAK / BELOW COST** |
| Volatility **level** quintiles | Feature study | Signs flip | — | — | **UNSTABLE** / **NO INFORMATION** |
| Volatility **transition** (expand) | Event `vol_expand_enter` | Direction coin-flip; mild two-sided |abs| lift | Close CI includes 0; abs 13.5 vs ~10.8 | Does not isolate a unique side | **WEAK / BELOW COST** (magnitude); **NO INFORMATION** (direction) |
| Session transition | Existing London buckets only | Asia→London flips in VALIDATION | ~50–52% hit; +0.11 to +0.29 pips | Below cost | **NO INFORMATION** (direction) |
| USD cross-pair context (other-pairs median / agreement) | Event study stages 14–15 | Symbol disagreement | ~0 to +0.15 pips | None | **NO INFORMATION** / **UNSTABLE** |
| USD divergence (TRAIN extreme residual) | `usd_div_extreme_*` | Unstable across pairs | ~0 | None | **NO INFORMATION** / **UNSTABLE** |
| Predeclared event combinations (5) | Range+reject, range+USD-div, breakout+vol, impulse+USD agree | Combo hit ~55% but TEST magnitude and symbols fail | Best close +0.78 pips | Still below 1× (GBP 1.5) | **WEAK / BELOW COST** / **UNSTABLE** |

No hypothesis is **ECONOMICALLY USEFUL** on this dataset.

---

## Stage 2 — Do-not-rediscover register

**Rule:** Do not claim novel discovery of the following from **the same 2025-09 through 2026-08 development data**. Scientifically justified **replication on genuinely new later data** is allowed and should reuse these exact definitions where possible.

| ID | Hypothesis | Definition (as already tested) | Dataset | Result | Why not actionable | Source |
| --- | --- | --- | --- | --- | --- | --- |
| V1-01 | Persistent SMA trend | `ma_fast` ≷ `ma_slow` every bar; stub allow on \|ret\| and ATR | Six-pair M5 mid 2025-09–2026-08 | 60m −0.10 pips, 48.8% | Wrong sign; overlapping votes | component, forensic, feature |
| V1-02 | SMA crossover | First bar of SMA-state change | same | ~0; split-unstable | Not an edge | component |
| V1-03 | Momentum confirmation | Last-bar sign agrees with SMA + stub | same | −0.21 pips, all splits | Makes it worse | component |
| V1-04 | Range-bottom / top mean reversion | `pos_in_range_24` TRAIN q1/q5; also **entry** into those quintiles | same | +0.3 pip event close; 0.1–0.65 pip buckets | Below spread; two-sided MFE | feature, event |
| V1-05 | Breakout continuation | First close beyond prior 12/24/48 high/low (prior excludes current bar) | same | Negative after upside breakouts | Fails; below cost | event |
| V1-06 | Breakout failure | Same definition, fade hypothesis | same | ~0.4 pip fade, broad | Below cost | event |
| V1-07 | Large impulse continuation | Enter TRAIN q5/q1 `signed_body_atr` | same | No continuation | Rejected | event |
| V1-08 | Large impulse reversal | Same | same | Tiny fade | Below cost | event |
| V1-09 | Volatility expansion transition | Enter TRAIN q5 `atr_pctile` | same | Magnitude-only, two-sided | No unique path | event |
| V1-10 | Volatility **level** quintile | Bar in ATR/vol quintile | same | Unstable signs | No information | feature |
| V1-11 | Session transition | asia→london, london→overlap, overlap→late NY | same | No direction | Clock only | event |
| V1-12 | Simple broad-USD context | Other-pairs median USD-direction `ret_6`; agreement count | same | Unstable / ~0 | Already tested | event |
| V1-13 | Simple USD divergence | Own USD ret − others median, TRAIN extremes | same | Unstable | Already tested | event |
| V1-14 | Predeclared combos (the five) | Range+reject; range+USD-div; breakout+vol; impulse+USD agree | same | Best still below cost / unstable | Do not re-mine neighbors on this year | event |
| V1-15 | Every-bar binary UP/DOWN | Mid close[t+h]−close[t], 5–240m | same | Logreg ≈ always-UP | Feature set insufficient | feature |
| V1-16 | 1×-cost three-way no-trade | Neither MFE ≥ 1× half-spread | same | Class ~0.06% at 60m | Empty no-trade class | event |
| V1-17 | HTF M15/H1/H4 sign as M5 direction | Closed HTF joined `end ≤ t` | same | ~49.5%; ablation unused | No information | feature |
| V1-18 | Inverse of current stub | −J | same | +0.10 pips | Negation, not a discovery | component |

**Also do not rediscover:** “more SMA periods,” “more ATR lookbacks,” or “another quintile of mid-price location” on this year as if they were new information.

---

## What Quant V1 authorizes next

- Archive these conclusions.
- Design Quant V2 around **new data types** or **later time**.
- Do **not** train on V1 targets.
- Do **not** add V1 events as live filters.

See `reports/decision_quality/quant_v2_research_plan.md`.
