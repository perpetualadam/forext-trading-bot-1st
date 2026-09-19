# Quant V2 Experiment C — M1 path-order resolution

**Status:** COMPLETE — research only. No model, no M1 signals, no event filters, no production change.

**Authorized data:** existing six M5 CSVs plus the authorized M1 MBA download for the same six symbols and the same DEVELOPMENT / DISCOVERY year (2025-09-01 through 2026-08-31 UTC).

**Parents:** V1 **NO ECONOMICALLY USEFUL EVENT FOUND**. A **A_USEFUL_CONTEXT_BUT_BELOW_G3**. B **B_USEFUL_CONTEXT_BUT_BELOW_G3**.

**Question C is allowed to answer:** does lower-timeframe path order resolve M5 same-bar first-touch ambiguity in a way that reveals **economically useful direction** for **already-frozen** M5 events?

C is **not** M1 feature, indicator, event, or strategy discovery. Frozen M5 definitions were not retuned. No activity or dispersion conditioning. No pair-specific thresholds from M1 results.

Progress: `reports/decision_quality/quant_v2_experiment_c_progress.json`  
Frozen spec (before outcomes): `reports/decision_quality/quant_v2_experiment_c_frozen_spec.json`  
Machine tables: `reports/decision_quality/quant_v2_experiment_c_data.json`  
M1 identity: `reports/decision_quality/quant_v2_experiment_c_m1_identity.json`  
M1 cache: `data/historical/m1/{SYMBOL}_M1.csv`

---

## Experiment C verdict

# C_RESOLVES_PATH_BUT_BELOW_G3

M1 **does** resolve most M5 same-bar ambiguity into a unique first-touch. Of pooled frozen-event paths that were M5_AMBIGUOUS at 60m / 1× contemporaneous half-spread, **73.1%** become UP_FIRST or DOWN_FIRST, **26.6%** remain **M1_AMBIGUOUS** (both hurdles inside one minute), and almost none are NEITHER or missing.

That resolved order is **nearly balanced**. The largest frozen hypothesis tilt is residual-negative reversal: favorable-first minus adverse-first = **+4.8 percentage points** at 60m / 1× (bootstrap 5–95% **+3.7 to +5.6**, seed 42), same sign in all three splits and all six symbols. Range-bottom is **+3.2pp**. Both sit only about **+0.7 to +1.3pp** above the unconditional M1 first-touch base rate.

First-touch of 1× cost is **not** a unique remaining path. V1/A/B already showed two-sided 60-minute excursion. M1 tells us which side prints 1× first; it does not make that side economically exclusive. **G3 is not passed.**

This does not authorize training, M1 signals, or live filters.

---

## Frozen experiment specification (Stage 1)

Persisted in `quant_v2_experiment_c_frozen_spec.json` **before** M1 outcome tables.

| Family | Exact definition | Hypothesis (instrument) |
| --- | --- | --- |
| A. range_bottom | ENTER `pos_in_range_24 ≤ 0.1911764703070358` | UP (mean reversion) |
| B. range_top | ENTER `pos_in_range_24 ≥ 0.8314606732231985` | DOWN |
| C. breakout_up_24 | ENTER close > prior 24-bar high (current bar excluded) | DOWN (failure) |
| D. breakout_dn_24 | ENTER close < prior 24-bar low | UP (failure) |
| E. resid_pos | ENTER frozen B `resid_pca6` q5 | B reversal of +USD residual |
| F. resid_neg | ENTER frozen B `resid_pca6` q1 | B reversal of −USD residual |

PCA weights/means/betas and residual edges are the **frozen Experiment B TRAIN** values. They were not refit on M1.

Hurdles: **1.0 / 1.5 / 2.0 / 3.0 ×** event-time M5 half-spread. Horizons: **15 / 30 / 60 / 120 / 240 / 480** minutes. Splits unchanged (T50=2026-03-03 12:15, T75=2026-06-02 05:05).

---

## Stage 2 — Decision timestamp / OANDA semantics

OANDA InstrumentsCandles `time` is the **bar start**.

An M5 event at `t` covers `[t, t+5m)` and is knowable only when that bar is complete (`t+5m`). The five M1 starts `t … t+4m` **formed** the event bar and are **excluded** from the future path.

**First eligible M1:** `t+5m`.  
**Last M1 for horizon H:** `t+5m + H − 1 minute`.

Tests cover this boundary. Using a forming-bar M1 that already went the hypothesized way cannot leak into the label.

---

## M1 download identity

