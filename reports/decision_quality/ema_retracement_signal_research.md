# EMA TREND + RETRACEMENT SIGNAL RESEARCH

**Scope:** Offline / read-only strategy research against the frozen SMA-state baseline.  
**Not included:** production strategy edits, `bot_loop` behaviour, OANDA execution, entry geometry, profit protection, risk controls, `.env`, Docker, deploys, or live orders.

Harness: `forex_bot/decision_quality/ema_retracement.py`  
Unit tests: `tests/test_ema_retracement_research.py`  
Machine-readable run: `reports/decision_quality/_ema_retracement_results.json`

Cache: six-pair M5 CSVs under `data/historical/` (bid/ask present on every row).  
Chronological cuts (`chrono_masks` 50/25/25 on pooled timestamps): train ≤ **2026-03-03 12:15**; validation ≤ **2026-06-02 05:05**; else test.

---

## CURRENT CODE AUDIT

Verified in source. Comments and prior reports were not treated as authority.

### Where the live quant SMA direction is calculated

1. `forex_bot/indicators.py` `compute_indicators` writes **SMA** columns:
   - `ma_fast = close.rolling(ma_fast_n).mean()`
   - `ma_slow = close.rolling(ma_slow_n).mean()`
2. `forex_bot/bot_loop.py` (evaluate path) reads the last `ma_fast` / `ma_slow`, last 1-bar `pct_change` as `returns`, and last `atr`, then calls `ai.vote(...)`.
3. Default voters (`LocalLLM.predict` / `ExternalLLMAPI.predict`) return `forex_bot/ai_ensemble.py` `_quant_stub_vote`.
4. `_quant_stub_vote` sets side **only** from the SMA comparison:
   - `sma_fast > sma_slow + eps` → `BUY`
   - `sma_fast < sma_slow - eps` → `SELL`
   - else no direction
   - `allow` additionally requires `|returns| > STUB_MOMENTUM_THRESHOLD` (default `0.0001`) and `atr > 0`
   - Momentum is **magnitude only**. Sign of the last return does not flip or confirm the side.

`forex_bot/decision_quality/live_path.py` matches this: strategy names (`trend`, `swing_mean_reversion`, …) label the hybrid pool. They do **not** set BUY/SELL.

RL (`rl_agent.decide`) can SKIP or block a mismatched side. It does not invent a new direction.

### SMA periods currently used

Period scaling in `compute_indicators` when `lookback` is set:

- `ma_fast_n = max(3, min(lookback // 10, cap))`
- `ma_slow_n = max(ma_fast_n + 1, min(lookback // 2, cap))`
- If `lookback` is `None` (legacy): **SMA 5 / 20**

Live lookback comes from `select_strategy` (`forex_bot/strategy_meta.py`), not from a fixed EMA pair:

| Horizon | Env default | Implied SMA on a long M5 series |
| --- | --- | --- |
| scalp | `SCALP_LOOKBACK=50` | **5 / 25** |
| swing | `SWING_LOOKBACK=100` | **10 / 50** |
| legacy | `DEFAULT_INDICATOR_LOOKBACK=50` | **5 / 25** |

This study’s **frozen baseline** reuses the published SMA-state lookbacks (not re-optimized): USD_JPY **50** (SMA 5/25); EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF **100** (SMA 10/50). Confirmed against `compute_indicators` on the cache lengths (`sma_periods` in the run JSON).

### Whether EMA already exists

| Location | What it is | Live BUY/SELL? |
| --- | --- | --- |
| `compute_indicators` MACD | `ewm(span≈12)` − `ewm(span≈26)` (spans capped from SMA periods) | **No.** `macd` is computed and unused by `_quant_stub_vote`. |
| `decision_quality/feature_discovery.py` | Research EMA 12/26 | **No.** Research only. |
| `decision_quality/research_features.py` / `fast_cache.py` | Fields named `ema_slope` / `ema_separation_atr` | **No.** Built from **SMA** `ma_fast`/`ma_slow`, not a standalone EMA trend. Research snapshots / regime labels only. |
| Production entry path | No EMA20/50/100/200 trend state | **No.** |

