# QUANT STUB COMPONENT STUDY

**Scope:** Read-only diagnosis of SMA state, crossover events, state age, and momentum sign.  
**Not included:** production changes, retraining, threshold search, trade replay, RL, ATR experiments.  
**Primary SMA windows (predeclared):** USD_JPY lookback 50 (SMA 5/25); other pairs lookback 100 (SMA 10/50).  
**Secondary (not optimized):** lookback 200 (SMA 20/100) on the five hybrid pairs.

Started: 2026-09-18T22:03:02Z  
Finished: 2026-09-18T22:05:28Z

This study distinguishes labels A–K from the forensic audit. It does **not** assume momentum is directional. The production stub uses momentum **magnitude only**.

---

## EXECUTIVE DIAGNOSIS

The current quant stub is a **persistent SMA-state assigner** that treats one SMA episode as many bars.

On the 12-month M5 CSVs (447,052 warmup-complete bars; 14,769 SMA episodes):

- **A / J.** SMA state exists on 99.86% of bars. The exact current stub (`state` + `|1-bar pct| > 0.0001` + `ATR > 0`) allows 236,828 bars from only **14,104 episodes** (~17 overlapping bars per episode). Direction-adjusted 60-minute mean = **−0.10 pips**, hit rate **48.8%**.
- **B / H.** The first crossover bar and the first magnitude-qualified bar of each episode are near zero (60m mean +0.01 / +0.03 pips, hit rate < 50%). Those small positives **do not survive** train / validation / test.
- **I.** Repeated qualifying bars after the first signal in the same state are **worse** than the first bar (−0.11 pips at 60m). The stub’s loss is concentrated in **re-using a stale state**.
- **C.** Predeclared age buckets do not show a stable early-age edge. Ages 13–24 are the most negative in-sample, but the size of that hole is **UNSTABLE** across partitions.
- **F / G.** Last-bar return **agreement** with SMA is **worse** than disagreement. Agreement+stub 60m = −0.21 pips (negative in all three partitions). Disagreement+stub is near zero and **UNSTABLE** in sign. Momentum sign is information about *lateness*, not a missing confirmation rule.
- **K.** The exact inverse of the current stub is the arithmetic negation of J (+0.10 pips, 50.4% hit). That is **not** a discovered edge.

**Dependence:** 236,828 stub bars are not 236,828 experiments. Adjacent M5 bars share most of a 60–240m path. Episode-level n is the relevant count for events (about 14k, not 200k+).

Production was not changed.

---

## METHOD

- Source: `data/historical/{symbol}_M5.csv` mid OHLC. No signal-generation backtest.
- SMA / ATR: production `compute_indicators`.
- Side: same comparison as `_quant_stub_vote` (`fast > slow + 1e-6` → BUY).
- Forward return: mid close → mid close, **direction-adjusted pips** (BUY: future−entry; SELL: entry−future). No spread, no SL/TP.
- Horizons: 5, 15, 30, 60, 120, 240 minutes (1, 3, 6, 12, 24, 48 M5 bars).
- Chronological cuts on pooled timestamps: train ≤ 2026-03-03 14:05 UTC; valid ≤ 2026-06-02 06:01 UTC; else test.
- Stub parity: 0 mismatches vs `_quant_stub_vote` on 400 random rows.
- Age buckets **predeclared:** 0, 1, 2–3, 4–6, 7–12, 13–24, 25+. Not searched.

**RAW BAR N** = number of M5 rows in the mask.  
**EVENT/STATE N** = unique namespaced SMA episodes touching that mask.

---

## LABEL MAP

| ID | Meaning | How constructed |
| --- | --- | --- |
| A | SMA STATE | `state ∈ {BUY,SELL}` every bar |
| B | FIRST SMA CROSSOVER | `bars_since_last_cross == 0` |
| C | AGE OF CURRENT SMA STATE | 0 on cross, then 1, 2, … |
| D | 1-BAR MOMENTUM MAGNITUDE | `|pct_change| ≷ 0.0001` (production threshold, unchanged) |
| E | 1-BAR MOMENTUM SIGN | sign of `pct_change` |
| F | AGREEMENT | SMA side == last-bar return sign |
| G | DISAGREEMENT | SMA side != last-bar return sign |
| H | FIRST qualifying bar after crossover | first stub-allow bar in the episode |
| I | EVERY qualifying bar in the state | all stub-allow bars; also split into repeats after H |
| J | CURRENT EXACT QUANT STUB | A + D above threshold + ATR>0 |
| K | EXACT INVERSE | same J mask, opposite signed forward |