Read-only InstrumentsCandles, `granularity=M1`, `price=MBA`, sequential pages of 2000, 0.6s pacing, in-process limiter, `--confirm` after dry-run. Dry-run plan: **263 pages/symbol, 1578 pages total**. Written only under `data/historical/m1/`. M5 source SHA-16 prefixes are unchanged from Experiment B (`3ae3c4d061792353` …).

| Symbol | M1 rows | First UTC | Last UTC | Duplicates | Unexpected 1m gaps |
| --- | ---: | --- | --- | ---: | ---: |
| EUR_USD | 370729 | 2025-09-01 00:00 | 2026-08-31 23:59 | 0 | 1176 |
| GBP_USD | 370998 | 2025-09-01 00:00 | 2026-08-31 23:59 | 0 | 844 |
| USD_JPY | 370450 | 2025-09-01 00:00 | 2026-08-31 23:59 | 0 | 1233 |
| AUD_USD | 369295 | 2025-09-01 00:00 | 2026-08-31 23:58 | 0 | 2327 |
| USD_CAD | 370249 | 2025-09-01 00:00 | 2026-08-31 23:58 | 0 | 1487 |
| USD_CHF | 368404 | 2025-09-01 00:00 | 2026-08-31 23:58 | 0 | 2680 |

MID / BID / ASK / volume / complete are present. Gaps are classified, **not interpolated or forward-filled**. Missing expected market-open minutes before a unique order → **INSUFFICIENT_DATA**, not NEITHER.

Full SHA-256 values are in `quant_v2_experiment_c_m1_identity.json`.

---

## Stages 3–5 — Alignment, cost, hurdles

Primary economic hurdle: **Experiment A contemporaneous M5 completed-bar half-spread** `(ask_close − bid_close)/2` at the event bar. JPY pip = 0.01. M1 bid/ask was stored but was **not** used to retune the hurdle after seeing results.

Same-M1-candle both-touch → **M1_AMBIGUOUS**. No intra-minute order is invented.

---

## Stage 6 — How much M5 ambiguity does M1 resolve?

Pooled frozen-event 60m / 1× paths (n = 133239):

| M5 label | n | Rate |
| --- | ---: | ---: |
| M5_AMBIGUOUS | 46304 | **34.8%** |
| UP_FIRST | 43065 | 32.3% |
| DOWN_FIRST | 42830 | 32.1% |
| NEITHER | 1040 | 0.8% |

V1’s ~22.5% AMBIGUOUS used a **larger modeled** 1.0 / 1.5 pip hurdle. Actual half-spread is typically ~0.80 pip, so both sides clear 1× more often and M5 ambiguity is **higher**. That is consistent with Experiment A (actual cost raised BOTH-path rates).

Of the 46304 M5_AMBIGUOUS events:

| M1 label | n | Of ambiguous |
| --- | ---: | ---: |
| UP_FIRST | 17062 | 36.8% |
| DOWN_FIRST | 16781 | 36.2% |
| M1_AMBIGUOUS | 12305 | **26.6%** |
| NEITHER | 100 | 0.2% |
| INSUFFICIENT_DATA | 56 | 0.1% |

**Resolved to a unique order: 73.1%.** Remaining same-minute ambiguity: 26.6%. Resolution is **not directional**: UP and DOWN are essentially equal.

Per-family M5 ambiguous rates: range ~32%, breakout ~35–36%, residual ~37%. Same resolution pattern in every family.

**VERIFIED DESCRIPTIVE RESULT.**

---

## Stage 7 — Range-bottom (hyp: UP)

Event n = **23743**. 60m / 1×:

| | n | Rate |
| --- | ---: | ---: |
| UP_FIRST (fav) | 10845 | 45.7% |
| DOWN_FIRST (adv) | 10088 | 42.5% |
| M1_AMBIGUOUS | 1995 | 8.4% |
| INSUFFICIENT | 665 | 2.8% |
| NEITHER | 150 | 0.6% |

fav − adv = **+3.19pp** (bootstrap **+2.25 to +4.22**).  
Incremental vs base UP rate 44.93%: **+0.74pp**.

Splits: TRAIN +1.1pp · VALID +4.6pp · DISCOVERY_TEST +6.0pp (same sign, growing).  
Symbols: all six fav−adv ≥ 0; GBP nearly 0 (+0.4pp); JPY +5.7pp; CAD +5.2pp.

15m / 1× already +2.7pp. 60m / 2× shrinks to +1.6pp. Time-to-first-touch is not a new edge: the tilt is present at 15m.

**STABLE CANDIDATE (statistical).** **BELOW G3.** Incremental vs base is small. BROAD-weak.

---

## Stage 8 — Range-top (hyp: DOWN)

Event n = **25054**. 60m / 1×: fav 45.6% / adv 43.7% / amb 7.8%.  
fav − adv = **+1.90pp** (CI **+0.88 to +2.75**). Incremental vs base DOWN 44.37%: **+1.27pp**.