There is **no** production EMA-trend or EMA-pullback entry.

### Existing retracement / pullback logic

None in the live entry path.

Research-only `distance_from_swing_atr` (`research_features.py`) measures close vs a 20-bar swing high/low in ATR units for snapshots. It is **not** a live filter and does not wait for a retrace-then-resume pattern.

This experiment added research-only ATR-zone retrace and a 50% swing retrace. Those masks are not imported by `bot_loop`.

### Other indicators already implemented

| Indicator | Where computed | Influences live BUY/SELL? |
| --- | --- | --- |
| RSI | `compute_indicators` (`_rsi`) | **No.** Not passed to `_quant_stub_vote`. |
| MACD | `compute_indicators` (EMA 12/26-scaled) | **No.** |
| Bollinger | `boll_up` / `boll_down` | **No.** |
| ATR | `compute_indicators`; used for stub `allow`, SL/TP, volatility gate | **Magnitude / sizing / skip only.** Does not set side. |
| Trend strength | `ma_fast − ma_slow` (SMA difference) | Logged / RL state string. Side still comes from the stub comparison. |
| ADX | `research_features.wilder_adx`, `feature_discovery._wilder_adx_series` | **No.** File header: research-only, never a live filter. |
| Swing distance | `distance_from_swing_atr` | **No.** Snapshot only. |
| Fibonacci | Not implemented in production or prior research harnesses | — |

`bot_loop` vote payload is `price`, `ma_fast`/`ma_slow` (also copied as `sma_*`), `returns`, `atr`, plus strategy/horizon metadata. RSI, MACD, Bollinger, ADX, and swing are absent.

### Audit conclusion for this experiment

The frozen baseline is the current live direction rule: persistent SMA-state + momentum-magnitude gate. EMA trend, retracement, resumption, and mean-reversion fade are **new research families**. They were not back-fitted into production.

---

## EXPERIMENT DESIGN

**Question:** does a trend-following entry improve if we wait for a retracement, and then for a resumption, instead of taking the first SMA/EMA state bar?

Three layers, kept separate:

1. **Trend regime** — fast MA above/below slow MA (SMA frozen baseline, or EMA 20/50, 50/100, 50/200).
2. **Retracement** — after the trend has extended, price comes back toward the trend MA.
3. **Resumption** — after that retrace, close reclaims the fast EMA in the trend direction (BUY if close > fast EMA; SELL if close < fast EMA).

**Frozen baseline (not rewritten):**

- H = first stub-qualifying bar of each SMA episode (`first_qual` from `stub_components.build_component_frame`).
- J = every stub-allow bar (`stub_allow`). Same construction as `quant_stub_component_study.md`.

**EMA trend:** first bar of each contiguous EMA-state episode (`trend_cross`).

**ATR-zone retrace (predeclared):** signed distance `(close − slow_EMA) / ATR` oriented with the trend. Require a prior extension ≥ **0.50 ATR**, then first touch of the zone **[−0.10, +0.25] ATR**. One pull event per episode.

**Resumption:** first later bar in the same episode with close back through the fast EMA.

**Swing retrace (one extra definition, EMA50/200 only):** causal 24-bar high/low range; 50% retrace of that range while close remains on the trend side of the slow EMA; then the same close-vs-fast-EMA resume. Fibonacci 38.2 / 61.8 were **not** searched.

**Mean-reversion (secondary, after the trend families):** first `|close − EMA50| / ATR ≥ 2` of a displacement episode; fade the extension. Re-arm when the z-score returns inside 2 or the sign flips.

**Two measurement layers (not mixed):**

