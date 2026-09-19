# QUANT STUB FORENSIC AUDIT

**Scope:** Read-only forensics of the production quant direction function.  
**Not included:** retraining, parameter search, production changes, full six-pair replay, RL, ATR experiments.  
**Known baseline context:** 18,689 QUANT/OFFLINE trades, expectancy −0.1995R; direction-adjusted forwards negative at 5–240m.

Started: 2026-09-18T21:55:32Z

---

## STAGE 1 — Inventory all quant-related code

**Status:** COMPLETED  
**Started:** 2026-09-18T21:55:32Z  
**Finished:** 2026-09-18T21:58:00Z  
**Elapsed:** 148s  
**Classification:** VERIFIED

### Exact production function

Direction originates in `forex_bot/ai_ensemble.py` function `_quant_stub_vote`.

Live call chain:

```
M5 candles (OANDA fetch_ohlcv, complete mid candles only)
  → compute_indicators(raw, HYBRID_ROUTE_LOOKBACK)     # routing ATR only
  → select_strategy(symbol, df_route)                   # name + lookback; NOT side
  → compute_indicators(raw, lookback)                   # MA/ATR used by stub
  → volatility_ok
  → seq_model / compute_nn_pred                         # payload only; unused by stub
  → ai.vote(payload) → LocalLLM.predict → _quant_stub_vote
  → RL same-side gate (not in QUANT/OFFLINE baseline)
  → SL/TP + sizing + execution
```

Offline QUANT/OFFLINE baseline uses the same stub via `production_quant_decision` / `evaluate_signal_cached`. RL and API voters are omitted.

### Dependency map

| Stage | File | Function | Role in BUY/SELL |
| --- | --- | --- | --- |
| M5 candles | `oanda_client.fetch_ohlcv` / historical CSV | last **complete** mid bar | price source |
| Indicators | `indicators.compute_indicators` | SMA `ma_fast`/`ma_slow`, ATR; `pct_change` computed by caller | features |
| Routing | `strategy_meta.select_strategy` | chooses lookback (50/100/200) | changes MA windows, **not** side |
| Quant vote | `ai_ensemble._quant_stub_vote` | MA state → BUY/SELL; `|returns|`+ATR → allow | **originates side** |
| Ensemble | `AIEnsemble.vote` | aggregates voters | quant-only when `ENSEMBLE_MODE=quant` |
| Offline | `decision_quality.signal.production_quant_decision` | same stub | baseline side |
| Offline fast | `decision_quality.fast_cache.evaluate_signal_cached` | same stub | baseline impl |
| Unused by stub | `nn_pred.compute_nn_pred`, `SeqModel` | payload hints | **do not change stub side** |
| Unused by stub | RSI, MACD, Bollinger, HTF, regime, strategy name | research/routing | **do not change stub side** |

### File inventory (quant-related)

**Production**
- `forex_bot/ai_ensemble.py` — `_quant_stub_vote`, `LocalLLM`, `ExternalLLMAPI` (unused constructor), `AIEnsemble.vote`
- `forex_bot/indicators.py` — SMA/ATR used as inputs
- `forex_bot/bot_loop.py` — live payload (`ma_fast`, `ma_slow`, `returns=pct_change`, `atr`)
- `forex_bot/backtest.py` — same payload as live
- `forex_bot/strategy_meta.py` — lookback selection; `SeqModel` unused by stub
- `forex_bot/nn_pred.py` — unused by stub
- `forex_bot/experiment.py` — `ENSEMBLE_MODE` normalization
- `forex_bot/session_rules.py` — `volatility_ok` gate after/around indicators

**Research**
- `forex_bot/decision_quality/signal.py`
- `forex_bot/decision_quality/fast_cache.py`
- `forex_bot/decision_quality/live_path.py`

**Tests**
- `tests/test_quant_stub_mapping.py`
- `tests/test_decision_quality_engine.py` (`test_quant_direction_matches_production_stub`)
- `tests/test_consensus_truth_table.py` (ensemble, not stub math)
- `tests/test_direction_authority.py`