TRAIN +1.1pp · VALID +0.1pp · DISCOVERY_TEST +5.3pp.  
JPY **−4.3pp** (opposes). CHF ~0. **UNSTABLE / PAIR-SPECIFIC disagreement.** Not G3.

---

## Stage 9 — Breakout failure (frozen 24-bar only)

**Upside breakout → DOWN** (n = 16301): fav 45.1% / adv 43.8%; fav−adv **+1.33pp** (CI +0.15 to +2.41). Incremental vs base DOWN: **+0.76pp**. TRAIN **−0.6pp**. JPY −6.1pp, AUD +8.6pp. **UNSTABLE.**

**Downside breakout → UP** (n = 15155): fav 44.0% / adv 42.9%; fav−adv **+1.17pp** (CI **−0.01 to +2.44**, includes 0). Incremental vs base UP: **−0.89pp** (worse than unconditional). **NO INFORMATION** beyond base.

M1 does **not** turn V1’s weak breakout-failure close into a genuine ordered-path advantage.

---

## Stage 10 — Residual-extreme reversal (frozen B)

PCA/residuals not refit. M1 only orders the subsequent path.

**Positive residual (fade +USD residual), n = 26517.**  
fav 44.3% / adv 42.0%; fav−adv **+2.29pp** (CI +1.28 to +3.13). JPY ~0. Splits all slightly positive.

**Negative residual (fade −USD residual), n = 26469.**  
fav 45.6% / adv 40.8%; fav−adv **+4.76pp** (CI **+3.74 to +5.64**).  
TRAIN +4.5 · VALID +5.6 · DISCOVERY_TEST +4.4.  
All six symbols +3.7 to +7.0pp. Monthly fav−adv is positive in 11/12 months (2026-08 ≈ 0).

This is the strongest **statistical** first-touch tilt in C. It is still a few percentage points around a ~45% / ~41% split, with ~10% ambiguous/insufficient, and it does not exceed G3. After first-touch, the opposite 1× still typically exists inside the same hour (V1/A two-sided paths).

**STABLE CANDIDATE (statistical, BROAD) for resid_neg first-touch.** **BELOW COST as an exclusive path. BELOW G3.**

---

## Stage 11 — Base-rate control

Predeclared control: **every eligible M5 timestamp** with a valid event-time half-spread (n = **447321**), same M1 first-touch machinery, 15/60/240m at 1×.

| 60m / 1× | Rate |
| --- | ---: |
| UP_FIRST | **44.93%** |
| DOWN_FIRST | **44.37%** |
| M1_AMBIGUOUS | 7.18% |
| INSUFFICIENT | 2.84% |
| NEITHER | 0.68% |

Unconditional first-touch is already almost a coin flip with a **+0.56pp** UP lean. Claiming “45% UP_FIRST” on an event is meaningless without this.

---

## Stage 12 — Unique directional path vs base

| Family | Hyp | fav−adv 60m 1× | Incremental fav vs matching base | Call |
| --- | --- | ---: | ---: | --- |
| range_bottom | UP | +3.19pp | **+0.74pp** | weak |
| range_top | DOWN | +1.90pp | **+1.27pp** | weak / JPY flips |
| breakout_up_24 | DOWN | +1.33pp | **+0.76pp** | TRAIN flips |
| breakout_dn_24 | UP | +1.17pp | **−0.89pp** | none |
| resid_pos | reversal | +2.29pp | ~0 vs mixed base | weak |
| resid_neg | reversal | +4.76pp | ~+1pp vs mixed ~44.6% | strongest, still small |

---

## Stage 13 — G3

| Requirement | Met? |
| --- | --- |
| Unique directional first-touch information | Statistical yes (resid_neg, range_bottom) |
| Chronological stability | resid_neg and range_bottom same sign |
| Adequate independent event n | Yes (tens of thousands) |
| Multi-symbol or justified structure | resid_neg BROAD; range_top/breakout not |
| Favorable path relevant to contemporaneous cost | First-touch **is** 1× cost; the **other** 1× still usually arrives |
| Materially stronger than base rate | **No** (≤ ~1pp incremental) |

M1 resolving ambiguity, bootstrap CIs excluding zero, 51%-like hit rates, and large two-sided MFE **do not** pass G3.

**G3 fail.**

---

## Stage 14 — Uncertainty

Event-level bootstrap, seed **42**, 200 reps, 60m / 1× fav−adv:

| Family | Mean | 5% | 95% |
| --- | ---: | ---: | ---: |
| range_bottom | +0.032 | +0.022 | +0.042 |
| range_top | +0.019 | +0.009 | +0.028 |
| breakout_up_24 | +0.013 | +0.002 | +0.024 |
| breakout_dn_24 | +0.012 | −0.000 | +0.024 |
| resid_pos | +0.023 | +0.013 | +0.031 |
| resid_neg | +0.048 | +0.037 | +0.056 |

Overlapping M1 paths are not treated as independent row experiments. Event n is primary.

---

## Stages 15–16 — Time and symbol

The whole year remains DEVELOPMENT / DISCOVERY. M1 does not create a holdout.

resid_neg monthly fav−adv is positive except 2026-08 (~0). range_bottom splits stay non-negative. Breakouts and range-top flip by split or by JPY.

Classification:

| Hypothesis | Class |
| --- | --- |
| range_bottom first-touch | BROAD-weak statistical |
| range_top first-touch | UNSTABLE (JPY opposite) |
| breakout_up_24 failure first-touch | UNSTABLE |
| breakout_dn_24 failure first-touch | NO INFORMATION vs base |
| resid_pos reversal first-touch | WEAK / JPY none |
| resid_neg reversal first-touch | BROAD statistical, below G3 |
| Dispersion / activity | not re-opened (frozen, not conditioned) |

---

## Stage 17 — Does M1 change V1 / B?

| # | Question | Answer |
| ---: | --- | --- |
| 1 | How much M5 ambiguity did M1 resolve? | **73.1%** of M5_AMBIGUOUS 60m/1× events get a unique M1 order; **26.6%** stay same-minute ambiguous. Pooled M5 ambiguous rate here is **34.8%** (actual ~0.80 pip hurdle, not V1’s modeled 1.0). |
| 2 | Range-bottom favorable-first? | Yes, +3.2pp, +0.7pp vs base. |
| 3 | Range-top favorable-first? | Weak +1.9pp; JPY disagrees. |
| 4 | Breakout failure favorable-first? | No material, stable, base-beating effect. |
| 5 | Residual-extreme reversal favorable-first? | resid_neg **+4.8pp**, broad and stable; resid_pos weaker. |
| 6 | Materially stronger than base? | **No.** |
| 7 | Stable in VALIDATION? | resid_neg and range_bottom yes; breakouts no. |
| 8 | Stable across symbols? | resid_neg yes; others no. |
| 9 | Any G3 pass? | **No.** |
| 10 | Did M5 aggregation hide an economically useful path? | **No.** It hid a coin-flip order plus a few-point tilt. That is not an exclusive 1× path. |

V1 “no economically useful event” and B “residual reversal below cost” **stand**. C adds: M1 can **name the first side** more often than M5 can, and that name is not worth trading.

---

## Stage 18 — Verdict

**Exact verdict:** `C_RESOLVES_PATH_BUT_BELOW_G3`

`C_PASS_PATH_INFORMATION` is not returned and would not have authorized training.

---

## Stage 19 — Next research decision

**NEW EXTERNAL INFORMATION RESEARCH**

A, B, and C have now spent the authorized **on-disk and downloadable price stack**: M5 mid, historical bid/ask, activity, six-pair residual/dispersion, and M1 path order. None passed G3.

The remaining V2 plan branches that are **not** a re-cut of these prices are calendar / macro / rates (V2 experiments D/E). Those require **new dated external series**, not more M1/M5 mining.

Not chosen now:

- **LONGER-TIMEFRAME TARGET RESEARCH** — every-bar and event closes already failed at 15–480m; stretching the same events further does not create uniqueness.
- **ACCUMULATE NEW FUTURE DATA** — the year is already inspected DEVELOPMENT / DISCOVERY; more months do not un-inspect it.
- **STOP QUANT V2 FOR NOW** — reasonable if the human does not want external data. C itself does not require that stop.

**Do not run the next branch in this task.**

---

## What was not done

- No production / `_quant_stub_vote` / BUY/SELL / SL/TP / ATR / risk / session / RL / API / execution change
- No M1 signals or event filters implemented
- No model trained
- No download except the authorized six-pair M1 history
- No bot restart
- M5 source CSVs not modified

---

## Tests

Focused tests in `tests/test_quant_v2_experiment_c.py`: M1 granularity (default remains M5), M1 MBA parse, separate M1 cache path, causal t+5m boundary, forming-bar exclusion, UP / DOWN / NEITHER / same-candle ambiguity, missing M1 → INSUFFICIENT_DATA, event-time half-spread and JPY pips, frozen event definitions, reversal side map, base-rate helper, split preservation, bootstrap seed 42, M5 immutability, no lookahead.

`python -m pytest -q --tb=line`: **396 passed**, **0 failed**, **0 skipped**, **32.39s**.