| Layer | Purpose | Costs / geometry |
| --- | --- | --- |
| Forward mid→mid pips | Directional information at 5 / 15 / 30 / 60 / 120 / 240 minutes | No spread, no SL/TP |
| Economic occupancy | Realisable 2R outcome | BUY enters `ask_close`, SELL enters `bid_close`; long exits vs bid extremes, short vs ask extremes; SL = 2×ATR, TP = 2R; one position per symbol |

Book coverage: 100% finite `bid_close` on all six files (74,514–74,572 rows each). No 1-pip fallback was required.

**Selection rule:** no parameter is chosen from the test split. Validation is used only to say which family looked least-bad *before* looking at test. Every predeclared config is reported.

---

## PARAMETERS TESTED

Small predeclared grid. Eleven configs. No search beyond this list.

| Config | Family | Parameters |
| --- | --- | --- |
| `baseline_sma_first_qual` | frozen_baseline | Frozen lookbacks; first stub-qual bar (H) |
| `baseline_sma_every_stub` | frozen_baseline | Frozen lookbacks; every stub bar (J) |
| `ema20_50_trend_cross` | ema_trend | EMA 20/50; first bar of state |
| `ema50_100_trend_cross` | ema_trend | EMA 50/100; first bar of state |
| `ema50_200_trend_cross` | ema_trend | EMA 50/200; first bar of state |
| `ema20_50_pull_resume` | ema_pull_resume | EMA 20/50; ATR-zone 0.50 / 0.25 / −0.10; resume close vs fast EMA |
| `ema50_100_pull_resume` | ema_pull_resume | Same retrace/resume on EMA 50/100 |
| `ema50_200_pull_resume` | ema_pull_resume | Same retrace/resume on EMA 50/200 |
| `ema50_200_pull_only` | ema_pull | EMA 50/200; ATR-zone retrace; **no** resume |
| `ema50_200_swing50_resume` | ema_pull_resume | EMA 50/200; 24-bar 50% swing retrace + resume |
| `mean_reversion_ema50_z2` | mean_reversion | Fade \|close−EMA50\|/ATR ≥ 2 |

Not tested (deliberately): other EMA pairs, Fibonacci 38.2/61.8, RSI/MACD/ADX filters, alternative SL/TP, session filters.

---

## BASELINE RESULTS

Frozen SMA H/J on the same cache and occupancy engine as the EMA families. Forward 60m for H is **+0.03 pips** overall — the same near-zero first-qual result as the published SMA-state study. J is **−0.10 pips** at 60m — the same stale-state drag. The baseline was not rewritten to look worse.

### Economic occupancy (bid/ask, SL=2×ATR, TP=2R)

| Split | n | BUY | SELL | Win rate | Exp. R | PF | Total R | Avg hold (min) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **H overall** | 9238 | 4605 | 4633 | 0.211 | **−0.366** | 0.536 | −3382 | 101 |
| H train | 4461 | 2211 | 2250 | 0.219 | −0.344 | 0.559 | −1536 | 110 |
| H valid | 2374 | 1191 | 1183 | 0.221 | −0.338 | 0.567 | −802 | 98 |
| H test | 2403 | 1203 | 1200 | 0.189 | **−0.435** | 0.464 | −1044 | 87 |
| H BUY | 4605 | 4605 | 0 | 0.221 | −0.338 | 0.567 | −1554 | 103 |
| H SELL | 4633 | 0 | 4633 | 0.202 | −0.395 | 0.506 | −1828 | 98 |
| **J overall** | 21591 | 10867 | 10724 | 0.210 | **−0.370** | 0.531 | −7999 | 94 |
| J train | 10947 | 5505 | 5442 | 0.215 | −0.355 | 0.548 | −3888 | 93 |
| J valid | 5188 | 2625 | 2563 | 0.215 | −0.355 | 0.548 | −1840 | 99 |
| J test | 5456 | 2737 | 2719 | 0.195 | **−0.416** | 0.483 | −2271 | 91 |

H per symbol (economic, all time): every pair negative. Least-bad USD_JPY (−0.246 R, n=1746). Worst USD_CAD (−0.451 R).