---

## INDEPENDENCE

| Object | n | Comment |
| --- | ---: | --- |
| Warmup-complete bars | 447,052 | 6 pairs |
| Bars with SMA state (A) | 446,440 | 99.86% |
| Unique SMA episodes | **14,769** | one crossover each |
| Current-stub bars (J) | 236,828 | 53.0% of bars |
| Unique episodes with a stub allow | **14,104** | ~16.8 J-bars / episode |
| Repeat-qualifying bars (I after H) | 222,724 | 94% of J bars |

A 60-minute forward from bar t shares 11/12 of the path with bar t+1. Means on J are **descriptive of the overlapping bar stream the stub would keep voting**. Episode-level tables (B, H) are the less-dependent event view.

---

## A — SMA STATE (every nonzero bar)

Direction-adjusted mid-to-mid pips. **VERIFIED DESCRIPTIVE RESULT.**

| horizon | raw n | episode n | mean | median | % pos |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5m | 446434 | 14769 | −0.014 | 0.00 | 47.88 |
| 15m | 446422 | 14769 | −0.038 | 0.00 | 48.34 |
| 30m | 446404 | 14769 | −0.073 | −0.10 | 48.41 |
| 60m | 446368 | 14769 | −0.127 | −0.20 | 48.43 |
| 120m | 446297 | 14769 | −0.270 | −0.30 | 48.19 |
| 240m | 446156 | 14769 | −0.102 | −0.30 | 48.87 |

60m by partition: train −0.130 (n=223237 / 7429 ep); valid −0.265 (111598 / 3666); test **+0.016** (111533 / 3686). Sign flips in test. **UNSTABLE.** Hit rate stays < 50% in train/valid and 49.2% in test.

---

## B — FIRST SMA CROSSOVER EVENT

One row per episode. This is the EVENT view.

| horizon | n | mean | median | % pos |
| --- | ---: | ---: | ---: | ---: |
| 5m | 14769 | −0.026 | 0.00 | 47.25 |
| 15m | 14769 | −0.027 | −0.10 | 47.38 |
| 30m | 14769 | −0.091 | −0.20 | 47.62 |
| 60m | 14768 | **+0.011** | −0.10 | 48.41 |
| 120m | 14760 | −0.222 | −0.30 | 48.27 |
| 240m | 14749 | −0.183 | −0.20 | 49.27 |

60m partitions: train +0.118 (7429); valid −0.177 (3660); test −0.016 (3679). **UNSTABLE.** Full-sample 60m near zero is **not** an edge.

Per symbol 60m (event n = raw n): EUR −0.11; GBP −0.04; JPY +0.18; AUD +0.15; CAD −0.15; CHF −0.14. **UNSTABLE** across symbols.

---

## C — STATE AGE (predeclared buckets)

All SMA-state bars. 60m shown; other horizons in the data file. Buckets were **not** tuned.

