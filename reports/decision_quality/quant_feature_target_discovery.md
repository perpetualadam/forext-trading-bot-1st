# QUANT FEATURE AND TARGET DISCOVERY

**Scope:** Leakage-safe feature/target discovery on six M5 mid series.  
**Not included:** production changes, stub edits, SL/TP, RL, ATR experiments, final model training.

Started: 2026-09-18T22:14:15Z  
Finished: 2026-09-18T22:17:18Z

Prior reports read: `baseline_12m_quant_offline.md`, `baseline_12m_diagnostic.md`, `quant_stub_forensic_audit.md`, `quant_stub_component_study.md`.

The current SMA stub is **not** assumed to deserve a seat in a replacement model. It remains only as a reference baseline.

---

## EXECUTIVE VERDICT

**FEATURE SET NOT YET SUFFICIENT**

A weak, temporally repeated **mean-reversion** pattern exists: bars near the bottom of the last-24-bar range (and the most negative short returns) have slightly positive subsequent mid returns; bars near the top have slightly negative ones. That pattern appears in TRAIN, VALIDATION, and DISCOVERY_TEST.

It is **not large enough to clear spread**. Typical 60-minute signed move in the extreme quintile is ~0.1–0.65 pips versus a **~1.08 pip mean half-spread**. A fixed L2 logistic model on 14 features reaches **AUC ≈ 0.523** and accuracy **51.3%** on DISCOVERY_TEST versus **51.1% always-UP**. Ablating any family barely changes that.

SMA continuation, HTF direction, and the current stub are at or **below** a coin flip.

Do **not** train or deploy a replacement quant model from this set.

**DISCOVERY_TEST warning:** the last 25% (after 2026-06-02 05:05 UTC) was inspected here. A later model-development phase **must not** treat this same window as a pristine unused holdout. Use a new holdout, later data, or nested walk-forward.

---

## STAGE 1 — Dataset integrity

| symbol | rows | earliest UTC | latest UTC | dups | incomplete | expected weekend gaps | unexpected gaps |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| EUR_USD | 74572 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 39 |
| GBP_USD | 74555 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 53 |
| USD_JPY | 74557 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 51 |
| AUD_USD | 74563 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 47 |
| USD_CAD | 74560 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 48 |
| USD_CHF | 74514 | 2025-09-01 00:00 | 2026-08-31 23:50 | 0 | 0 | 34 | 82 |

Total raw rows: **447,321**. SHA256 fingerprints stored in the data JSON. Gaps were **classified, not repaired**. Unexpected gaps are holiday/short holes; no interpolation.

Primary price: **MID**. Bid/ask columns exist on the CSVs and were not used for targets.

---

## STAGE 2 — Frozen chronological splits

Pooled-time quantiles (consistent across symbols):

| partition | UTC rule | n after warmup |
| --- | --- | ---: |
| TRAIN | ≤ 2026-03-03 12:15 | 223370 |
| VALIDATION | ≤ 2026-06-02 05:05 | 111828 |
| **DISCOVERY_TEST** | after that | 111829 |

This TEST window is **OOS for the stub era** but **in-sample for this discovery process** because we inspect it below.

---

## STAGE 3 — Frozen targets

At completed candle `t` (CSV timestamp = M5 start; close is that bar’s completed mid):

`y = close[t + h] − close[t]`

Horizons: 5, 15, 30, 60, 120, 240 minutes (1, 3, 6, 12, 24, 48 bars).

For each: raw price change, percent, pips (JPY pip=0.01), ATR-normalized, sign UP/DOWN (zero stays 0; no neutral band).

**Alignment proof:** `ret_n` uses `close[t] − close[t−n]`. Targets use `close.shift(−h)`. HTF rows are `merge_asof` on `htf_end ≤ t` so an unfinished H1/H4/M15 never joins.

---

## STAGE 4 — Feature families

47 continuous/coded features, predeclared, not searched. Families: price action, trend (SMA 5/20/50 + EMA 12/26 only), momentum, volatility, candle, extension, breakout (24/72), closed HTF, session/regime.