### Forward mid→mid pips (mean), H then J

| Config / split | n | 5m | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H all | 14104 | −0.001 | +0.013 | −0.043 | **+0.030** | −0.256 | −0.132 |
| H train | 7170 | −0.016 | −0.009 | −0.012 | +0.104 | −0.122 | −0.079 |
| H valid | 3529 | +0.009 | +0.022 | −0.159 | −0.195 | −0.687 | −0.460 |
| H test | 3405 | +0.018 | +0.050 | +0.011 | +0.108 | −0.093 | +0.095 |
| J all | 236828 | −0.004 | −0.024 | −0.061 | **−0.102** | −0.230 | −0.040 |
| J train | 123346 | +0.003 | −0.008 | −0.039 | −0.100 | −0.320 | −0.375 |
| J valid | 61597 | −0.037 | −0.097 | −0.175 | −0.269 | −0.333 | +0.259 |
| J test | 51885 | +0.019 | +0.022 | +0.023 | +0.090 | +0.106 | +0.405 |

Occupancy trade count is lower than event count because only one position per symbol is open at a time.

---

## EMA TREND RESULTS

First bar of each EMA-state episode. No retrace filter.

### Economic

| Config | Split | n | BUY | SELL | WR | Exp. R | PF | Total R | Hold min |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ema20/50 | overall | 7130 | 3577 | 3553 | 0.213 | −0.360 | 0.542 | −2569 | 97 |
|  | train | 3621 | 1819 | 1802 | 0.216 | −0.353 | 0.550 | −1278 | 99 |
|  | valid | 1732 | 871 | 861 | 0.221 | −0.337 | 0.568 | −583 | 102 |
|  | test | 1777 | 887 | 890 | 0.200 | −0.399 | 0.501 | −708 | 88 |
| ema50/100 | overall | 3651 | 1824 | 1827 | 0.224 | −0.327 | 0.579 | −1193 | 109 |
|  | train | 1901 | 947 | 954 | 0.225 | −0.325 | 0.581 | −617 | 107 |
|  | valid | 822 | 413 | 409 | 0.243 | **−0.270** | 0.643 | −222 | 127 |
|  | test | 928 | 464 | 464 | 0.206 | −0.381 | 0.519 | −354 | 98 |
| ema50/200 | overall | 2518 | 1247 | 1271 | 0.217 | −0.349 | 0.555 | −878 | 123 |
|  | train | 1295 | 633 | 662 | 0.215 | −0.354 | 0.549 | −458 | 126 |
|  | valid | 580 | 287 | 293 | 0.243 | −0.271 | 0.642 | −157 | 122 |
|  | test | 643 | 327 | 316 | 0.198 | −0.409 | 0.490 | −263 | 116 |

### Forward mid→mid (mean pips)

| Config / split | n | 5m | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20/50 all | 9067 | −0.123 | −0.129 | −0.109 | −0.116 | −0.318 | −0.165 |
| 20/50 valid | 2232 | −0.096 | −0.087 | −0.257 | −0.439 | −1.005 | −0.239 |
| 20/50 test | 2188 | −0.075 | −0.206 | −0.258 | −0.233 | −0.075 | +0.369 |
| 50/100 all | 4019 | +0.021 | +0.031 | −0.023 | +0.066 | −0.209 | −0.192 |
| 50/100 valid | 921 | +0.022 | +0.026 | −0.070 | −0.519 | −0.385 | +0.998 |
| 50/100 test | 1005 | −0.081 | +0.110 | +0.126 | +0.353 | +0.283 | +1.184 |
| 50/200 all | 2718 | −0.016 | −0.012 | −0.109 | −0.136 | −0.288 | −0.387 |
| 50/200 valid | 629 | −0.115 | +0.260 | +0.093 | +0.380 | +0.608 | +1.651 |
| 50/200 test | 677 | +0.008 | −0.157 | −0.188 | +0.076 | +0.322 | +1.389 |