**Config / docs**
- `.env.example` documents `STUB_*` defaults; comments say unused: `STUB_ALLOW_THRESHOLD` / `STUB_CONFIDENCE_MIN` / `MAX`
- `docker-compose.yml` passes `STUB_*`, `ENSEMBLE_MODE`, lookbacks
- `DEPLOYMENT.md` mentions `AI_DISABLE_STUB`
- Prior audits: `live_decision_gate_audit.md`, `baseline_12m_diagnostic.md`

**Model artifacts**
- **None found** (no `.pkl`, `.joblib`, `.pt`, `.pth`, `.onnx`, `.h5`, `.npz`, notebooks)

### What is NOT the quant stub

- RL Q-table (`rl_agent.py`) — separate gate; not this baseline
- API voters — not attached when `ENSEMBLE_MODE=quant`
- Strategy labels — names do not set BUY/SELL
- `seq_model` / `nn_pred` — not read by `_quant_stub_vote`

### Workspace / baseline configuration (VERIFIED)

| Key | Workspace `.env` | Code default | Used by stub? |
| --- | --- | --- | --- |
| `ENSEMBLE_MODE` | `quant` | hybrid | yes (attaches LocalLLM only) |
| `AI_DISABLE_STUB` | `false` | off | ignored in quant mode |
| `STUB_SMA_EPSILON` | unset | `1e-6` | yes |
| `STUB_MOMENTUM_THRESHOLD` | unset | `0.0001` | yes (allow only) |
| `STUB_CONFIDENCE_SCALE` | unset | `1000` | yes (confidence only) |
| `SCALP_LOOKBACK` | `100` | `50` | MA windows |
| `SWING_LOOKBACK` | `200` | `100` | MA windows |
| `DEFAULT_INDICATOR_LOOKBACK` | `50` | `50` | USD_JPY (hybrid off) |
| `HYBRID_ROUTE_LOOKBACK` | `120` | `60` | routing ATR only |
| `HYBRID_USD_JPY` | `false` | off | JPY uses lookback 50 |
| other `HYBRID_*` | `true` | off | scalp vs swing lookback |
| `HYBRID_ATR_SCALP_THRESHOLD` | `1.5` | `1.0` | routing only |
| `NN_PRED_MODE` | `seq` | live noise | **unused by stub** |

No model files. No pickle/joblib weights.

### Unresolved after Stage 1

- Numerical traces (Stage 3)
- Signal frequency (Stage 11)

---

## STAGE 2 — Exact decision equation

**Status:** COMPLETED  
**Started:** 2026-09-18T21:58:00Z  
**Finished:** 2026-09-18T21:59:20Z  
**Elapsed:** 80s  
**Classification:** VERIFIED

### Inputs

| Input | Source | Calculation | Lookback | Normalization | NaN / warmup |
| --- | --- | --- | --- | --- | --- |
| `ma_fast` | `close.rolling(ma_fast_n).mean()` | SMA, **not EMA** despite names | `max(3, min(lookback//10, n-1))` | **raw price** | NaN until window fills; stub rejects NaN MAs |
| `ma_slow` | `close.rolling(ma_slow_n).mean()` | SMA | `max(ma_fast_n+1, min(lookback//2, n-1))` | **raw price** | same |
| `returns` | `close.pct_change().iloc[-1]` | `(c_t - c_{t-1}) / c_{t-1}` | **1 bar** | **fractional return**, not pips | missing → `0.0` via `or 0.0` |
| `atr` | mean true range | rolling mean of TR | `max(7, min(lookback//5, 30, n-1))` | raw price | `<=0` or NaN → `allow=False` |
| `price` | last close | fallback if MA missing | last bar | raw | `0.0` if missing |
| `sma_fast`/`sma_slow` | aliases | preferred over `ma_*` if present | live sets both equal | raw | — |

Period lengths at full history (n much larger than lookback):

| lookback | used when | ma_fast_n | ma_slow_n | atr_n |
| ---: | --- | ---: | ---: | ---: |
| 50 | USD_JPY (hybrid off) / legacy | 5 | 25 | 10 |
| 100 | scalp pool | 10 | 50 | 20 |
| 200 | swing pool | 20 | 100 | 30 |

### Pseudocode (production)

```
eps = 1e-6
mom_thr = 0.0001

if ma_fast is NaN or ma_slow is NaN:
    return allow=False, direction=None

if ma_fast > ma_slow + eps:
    direction = BUY
elif ma_fast < ma_slow - eps:
    direction = SELL
else:
    return allow=False, direction=None   # tie / flat

allow = (abs(returns) > mom_thr) and (atr > 0)
confidence = min(1, abs(returns) * 1000)
return allow, confidence, direction
```