SMA stub features are **reference only**.

Cache: `data/research/quant_features/six_pair_features.pkl` (447,027 warmup-complete rows). Source CSVs untouched.

---

## STAGE 5 — Correctness tests

Automated tests cover: target shift, train-only quintiles, JPY pip size, closed HTF, rolling returns, chronological splits. See `tests/test_quant_feature_discovery.py`.

---

## STAGE 6 — Distributions

No constant features. All candidates have finite mass after warmup. Scales: percent returns ~1e-4; ATR-normalized ~O(1); JPY and majors share ATR-normalized space. Hour sin/cos bounded [−1, 1].

---

## STAGE 7 — Redundancy (TRAIN |corr| ≥ 0.90)

Highly redundant groups (prefer the simpler name):

| keep | drop (suggested) |
| --- | --- |
| `ret_1` / `ret_1_atr` | `signed_body_atr` (0.98 with ret_1_atr) |
| `ret_12_atr` | `rsi14`, `dist_sma20_atr`, `dist_rollmean24_atr` |
| `sma20_slope_atr` | `ema12_26_diff_atr` |
| `range_atr` | `tr_atr` |
| `hour_sin/cos` | London hour sin/cos |
| range position | `dist_sma20_atr` / roll-mean distance |

`pos_in_range_24` is correlated with SMA distances but is the more interpretable range location. It is **retained as a concept**, not auto-dropped because it scored well later.

---

## STAGE 8 — Univariate quintiles (TRAIN edges frozen)

**Most consistent pattern: mean reversion in short location / return.**

`pos_in_range_24` (q1 = near 24-bar low, q5 = near high), 60m mid pips:

| split | q1 mean / %pos | q5 mean / %pos |
| --- | --- | --- |
| TRAIN | +0.11 / 52.1% | −0.16 / 48.4% |
| VALID | +0.65 / 53.4% | −0.69 / 47.2% |
| DISCOVERY_TEST | +0.35 / 53.4% | −0.25 / 48.0% |

Valid/test are monotonic q1 > q2 > q3 > q4 > q5 in hit rate.

`ret_1` 60m: q1 (down-bar) +0.22 / 51.6% train, +0.44 / 52.8% valid, +0.10 / 52.3% test. q5 mixed/negative.

`sma5_20_diff_atr` q5 (strong fast>slow) is **negative** on valid (−0.42) and flat/negative on test — SMA continuation is the *bad* tail.

`atr_pctile` and `rv_ratio` quintiles **change sign across splits**. **UNSTABLE.**

---

## STAGE 9 — Signed features → future sign (60m)

| feature | train hit | valid hit | discovery_test hit |
| --- | ---: | ---: | ---: |
| `ret_1` | 49.58% | 49.05% | 48.96% |
| `ret_6` | 49.46% | 48.58% | 48.36% |
| `sma_state` | 49.45% | 48.49% | 48.53% |
| `sma5_20_diff_atr` | 49.45% | 48.50% | 48.53% |
| `h1_ret` | 49.32% | 49.41% | 49.47% |
| `m5_vs_h1` | 49.98% | 49.84% | 50.27% |

**Continuation sign of recent return or SMA state does not predict future sign.** Hits are ≤ 50% and slightly worse OOS. That matches the stub forensic: following SMA/last-bar sign is a losing or flat rule.

Mean reversion is the opposite of these sign-hits (q1 vs q5), not “feature sign = future sign.”

---

## STAGE 10 — Horizon structure

For `ret_1` TRAIN q1 (already-down bars), mean future pips stay slightly positive from 5m through 240m (0.09 → 0.57) with %pos ~50.6–52.2. It does **not** reverse into a continuation edge at longer horizons. Magnitude grows slowly and remains **sub-pip at 60m**.

Information class: **weak short-to-medium mean reversion, no useful continuation, no horizon that becomes tradable.**

Do not freeze a winner horizon.

---