EMA50/100 is the least-bad *trend-only* family on validation expectancy (−0.270 vs H −0.338). Test still −0.381 R. Forward signs flip across partitions and horizons. EMA20/50 is worse than H at every listed forward horizon.

**EMA alone does not add usable directional information over the frozen SMA first-qual bar.**

---

## EMA + RETRACEMENT RESULTS

ATR-zone pull **without** resumption, EMA50/200 only (`ema50_200_pull_only`). This is the isolated retracement layer.

### Economic

| Split | n | BUY | SELL | WR | Exp. R | PF | Total R | Hold min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 2183 | 1079 | 1104 | 0.240 | **−0.280** | 0.632 | −611 | 108 |
| train | 1113 | 546 | 567 | 0.240 | −0.280 | 0.631 | −312 | 110 |
| valid | 518 | 260 | 258 | 0.261 | **−0.218** | 0.705 | −113 | 109 |
| test | 552 | 273 | 279 | 0.221 | **−0.336** | 0.568 | −186 | 103 |
| BUY | 1079 | 1079 | 0 | 0.257 | −0.230 | 0.691 | −248 | 109 |
| SELL | 1104 | 0 | 1104 | 0.224 | −0.329 | 0.576 | −363 | 108 |

Validation pick (least-bad economic expectancy among all eleven configs): **−0.218 R**. Still a loss. Test is worse (−0.336 R), so the validation ranking does not survive the untouched period as an edge.

### Forward mid→mid (mean pips)

| Split | n | 5m | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 2271 | +0.066 | +0.105 | +0.203 | **+0.325** | +0.519 | +0.423 |
| train | 1165 | +0.001 | −0.077 | +0.190 | +0.184 | +0.256 | +0.718 |
| valid | 529 | +0.047 | +0.224 | +0.267 | **+0.733** | +1.112 | +0.706 |
| test | 577 | +0.215 | +0.364 | +0.172 | **+0.234** | +0.505 | −0.437 |

This is the only trend-family mask whose **mid-to-mid** 60-minute mean is positive in train, validation, **and** test. The 240-minute test mean flips negative. Per-symbol 60m is not uniform (USD_CAD −0.292; EUR_USD +0.714).

**Waiting for a retracement slightly improves directional drift versus entering on the EMA cross. It does not survive bid/ask + 2R occupancy.**

---

## EMA + RETRACEMENT + RESUMPTION RESULTS

Same ATR-zone pull, then close-through-fast-EMA. Plus the one swing-50% + resume variant.

### Economic

| Config | Split | n | WR | Exp. R | PF | Total R | Hold min |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20/50 pull+resume | overall | 4988 | 0.206 | −0.382 | 0.519 | −1906 | 96 |
|  | valid | 1235 | 0.209 | −0.373 | 0.528 | −461 | 98 |
|  | test | 1237 | 0.196 | −0.412 | 0.487 | −510 | 95 |
| 50/100 pull+resume | overall | 2696 | 0.211 | −0.368 | 0.533 | −993 | 97 |
|  | valid | 628 | 0.205 | −0.384 | 0.517 | −241 | 102 |
|  | test | 675 | 0.207 | −0.379 | 0.521 | −256 | 90 |
| 50/200 pull+resume | overall | 1712 | 0.217 | −0.350 | 0.553 | −599 | 105 |
|  | valid | 405 | 0.237 | −0.289 | 0.621 | −117 | 112 |
|  | test | 421 | 0.200 | −0.401 | 0.499 | −169 | 96 |
| 50/200 swing50+resume | overall | 2388 | 0.215 | −0.354 | 0.549 | −845 | 114 |
|  | valid | 548 | 0.223 | −0.332 | 0.573 | −182 | 128 |
|  | test | 610 | 0.198 | −0.404 | 0.496 | −246 | 99 |

### Forward mid→mid 60m