### Specific answers

**Does fast MA > slow MA imply BUY or SELL?**  
**BUY.** VERIFIED in code and `test_quant_stub_mapping.py`.

**Does positive momentum imply BUY or SELL?**  
**Neither.** Momentum **sign is discarded**. Only `abs(returns)` is used, and only for `allow` and `confidence`. Positive or negative 1-bar return does **not** flip side.

**What happens when MA and momentum disagree?**  
Side follows **MA**. If `|returns| > 0.0001` and ATR>0, the trade is still **allowed** against the last-bar return. Example: fast>slow (BUY) with negative 1-bar return still BUY+allow.

**STATE vs EVENT?**  
**STATE.** There is no previous-bar MA comparison, no cross detection, no “was below, now above.” The docstring says “MA cross”; that comment is **incorrect**. The rule is `fast > slow` on the current closed bar.

**SKIP / neutral?**  
Yes, as `allow=False` and/or `direction=None`:
- `|ma_fast - ma_slow| <= 1e-6` → no direction
- `|returns| <= 0.0001` → direction set, **not allowed** (live and offline both skip)
- `atr <= 0` → same
- NaN MAs → no direction

If MAs are unequal by more than 1e-6 (almost always, after warmup), the stub **assigns a side**. Allow is then a weak 1-bar |return| filter. So it is a **near-continuous direction assigner**, not a selective event signal. Frequency quantified in Stage 11.

**Tie handling:** MA tie → no signal. Ensemble tie-break BUY is irrelevant in quant-only mode with one voter.

**Sign convention:** MAs compared in quote-currency price units. BUY means expect price up. `returns` is close-to-close percent (positive = up). JPY uses the same percent formula; pip size is not used for direction.

---

## STAGE 3 — Trace real examples

**Status:** COMPLETED  
**Started:** 2026-09-18T21:57:12Z  
**Finished:** 2026-09-18T21:57:41Z  
**Elapsed:** 29s  
**Classification:** VERIFIED DESCRIPTIVE RESULT  
**Method:** `compute_indicators` + `_quant_stub_vote` on persisted M5 CSVs at fixed indices. **No trade simulation.** Lookback = 50 on USD_JPY (hybrid off), 100 on the other five.

Independent SMA recompute at i=15000 matched `compute_indicators` to floating-point noise (≤ 2.2e-16) on all six pairs.

### Representative traces

| symbol | time UTC | close | ma_fast | ma_slow | ret_1 | MA | MOM | vote | allow | class |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| EUR_USD | 2025-09-24 08:50 | 1.177020 | 1.177305 | 1.179011 | +0.000212 | SELL | BUY | SELL | True | DISAGREE |
| EUR_USD | 2025-12-31 20:35 | 1.174910 | 1.174477 | 1.173787 | +0.000153 | BUY | BUY | BUY | True | AGREE BUY |
| GBP_USD | 2025-12-31 21:20 | 1.347700 | 1.347683 | 1.346031 | −0.000126 | BUY | SELL | BUY | True | DISAGREE |
| GBP_USD | 2026-06-22 09:45 | 1.323170 | 1.322433 | 1.320808 | +0.000370 | BUY | BUY | BUY | True | AGREE BUY |
| USD_JPY | 2025-09-24 08:55 | 148.266 | 148.2606 | 148.1134 | +6.7e-6 | BUY | BUY | BUY | False | NEAR-THRESHOLD mom |
| USD_JPY | 2025-10-08 18:55 | — | — | — | +0.000157 | SELL | BUY | SELL | True | DISAGREE |
| AUD_USD | 2025-09-24 08:55 | 0.661300 | 0.661184 | 0.661860 | +0.000242 | SELL | BUY | SELL | True | DISAGREE |
| USD_CAD | 2025-12-31 21:10 | 1.372340 | 1.372077 | 1.372123 | −0.000335 | SELL | SELL | SELL | True | AGREE SELL |
| USD_CHF | 2025-09-24 09:00 | 0.793840 | 0.793952 | 0.792890 | −0.000151 | BUY | SELL | BUY | True | DISAGREE |
| EUR_USD | 2025-10-13 23:00 | — | diff=−4e-7 | — | — | FLAT | — | None | False | NEAR-THRESHOLD MA |