## STAGE 11 — Cross-symbol

`ret_1` 60m sign-hit (continuation): USD-quote pairs 49.27%; USD-base pairs 49.32%. Same definition: instrument own mid. **No accidental USD-direction conversion.**

`pos_in_range_24` mean reversion appears on both groups (see stage 8 pooled; per-symbol sign-hits for continuation features are all 48.5–49.6%).

---

## STAGE 12 — Temporal stability

Monthly `ret_1` and `sma_state` 60m continuation hits cluster in 47–51%. No month makes SMA continuation work. The mean-reversion quintile pattern is not a one-month artifact (it appears in all three chronological thirds). Individual months remain noisy — **do not overfit a month.**

---

## STAGE 13 — Dependence-aware uncertainty

Method: (1) overlapping bars; (2) **non-overlapping** every 12th bar (60m horizon); (3) **block bootstrap** blocks of 12 M5 bars, 200 reps, seed **42**.

`ret_1 > 0` → 60m pips (continuation):

| estimator | n | mean | notes |
| --- | ---: | ---: | --- |
| overlapping | 217163 | −0.014 | CI not applicable |
| block bootstrap | 217163 | −0.014 | 5–95% **[−0.097, +0.056]** includes 0 |
| non-overlap | 17985 | −0.093 | still ≤ 0 |

**Hundreds of thousands of rows are not independent.** The continuation mean is indistinguishable from zero once dependence is respected.

---

## STAGE 14 — Simple multivariate (not a deployment model)

Fixed L2 logistic (λ=1, 250 steps, TRAIN-only standardization) on 14 predeclared features. No search. No test-driven selection.

| rule | train acc / AUC | valid acc / AUC | discovery_test acc / AUC |
| --- | --- | --- | --- |
| always UP | 50.77 / 0.50 | 51.17 / 0.50 | 51.11 / 0.50 |
| `ret_1` sign | 49.54 / 0.50 | 49.02 / 0.49 | 48.95 / 0.49 |
| SMA state | 49.44 / 0.49 | 48.49 / 0.48 | 48.52 / 0.48 |
| current stub (5/20 ref) | 49.73 / 0.50 | 48.60 / 0.49 | 49.00 / 0.49 |
| L2 logreg | — | **51.60 / 0.523** | **51.31 / 0.522** |

Logreg balanced accuracy ≈ 0.504: it predicts UP on ~92% of rows. Mean 60m pips when pred-UP: +0.16 valid / +0.06 test. When pred-DOWN (rare): more negative. That is a faint mean-reversion tilt, **not** a calibrated directional engine.

---

## STAGE 15 — Family ablation

Dropping price action, trend, extension, candle, volatility, HTF, or session changes valid/test AUC by ≤ 0.005. **No family is load-bearing.** Dropping HTF does not hurt.

---

## STAGE 16 — Cost hurdle

Production mean **round-trip-style half-spread** ≈ **1.08 pips** (GBP 1.5, others 1.0).

Following feature **sign** (continuation) at 60m: mean signed pips **−0.07 to −0.12** (ratio ≈ −0.07 to −0.11 of half-spread).

Flipping to mean reversion on the same features would be about **+0.07 to +0.35 pips** in extreme quintiles vs **1.08 pips** cost. Classification: **far below spread**.

No SL/TP was run.

---

## STAGE 17 — Feature classification

| feature / family | class | why |
| --- | --- | --- |
| `pos_in_range_24` (and correlated extension) | **WEAK / POSSIBLY USEFUL** | q1 vs q5 mean reversion in train/valid/test; below cost |
| `ret_1`, `ret_6`, short returns | **WEAK / POSSIBLY USEFUL** | same direction; weaker than range position |
| SMA state / `sma5_20_diff_atr` as continuation | **NO REPRODUCIBLE INFORMATION** | hit < 50% valid/test; high quintile loses |
| EMA/RSI/MACD-like trend distances | **REDUNDANT** | TRAIN |corr| ≥ 0.90 with returns/SMA |
| HTF H1/H4 | **NO REPRODUCIBLE INFORMATION** | ~49.5% sign-hit; ablation unused |
| volatility / ATR percentile | **UNSTABLE** | quintile signs flip across splits |
| session hour encodings | **NO REPRODUCIBLE INFORMATION** | ablation unused |
| current stub allow+SMA | **NO REPRODUCIBLE INFORMATION** | acc < always-UP |
| none | **LEAKY / INVALID** | no lookahead found |
| none | **PROMISING FOR MODEL RESEARCH** | nothing clears cost + stability + magnitude together |