| Config | all | train | valid | test |
| --- | ---: | ---: | ---: | ---: |
| 20/50 pull+resume | −0.007 | −0.264 | +0.117 | +0.389 |
| 50/100 pull+resume | −0.166 | −0.437 | +0.164 | +0.090 |
| 50/200 pull+resume | +0.158 | +0.071 | +0.258 | +0.244 |
| 50/200 swing50+resume | −0.099 | −0.665 | +0.812 | +0.223 |

Requiring resumption **does not improve** the economic layer versus pull-only (valid −0.289 / −0.332 vs pull-only −0.218). It also **erases** most of the pull-only mid-to-mid lift (50/200 resume 60m all = +0.16 vs pull-only +0.33). Swing-50% resume is unstable: train 60m −0.67, valid +0.81.

**Resumption is not a confirmation edge on this grid.**

---

## MEAN-REVERSION COMPARISON

Run only after the trend/pullback families. One predeclared fade: first `|close − EMA50| / ATR ≥ 2`, opposite to the displacement.

### Economic

| Split | n | BUY | SELL | WR | Exp. R | PF | Total R | Hold min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 10951 | 5269 | 5682 | 0.225 | −0.327 | 0.579 | −3577 | 109 |
| train | 5507 | 2669 | 2838 | 0.228 | −0.316 | 0.590 | −1742 | 107 |
| valid | 2662 | 1251 | 1411 | 0.236 | −0.293 | 0.616 | −781 | 115 |
| test | 2782 | 1349 | 1433 | 0.207 | −0.379 | 0.522 | −1054 | 106 |

### Forward mid→mid (mean pips)

| Split | n | 5m | 15m | 30m | 60m | 120m | 240m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 27441 | +0.096 | +0.183 | +0.233 | **+0.300** | +0.413 | +0.382 |
| train | 13824 | +0.109 | +0.200 | +0.218 | +0.223 | +0.538 | +0.715 |
| valid | 6749 | +0.086 | +0.244 | +0.315 | +0.566 | +0.678 | +0.219 |
| test | 6868 | +0.082 | +0.088 | +0.180 | +0.195 | **−0.101** | **−0.131** |

All six symbols have a positive 60m mid-to-mid mean (GBP_USD +0.60; AUD_USD +0.17). That is the most consistent **directional** pattern in this file. It still fails the economic 2R occupancy in every split, and the test 2–4 hour means flip negative (mean-reversion that does not persist).

---

## TRAIN / VALIDATION / TEST

Same timestamps for every config. Test was not used to pick parameters.

| Config | Valid exp. R | Test exp. R | Valid 60m pips | Test 60m pips |
| --- | ---: | ---: | ---: | ---: |
| baseline H | −0.338 | −0.435 | −0.195 | +0.108 |
| baseline J | −0.355 | −0.416 | −0.269 | +0.090 |
| ema20/50 trend | −0.337 | −0.399 | −0.439 | −0.233 |
| ema50/100 trend | −0.270 | −0.381 | −0.519 | +0.353 |
| ema50/200 trend | −0.271 | −0.409 | +0.380 | +0.076 |
| ema20/50 pull+resume | −0.373 | −0.412 | +0.117 | +0.389 |
| ema50/100 pull+resume | −0.384 | −0.379 | +0.164 | +0.090 |
| ema50/200 pull+resume | −0.289 | −0.401 | +0.258 | +0.244 |
| **ema50/200 pull-only** | **−0.218** | −0.336 | +0.733 | +0.234 |
| ema50/200 swing+resume | −0.332 | −0.404 | +0.812 | +0.223 |
| mean-reversion z2 | −0.293 | −0.379 | +0.566 | +0.195 |

If a researcher were forced to pick on validation only, they would pick **EMA50/200 pull-only**. Test expectancy is still −0.336 R (better than H −0.435, still a large loss). That ranking is recorded; it is **not** a deployment recommendation.