Manual EUR_USD 2025-12-31 20:35 check: `1.174477 > 1.173787 + 1e-6` → BUY; `|0.000153| > 0.0001` and ATR>0 → allow. Matches implementation.

Window 8000:12000 (4000 bars) found MA/momentum disagreement on every symbol among *allowed* votes (738–1292 bars). High-vol and low-vol examples exist; low-vol more often fails the |return| allow gate.

---

## STAGE 4 — Sign / orientation audit

**Status:** COMPLETED  
**Started:** 2026-09-18T21:59:20Z  
**Finished:** 2026-09-18T22:00:10Z  
**Elapsed:** 50s  
**Classification:** VERIFIED CORRECT (no inversion found)

Checked on all six pairs:

| Hypothesis | Result |
| --- | --- |
| BUY/SELL labels swapped | **NOT FOUND.** fast>slow is BUY on EUR and JPY traces. |
| Momentum sign inverted | **N/A as a side input.** Sign is unused. |
| Return sign inverted | **NOT FOUND.** `pct_change` is `(c_t-c_{t-1})/c_{t-1}`; EUR up-bar was positive. |
| MA ordering inverted | **NOT FOUND.** Independent SMA(fast) vs SMA(slow) matches code. |
| BASE/QUOTE confusion | **NOT FOUND.** Direction is quote-price up/down, same for USDXXX and XXXUSD. |
| JPY pip affecting direction | **NOT FOUND.** Direction does not use pip size. JPY MAs compared in yen. |
| Comparison operators reversed | **NOT FOUND.** |
| Accidental negation | **NOT FOUND.** |
| Label / class-index reversal | **N/A.** No classifier. |

**Important:** even a complete BUY/SELL inversion would **not** explain the −0.1995R book. Swapping labels only swaps the two already-negative sides. The 12-month diagnostic showed **both** directions lose. Orientation error is therefore **not** the cause of negative expectancy.

JPY vs majors: MA *differences* are in different price units (0.15 JPY vs 0.001 EUR) but the comparison sign is consistent.

---

## STAGE 5 — Temporal alignment / lookahead

**Status:** COMPLETED  
**Started:** 2026-09-18T22:00:10Z  
**Finished:** 2026-09-18T22:01:00Z  
**Elapsed:** 50s  
**Classification:** VERIFIED — no lookahead; STATE is naturally lagged

| Feature | Candles used | Closed? | When known |
| --- | --- | --- | --- |
| `ma_fast` / `ma_slow` | last `ma_*_n` **closes including bar i** | yes (rolling on complete bars) | at close of bar i |
| `returns` | close[i] and close[i−1] | yes | at close of bar i |
| `atr` | TR through bar i, then rolling mean | yes | at close of bar i |
| HTF | **not consumed by stub** | n/a | n/a |

- No `shift()` on MAs. No future `iloc` in the stub.
- Offline: `history_at(df, i)` is `[:i+1]`. Engine evaluates at bar i timestamp; SL/TP path starts at **i+1**.
- Live: `fetch_ohlcv` **drops incomplete** candles. The bot votes on the last complete M5 mid close.
- GBP i=15000 had `close[i] == close[i+1]` by coincidence; eval time still equals bar i. **Not lookahead.**

**Lag (not a bug):** this is a STATE of overlapping SMAs. On the 4000-bar window, identical direction runs had median 12 bars (USD_JPY 5/25) to 35 bars (USD_CHF 10/50), i.e. ~1–3 hours, and swing-200 medians ~55–72 bars (~5–6 hours). The signal can stay BUY long after the last up-bar. That is consistent with “late” trend-following, not an off-by-one indexing error.

Training-label alignment: **N/A** (no trainer).

---

## STAGE 6 — Training history

**Status:** COMPLETED  
**Started:** 2026-09-18T22:01:00Z  
**Finished:** 2026-09-18T22:01:40Z  
**Elapsed:** 40s