---

## STAGE 18 — Target classification

| horizon | class |
| --- | --- |
| 5m | WEAK — same mean-reversion sign, more noise |
| 15–60m | WEAK — clearest quintile separation, still sub-spread |
| 120–240m | WEAK / UNSTABLE — means drift with overlap; not a better target |
| any as a production label | **NO REPRODUCIBLE INFORMATION** large enough to justify training |

Do not pick a “best” horizon from the largest historical mean.

---

## STAGE 19 — Frozen dataset spec (for a *future* phase only)

- Rows: completed M5 mid, six symbols, 2025-09-01–2026-08-31, warmup until SMA50/ATR14/`ret_24` finite.
- Features: families in `FEATURE_FAMILIES`; drop London-hour twins and `tr_atr` / `signed_body_atr` as redundant.
- Targets: `y_pips_*` / `y_dir_*` as specified; mid only.
- HTF: closed bars via `end ≤ t`.
- Missing: leave NaN; do not interpolate gaps.
- Symbol: instrument mid returns, not USD-factor.
- Splits: if modeling later, **create a new holdout**. Do not reuse DISCOVERY_TEST as unused OOS.
- Normalization: TRAIN-only z-score if a linear model is used.
- Cache: `data/research/quant_features/six_pair_features.pkl`.

**Do not train a final model now.**

---

## STAGE 20 — Answers

1. **Reproducible forward information?** A **weak mean-reversion** location/return effect, yes. Continuation/SMA, no.
2. **Strongest family?** Short **extension / range location** and **short returns**, as *reversion*, not trend.
3. **Clearly useless as continuation?** SMA state, current stub, HTF sign, last-bar sign.
4. **Unstable?** Volatility quintiles, SMA high-quintile magnitude, monthly continuation hits.
5. **Keep SMA?** **Not as a directional feature.** At most a redundancy/control.
6. **Short-term price action vs SMA?** Price action (inverted) is the only stable hint. SMA continuation is worse than a coin flip.
7. **Volatility alter predictability?** Not stably.
8. **HTF?** No material contribution.
9. **Mean reversion?** **Yes, weak.**
10. **Continuation?** **No** (hits < 50% OOS).
11. **Horizons?** 15–60m show the quintile gap most cleanly; none is economically large.
12. **Above spread?** **No. Far below.**
13. **Proceed to model training?** **No.**

**Final research verdict: FEATURE SET NOT YET SUFFICIENT**

Why: the only stable directional pattern is a sub-spread mean-reversion tilt. A simple multivariate model does not beat always-UP in any decision-relevant way. Training a replacement quant now would be fitting ~0.52 AUC noise on a discovery-tainted test window.

---

## LIMITATIONS

- DISCOVERY_TEST was viewed.
- Overlapping M5 targets; block bootstrap used only on selected contrasts.
- Logreg is a linear probe, not an exhaustive learner.
- Hybrid production lookbacks (100/200) were not re-imposed; SMA 5/20 is the predeclared research pair.
- Unexpected CSV gaps left as-is.

## NEXT — NOT RUN

A later phase, if any, should start from **range-position mean reversion** with a **new holdout**, cost-aware labels, and **non-overlapping** evaluation — not from SMA-state cloning. Do not implement that now.

---

# TESTING

```
python -m pytest -q --tb=line
340 passed, 0 failed, 0 skipped, 25.67s
```

Production was not changed.

---