Chrono cut times differ by ~2 hours from the published SMA-state study (that study’s cuts were 2026-03-03 14:05 / 2026-06-02 06:01) because this run’s quantile includes the full frozen frames (warmup rows). The SMA construction itself is unchanged.

---

## PER-SYMBOL RESULTS

Economic expectancy R, all time. No pair is profitable under bid/ask + 2R.

| Symbol | H | ema50/100 trend | ema50/200 pull-only | ema50/200 pull+resume | MR z2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| EUR_USD | −0.342 | −0.322 | −0.219 | −0.394 | −0.330 |
| GBP_USD | −0.362 | −0.348 | −0.230 | −0.215 | −0.294 |
| USD_JPY | −0.246 | −0.308 | −0.226 | −0.288 | −0.236 |
| AUD_USD | −0.387 | −0.270 | −0.264 | −0.438 | −0.334 |
| USD_CAD | −0.451 | −0.389 | −0.369 | −0.390 | −0.362 |
| USD_CHF | −0.422 | −0.324 | −0.368 | −0.378 | −0.385 |

USD_JPY is usually the least-bad *SMA* pair. Pull-only’s mid-to-mid 60m lift is concentrated in EUR_USD / GBP_USD / USD_JPY and is negative on USD_CAD. Apparent “edges” are not a single-pair artefact of a tiny n (hundreds of trades per symbol), but they are also not an edge after costs.

---

## FORWARD-RETURN ANALYSIS

Purpose: separate directional quality from stop/TP geometry.

1. **Frozen SMA H** is near zero at 5–60m and negative at 2–4h. First-qual is not a directional signal; it is a state label.
2. **Frozen SMA J** is negative at 15–120m overall. Re-using the same SMA state is worse than taking it once — same conclusion as the component study.
3. **EMA trend crosses** do not beat H. Fast EMA20/50 is worse. Slower EMA pairs are noisy across partitions.
4. **ATR-zone retrace (no resume)** is the only trend family with a small, same-sign 60m mid-to-mid mean in train/valid/test (~0.2–0.7 pips). That is **below typical M5 half-spread** on these pairs and dies at 240m on test.
5. **Resumption** after the retrace reduces that mid-to-mid lift. It is not a quality filter here.
6. **Mean-reversion z≥2** has the cleanest short-horizon directional table (all symbols, all three chrono splits positive at 5–60m). Test 120m/240m reverse. This looks like a short-lived stretch/snap, not a hold-for-2R trend.

Horizon disagreement vs occupancy is the main result: a 0.3-pip 60m drift cannot pay a 2-ATR stop after crossing the spread.

---

## COST SENSITIVITY

- Book prices were available on **every** cache row. Economic results are not mid-price fiction.
- BUY pays ask; SELL pays bid; exits use the trigger-side book extremes (`bar_touches`).
- Win rates cluster at **19–26%**. A 2R payoff without costs needs ~33% wins for PF = 1. Observed PF is 0.45–0.70 everywhere.
- The least-bad economic expectancy on the whole grid is **−0.218 R** (pull-only, validation). Overall pull-only is −0.280 R. H is −0.366 R. The gap is a *smaller loss*, not a profit.
- Mid-to-mid positives (pull-only, MR) **do not survive** the book + 2R layer in any split.
- No separate “zero-cost vs 0.2-pip” grid was searched. The two layers already answer the question: directional drift exists at a size that transaction costs and 2R geometry consume.

---

## FAILURE MODES / LIMITATIONS

- Occupancy one-position-per-symbol drops many later signals; economic n < event n.
- Same-bar SL/TP ambiguity is resolved by `bar_touches` (can mark `ambiguous_sl`). That is conservative, not optimistic.
- No session filter, no news blackout, no weekend flatten in the occupancy loop (eod marks only the file end).
- ATR-zone thresholds were predeclared, not proven. A different zone might look different; that would be a new study, not a reason to promote this one.
- Pull-only’s mid-to-mid lift is small enough that a modest change in spread regime can erase it (test 240m already flips).
- Chrono cuts are timestamp quantiles, not calendar years. Test is the most recent ~25% of this cache, not a future live year.
- Mean-reversion events overlap (27k events vs 11k occupied trades). Event means overstate independence.
- This study does not claim the live bot’s full stack (RL gate, volatility_ok, profit protection) was replayed. It compares **signals** to the frozen SMA stub on the same economic geometry.