| age | raw n | episode n | 5m mean / %pos | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| 0 | 14769 | 14769 | −0.026 / 47.3 | −0.027 / 47.4 | −0.091 / 47.6 | +0.011 / 48.4 | −0.222 / 48.3 | −0.183 / 49.3 |
| 1 | 14264 | 14264 | −0.010 / 47.4 | −0.010 / 47.7 | −0.089 / 48.1 | +0.063 / 49.2 | −0.246 / 47.9 | −0.220 / 49.3 |
| 2–3 | 27292 | 13849 | −0.011 / 47.5 | −0.046 / 48.2 | −0.053 / 48.6 | +0.055 / 49.2 | −0.301 / 47.9 | −0.136 / 49.5 |
| 4–6 | 37851 | 13065 | −0.022 / 48.0 | −0.013 / 48.5 | +0.077 / 49.3 | +0.129 / 49.2 | −0.249 / 48.6 | −0.039 / 49.5 |
| 7–12 | 65154 | 11800 | +0.025 / 48.2 | +0.056 / 49.2 | +0.061 / 49.4 | −0.074 / 48.8 | −0.419 / 48.4 | −0.118 / 49.2 |
| 13–24 | 97697 | 9674 | −0.037 / 47.7 | −0.122 / 47.8 | −0.247 / 47.6 | **−0.455** / 47.6 | −0.513 / 48.2 | −0.230 / 48.9 |
| 25+ | 189413 | 6522 | −0.014 / 48.0 | −0.034 / 48.4 | −0.059 / 48.3 | −0.079 / 48.4 | −0.098 / 48.1 | −0.022 / 48.5 |

60m chronological:

| age | train n / mean | valid n / mean | test n / mean | class |
| --- | --- | --- | --- | --- |
| 0 | 7429 / +0.118 | 3660 / −0.177 | 3679 / −0.016 | UNSTABLE |
| 1 | 7161 / +0.208 | 3555 / −0.206 | 3545 / +0.040 | UNSTABLE |
| 2–3 | 13670 / +0.166 | 6840 / −0.284 | 6775 / +0.175 | UNSTABLE |
| 4–6 | 19030 / +0.244 | 9489 / −0.146 | 9321 / +0.174 | UNSTABLE |
| 7–12 | 32771 / −0.002 | 16331 / −0.272 | 16029 / −0.021 | CONSISTENTLY WEAK / NEGATIVE |
| 13–24 | 49413 / −0.336 | 24500 / −1.010 | 23767 / −0.132 | WORSE subgroup; magnitude UNSTABLE |
| 25+ | 93763 / −0.231 | 47223 / +0.091 | 48417 / +0.048 | UNSTABLE |

**Does information decay as the state ages?** Full-sample 60m is less negative at ages 0–6 than at 13–24, but **validation is negative in every early bucket**. That is not a verified decay-to-zero edge. It is consistent with **stale-state bars adding overlapping negative observations**, especially 13–24.

Same pattern on stub-allow-only ages (J ∩ age): age 0 stub 60m +0.10 overall, but valid −0.25 / test +0.38. **UNSTABLE.**

---

## D — MOMENTUM MAGNITUDE (threshold unchanged)

Among SMA-state bars:

| mask | raw n | episode n | 60m mean | 60m %pos |
| --- | ---: | ---: | ---: | ---: |
| `|ret| > 0.0001` (D pass = J) | 236828 | 14104 | −0.102 | 48.78 |
| `|ret| ≤ 0.0001` (D fail) | 209612 | 14101 | −0.155 | 48.03 |

The production magnitude gate **does not select a positive subset**. Both sides of the threshold are negative. D-fail is slightly worse. Do not retune the threshold here.

---

## E / F / G — MOMENTUM SIGN vs SMA

Last-bar return sign is **almost a coin flip** vs SMA (agree 218,096 vs disagree 212,415).

### Four-way (all SMA-state bars, 60m)

| cell | raw n | episode n | mean | %pos |
| --- | ---: | ---: | ---: | ---: |
| SMA BUY + +ret (F) | 112424 | 7081 | −0.140 | 48.79 |
| SMA BUY + −ret (G) | 107920 | 7239 | +0.007 | 49.97 |
| SMA SELL + −ret (F) | 105672 | 7052 | −0.254 | 46.66 |
| SMA SELL + +ret (G) | 104495 | 7202 | −0.120 | 48.28 |

### Four-way restricted to current stub allow (J)