| Statement | Class |
| --- | --- |
| Current `_quant_stub_vote` is a hard-coded heuristic | **VERIFIED** (`ai_ensemble.py` since `bd24462` 2026-03-31) |
| No fitted model file exists in the repo | **VERIFIED** (no pkl/joblib/pt/onnx/h5/ipynb) |
| `STUB_*` thresholds are code defaults, not loaded weights | **VERIFIED** (workspace unset; defaults 1e-6 / 0.0001 / 1000) |
| Initial LocalLLM (commit `ec68e8e`) was **random allow + random side** | **VERIFIED** (git show) |
| Stub replaced randomness; docstring still says “MA cross” | **VERIFIED** |
| Someone trained this stub offline | **UNKNOWN** — no script, log, or artifact |
| User report that “the quant stub was difficult to train” | **LIKELY** refers to trying to treat this heuristic/thresholds as a model, or to RL — **not recoverable as a completed training run** |
| Incomplete training system / failed-training fallback | **LIKELY** the name `LocalLLM` / `quant stub` itself is the fallback for missing LLMs |
| Obsolete model no longer loaded | **NO EVIDENCE** of a prior loaded model |

**Classification of current parameters:** hand-written defaults + env lookbacks. Not training output.

---

## STAGE 7 — Target / label audit

**Status:** COMPLETED  
**Started:** 2026-09-18T22:01:40Z  
**Finished:** 2026-09-18T22:02:00Z  
**Elapsed:** 20s

**No training implementation exists for the quant stub.**

| Question | Finding |
| --- | --- |
| Target variable | **NONE** |
| Future horizon the stub was trained to predict | **NONE.** Live/offline do not score a horizon. Research forwards (5–240m) are diagnostic only. |
| BUY/SELL encoding | Immediate if-then on MA state |
| Neutral class | MA flat or (direction set but not allowed) |
| Spread in labels | N/A |
| Overlapping labels | N/A |
| Accidental past-return target | The stub does **not** predict `returns`. It uses last-bar `|returns|` only as an allow gate. That is **not** a future label. |

`feature[t] predicting return t→t+h` was **never implemented**. The 12-month diagnostic later asked that question of the *deployed rule* and found no edge.

---

## STAGE 8 — Feature scaling / normalization

**Status:** COMPLETED  
**Started:** 2026-09-18T22:02:00Z  
**Finished:** 2026-09-18T22:02:20Z  
**Elapsed:** 20s  
**Classification:** PROBLEM FOUND (scale inconsistency on the allow gate, not on MA sign)

| Feature | Scale | Pair-specific? | Persisted stats? |
| --- | --- | --- | --- |
| MAs | raw price | compared within-symbol only | no |
| MA comparison | raw price difference vs 1e-6 | 1e-6 is tiny on JPY and majors | no |
| `returns` | percent | **same 0.0001 threshold on all pairs** | no |
| ATR | raw price | `atr > 0` only | no |

EUR_USD vs USD_JPY do **not** enter a shared learned rule. Direction is within-symbol SMA sign — **sound for side**.

The **allow** gate `|pct_change| > 0.0001` is **not** pip- or ATR-normalized:
- ~1.1 pips on EUR at 1.10
- ~1.5 pips on JPY at 150
- ~0.65 pips on AUD at 0.65

That changes *selectivity* by pair (Stage 11 allow_frac 0.36–0.64) but does not invert direction.

No z-score. No global scaler. Training vs inference stats: **N/A**.

---

## STAGE 9 — Train / validation / test audit

**Status:** COMPLETED  
**Started:** 2026-09-18T22:02:20Z  
**Finished:** 2026-09-18T22:02:40Z  
**Elapsed:** 20s

**Cannot reconstruct a quant-stub training split because no trainer exists.**

The 50/25/25 chronological split in the 12-month diagnostic is a **research partition of already-generated trades**, not a model-fit split. Lookbacks/thresholds were not selected on that test set by a recovered training script.

Leakage modes (shuffle, full-set scaler, future features) **do not apply** to a hard-coded rule. The rule can still be a bad predictor (it is).

---

## STAGE 10 — Training / inference parity

**Status:** COMPLETED  
**Started:** 2026-09-18T22:02:40Z  
**Finished:** 2026-09-18T22:03:00Z  
**Elapsed:** 20s

| Feature | Training calc | Production calc | Difference |
| --- | --- | --- | --- |
| all stub inputs | **no trainer** | `compute_indicators` + `pct_change` + `_quant_stub_vote` | **N/A** |