---

## EVIDENCE CLASSIFICATION

Production is unchanged regardless of class.

| Family | Class | Why |
| --- | --- | --- |
| Frozen SMA baseline (H / J) | **NO EVIDENCE** of a tradeable directional edge | Same as the published component study. Economic occupancy is a large, stable loss. |
| EMA trend alone | **NO EVIDENCE** | Does not beat H on validation *and* test. Forward signs unstable. Costs remain ~−0.33 to −0.40 R. |
| EMA + retracement (pull-only) | **WEAK / INSUFFICIENT** | Small same-sign 60m mid-to-mid in all three splits, not pair-tiny. **Fails costs** in train, valid, and test. Not promising under the stated gate. |
| EMA + retracement + resumption | **NO EVIDENCE** | Worse than pull-only economically; forward lift shrinks or flips by partition. |
| Mean-reversion fade (EMA50 z=2) | **WEAK / INSUFFICIENT** | Best directional table at 5–60m, all six symbols. Does **not** survive bid/ask + 2R. Test 2–4h reverses. One threshold, not a validated system. |

Nothing in this file is **PROMISING — NEEDS FURTHER VALIDATION**. Promising required out-of-sample stability **and** survival after costs **and** no single-pair / tiny-n dependence **and** no obvious selection artefact. Cost survival failed for every family.

### Answers to the comparison questions

| Question | Answer |
| --- | --- |
| Does EMA alone improve directional information? | **No.** |
| Does waiting for a retracement improve it? | **Slightly, mid-to-mid only.** Not enough to matter after costs. |
| Does requiring resumption improve it? | **No.** |
| Does any result survive bid/ask costs? | **No.** |
| Survive validation? | Economic: all negative. Directional: pull-only and MR look better on valid than H; still losing trades. |
| Survive untouched test? | Economic: no. Pull-only / MR 60m mid-to-mid stay small-positive; 240m (pull-only) and 120–240m (MR) do not. |
| Concentrated in one symbol or period? | Losses are broad. Directional crumbs are uneven (GBP/EUR/JPY better than CAD/CHF) and stronger on validation than test. |
| BUY vs SELL materially different? | SELL is usually a bit worse (H SELL −0.395 vs BUY −0.338 R). Same conclusion both sides. |

---

## NEXT RESEARCH STEP

Do **not** expand the EMA period grid. Do **not** deploy a pullback or fade rule.

If this line is continued at all:

1. Cost the pull-only and MR 60m mid-to-mid paths as **half-spread-adjusted pips on the signal bar**, with no 2R occupancy — only to measure whether the 0.2–0.7 pip drift exceeds the spread that was already paid. This study’s occupancy result already says it does not at 2R.
2. Keep any follow-up to those two masks and the frozen H baseline. No new EMA pairs.
3. If the half-spread-adjusted 60m mean is still ≤ 0 on validation **and** test, close the topic.

---

## IMPLEMENTATION / TEST NOTES

- Research module does not import `bot_loop`, `oanda_exec`, or `oanda_client`.
- Tests: `tests/test_ema_retracement_research.py` (SMA period parity vs `compute_indicators`, orientation, pull/resume, swing-once, MR fade + sign-flip re-arm, economic SL ≈ −1R).
- Related reused tests: `tests/test_quant_stub_components.py`.
- Run artefacts: `_ema_retracement_run.py`, `_ema_retracement_results.json`.

---

PRODUCTION CODE CHANGED: NO  
LIVE STRATEGY CHANGED: NO  
OANDA ORDERS SENT: NO  
DOCKER RESTARTED: NO