| cell | raw n | episode n | 5m | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BUY + +ret (agree) | 61643 | 6370 | −0.037 / 47.6 | −0.069 / 47.7 | −0.114 / 48.2 | −0.132 / 49.0 | −0.224 / 48.9 | +0.018 / 50.0 |
| BUY + −ret (oppose) | 58565 | 6909 | +0.058 / 50.4 | +0.088 / 51.0 | +0.107 / 50.8 | +0.132 / 50.8 | +0.124 / 50.6 | +0.521 / 51.2 |
| SELL + −ret (agree) | 58961 | 6308 | −0.064 / 46.8 | −0.129 / 46.7 | −0.207 / 46.7 | −0.289 / 46.5 | −0.466 / 46.5 | −0.503 / 46.7 |
| SELL + +ret (oppose) | 57659 | 6900 | +0.029 / 49.0 | +0.017 / 49.4 | −0.024 / 49.3 | −0.118 / 48.8 | −0.355 / 47.8 | −0.197 / 47.9 |

### Agree vs oppose on stub-allow bars

| group | raw n | episode n | 60m mean | 60m %pos |
| --- | ---: | ---: | ---: | ---: |
| F agree + stub | 120604 | 12678 | **−0.209** | 47.78 |
| G oppose + stub | 116224 | 13809 | +0.008 | 49.81 |

60m partitions, stub-allow:

| group | train | valid | test |
| --- | --- | --- | --- |
| F agree | 62843 / −0.138 | 31319 / −0.501 | 26432 / −0.031 |
| G oppose | 60608 / −0.066 | 30191 / −0.013 | 25412 / +0.207 |

**F is CONSISTENTLY NEGATIVE** across partitions (still ~48% hit). **G is UNSTABLE** (negative then near-zero then +0.21).

BUY+oppose stub is the only four-way cell with the same 60m sign in train/valid/test (+0.09 / +0.18 / +0.17) and hit rate ~50–52%. Classification: **STABLE CANDIDATE as a relative descriptive pattern only.** Mean is ~0.13 pips / 60m before spread — **not an edge**, and bars are overlapping. **Do not change production to require agreement.** Agreement is the *worse* cell.

Per-symbol 60m agree+stub: all negative except USD_CHF +0.07. Oppose+stub mixed (EUR/JPY/CHF small positive; GBP/AUD negative).

---

## H / I — EVENT vs PERSISTENT STATE

| view | raw n | episode n | 60m mean | 60m %pos | 60m train | 60m valid | 60m test |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| B crossover bar | 14769 | 14769 | +0.011 | 48.41 | +0.118 | −0.177 | −0.016 |
| H first stub-allow in episode | 14104 | 14104 | +0.030 | 48.92 | +0.106 | −0.199 | +0.108 |
| I every stub-allow bar | 236828 | 14104 | −0.102 | 48.78 | −0.102 | −0.261 | +0.085 |
| I repeats only (after H) | 222724 | 13141 | −0.111 | 48.77 | −0.115 | −0.265 | +0.084 |

**VERIFIED:** the current stub **re-treats one SMA episode as many signals**. 94% of allowed bars are repeats inside an already-opened state. Those repeats are the more negative set.

H is not a stable positive event (validation −0.20). The structural finding is about **duplication**, not about a tradable first-cross rule.

665 episodes never produce a magnitude-qualified bar (14769 − 14104).

---

## J — CURRENT EXACT QUANT STUB

Same allow rule as production. Forwards ignore spread/SL/TP (so this is cleaner than the −0.20R trade book).

| horizon | n | mean pips | median | % pos |
| --- | ---: | ---: | ---: | ---: |
| 5m | 236824 | −0.004 | 0.00 | 48.45 |
| 15m | 236819 | −0.024 | 0.00 | 48.69 |
| 30m | 236814 | −0.061 | −0.10 | 48.72 |
| 60m | 236805 | −0.102 | −0.10 | 48.78 |
| 120m | 236798 | −0.230 | −0.30 | 48.46 |
| 240m | 236766 | −0.040 | −0.30 | 48.98 |

Per symbol 60m: EUR −0.07; GBP −0.28; JPY +0.04; AUD −0.27; CAD −0.15; CHF +0.12. Hit rates 48.0–49.5%. **NO MATERIAL directional edge** on any pair.

This is the bar-stream analogue of the 12-month trade diagnostic (negative / sub-50% hit). Trade expectancy is worse because of spread and 2R geometry.

---

## K — EXACT INVERSE OF CURRENT STUB