Live vs offline inference (the real parity that exists):

| Item | Live `bot_loop` | Offline `production_quant_decision` | Match? |
| --- | --- | --- | --- |
| MA / ATR | `compute_indicators(raw, lookback)` last row | same | YES |
| returns | `close.pct_change().iloc[-1]` | same | YES |
| vote | `_quant_stub_vote` via `ai.vote` | `_quant_stub_vote` direct | YES (quant mode) |
| NaN MA | passed as NaN → stub no-signal | replaced with price → usually flat no-signal | equivalent outcome |
| `seq`/`nn_pred` | computed, unused by stub | not computed | unused |
| RL / API | live RL gate; APIs off in this `.env` | omitted | **intentional offline difference** |

**HIGH PRIORITY mismatch:** none between a trainer and live (no trainer). Live vs QUANT/OFFLINE stub math: **parity YES**.

---

## STAGE 11 — Signal frequency / forced decision

**Status:** COMPLETED  
**Started:** 2026-09-18T21:57:12Z  
**Finished:** 2026-09-18T21:57:41Z  
**Elapsed:** 29s (same bounded pass as Stage 3)  
**Sample:** 4000 M5 bars per symbol, indices 8000–11999. Not a trade backtest.

| symbol | lookback | dir BUY | dir SELL | dir NONE | allow n | allow frac | allow agree | dir-run median | dir-run p90 | dir-run max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EUR_USD | 100 | 2109 | 1885 | 6 | 2085 | 0.521 | 0.505 | 28 | 77 | 132 |
| GBP_USD | 100 | 2060 | 1936 | 4 | 2137 | 0.534 | 0.498 | 25 | 75 | 128 |
| USD_JPY | 50 | 1985 | 2015 | 0 | 2474 | 0.619 | 0.514 | 12 | 36 | 78 |
| AUD_USD | 100 | 2090 | 1902 | 8 | 2568 | 0.642 | 0.497 | 32 | 76 | 134 |
| USD_CAD | 100 | 1960 | 2034 | 6 | 1455 | 0.364 | 0.493 | 27 | 71 | 119 |
| USD_CHF | 100 | 1848 | 2149 | 3 | 2304 | 0.576 | 0.522 | 35 | 89 | 173 |

**VERIFIED:** the stub **assigns BUY or SELL on >99.8% of bars**. Neutral is rare (MA equality within 1e-6).

Allow (~36–64%) is the only real filter, and it is 1-bar |percent| noise, **not** directional confirmation (agree ≈ 50%).

Swing lookback 200: even longer runs (median 55–72, max 177–374 bars).

This is a **continuous state classifier**, not a selective event signal. Combined with one-position-at-a-time execution, many assigned bars never become trades; the 18,689 baseline trades are the subset that passed routing/vol/FX-week and had a free slot.

---

## STAGE 12 — Test coverage audit

**Status:** COMPLETED  
**Started:** 2026-09-18T22:03:00Z  
**Finished:** 2026-09-18T22:04:00Z  
**Elapsed:** 60s

| Question | Already proven? | Notes |
| --- | --- | --- |
| BUY orientation | YES | `test_quant_buy_when_fast_above_slow_and_momentum` |
| SELL orientation | YES | matching SELL test |
| MA/momentum disagreement | **added** | side still follows MA |
| JPY same comparison | **added** | |
| Target sign | N/A | no trainer |
| Temporal alignment | partial + **added** `history_at` future-bar test | |
| SMA recompute | **added** | lookback 100 → 10/50 |
| Training/inference parity | N/A trainer; offline matches stub | `test_quant_direction_matches_production_stub` |
| Normalization | confidence scale only | no pip-threshold test previously |
| All six symbols | mapping tests EUR-like; JPY added; traces used all six | |

Existing tests did **not** prove the docstring “cross” claim (and the code is not a cross). They also did not prove a trained target.

---

## STAGE 13 — Forensic conclusion

**Status:** COMPLETED  
**Started:** 2026-09-18T22:04:00Z  
**Finished:** 2026-09-18T22:05:00Z  
**Elapsed:** 60s