Same 236,828 bars; signed return flipped.

| horizon | mean pips | % pos |
| --- | ---: | ---: |
| 5m | +0.004 | 48.65 |
| 15m | +0.024 | 49.78 |
| 30m | +0.061 | 50.13 |
| 60m | +0.102 | 50.44 |
| 120m | +0.230 | 50.97 |
| 240m | +0.040 | 50.66 |

**VERIFIED** that K = −J in the mean. Hit rate is not exactly `1 − J` because of zeros. **NOT an edge:** ~50% hits and ~0.1 pip / hour before cost. Implementing the inverse would still pay spread.

---

## SECONDARY SMA (lookback 200, not optimized)

Five hybrid pairs only. Longer SMAs → fewer episodes (5,155 vs ~10,580 on those pairs at lookback 100).

| group | raw n | episode n | 60m mean | 60m %pos |
| --- | ---: | ---: | ---: | ---: |
| A state | 371886 | 5155 | −0.055 | 48.83 |
| B cross | 5155 | 5155 | −0.022 | 48.57 |
| J stub | 198115 | 5074 | −0.039 | 49.01 |

Same qualitative picture: state almost always on, stub slightly negative, cross not helpful. **Not selected as better.**

---

## ROOT READ-ACROSS TO THE −0.1995R BOOK

| Forensic fact | This study |
| --- | --- |
| Stub is SMA STATE, not a cross | A is 99.86% of bars; B is 3.3% |
| Momentum sign ignored | F vs G: agreement is worse, not better |
| Persistent runs of hours | 14,769 episodes vs 446k state bars; J reuses each episode ~17 times |
| No sign inversion | K is just −J; J hit rate < 50% |
| No lookahead | Forwards start at the next M5 close after the feature bar |

The trade book loses because the **same no-edge state is entered after costs**. Repeating the vote on later bars of that state does not add independent predictive information.

---

## WHAT THE DATA SUPPORTS

- Current stub ≈ slightly negative mid-to-mid drift plus sub-50% hit rate at 5–240m.
- Almost all stub allows are **repeat bars in an existing SMA episode**.
- Momentum **agreement** with SMA is associated with **worse** subsequent signed returns (late / already-moved).
- Age 13–24 is a worse *full-sample* bucket; not a stable tradable rule.
- Inverse stub is not a model — it is −J.

## WHAT THE DATA DOES NOT SUPPORT

- A usable first-crossover edge.
- Requiring momentum-sign agreement as a live filter.
- Calling BUY+oppose an edge (hit rate ~51%, ~0.1 pip / 60m, overlapping bars).
- Decay-with-age as a tuned trading schedule.
- Any change to production from this file.

## LIMITATIONS

- Mid-to-mid, no spread/SL/TP (by design). The live/offline trade book is harsher.
- Primary lookback is forensic-matched (50/100), not the hybrid ATR switch bar-by-bar.
- Episode forwards still overlap in calendar time when episodes are short.
- Multiple subgroups inspected; relative “least bad” cells are not edges.

## NEXT EXPERIMENTS — NOT RUN

1. **Cooldown / one-vote-per-episode (research trades only)**  
   Hypothesis: entering only on H (first qualify) reduces trade count and may change R expectancy vs entering on every J bar that also has a free slot.  
   Evidence: I-repeats are 94% of J and more negative in pips.  
   Variable: at most one offline entry per episode.  
   Fixed: SMA rule, SL/TP, spread.  
   OOS: test-split trade expectancy must be shown; do not go live on pip tables.

2. **Do not implement momentum-agreement.**  
   Evidence: F is worse than G. If anything were measured next, it would be *disagreement* as a descriptive split — still not a live rule.

Do not run ATR grids, invert the stub live, or retrain.

---

# TESTING

Focused tests in `tests/test_quant_stub_components.py`: SMA orientation, age=0 then increment, predeclared buckets, agree/oppose, first-qualify-once, stub ignores momentum sign, inverse = negation.

```
python -m pytest -q --tb=line
333 passed, 0 failed, 0 skipped, 26.22s
```

Production trading modules were not changed.

---