| Question | Answer |
| --- | --- |
| CURRENT QUANT TYPE | **HAND-WRITTEN HEURISTIC / FALLBACK STUB** |
| TRAINED MODEL | no |
| PARTIALLY TRAINED | no (RL is separate and not this stub) |
| TRAINING REPRODUCIBLE | **NO** |
| TRAINING/INFERENCE PARITY | **N/A** (no trainer). Live vs offline stub: **YES** |
| SIGN/ORIENTATION | **VERIFIED CORRECT** |
| TEMPORAL ALIGNMENT | **VERIFIED** (close of last complete M5; no future bar) |
| LOOKAHEAD | **NONE FOUND** |
| FEATURE SCALING | **PROBLEM FOUND** on allow-gate percent threshold across pairs; MA sign is sound |
| TARGET CONSTRUCTION | **N/A / UNKNOWN** — no target was implemented |

### Defects and concerns (do not fix in this task)

**CRITICAL**
- None that invert BUY/SELL or leak future prices.

**HIGH**
1. The “quant” direction is **not a trained predictor**. It is `SMA_fast ? SMA_slow` state plus `|1-bar return|` allow. That matches the 12-month finding of no directional edge.
2. Docstring / mental model says **“MA cross” (EVENT)**; implementation is **STATE**. Persistent same-side runs of hours are expected.
3. Momentum **sign is ignored**. Allowed trades are ~50% against the last bar. The name “momentum filter” is misleading.
4. No training target/horizon exists, so “difficult to train” cannot be a failed fit of *this* function — there is nothing to fit.

**MEDIUM**
5. `|returns| > 0.0001` is a **percent** threshold, so allow-rate differs by pair (0.36–0.64 in the sample).
6. Lookback (and therefore SMA lengths) depends on hybrid routing / USD_JPY hybrid-off. Direction formula is the same; sensitivity differs.
7. `LocalLLM` / `ExternalLLMAPI` names hide a non-LLM rule. `ExternalLLMAPI.predict` is a second copy of the stub and is never constructed.

**LOW**
8. `STUB_*` env vars exist but are unset; defaults are implicit.
9. Ensemble empty-vote path still returns `direction="BUY"` with `allow=False` — unused in quant mode with LocalLLM attached.
10. Live invalid-direction coerce to BUY is after the stub; stub itself returns None on flat.

### Answers to the ten primary questions

1. **What is it?** A deterministic if-then on SMA state + ATR presence + absolute 1-bar percent return.
2. **Is it trained?** **No.**
3. **How trained?** Not applicable.
4. **Persisted learned state?** **None.**
5. **Features for BUY/SELL?** Only `ma_fast` vs `ma_slow` (raw price). Strategy, HTF, RSI, MACD, nn_pred unused.
6. **Training target?** **None.**
7. **Intended horizon?** **None encoded.** Indicators span 5–100 bars depending on lookback; that is window length, not a forecast horizon.
8. **Current parameters?** **Hand-written defaults** + workspace lookbacks / hybrid flags. Not fitted.
9. **Implementation error explaining negative direction?** **No sign inversion or lookahead found.** The rule is a no-edge trend-state heuristic; costs then make expectancy worse (prior diagnostic).
10. **Training/research/live consistency?** Live and QUANT/OFFLINE share `_quant_stub_vote`. There is no training path to compare.

---

# WHAT THIS AUDIT SUPPORTS

- Negative 12-month directional forwards are the behaviour of a **hand-written SMA-state stub**, not a mis-loaded or inverted trained model.
- BUY means fast SMA above slow SMA. That orientation is correctly implemented on all six pairs.
- The stub is nearly always “on”; it does not wait for a cross.

# WHAT THIS AUDIT DOES NOT SUPPORT

- A missing/corrupt weight file as the cause.
- A BUY/SELL inversion as the cause of bilateral losses.
- Future leakage in the stub features.
- Any claim that the stub was successfully trained on a future-return target.

# LIMITATIONS

- Frequency used 4000-bar windows, not every bar of the year.
- Workspace `.env` hybrid/lookback values may differ from a running container if that container was not recreated; this audit used the workspace file.
- User-reported training difficulty has no repo artifact; classified UNKNOWN/LIKELY only.

# NEXT STEPS — NOT RUN

This audit does not recommend or execute retraining, threshold search, or live changes.

---

# TESTING

```
python -m pytest -q --tb=line
325 passed, 0 failed, 0 skipped, 25.35s
```

Production trading modules were not changed.

---
