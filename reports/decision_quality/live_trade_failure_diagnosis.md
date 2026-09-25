# Live trade failure diagnosis

READ-ONLY FORENSICS. Production code, live strategy, SL/TP, ATR, profit protection, risk, `.env`, Docker, and OANDA orders were not changed.

**Verdict:** The current corrected live build loses because the chosen direction is wrong more often than it is right. Stop-loss exits outnumber take-profit exits because most stopped trades never travel far in the predicted direction (59% of SL exits have MFE < 0.25R). Widening stops or shortening targets does not flip expectancy positive.

---

## ANALYSIS WINDOW

| Item | Value |
|---|---|
| Trustworthy post-deploy boundary | `2026-09-21T22:00:04Z` |
| Why this boundary | Container start of the current corrected production build: executable-side entry geometry and non-M5 position management. Trades before this boundary include the historical stale-M5 management bug and/or stale entry-geometry defect and are **excluded** from the primary sample. |
| First eligible entry | `2026-09-21T22:00:14.391820Z` |
| Last eligible entry | `2026-09-24T07:53:06.220669Z` |
| First eligible exit | `2026-09-21T22:06:29.529397Z` |
| Last eligible exit | `2026-09-24T09:10:23.734926Z` |
| Calendar span | ~2 days 11 hours of closed live trades |
| Headroom-deploy sensitivity start | `2026-09-22T22:28:31Z` (same economics; skip-before-order only) |
| Telegram-recreate sensitivity start | `2026-09-24T00:44:07Z` |

Pre-boundary live closes exist in Postgres from `2026-09-14` onward (433 live-ish rows in the dump). They are not mixed into the primary sample.

### Data sources (read-only)

- Local Docker Postgres: `trades`, `exec_orders`, `broker_exit_ledger`, `broker_exit_pending`, `operational_event_log`
- `trades.diagnostics` JSONB: original SL/TP, ATR at entry, MFE/MAE, realised R, exit reason, OANDA reason, broker trade id
- `exec_orders.metadata`: executable reference, mid, submitted SL/TP, strategy, fill time
- OANDA InstrumentsCandles `price=BA` granularity M5, GET only, complete candles, `2026-09-21T16:00Z` through ~`2026-09-24T12:00Z` (capped at now−10m). Counts: EUR/GBP/JPY/AUD/CAD 772 bars; CHF 771.

No production writes. No OrderCreate. No Docker restart for this task.

### Eligibility

Closed rows with `execution_kind=live` and `trading_mode=live` and exit time `>= 2026-09-21T22:00:04Z`. Open positions at dump time are excluded.

Entry timestamps: `diagnostics.entry_time` is a Unix epoch float on broker-closed rows. ISO parse failed on the first pass; the published numbers below use epoch parse plus `exec_orders.filled_at` fallback (including profit-protection rows that lack `broker_trade_id`). After correction, 0 of 212 scored trades have `entry_ts == exit_ts`.

---

## ELIGIBLE TRADES

| Set | N |
|---|---|
| Eligible closed live trades | 218 |
| Scored (SL / TP / profit protection) | 212 |
| MANUAL (excluded from win/loss, expectancy, PF) | 6 |
| BOT_OTHER | 0 |
| UNKNOWN | 0 |
| Headroom subset (exit `>= 2026-09-22T22:28:31Z`) | 111 |
| Telegram subset (exit `>= 2026-09-24T00:44:07Z`) | 29 |

All 218 have `atr_fallback_used=False`. Initial R is exactly **2.0** on every scored trade (`original_tp_pips / original_sl_pips`). Mean stop 6.04 pips (median 5.41). Mean ATR at entry 3.14 pips (median 2.82). Mean stop/ATR **1.93** (median 1.90) — the live 2×ATR stop is present as designed.

Signal diagnostics persisted at entry are geometry and MFE/PP fields only. `ma_fast`, `ma_slow`, and stub return are **not** stored on the trade row. Strategy label and side are available. Direction is the live `_quant_stub_vote` (SMA fast vs slow + `|ret|>0.0001` + ATR>0).

---

## EXIT BREAKDOWN

| Class | Count | % of 218 | Scored? |
|---|---:|---:|---|
| BROKER_STOP_LOSS | 154 | 70.6% | yes |
| BOT_PROFIT_PROTECTION | 44 | 20.2% | yes |
| BROKER_TAKE_PROFIT | 14 | 6.4% | yes |
| MANUAL | 6 | 2.8% | **no** |
| BOT_OTHER | 0 | 0% | — |
| UNKNOWN | 0 | 0% | — |

SL:TP ratio among scored exits = **154:14 ≈ 11:1**. Including profit-protection as a non-SL exit, SL is still 154/212 = **72.6%**.

Scored expectancy (broker SL/TP + bot PP only):

| Metric | Value |
|---|---|
| Mean R | **−0.352** |
| Sum R | **−74.57** |
| Win rate (realised_R > 0) | **0.274** (58 / 212) |
| Profit factor | **0.524** |
| Median hold | 22.3 min |
| Median hold SL | 16.8 min |
| Median hold TP | 24.6 min |
| Median hold PP | 56.4 min |

MANUAL closes (not scored): trade ids 1371 GBP SELL, 1372 EUR SELL, 1437 CHF SELL, 1474 GBP BUY, 1475 CAD SELL, 1476 JPY BUY.

### Sensitivity subsets (same classification, not mixed with pre-boundary)

| Subset | SL | PP | TP | SL share of those three |
|---|---:|---:|---:|---:|
| Full window | 154 | 44 | 14 | 72.6% |
| After headroom deploy | 77 | 27 | 7 | 69.4% |
| After Telegram recreate | 24 | 4 | 1 | 82.8% |

The SL>>TP pattern is not an artifact of the first hours after the 21 Sep deploy.

---

## PER-SYMBOL RESULTS

Scored only. EUR_USD is the only pair with positive mean R.

| Symbol | N | SL | TP | PP | SL% | Mean R | Sum R | Win rate | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | 35 | 19 | 6 | 10 | 54.3 | **+0.138** | +4.82 | 0.457 | **1.25** |
| GBP_USD | 24 | 17 | 1 | 6 | 70.8 | −0.282 | −6.76 | 0.292 | 0.61 |
| USD_JPY | 48 | 34 | 6 | 8 | 70.8 | −0.302 | −14.49 | 0.292 | 0.58 |
| AUD_USD | 47 | 35 | 1 | 11 | 74.5 | −0.399 | −18.74 | 0.255 | 0.47 |
| USD_CHF | 36 | 30 | 0 | 6 | 83.3 | −0.649 | −23.36 | 0.167 | 0.24 |
| USD_CAD | 22 | 19 | 0 | 3 | 86.4 | **−0.729** | −16.03 | 0.136 | **0.17** |

USD_CAD and USD_CHF recorded **zero** broker take-profits. They are the largest per-trade drain. Do not disable them from this sample alone; the directional miss is visible on every pair except EUR_USD.

---

## BUY VS SELL

| Side | N | SL | TP | PP | SL% | Mean R | Sum R | Win rate | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BUY | 88 | 68 | 4 | 16 | 77.3 | **−0.480** | −42.22 | 0.227 | 0.39 |
| SELL | 124 | 86 | 10 | 28 | 69.4 | −0.261 | −32.35 | 0.306 | 0.63 |

Both sides lose. BUY is worse. This is not a one-sided spread artifact: executable-side forwards (BUY vs bid, SELL vs ask) stay negative for both.

---

## STRATEGY LABEL RESULTS

`select_strategy` names a route. Side still comes from the SMA stub.

| Strategy | N | SL | TP | PP | SL% | Mean R | Sum R | Win rate | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scalp | 22 | 14 | 1 | 7 | 63.6 | −0.130 | −2.87 | 0.364 | 0.80 |
| mean_reversion | 28 | 19 | 3 | 6 | 67.9 | −0.227 | −6.35 | 0.321 | 0.67 |
| swing_mean_reversion | 48 | 33 | 4 | 11 | 68.8 | −0.252 | −12.12 | 0.312 | 0.64 |
| swing_trend | 51 | 37 | 4 | 10 | 72.5 | −0.332 | −16.92 | 0.275 | 0.55 |
| trend | 19 | 14 | 0 | 5 | 73.7 | −0.445 | −8.45 | 0.263 | 0.41 |
| swing_breakout | 44 | 37 | 2 | 5 | **84.1** | **−0.633** | −27.86 | 0.159 | **0.27** |

Every label loses. `swing_breakout` is the worst concentration (84% SL, PF 0.27). Not disabled.

---

## MFE / MAE

Primary MFE/MAE are the **bot diagnostics** recorded during live management (tick/update path, no look-ahead past the actual exit). Secondary reconstruction uses complete M5 bid/ask OHLC from entry to exit only. Intra-bar high/low order is unknown, so reconstructed first-touch can overstate the chance that SL and TP were both touched in the same bar.

Executable convention: BUY favourable = bid high − entry; BUY adverse = entry − bid low. SELL favourable = entry − ask low; SELL adverse = ask high − entry. R = pips / initial stop pips.

### All scored (n=212)

| | Mean | Median | Sum |
|---|---:|---:|---:|
| MFE_R | 0.643 | 0.397 | 136.2 |
| MAE_R | 1.304 | 1.267 | 276.5 |

### BROKER_STOP_LOSS only (n=154)

| | Mean | Median | Sum |
|---|---:|---:|---:|
| MFE_R | **0.296** | **0.106** | 45.6 |
| MAE_R | 1.452 | 1.411 | 223.6 |

Stopped trades typically never get a quarter-R of room. MAE > 1R is expected once the broker stop fills (fill past the stop plus noise).

### Bot vs reconstructed M5 path

196 scored trades have both series. Mean (recon MFE pips − bot MFE pips) = **+0.25 pips**. Close. On stopped trades with a path (138): bot bucket A = 75, M5-recon bucket A = 90. Reconstruction is slightly harsher (more “never went our way”), consistent with M5 missing intra-bar ticks that the bot saw. **Bucket conclusions below use bot MFE**, which is the less pessimistic and the one the live manage path actually recorded.

16 SL trades have no M5 bars strictly after entry and at or before exit (sub-5-minute holds). Their bot MFE is still used.

---

## STOPPED-TRADE MFE BUCKETS

BROKER_STOP_LOSS only. Bot `mfe_r`. E and F are empty.

| Bucket | Definition | Count | % of 154 SL |
|---|---|---:|---:|
| A | MFE < +0.25R | **91** | **59.1%** |
| B | +0.25R ≤ MFE < +0.5R | 23 | 14.9% |
| C | +0.5R ≤ MFE < +1.0R | 27 | 17.5% |
| D | +1.0R ≤ MFE < +1.5R | 13 | 8.4% |
| E | +1.5R ≤ MFE < +2.0R | 0 | 0% |
| F | MFE ≥ +2.0R | 0 | 0% |

**A+B = 74.0%.** Three of four stopped trades never reached +0.5R. Zero stopped trades had already reached the 2R target and then reversed through the stop. The SL pile is mostly **wrong direction**, not **gave back a working trade**.

M5-recon buckets on the 138 path-complete SL trades: A 90, B 15, C 25, D 7, F 1, plus 16 no-path. Same shape.

---

## FORWARD RETURNS

Uncensored executable-side close at horizon (BUY `bid_c`, SELL `ask_c`). **Not** clipped at the actual exit. This answers “was the direction right?” not “what did the booked trade earn?”

`dir_hit` = fraction with positive executable pips at that horizon.

### All scored (n=212)

| Horizon | Mean R | Dir hit |
|---|---:|---:|
| 5m | −0.292 | **0.269** |
| 15m | −0.292 | 0.354 |
| 30m | −0.284 | 0.358 |
| 60m | −0.180 | **0.443** |
| 120m | −0.503 | 0.382 |
| 240m | −0.356 | 0.415 |

No horizon has positive mean R. No horizon has dir_hit ≥ 0.50 on the full scored set. Best directional rate is 60m at 44.3%, still a coin-flip loss after costs.

### BUY vs SELL (uncensored)

| Horizon | BUY mean R | BUY dir | SELL mean R | SELL dir |
|---|---:|---:|---:|---:|
| 5m | −0.248 | 0.295 | −0.323 | 0.250 |
| 15m | −0.306 | 0.386 | −0.282 | 0.331 |
| 30m | −0.324 | 0.318 | −0.255 | 0.387 |
| 60m | −0.401 | 0.386 | −0.023 | 0.484 |
| 120m | −0.862 | 0.341 | −0.248 | 0.411 |
| 240m | −0.909 | 0.409 | +0.037 | 0.419 |

SELL mean R is near flat at 60m and slightly positive at 240m. BUY stays negative and worsens with time. Neither side is a usable edge.

### Stopped trades after entry (uncensored)

| Horizon | Mean R | Dir hit |
|---|---:|---:|
| 5m | −0.524 | **0.149** |
| 15m | −0.644 | 0.208 |
| 30m | −0.703 | 0.214 |
| 60m | −0.730 | 0.279 |
| 120m | −1.113 | 0.221 |
| 240m | −0.989 | 0.305 |

Losing trades **do** move against the signal immediately: 85% of SL trades are already on the wrong side of entry at 5 minutes. They do not later become correct often enough to justify the stop.

### Forward by symbol (dir hit / mean R)

| Symbol | 5m hit | 5m R | 60m hit | 60m R | 240m hit | 240m R |
|---|---:|---:|---:|---:|---:|---:|
| EUR_USD | 0.229 | −0.275 | 0.486 | **+0.111** | 0.486 | −0.074 |
| GBP_USD | 0.250 | −0.212 | 0.542 | +0.028 | 0.417 | −0.146 |
| USD_JPY | 0.354 | −0.162 | 0.521 | −0.056 | 0.417 | −0.578 |
| AUD_USD | 0.298 | −0.169 | 0.319 | −0.294 | 0.319 | −0.528 |
| USD_CHF | 0.222 | −0.510 | 0.389 | −0.335 | 0.333 | −0.474 |
| USD_CAD | 0.182 | −0.595 | 0.455 | −0.639 | 0.636 | +0.016 |

EUR_USD is the only pair with a clearly positive 60m mean R. USD_CAD’s 240m dir_hit of 0.636 is a small-n late bounce after a terrible first hour; it does not rescue the booked stops.

### Forward by strategy (dir hit)

| Strategy | 5m | 15m | 30m | 60m | 120m | 240m |
|---|---:|---:|---:|---:|---:|---:|
| scalp | 0.409 | 0.409 | 0.409 | 0.545 | 0.455 | 0.318 |
| mean_reversion | 0.393 | 0.464 | 0.357 | 0.393 | 0.286 | 0.321 |
| trend | 0.368 | 0.421 | 0.526 | 0.474 | 0.316 | 0.421 |
| swing_mean_reversion | 0.271 | 0.458 | 0.417 | 0.458 | 0.354 | 0.396 |
| swing_trend | 0.196 | 0.294 | 0.275 | 0.431 | 0.431 | 0.451 |
| swing_breakout | **0.159** | **0.182** | 0.295 | 0.409 | 0.409 | 0.500 |

`swing_breakout` is almost immediately wrong. Its 240m 50% hit arrives too late for a 2×ATR stop that dies in 17 minutes.

**Answer:** The chosen direction does **not** have positive forward expectancy at 5–240m. Losing trades usually move against the signal within 5 minutes. Directional rate improves toward 60m (0.269 → 0.443) but never becomes an edge after costs.

---

## ENTRY TIMING

Stopped trades, M5 executable-side move **before** entry (positive = already moving in the eventual trade direction).

| Pre-window | N | Mean pips | Median pips |
|---|---:|---:|---:|
| 5m | 154 | **−0.82** | −0.5 |
| 15m | 154 | **−0.83** | −1.1 |
| 30m | 154 | −0.24 | −1.6 |

The typical SL entry is **not** chasing an already-completed move in its own direction. The 5–15m tape before entry is slightly **against** the stub.

Swing extension (distance from last 36 M5 bars’ swing high for BUY / swing low for SELL; `extended` if ≤ 2 pips from that extreme):

| | Value |
|---|---|
| Stopped with swing distance | 154 |
| Mean swing distance | 8.31 pips |
| Median swing distance | 6.7 pips |
| Marked extended (≤2 pips) | **23 / 154 (14.9%)** |

Spread at entry (from `executable_reference` vs `mid`, 168 measured):

| | Mean | Median |
|---|---:|---:|
| Spread pips | 4.45 | **2.0** |
| Stop / spread | 4.93 | 2.08 |
| Stop / ATR | 1.93 | 1.90 |

34 of 168 measured spreads > 5 pips. Extreme outliers: USD_JPY 90.2 and 60.4, USD_CHF 52.0, AUD_USD 20.2. Those look like holiday/thin-book or metadata reconstruction, not typical London spreads. Median 2.0 pips against a 5.4 pip stop is the defensible cost picture.

By symbol, median spread: EUR 1.6, CAD 1.6, CHF 1.6, AUD 2.0, GBP 2.0, JPY 4.2. USD_JPY is the expensive pair (15 of 40 measured > 5 pips).

**Answer:** There is **not** systematic late-chase evidence. The more accurate timing statement is: the stub often enters **into or after a short adverse tick**, then the stop is hit.

---

## ATR / STOP ANALYSIS

Live geometry: 2×ATR stop, 2R target. Confirmed: mean stop/ATR 1.93, initial R 2.0, ATR fallback unused.

MAE on stopped trades (mean 1.45R) is the fill through a 1R stop, not independent proof that 2×ATR is “too tight.” The relevant test is whether a **wider stop at constant monetary risk** (conceptually smaller size so −1R is the same money) improves expectancy. TP **pips** held at the original target; R on a TP hit becomes `original_tp_pips / new_stop_pips` (a 2R pip target is ~0.67R at a 3×ATR stop). M5 first-touch, 8 hours, no look-ahead past that window. Same-bar SL+TP = AMBIGUOUS, dropped.

| Stop | Resolved | TP | SL | Win rate | Mean R | Sum R | PF |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2.0 ATR | 205 | 48 | 157 | 0.234 | −0.322 | −66.0 | 0.58 |
| 2.5 ATR | 206 | 61 | 145 | 0.296 | −0.256 | −52.7 | 0.64 |
| 3.0 ATR | 202 | 72 | 130 | 0.356 | −0.194 | −39.3 | 0.70 |

Wider stops **reduce the SL label count** and modestly improve mean R / PF. They remain **negative**. This is not a structural “2×ATR is the reason the book loses.” It is a smaller hole in a still-wrong direction.

Research-only. Production SL unchanged.

---

## TARGET COUNTERFACTUALS

Same entries, original SL, counterfactual TP at 1.0R / 1.5R / 2.0R. M5 first-touch, 8h, constant size (this is a target test, not a size test). Costs implicit in bid/ask path. Higher win rate with worse expectancy is **not** an improvement.

| Target | Resolved | TP | SL | Win rate | Mean R | Sum R | PF |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1.0R | 211 | 59 | 152 | **0.280** | −0.441 | −93.0 | 0.39 |
| 1.5R | 210 | 48 | 162 | 0.229 | −0.429 | −90.0 | 0.44 |
| 2.0R | 208 | 45 | 163 | 0.216 | **−0.351** | **−73.0** | **0.55** |

Shorter targets raise win rate and **worsen** expectancy. The live 2R target is the least-bad of the three. The SL>>TP count is not explained by “targets too far.”

Research-only. Production TP unchanged.

---

## SIGNAL QUALITY

Live side vs subsequent executable close. Same uncensored series as FORWARD RETURNS.

**Directionally correct after entry (all scored):**

| | 5m | 15m | 30m | 60m | 120m | 240m |
|---|---:|---:|---:|---:|---:|---:|
| All | 0.269 | 0.354 | 0.358 | 0.443 | 0.382 | 0.415 |
| BUY | 0.295 | 0.386 | 0.318 | 0.386 | 0.341 | 0.409 |
| SELL | 0.250 | 0.331 | 0.387 | 0.484 | 0.411 | 0.419 |

Disproportionate loss concentrations (descriptive, not a disable list):

| Slice | Evidence |
|---|---|
| USD_CAD | SL 86%, PF 0.17, 0 TP, 5m dir 0.182 |
| USD_CHF | SL 83%, PF 0.24, 0 TP, 5m dir 0.222 |
| BUY | mean R −0.480 vs SELL −0.261 |
| swing_breakout | SL 84%, mean R −0.633, 5m dir 0.159 |
| SHORT_USD | SL 80%, mean R −0.485 vs LONG_USD −0.264 |
| Hour 21 UTC | 9/9 scored SL, mean R −1.07 (JPY/EUR/GBP cluster) |
| Hour 01 UTC | n=29, SL 79%, mean R −0.46 |
| Hour 00 UTC | n=19, SL 79%, mean R −0.53 |

Hour 00 was stored as `"unknown"` in the helper JSON because `hour_utc or "unknown"` treats `0` as missing. The 19 rows are hour 00.

No symbol, side, or strategy is disabled.

---

## USD EXPOSURE CLUSTERS

All six pairs contain USD.

| USD call | N scored | SL | TP | PP | SL% | Mean R | PF |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG_USD | 128 | 87 | 6 | 35 | 68.0 | −0.264 | 0.62 |
| SHORT_USD | 84 | 67 | 8 | 9 | **79.8** | **−0.485** | 0.40 |

**101 of 154 SL trades** overlap in time with at least one other SL in the **same** USD direction. Greedy cluster extract: **34 clusters, 88 SL trades** in multi-name groups.

Example clusters (first five):

| USD dir | N | Symbols | Trade ids | First entry UTC |
|---|---:|---|---|---|
| LONG_USD | 2 | CHF, JPY | 1373, 1377 | 2026-09-21T22:39:10 |
| SHORT_USD | 4 | JPY, CAD, CAD, CHF | 1384, 1381, 1383, 1385 | 2026-09-22T00:59:27 |
| SHORT_USD | 3 | EUR, CHF, CAD | 1389, 1387, 1388 | 2026-09-22T01:15:45 |
| LONG_USD | 2 | AUD, JPY | 1392, 1393 | 2026-09-22T01:52:22 |
| LONG_USD | 2 | AUD, CAD | 1397, 1398 | 2026-09-22T02:21:50 |

One wrong USD view is being booked on several pairs at once. That **amplifies** the R hole; it does not create the directional miss (uncorrelated, per-trade forwards are still negative). Existing USD-direction guard not modified.

---

## PROFIT PROTECTION

BOT_PROFIT_PROTECTION only. n=44. Not mixed into “strategy TP.”

| | Mean | Median |
|---|---:|---:|
| MFE_R | 1.536 | 1.492 |
| Exit R | 1.231 | 1.185 |
| Giveback R | 0.305 | 0.263 |
| Hold | 63.3 min | 56.9 min |

| | Value |
|---|---|
| Min / max MFE_R | 1.348 / 1.973 |
| Min / max exit R | 0.527 / 1.832 |
| Reached 2.0R MFE before PP exit | **0 / 44** |

PP is activating in its designed zone (~67% of the 2R target ≈ 1.34R) and giving back ~0.3R (ATR×0.5). It **preserved** a mean +1.23R that the stop-loss book does not have. It did **not** flatten trades that had already printed 2R MFE.

Whether those 44 would later have hit the broker TP if left alone is not a clean separate first-touch series. None had MFE ≥ 2R while open, so PP did not steal completed targets. The 8h 2R counterfactual on the full scored set still loses (mean R −0.351). PP is not the reason SL>>TP.

Production profit protection unchanged.

---

## DATA LIMITATIONS

1. **Sample length.** 218 closed trades, ~2.5 days, one corrected build. Enough to diagnose SL>>TP and negative direction. Not enough to permanently disable a pair or strategy.
2. **M5 path order.** Bid/ask OHLC does not say whether high or low printed first. Same-bar SL+TP marked AMBIGUOUS and dropped from counterfactuals. MFE/MAE extremes can overstate both sides inside one bar.
3. **Sub-5-minute SL holds.** 16 SL trades have no complete M5 bar between entry and exit. Bot tick MFE used; recon path empty.
4. **Forward after exit.** Uncensored 5–240m series uses market prices after the trade is closed. Correct for signal quality; not the booked P&L.
5. **Spread reconstruction.** `2 * |executable_reference − mid| / pip`. Extreme JPY/CHF values are not treated as typical cost. Median used for the cost conclusion.
6. **Missing stub features.** `ma_fast` / `ma_slow` / return at entry were not persisted. Strategy label and side are the available signal tags.
7. **PP rows.** 44 profit-protection closes lack `broker_trade_id` / `oanda_reason`. Entry time inferred from nearest same-symbol, same-side FILLED order within 6h. Holds look consistent (median 56.9 min).
8. **MANUAL / UNKNOWN.** Six manual closes excluded from win/loss. Zero UNKNOWN / BOT_OTHER in this window.
9. **Hour 00 bug in helper JSON.** `by_hour["unknown"]` is hour 00. Corrected in this report.
10. **Pre-boundary exclusion.** Older live trades are in the dump but were affected by stale-M5 management and/or stale entry geometry. They are not in the primary sample.
11. **Account P&L.** Sum of scored `trades.pnl` is about −0.06 account units over 212 rows; R is the decision metric (units vary).
12. **Counterfactuals** are research-only first-touch on M5. They are not a production proposal.

Machine-readable reconstruction: `reports/decision_quality/_live_trade_failure_analysis.json` (218 trades, MFE/MAE, forwards, buckets). Source dump: `reports/decision_quality/_live_trade_dump.json`.

---

## PRIMARY EVIDENCE POINTS TO

More than one applies.

| Hypothesis | Evidence grade | Why |
|---|---|---|
| SIGNAL DIRECTION | **HIGH** | Dir-hit 0.269 at 5m, 0.443 at 60m, never ≥0.50 on the full scored set. Mean forward R negative at every horizon. 59% of SL never reach +0.25R. Stopped 5m dir-hit 0.149. Matches the prior offline stub result (negative 5–240m forwards). |
| ENTRY TIMING | **LOW** | Pre-entry 5/15m move is **against** the signal. Only 14.9% of SL entries sit within 2 pips of the recent swing extreme. Not a late-chase book. |
| STOP TOO TIGHT | **LOW** | Live stop is ~1.93×ATR as designed. Constant-risk 2.5× and 3.0×ATR still have negative mean R (−0.256, −0.194). Wider stops shrink the SL count; they do not create an edge. |
| TARGET TOO FAR | **NO EVIDENCE** | 1R / 1.5R / 2R counterfactuals: shorter targets raise win rate and **worsen** expectancy. Live 2R is the least-bad of the three. |
| TRANSACTION COSTS | **MEDIUM** | Median spread 2.0 vs median stop 5.4 (stop/spread ~2.1). USD_JPY median 4.2 with many >5 pip prints. Enough to hurt a weak signal; not enough to explain 11:1 SL:TP on a 2R book if direction were >50%. |
| CORRELATED USD EXPOSURE | **MEDIUM** | 101/154 SL overlap another SL in the same USD direction. SHORT_USD mean R −0.485 vs LONG_USD −0.264. 34 clusters / 88 clustered SL trades. Amplifies one wrong USD call; does not replace the per-trade directional miss. |
| INSUFFICIENT SAMPLE | **LOW** | 212 scored / 2.5 days is short for disabling symbols. It is **not** short for the SL>>TP diagnosis: headroom (111) and Telegram (29) subsets repeat the same shape. |
| OTHER | **MEDIUM** | `swing_breakout` (SL 84%, mean R −0.633). USD_CAD and USD_CHF (0 TP, PF 0.17 / 0.24). Hour 21 UTC 9/9 SL. These are concentrations of the same directional failure, not a separate mechanism. |

---

## CONSTRAINT CHECK

| Constraint | Status |
|---|---|
| PRODUCTION CODE CHANGED | **NO** |
| LIVE STRATEGY CHANGED | **NO** |
| SL / TP CHANGED | **NO** |
| ATR CHANGED | **NO** |
| PROFIT PROTECTION CHANGED | **NO** |
| RISK CONTROLS CHANGED | **NO** |
| `.env` CHANGED | **NO** |
| OANDA ORDERS SENT | **NO** |
| DOCKER RESTARTED | **NO** |
| PARAMETERS OPTIMIZED | **NO** |

STOP.

---

## APPENDIX — Per-trade reconstruction

Compact table of every eligible closed live trade in the window. MANUAL rows are included for completeness and must not be counted as strategy wins or losses. Full fields (prices, recon MFE/MAE, forwards, swing, spread) are in `_live_trade_failure_analysis.json`.

| id | symbol | side | strategy | entry UTC | exit UTC | class | hold min | SL pips | init R | MFE_R | MAE_R | exit R | bucket | USD |
|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 1371 | GBP_USD | SELL | swing_trend | 2026-09-21 22:00:14 | 2026-09-21 22:36:15 | MANUAL | 36.0 | 4.62 | 2.0 | 0.04 | 0.95 | -0.28 |  | LONG_USD |
| 1369 | USD_JPY | SELL | trend | 2026-09-21 22:00:14 | 2026-09-21 22:06:29 | BROKER_STOP_LOSS | 6.2 | 6.10 | 2.0 | 0.00 | 0.95 | -1.00 | A | SHORT_USD |
| 1370 | USD_JPY | SELL | swing_mean_reversion | 2026-09-21 22:08:23 | 2026-09-21 23:15:31 | BOT_PROFIT_PROTECTION | 67.1 | 7.04 | 2.0 | 1.41 | 0.54 | 0.88 |  | SHORT_USD |
| 1372 | EUR_USD | SELL | swing_mean_reversion | 2026-09-21 22:09:24 | 2026-09-21 22:36:18 | MANUAL | 26.9 | 3.08 | 2.0 | 0.06 | 1.01 | -0.39 |  | LONG_USD |
| 1373 | USD_CHF | BUY | swing_breakout | 2026-09-21 22:39:10 | 2026-09-21 22:52:06 | BROKER_STOP_LOSS | 12.9 | 3.17 | 2.0 | 0.00 | 1.80 | -1.01 | A | LONG_USD |
| 1377 | USD_JPY | BUY | swing_breakout | 2026-09-21 22:41:12 | 2026-09-22 00:40:15 | BROKER_STOP_LOSS | 119.1 | 8.42 | 2.0 | 0.69 | 0.90 | -1.05 | C | LONG_USD |
| 1374 | AUD_USD | SELL | swing_trend | 2026-09-21 23:16:46 | 2026-09-22 00:02:52 | BROKER_STOP_LOSS | 46.1 | 1.78 | 2.0 | 0.56 | 3.20 | -1.01 | C | LONG_USD |
| 1375 | USD_CAD | BUY | swing_breakout | 2026-09-22 00:05:34 | 2026-09-22 00:06:26 | BROKER_STOP_LOSS | 0.9 | 2.29 | 2.0 | 0.00 | 0.00 | -1.13 | A | LONG_USD |
| 1376 | USD_CHF | SELL | swing_trend | 2026-09-22 00:05:35 | 2026-09-22 00:10:24 | BROKER_STOP_LOSS | 4.8 | 2.17 | 2.0 | 0.00 | 1.93 | -1.01 | A | SHORT_USD |
| 1378 | GBP_USD | SELL | swing_breakout | 2026-09-22 00:06:35 | 2026-09-22 00:48:34 | BROKER_STOP_LOSS | 42.0 | 3.83 | 2.0 | 0.16 | 1.28 | -0.99 | A | LONG_USD |
| 1380 | USD_JPY | SELL | trend | 2026-09-22 00:42:10 | 2026-09-22 00:56:18 | BROKER_STOP_LOSS | 14.1 | 8.66 | 2.0 | 0.00 | 1.11 | -1.00 | A | SHORT_USD |
| 1384 | USD_JPY | SELL | swing_trend | 2026-09-22 00:59:27 | 2026-09-22 01:14:30 | BROKER_STOP_LOSS | 15.0 | 8.82 | 2.0 | 0.00 | 1.03 | -1.02 | A | SHORT_USD |
| 1381 | USD_CAD | SELL | swing_breakout | 2026-09-22 01:02:31 | 2026-09-22 01:04:12 | BROKER_STOP_LOSS | 1.7 | 2.21 | 2.0 | 0.00 | 2.44 | -0.99 | A | SHORT_USD |
| 1383 | USD_CAD | SELL | swing_mean_reversion | 2026-09-22 01:09:38 | 2026-09-22 01:10:02 | BROKER_STOP_LOSS | 0.4 | 2.33 | 2.0 | 0.00 | 2.41 | -0.99 | A | SHORT_USD |
| 1385 | USD_CHF | SELL | swing_trend | 2026-09-22 01:11:41 | 2026-09-22 01:24:50 | BROKER_STOP_LOSS | 13.2 | 2.28 | 2.0 | 0.22 | 2.19 | -1.01 | A | SHORT_USD |
| 1389 | EUR_USD | BUY | swing_trend | 2026-09-22 01:15:45 | 2026-09-22 01:41:34 | BROKER_STOP_LOSS | 25.8 | 2.39 | 2.0 | 0.04 | 1.21 | -1.04 | A | SHORT_USD |
| 1387 | USD_CHF | SELL | swing_breakout | 2026-09-22 01:25:55 | 2026-09-22 01:30:33 | BROKER_STOP_LOSS | 4.6 | 2.48 | 2.0 | 0.00 | 1.94 | -1.05 | A | SHORT_USD |
| 1379 | USD_CHF | SELL | swing_breakout | 2026-09-22 01:25:56 | 2026-09-22 01:55:24 | BOT_PROFIT_PROTECTION | 29.5 | 2.15 | 2.0 | 1.49 | 1.95 | 1.07 |  | SHORT_USD |
| 1388 | USD_CAD | SELL | swing_trend | 2026-09-22 01:31:00 | 2026-09-22 01:33:49 | BROKER_STOP_LOSS | 2.8 | 2.75 | 2.0 | 0.00 | 2.11 | -0.98 | A | SHORT_USD |
| 1395 | EUR_USD | BUY | swing_mean_reversion | 2026-09-22 01:45:14 | 2026-09-22 02:24:56 | BROKER_TAKE_PROFIT | 39.7 | 2.81 | 2.0 | 1.60 | 0.64 | 2.00 |  | SHORT_USD |
| 1396 | GBP_USD | BUY | swing_trend | 2026-09-22 01:45:14 | 2026-09-22 02:24:41 | BROKER_TAKE_PROFIT | 39.4 | 3.96 | 2.0 | 1.59 | 0.73 | 1.99 |  | SHORT_USD |
| 1391 | USD_CAD | BUY | swing_trend | 2026-09-22 01:45:15 | 2026-09-22 01:51:51 | BROKER_STOP_LOSS | 6.6 | 3.06 | 2.0 | 0.00 | 1.76 | -1.01 | A | LONG_USD |
| 1392 | AUD_USD | SELL | scalp | 2026-09-22 01:52:22 | 2026-09-22 02:03:59 | BROKER_STOP_LOSS | 11.6 | 5.75 | 2.0 | 0.00 | 1.70 | -0.99 | A | LONG_USD |
| 1393 | USD_JPY | BUY | trend | 2026-09-22 01:58:28 | 2026-09-22 02:20:11 | BROKER_STOP_LOSS | 21.7 | 9.26 | 2.0 | 0.00 | 1.18 | -1.04 | A | LONG_USD |
| 1394 | AUD_USD | SELL | mean_reversion | 2026-09-22 02:05:35 | 2026-09-22 02:20:20 | BROKER_STOP_LOSS | 14.8 | 6.17 | 2.0 | 0.00 | 1.64 | -1.00 | A | LONG_USD |
| 1382 | AUD_USD | SELL | swing_trend | 2026-09-22 02:05:35 | 2026-09-22 02:10:39 | BOT_PROFIT_PROTECTION | 5.1 | 2.25 | 2.0 | 1.82 | 2.80 | 1.78 |  | LONG_USD |
| 1397 | AUD_USD | SELL | mean_reversion | 2026-09-22 02:21:50 | 2026-09-22 02:26:39 | BROKER_STOP_LOSS | 4.8 | 6.24 | 2.0 | 0.00 | 1.71 | -0.99 | A | LONG_USD |
| 1386 | AUD_USD | SELL | swing_trend | 2026-09-22 02:21:50 | 2026-09-22 02:25:55 | BOT_PROFIT_PROTECTION | 4.1 | 2.59 | 2.0 | 1.81 | 1.62 | 0.96 |  | LONG_USD |
| 1398 | USD_CAD | BUY | swing_mean_reversion | 2026-09-22 02:25:54 | 2026-09-22 02:28:38 | BROKER_STOP_LOSS | 2.7 | 3.69 | 2.0 | 0.00 | 1.76 | -0.98 | A | LONG_USD |
| 1403 | EUR_USD | BUY | swing_trend | 2026-09-22 02:26:55 | 2026-09-22 04:35:01 | BOT_PROFIT_PROTECTION | 128.1 | 3.13 | 2.0 | 1.60 | 0.86 | 1.44 |  | SHORT_USD |
| 1400 | GBP_USD | SELL | swing_mean_reversion | 2026-09-22 02:27:56 | 2026-09-22 03:02:44 | BROKER_STOP_LOSS | 34.8 | 4.43 | 2.0 | 0.02 | 1.33 | -1.02 | A | LONG_USD |
| 1399 | USD_CHF | SELL | swing_mean_reversion | 2026-09-22 02:27:57 | 2026-09-22 02:36:07 | BROKER_STOP_LOSS | 8.2 | 3.09 | 2.0 | 0.00 | 1.81 | -1.00 | A | SHORT_USD |
| 1402 | AUD_USD | SELL | trend | 2026-09-22 02:37:05 | 2026-09-22 03:22:10 | BROKER_STOP_LOSS | 45.1 | 7.04 | 2.0 | 0.00 | 1.55 | -1.01 | A | LONG_USD |
| 1390 | AUD_USD | SELL | scalp | 2026-09-22 02:37:05 | 2026-09-22 02:50:20 | BOT_PROFIT_PROTECTION | 13.2 | 5.13 | 2.0 | 1.68 | 1.21 | 1.15 |  | LONG_USD |
| 1401 | USD_CHF | SELL | swing_trend | 2026-09-22 02:40:09 | 2026-09-22 03:05:06 | BROKER_STOP_LOSS | 25.0 | 3.01 | 2.0 | 0.10 | 1.76 | -1.03 | A | SHORT_USD |
| 1404 | USD_CHF | SELL | swing_trend | 2026-09-22 03:05:32 | 2026-09-22 04:55:22 | BOT_PROFIT_PROTECTION | 109.8 | 2.99 | 2.0 | 1.40 | 1.70 | 0.87 |  | SHORT_USD |
| 1407 | USD_JPY | BUY | swing_breakout | 2026-09-22 03:31:58 | 2026-09-22 06:05:34 | BROKER_TAKE_PROFIT | 153.6 | 6.86 | 2.0 | 1.69 | 0.98 | 1.98 |  | LONG_USD |
| 1405 | USD_CAD | BUY | swing_trend | 2026-09-22 03:35:02 | 2026-09-22 04:13:45 | BROKER_STOP_LOSS | 38.7 | 4.02 | 2.0 | 0.82 | 1.69 | -1.00 | C | LONG_USD |
| 1406 | GBP_USD | BUY | swing_trend | 2026-09-22 03:38:05 | 2026-09-22 06:00:19 | BROKER_STOP_LOSS | 142.2 | 4.76 | 2.0 | 0.78 | 1.60 | -1.03 | C | SHORT_USD |
| 1408 | AUD_USD | BUY | mean_reversion | 2026-09-22 03:58:25 | 2026-09-22 06:05:05 | BROKER_STOP_LOSS | 126.7 | 5.73 | 2.0 | 0.30 | 1.75 | -0.99 | B | SHORT_USD |
| 1409 | USD_CAD | SELL | swing_mean_reversion | 2026-09-22 06:02:25 | 2026-09-22 06:06:40 | BROKER_STOP_LOSS | 4.2 | 2.87 | 2.0 | 0.00 | 1.81 | -1.05 | A | SHORT_USD |
| 1412 | GBP_USD | BUY | swing_mean_reversion | 2026-09-22 06:07:30 | 2026-09-22 06:20:07 | BROKER_STOP_LOSS | 12.6 | 3.69 | 2.0 | 0.52 | 1.57 | -1.00 | C | SHORT_USD |
| 1410 | USD_CHF | SELL | swing_breakout | 2026-09-22 06:08:32 | 2026-09-22 06:13:26 | BROKER_STOP_LOSS | 4.9 | 2.61 | 2.0 | 0.00 | 2.49 | -1.19 | A | SHORT_USD |
| 1411 | USD_CHF | SELL | swing_mean_reversion | 2026-09-22 06:14:38 | 2026-09-22 06:17:47 | BROKER_STOP_LOSS | 3.1 | 2.73 | 2.0 | 0.00 | 1.83 | -0.99 | A | SHORT_USD |
| 1413 | USD_CAD | SELL | swing_breakout | 2026-09-22 06:19:44 | 2026-09-22 06:19:54 | BROKER_STOP_LOSS | 0.2 | 2.93 | 2.0 | 0.00 | 0.00 | -0.99 | A | SHORT_USD |
| 1416 | AUD_USD | BUY | swing_breakout | 2026-09-22 06:20:45 | 2026-09-22 07:08:01 | BROKER_STOP_LOSS | 47.3 | 3.73 | 2.0 | 1.02 | 1.96 | -0.99 | D | SHORT_USD |
| 1415 | EUR_USD | BUY | swing_trend | 2026-09-22 06:21:46 | 2026-09-22 08:00:58 | BOT_PROFIT_PROTECTION | 99.2 | 3.43 | 2.0 | 1.37 | 0.41 | 0.84 |  | SHORT_USD |
| 1425 | USD_JPY | BUY | scalp | 2026-09-22 07:00:58 | 2026-09-22 08:39:18 | BROKER_STOP_LOSS | 98.3 | 9.98 | 2.0 | 0.93 | 0.93 | -1.00 | C | LONG_USD |
| 1414 | USD_JPY | BUY | mean_reversion | 2026-09-22 07:00:58 | 2026-09-22 07:50:15 | BOT_PROFIT_PROTECTION | 49.3 | 7.02 | 2.0 | 1.41 | 0.46 | 0.53 |  | LONG_USD |
| 1417 | USD_CHF | BUY | swing_breakout | 2026-09-22 07:00:59 | 2026-09-22 07:15:26 | BROKER_STOP_LOSS | 14.4 | 3.75 | 2.0 | 0.37 | 1.52 | -1.01 | B | LONG_USD |
| 1418 | GBP_USD | BUY | swing_mean_reversion | 2026-09-22 07:03:01 | 2026-09-22 07:32:22 | BROKER_STOP_LOSS | 29.3 | 4.81 | 2.0 | 1.25 | 2.27 | -1.00 | D | SHORT_USD |
| 1419 | AUD_USD | BUY | swing_mean_reversion | 2026-09-22 07:10:09 | 2026-09-22 07:32:28 | BROKER_STOP_LOSS | 22.3 | 4.47 | 2.0 | 0.65 | 2.08 | -1.01 | C | SHORT_USD |
| 1420 | EUR_USD | SELL | swing_trend | 2026-09-22 07:16:16 | 2026-09-22 07:32:58 | BROKER_TAKE_PROFIT | 16.7 | 4.35 | 2.0 | 1.47 | 0.85 | 2.02 |  | LONG_USD |
| 1421 | AUD_USD | SELL | swing_mean_reversion | 2026-09-22 07:33:34 | 2026-09-22 07:39:50 | BROKER_STOP_LOSS | 6.3 | 4.86 | 2.0 | 0.00 | 1.73 | -1.01 | A | LONG_USD |
| 1422 | USD_CAD | SELL | swing_trend | 2026-09-22 07:36:37 | 2026-09-22 07:51:49 | BROKER_STOP_LOSS | 15.2 | 4.78 | 2.0 | 0.38 | 1.72 | -1.00 | B | SHORT_USD |
| 1423 | EUR_USD | SELL | mean_reversion | 2026-09-22 07:40:41 | 2026-09-22 08:00:23 | BROKER_TAKE_PROFIT | 19.7 | 6.44 | 2.0 | 1.77 | 0.34 | 2.00 |  | LONG_USD |
| 1426 | USD_CHF | BUY | mean_reversion | 2026-09-22 08:36:41 | 2026-09-22 08:39:50 | BROKER_STOP_LOSS | 3.1 | 6.90 | 2.0 | 0.00 | 1.13 | -1.03 | A | LONG_USD |
| 1427 | AUD_USD | SELL | mean_reversion | 2026-09-22 08:40:45 | 2026-09-22 08:42:39 | BROKER_STOP_LOSS | 1.9 | 7.24 | 2.0 | 0.00 | 1.52 | -1.01 | A | LONG_USD |
| 1430 | EUR_USD | SELL | scalp | 2026-09-22 08:41:46 | 2026-09-22 08:50:49 | BROKER_STOP_LOSS | 9.1 | 8.16 | 2.0 | 0.18 | 1.07 | -1.02 | A | LONG_USD |
| 1428 | USD_JPY | SELL | scalp | 2026-09-22 08:42:47 | 2026-09-22 08:43:14 | BROKER_STOP_LOSS | 0.4 | 11.48 | 2.0 | 0.00 | 0.00 | -1.01 | A | SHORT_USD |
| 1429 | USD_JPY | SELL | mean_reversion | 2026-09-22 08:43:49 | 2026-09-22 08:45:26 | BROKER_TAKE_PROFIT | 1.6 | 11.48 | 2.0 | 0.95 | 0.00 | 2.01 |  | SHORT_USD |
| 1431 | AUD_USD | SELL | mean_reversion | 2026-09-22 08:43:49 | 2026-09-22 08:51:39 | BROKER_STOP_LOSS | 7.8 | 7.24 | 2.0 | 0.19 | 1.73 | -0.99 | A | LONG_USD |
| 1435 | EUR_USD | SELL | trend | 2026-09-22 08:51:57 | 2026-09-22 09:56:27 | BROKER_STOP_LOSS | 64.5 | 9.58 | 2.0 | 1.10 | 1.00 | -1.01 | D | LONG_USD |
| 1424 | EUR_USD | SELL | mean_reversion | 2026-09-22 08:51:57 | 2026-09-22 09:35:39 | BOT_PROFIT_PROTECTION | 43.7 | 6.72 | 2.0 | 1.47 | 0.49 | 0.88 |  | LONG_USD |
| 1433 | USD_CHF | BUY | scalp | 2026-09-22 09:05:14 | 2026-09-22 09:25:44 | BROKER_STOP_LOSS | 20.5 | 9.60 | 2.0 | 0.00 | 1.22 | -1.00 | A | LONG_USD |
| 1434 | USD_CAD | BUY | scalp | 2026-09-22 09:27:39 | 2026-09-22 09:47:09 | BROKER_STOP_LOSS | 19.5 | 8.16 | 2.0 | 0.20 | 1.27 | -1.02 | A | LONG_USD |
| 1437 | USD_CHF | SELL | mean_reversion | 2026-09-22 09:33:46 | 2026-09-22 10:20:20 | MANUAL | 46.6 | 9.98 | 2.0 | 1.18 | 0.34 | 0.16 |  | SHORT_USD |
| 1436 | AUD_USD | SELL | scalp | 2026-09-22 09:49:02 | 2026-09-22 10:06:16 | BROKER_STOP_LOSS | 17.2 | 8.65 | 2.0 | 0.00 | 1.45 | -1.01 | A | LONG_USD |
| 1432 | AUD_USD | SELL | scalp | 2026-09-22 09:49:02 | 2026-09-22 10:05:14 | BOT_PROFIT_PROTECTION | 16.2 | 7.85 | 2.0 | 1.41 | 0.56 | 1.38 |  | LONG_USD |
| 1440 | EUR_USD | BUY | trend | 2026-09-22 10:23:40 | 2026-09-22 13:27:25 | BROKER_STOP_LOSS | 183.7 | 11.35 | 2.0 | 0.42 | 1.10 | -1.00 | B | SHORT_USD |
| 1438 | USD_CHF | SELL | mean_reversion | 2026-09-22 10:28:47 | 2026-09-22 12:52:30 | BROKER_STOP_LOSS | 143.7 | 12.09 | 2.0 | 0.67 | 1.17 | -1.01 | C | SHORT_USD |
| 1445 | AUD_USD | SELL | swing_mean_reversion | 2026-09-22 11:11:32 | 2026-09-22 15:45:32 | BOT_PROFIT_PROTECTION | 274.0 | 7.20 | 2.0 | 1.42 | 1.36 | 1.11 |  | LONG_USD |
| 1439 | USD_JPY | BUY | mean_reversion | 2026-09-22 12:53:20 | 2026-09-22 13:02:37 | BROKER_STOP_LOSS | 9.3 | 11.50 | 2.0 | 0.00 | 1.03 | -1.01 | A | LONG_USD |
| 1442 | GBP_USD | BUY | mean_reversion | 2026-09-22 12:56:23 | 2026-09-22 14:17:31 | BROKER_STOP_LOSS | 81.1 | 8.98 | 2.0 | 0.97 | 1.09 | -1.01 | C | SHORT_USD |
| 1441 | USD_CAD | BUY | swing_trend | 2026-09-22 13:03:31 | 2026-09-22 13:45:42 | BROKER_STOP_LOSS | 42.2 | 4.79 | 2.0 | 0.69 | 1.50 | -1.04 | C | LONG_USD |
| 1443 | EUR_USD | SELL | trend | 2026-09-22 13:47:20 | 2026-09-22 15:20:03 | BOT_PROFIT_PROTECTION | 92.7 | 6.14 | 2.0 | 1.50 | 0.75 | 1.11 |  | LONG_USD |
| 1444 | GBP_USD | SELL | scalp | 2026-09-22 14:20:03 | 2026-09-22 14:39:11 | BROKER_STOP_LOSS | 19.1 | 10.26 | 2.0 | 0.00 | 0.91 | -0.99 | A | LONG_USD |
| 1447 | USD_JPY | SELL | mean_reversion | 2026-09-22 14:41:27 | 2026-09-22 15:31:37 | BROKER_STOP_LOSS | 50.2 | 11.44 | 2.0 | 0.44 | 1.06 | -1.00 | B | SHORT_USD |
| 1448 | AUD_USD | BUY | swing_breakout | 2026-09-22 14:47:34 | 2026-09-22 15:45:18 | BROKER_STOP_LOSS | 57.7 | 5.91 | 2.0 | 0.71 | 1.76 | -1.00 | C | SHORT_USD |
| 1446 | GBP_USD | SELL | scalp | 2026-09-22 15:29:19 | 2026-09-22 16:15:04 | BOT_PROFIT_PROTECTION | 45.7 | 10.76 | 2.0 | 1.40 | 0.42 | 1.20 |  | LONG_USD |
| 1449 | GBP_USD | SELL | scalp | 2026-09-22 15:29:19 | 2026-09-22 16:50:41 | BOT_PROFIT_PROTECTION | 81.4 | 11.66 | 2.0 | 1.42 | 0.22 | 1.30 |  | LONG_USD |
| 1451 | AUD_USD | SELL | swing_trend | 2026-09-22 15:50:42 | 2026-09-22 16:44:06 | BROKER_STOP_LOSS | 53.4 | 6.26 | 2.0 | 0.00 | 1.65 | -1.02 | A | LONG_USD |
| 1452 | USD_CHF | BUY | trend | 2026-09-22 16:08:03 | 2026-09-22 16:49:50 | BROKER_STOP_LOSS | 41.8 | 7.05 | 2.0 | 0.11 | 1.30 | -1.01 | A | LONG_USD |
| 1450 | USD_CHF | BUY | scalp | 2026-09-22 16:08:03 | 2026-09-22 17:06:01 | BOT_PROFIT_PROTECTION | 58.0 | 8.52 | 2.0 | 1.42 | 0.73 | 1.24 |  | LONG_USD |
| 1453 | USD_JPY | BUY | trend | 2026-09-22 16:44:43 | 2026-09-22 16:49:56 | BROKER_STOP_LOSS | 5.2 | 7.50 | 2.0 | 0.20 | 0.93 | -1.00 | A | LONG_USD |
| 1456 | EUR_USD | SELL | mean_reversion | 2026-09-22 16:50:50 | 2026-09-22 18:14:04 | BROKER_STOP_LOSS | 83.2 | 5.68 | 2.0 | 1.14 | 1.14 | -1.02 | D | LONG_USD |
| 1454 | AUD_USD | SELL | swing_mean_reversion | 2026-09-22 16:50:51 | 2026-09-22 17:52:47 | BROKER_STOP_LOSS | 61.9 | 5.06 | 2.0 | 0.55 | 1.98 | -1.01 | C | LONG_USD |
| 1458 | GBP_USD | SELL | swing_trend | 2026-09-22 17:53:55 | 2026-09-22 19:15:00 | BROKER_STOP_LOSS | 81.1 | 7.18 | 2.0 | 0.43 | 1.27 | -1.00 | B | LONG_USD |
| 1457 | USD_JPY | SELL | mean_reversion | 2026-09-22 17:57:59 | 2026-09-22 18:31:51 | BROKER_STOP_LOSS | 33.9 | 9.24 | 2.0 | 0.27 | 1.22 | -1.00 | B | SHORT_USD |
| 1460 | AUD_USD | SELL | swing_mean_reversion | 2026-09-22 18:15:16 | 2026-09-22 19:32:50 | BROKER_STOP_LOSS | 77.6 | 3.99 | 2.0 | 0.93 | 1.93 | -1.03 | C | LONG_USD |
| 1462 | USD_JPY | SELL | mean_reversion | 2026-09-22 18:38:39 | 2026-09-22 19:35:57 | BROKER_TAKE_PROFIT | 57.3 | 11.80 | 2.0 | 1.85 | 0.36 | 2.00 |  | SHORT_USD |
| 1455 | USD_JPY | SELL | trend | 2026-09-22 18:38:39 | 2026-09-22 18:55:57 | BOT_PROFIT_PROTECTION | 17.3 | 8.90 | 2.0 | 1.69 | 0.63 | 1.52 |  | SHORT_USD |
| 1459 | USD_CHF | BUY | swing_trend | 2026-09-22 19:16:16 | 2026-09-22 19:25:29 | BROKER_STOP_LOSS | 9.2 | 4.67 | 2.0 | 0.00 | 1.52 | -1.11 | A | LONG_USD |
| 1461 | USD_CHF | BUY | swing_breakout | 2026-09-22 19:26:26 | 2026-09-22 19:32:28 | BROKER_STOP_LOSS | 6.0 | 4.46 | 2.0 | 0.00 | 1.59 | -1.01 | A | LONG_USD |
| 1463 | GBP_USD | SELL | swing_trend | 2026-09-22 19:33:33 | 2026-09-22 19:35:57 | BROKER_STOP_LOSS | 2.4 | 5.82 | 2.0 | 0.00 | 1.37 | -1.01 | A | LONG_USD |
| 1464 | AUD_USD | BUY | swing_breakout | 2026-09-22 19:33:33 | 2026-09-22 20:44:13 | BROKER_STOP_LOSS | 70.7 | 3.51 | 2.0 | 0.88 | 2.11 | -1.00 | C | SHORT_USD |
| 1465 | USD_CAD | BUY | swing_mean_reversion | 2026-09-22 19:35:36 | 2026-09-22 21:04:55 | BROKER_STOP_LOSS | 89.3 | 5.73 | 2.0 | 0.44 | 1.52 | -1.06 | B | LONG_USD |
| 1468 | EUR_USD | SELL | swing_mean_reversion | 2026-09-22 19:37:37 | 2026-09-22 22:30:32 | BOT_PROFIT_PROTECTION | 172.9 | 4.39 | 2.0 | 1.37 | 0.52 | 1.19 |  | LONG_USD |
| 1466 | USD_JPY | SELL | trend | 2026-09-22 20:52:51 | 2026-09-22 21:05:00 | BROKER_STOP_LOSS | 12.2 | 5.66 | 2.0 | 0.07 | 1.18 | -1.06 | A | SHORT_USD |
| 1467 | USD_JPY | BUY | swing_breakout | 2026-09-22 21:21:22 | 2026-09-22 21:22:30 | BROKER_STOP_LOSS | 1.1 | 5.06 | 2.0 | 0.00 | 1.05 | -1.32 | A | LONG_USD |
| 1469 | USD_JPY | BUY | mean_reversion | 2026-09-22 21:23:24 | 2026-09-22 21:35:16 | BROKER_STOP_LOSS | 11.9 | 5.06 | 2.0 | 0.00 | 0.83 | -1.01 | A | LONG_USD |
| 1471 | GBP_USD | BUY | swing_breakout | 2026-09-22 21:35:37 | 2026-09-22 21:48:59 | BROKER_STOP_LOSS | 13.4 | 4.79 | 2.0 | 0.40 | 0.88 | -1.13 | B | SHORT_USD |
| 1470 | USD_JPY | BUY | swing_breakout | 2026-09-22 21:41:44 | 2026-09-22 21:42:01 | BROKER_STOP_LOSS | 0.3 | 4.34 | 2.0 | 0.00 | 0.00 | -1.11 | A | LONG_USD |
| 1472 | USD_JPY | BUY | scalp | 2026-09-22 21:56:00 | 2026-09-22 21:59:56 | BROKER_STOP_LOSS | 3.9 | 4.28 | 2.0 | 0.00 | 1.22 | -1.00 | A | LONG_USD |
| 1473 | EUR_USD | BUY | swing_trend | 2026-09-22 21:58:02 | 2026-09-22 22:00:26 | BROKER_STOP_LOSS | 2.4 | 3.38 | 2.0 | 0.00 | 0.65 | -0.98 | A | SHORT_USD |
| 1474 | GBP_USD | BUY | swing_breakout | 2026-09-22 22:04:09 | 2026-09-22 22:23:57 | MANUAL | 19.8 | 5.45 | 2.0 | 0.24 | 0.77 | 0.02 |  | SHORT_USD |
| 1475 | USD_CAD | SELL | swing_mean_reversion | 2026-09-22 22:06:11 | 2026-09-22 22:26:12 | MANUAL | 20.0 | 4.19 | 2.0 | 0.05 | 1.27 | -0.21 |  | SHORT_USD |
| 1476 | USD_JPY | BUY | trend | 2026-09-22 22:20:26 | 2026-09-22 22:26:26 | MANUAL | 6.0 | 6.02 | 2.0 | 0.00 | 0.71 | -0.55 |  | LONG_USD |
| 1477 | AUD_USD | BUY | swing_breakout | 2026-09-22 22:35:47 | 2026-09-22 22:59:02 | BROKER_STOP_LOSS | 23.3 | 2.70 | 2.0 | 0.00 | 2.41 | -1.04 | A | SHORT_USD |
| 1479 | GBP_USD | BUY | swing_mean_reversion | 2026-09-22 23:20:31 | 2026-09-23 00:04:31 | BROKER_STOP_LOSS | 44.0 | 4.57 | 2.0 | 0.24 | 1.31 | -1.01 | A | SHORT_USD |
| 1478 | AUD_USD | BUY | swing_trend | 2026-09-22 23:40:52 | 2026-09-23 00:00:41 | BROKER_STOP_LOSS | 19.8 | 2.46 | 2.0 | 0.04 | 2.44 | -1.02 | A | SHORT_USD |
| 1482 | GBP_USD | BUY | swing_mean_reversion | 2026-09-23 00:05:27 | 2026-09-23 00:37:01 | BROKER_STOP_LOSS | 31.6 | 3.74 | 2.0 | 0.27 | 1.36 | -0.99 | B | SHORT_USD |
| 1480 | USD_JPY | BUY | trend | 2026-09-23 00:24:50 | 2026-09-23 01:10:33 | BOT_PROFIT_PROTECTION | 45.7 | 6.34 | 2.0 | 1.51 | 0.74 | 0.87 |  | LONG_USD |
| 1483 | AUD_USD | BUY | swing_trend | 2026-09-23 00:27:53 | 2026-09-23 00:38:14 | BROKER_STOP_LOSS | 10.3 | 2.17 | 2.0 | 0.42 | 2.72 | -1.06 | B | SHORT_USD |
| 1486 | AUD_USD | BUY | swing_trend | 2026-09-23 00:39:05 | 2026-09-23 01:13:03 | BROKER_STOP_LOSS | 34.0 | 2.21 | 2.0 | 1.17 | 2.58 | -0.99 | D | SHORT_USD |
| 1484 | USD_CHF | SELL | swing_breakout | 2026-09-23 00:42:08 | 2026-09-23 00:42:26 | BROKER_STOP_LOSS | 0.3 | 2.26 | 2.0 | 0.00 | 1.95 | -1.02 | A | SHORT_USD |
| 1485 | USD_CHF | SELL | swing_breakout | 2026-09-23 00:45:12 | 2026-09-23 00:59:37 | BROKER_STOP_LOSS | 14.4 | 2.38 | 2.0 | 0.38 | 2.06 | -1.01 | B | SHORT_USD |
| 1487 | EUR_USD | BUY | swing_trend | 2026-09-23 01:03:30 | 2026-09-23 01:15:13 | BROKER_STOP_LOSS | 11.7 | 2.20 | 2.0 | 0.27 | 1.23 | -1.00 | B | SHORT_USD |
| 1488 | USD_CAD | SELL | swing_trend | 2026-09-23 01:13:41 | 2026-09-23 01:15:50 | BROKER_STOP_LOSS | 2.2 | 2.61 | 2.0 | 0.00 | 1.99 | -1.00 | A | SHORT_USD |
| 1489 | AUD_USD | BUY | swing_mean_reversion | 2026-09-23 01:19:47 | 2026-09-23 01:21:58 | BROKER_STOP_LOSS | 2.2 | 2.67 | 2.0 | 0.00 | 2.24 | -1.01 | A | SHORT_USD |
| 1481 | AUD_USD | BUY | swing_mean_reversion | 2026-09-23 01:19:47 | 2026-09-23 01:25:51 | BOT_PROFIT_PROTECTION | 6.1 | 2.25 | 2.0 | 1.46 | 2.53 | 1.69 |  | SHORT_USD |
| 1493 | USD_CAD | BUY | swing_trend | 2026-09-23 01:20:49 | 2026-09-23 01:34:18 | BROKER_STOP_LOSS | 13.5 | 2.89 | 2.0 | 0.59 | 1.84 | -1.04 | C | LONG_USD |
| 1490 | EUR_USD | BUY | swing_trend | 2026-09-23 01:23:52 | 2026-09-23 01:27:18 | BROKER_STOP_LOSS | 3.4 | 2.56 | 2.0 | 0.00 | 0.90 | -1.02 | A | SHORT_USD |
| 1492 | USD_CHF | BUY | swing_breakout | 2026-09-23 01:31:00 | 2026-09-23 01:32:44 | BROKER_STOP_LOSS | 1.7 | 3.19 | 2.0 | 0.00 | 1.95 | -1.00 | A | LONG_USD |
| 1494 | EUR_USD | BUY | swing_breakout | 2026-09-23 01:34:02 | 2026-09-23 01:55:39 | BROKER_STOP_LOSS | 21.6 | 2.76 | 2.0 | 0.25 | 1.12 | -1.01 | B | SHORT_USD |
| 1495 | AUD_USD | SELL | swing_trend | 2026-09-23 01:34:03 | 2026-09-23 02:03:35 | BROKER_TAKE_PROFIT | 29.5 | 2.96 | 2.0 | 1.25 | 2.30 | 1.99 |  | LONG_USD |
| 1497 | USD_JPY | BUY | swing_breakout | 2026-09-23 01:35:04 | 2026-09-23 04:28:21 | BROKER_STOP_LOSS | 173.3 | 9.06 | 2.0 | 0.74 | 0.99 | -1.00 | C | LONG_USD |
| 1491 | USD_JPY | BUY | mean_reversion | 2026-09-23 01:35:04 | 2026-09-23 02:30:59 | BOT_PROFIT_PROTECTION | 55.9 | 8.68 | 2.0 | 1.52 | 0.85 | 1.14 |  | LONG_USD |
| 1498 | USD_JPY | SELL | swing_breakout | 2026-09-23 04:33:00 | 2026-09-23 04:58:32 | BROKER_STOP_LOSS | 25.5 | 6.50 | 2.0 | 0.29 | 1.08 | -1.02 | B | SHORT_USD |
| 1499 | AUD_USD | SELL | swing_trend | 2026-09-23 04:49:17 | 2026-09-23 05:24:46 | BROKER_STOP_LOSS | 35.5 | 3.53 | 2.0 | 0.20 | 2.15 | -0.99 | A | LONG_USD |
| 1496 | AUD_USD | SELL | swing_mean_reversion | 2026-09-23 04:49:17 | 2026-09-23 04:55:23 | BOT_PROFIT_PROTECTION | 6.1 | 3.65 | 2.0 | 1.62 | 1.92 | 1.12 |  | LONG_USD |
| 1500 | USD_JPY | SELL | trend | 2026-09-23 05:10:38 | 2026-09-23 05:39:14 | BROKER_STOP_LOSS | 28.6 | 7.80 | 2.0 | 0.32 | 1.08 | -1.00 | B | SHORT_USD |
| 1502 | GBP_USD | SELL | swing_breakout | 2026-09-23 05:50:15 | 2026-09-23 05:54:21 | BROKER_STOP_LOSS | 4.1 | 3.77 | 2.0 | 0.00 | 1.46 | -1.01 | A | LONG_USD |
| 1501 | AUD_USD | SELL | swing_breakout | 2026-09-23 05:56:22 | 2026-09-23 06:45:10 | BOT_PROFIT_PROTECTION | 48.8 | 3.23 | 2.0 | 1.58 | 1.55 | 1.42 |  | LONG_USD |
| 1504 | EUR_USD | SELL | swing_trend | 2026-09-23 06:18:43 | 2026-09-23 06:38:53 | BROKER_STOP_LOSS | 20.2 | 3.09 | 2.0 | 0.19 | 1.45 | -1.07 | A | LONG_USD |
| 1503 | EUR_USD | SELL | swing_trend | 2026-09-23 06:18:43 | 2026-09-23 07:15:40 | BOT_PROFIT_PROTECTION | 56.9 | 3.33 | 2.0 | 1.56 | 1.14 | 1.32 |  | LONG_USD |
| 1507 | USD_CHF | BUY | swing_breakout | 2026-09-23 06:56:22 | 2026-09-23 08:10:37 | BOT_PROFIT_PROTECTION | 74.2 | 3.46 | 2.0 | 1.62 | 1.01 | 1.39 |  | LONG_USD |
| 1505 | AUD_USD | SELL | swing_breakout | 2026-09-23 07:11:38 | 2026-09-23 07:55:20 | BOT_PROFIT_PROTECTION | 43.7 | 3.56 | 2.0 | 1.35 | 1.91 | 1.32 |  | LONG_USD |
| 1508 | GBP_USD | SELL | swing_trend | 2026-09-23 07:12:39 | 2026-09-23 07:16:53 | BROKER_STOP_LOSS | 4.2 | 5.20 | 2.0 | 0.00 | 1.02 | -1.04 | A | LONG_USD |
| 1509 | EUR_USD | SELL | swing_breakout | 2026-09-23 07:19:46 | 2026-09-23 07:57:21 | BROKER_TAKE_PROFIT | 37.6 | 3.85 | 2.0 | 1.69 | 0.67 | 1.97 |  | LONG_USD |
| 1506 | USD_JPY | BUY | swing_mean_reversion | 2026-09-23 07:58:25 | 2026-09-23 08:10:36 | BOT_PROFIT_PROTECTION | 12.2 | 7.24 | 2.0 | 1.49 | 0.43 | 1.09 |  | LONG_USD |
| 1513 | USD_JPY | BUY | trend | 2026-09-23 07:58:25 | 2026-09-23 10:20:47 | BOT_PROFIT_PROTECTION | 142.4 | 8.76 | 2.0 | 1.36 | 0.62 | 1.08 |  | LONG_USD |
| 1511 | AUD_USD | SELL | swing_breakout | 2026-09-23 08:11:38 | 2026-09-23 08:25:34 | BROKER_STOP_LOSS | 13.9 | 5.53 | 2.0 | 0.14 | 1.66 | -1.01 | A | LONG_USD |
| 1510 | AUD_USD | SELL | swing_mean_reversion | 2026-09-23 08:11:38 | 2026-09-23 09:10:37 | BOT_PROFIT_PROTECTION | 59.0 | 4.82 | 2.0 | 1.43 | 1.37 | 1.18 |  | LONG_USD |
| 1512 | GBP_USD | SELL | swing_breakout | 2026-09-23 08:26:53 | 2026-09-23 10:15:41 | BOT_PROFIT_PROTECTION | 108.8 | 7.65 | 2.0 | 1.37 | 0.88 | 1.20 |  | LONG_USD |
| 1518 | EUR_USD | SELL | swing_breakout | 2026-09-23 09:21:48 | 2026-09-23 11:00:48 | BROKER_STOP_LOSS | 99.0 | 5.87 | 2.0 | 1.02 | 0.97 | -1.06 | D | LONG_USD |
| 1515 | USD_CHF | BUY | swing_mean_reversion | 2026-09-23 09:51:17 | 2026-09-23 10:06:35 | BROKER_STOP_LOSS | 15.3 | 5.55 | 2.0 | 0.00 | 1.39 | -1.01 | A | LONG_USD |
| 1516 | USD_CAD | SELL | swing_mean_reversion | 2026-09-23 10:05:31 | 2026-09-23 10:12:32 | BROKER_STOP_LOSS | 7.0 | 5.41 | 2.0 | 0.00 | 1.59 | -1.00 | A | SHORT_USD |
| 1514 | USD_CHF | BUY | swing_mean_reversion | 2026-09-23 10:07:34 | 2026-09-23 10:50:16 | BOT_PROFIT_PROTECTION | 42.7 | 5.42 | 2.0 | 1.38 | 1.16 | 0.98 |  | LONG_USD |
| 1517 | USD_JPY | SELL | swing_mean_reversion | 2026-09-23 10:21:48 | 2026-09-23 10:31:11 | BROKER_STOP_LOSS | 9.4 | 8.12 | 2.0 | 0.00 | 1.05 | -1.00 | A | SHORT_USD |
| 1519 | USD_JPY | SELL | swing_mean_reversion | 2026-09-23 10:31:58 | 2026-09-23 11:26:26 | BROKER_STOP_LOSS | 54.5 | 8.36 | 2.0 | 0.57 | 1.27 | -1.00 | C | SHORT_USD |
| 1520 | EUR_USD | SELL | swing_mean_reversion | 2026-09-23 11:03:28 | 2026-09-23 12:40:04 | BOT_PROFIT_PROTECTION | 96.6 | 5.19 | 2.0 | 1.93 | 0.98 | 1.56 |  | LONG_USD |
| 1524 | USD_JPY | BUY | swing_mean_reversion | 2026-09-23 12:31:56 | 2026-09-23 12:56:37 | BROKER_STOP_LOSS | 24.7 | 6.96 | 2.0 | 0.37 | 1.09 | -1.03 | B | LONG_USD |
| 1523 | USD_CAD | BUY | swing_mean_reversion | 2026-09-23 12:40:05 | 2026-09-23 12:48:33 | BROKER_STOP_LOSS | 8.5 | 6.12 | 2.0 | 0.00 | 1.55 | -1.01 | A | LONG_USD |
| 1525 | EUR_USD | SELL | swing_mean_reversion | 2026-09-23 12:50:16 | 2026-09-23 13:27:28 | BROKER_STOP_LOSS | 37.2 | 6.05 | 2.0 | 0.64 | 1.34 | -1.01 | C | LONG_USD |
| 1526 | GBP_USD | SELL | mean_reversion | 2026-09-23 12:57:23 | 2026-09-23 13:27:27 | BROKER_STOP_LOSS | 30.1 | 9.39 | 2.0 | 0.89 | 1.45 | -1.01 | C | LONG_USD |
| 1522 | GBP_USD | SELL | scalp | 2026-09-23 12:57:23 | 2026-09-23 13:40:05 | BOT_PROFIT_PROTECTION | 42.7 | 9.48 | 2.0 | 1.49 | 0.80 | 1.32 |  | LONG_USD |
| 1527 | USD_JPY | SELL | swing_mean_reversion | 2026-09-23 13:12:39 | 2026-09-23 13:30:04 | BROKER_TAKE_PROFIT | 17.4 | 8.34 | 2.0 | 1.74 | 0.29 | 2.03 |  | SHORT_USD |
| 1528 | USD_CHF | BUY | swing_trend | 2026-09-23 13:28:56 | 2026-09-23 13:31:24 | BROKER_STOP_LOSS | 2.5 | 5.35 | 2.0 | 0.00 | 1.20 | -1.05 | A | LONG_USD |
| 1521 | USD_CHF | BUY | swing_trend | 2026-09-23 13:28:56 | 2026-09-23 13:30:55 | BOT_PROFIT_PROTECTION | 2.0 | 5.37 | 2.0 | 1.64 | 1.32 | 1.71 |  | LONG_USD |
| 1531 | EUR_USD | SELL | swing_mean_reversion | 2026-09-23 13:29:56 | 2026-09-23 13:48:44 | BROKER_TAKE_PROFIT | 18.8 | 6.51 | 2.0 | 2.27 | 0.32 | 2.01 |  | LONG_USD |
| 1529 | AUD_USD | SELL | mean_reversion | 2026-09-23 13:31:59 | 2026-09-23 14:45:13 | BOT_PROFIT_PROTECTION | 73.2 | 6.60 | 2.0 | 1.50 | 0.44 | 1.62 |  | LONG_USD |
| 1530 | USD_JPY | SELL | swing_mean_reversion | 2026-09-23 13:41:09 | 2026-09-23 13:45:24 | BROKER_STOP_LOSS | 4.2 | 13.56 | 2.0 | 0.00 | 0.86 | -1.03 | A | SHORT_USD |
| 1532 | USD_CAD | BUY | mean_reversion | 2026-09-23 13:45:13 | 2026-09-23 15:31:00 | BOT_PROFIT_PROTECTION | 105.8 | 8.81 | 2.0 | 1.59 | 0.64 | 1.15 |  | LONG_USD |
| 1533 | USD_JPY | BUY | swing_mean_reversion | 2026-09-23 14:32:01 | 2026-09-23 14:53:47 | BROKER_STOP_LOSS | 21.8 | 20.12 | 2.0 | 0.09 | 1.01 | -0.99 | A | LONG_USD |
| 1535 | USD_JPY | BUY | mean_reversion | 2026-09-23 15:45:13 | 2026-09-23 16:35:55 | BROKER_STOP_LOSS | 50.7 | 12.96 | 2.0 | 0.16 | 1.13 | -1.00 | A | LONG_USD |
| 1534 | USD_JPY | BUY | trend | 2026-09-23 15:45:13 | 2026-09-23 16:43:11 | BOT_PROFIT_PROTECTION | 58.0 | 19.96 | 2.0 | 1.37 | 0.00 | 1.17 |  | LONG_USD |
| 1537 | USD_JPY | SELL | scalp | 2026-09-23 16:40:08 | 2026-09-23 16:51:29 | BROKER_STOP_LOSS | 11.4 | 9.34 | 2.0 | 0.00 | 1.05 | -1.01 | A | SHORT_USD |
| 1539 | USD_CHF | BUY | trend | 2026-09-23 16:50:19 | 2026-09-23 17:34:48 | BROKER_STOP_LOSS | 44.5 | 5.95 | 2.0 | 1.04 | 1.34 | -1.01 | D | LONG_USD |
| 1541 | USD_JPY | SELL | scalp | 2026-09-23 16:52:21 | 2026-09-23 17:43:39 | BROKER_TAKE_PROFIT | 51.3 | 9.60 | 2.0 | 1.94 | 0.61 | 2.00 |  | SHORT_USD |
| 1542 | EUR_USD | SELL | mean_reversion | 2026-09-23 16:56:26 | 2026-09-23 17:43:55 | BROKER_STOP_LOSS | 47.5 | 7.38 | 2.0 | 1.10 | 0.99 | -1.00 | D | LONG_USD |
| 1538 | EUR_USD | SELL | mean_reversion | 2026-09-23 16:56:26 | 2026-09-23 17:55:24 | BOT_PROFIT_PROTECTION | 59.0 | 7.54 | 2.0 | 1.84 | 0.44 | 1.47 |  | LONG_USD |
| 1540 | USD_CHF | BUY | swing_breakout | 2026-09-23 17:38:09 | 2026-09-23 17:42:04 | BROKER_STOP_LOSS | 3.9 | 6.32 | 2.0 | 0.00 | 1.47 | -1.00 | A | LONG_USD |
| 1543 | AUD_USD | SELL | swing_trend | 2026-09-23 17:43:14 | 2026-09-23 17:59:31 | BROKER_STOP_LOSS | 16.3 | 5.73 | 2.0 | 0.00 | 1.73 | -1.01 | A | LONG_USD |
| 1536 | GBP_USD | SELL | scalp | 2026-09-23 17:46:18 | 2026-09-23 17:50:19 | BOT_PROFIT_PROTECTION | 4.0 | 13.62 | 2.0 | 1.81 | 0.59 | 1.67 |  | LONG_USD |
| 1545 | USD_JPY | SELL | scalp | 2026-09-23 17:47:19 | 2026-09-23 18:45:29 | BROKER_STOP_LOSS | 58.2 | 13.74 | 2.0 | 0.33 | 1.06 | -1.00 | B | SHORT_USD |
| 1544 | USD_CHF | SELL | mean_reversion | 2026-09-23 17:58:31 | 2026-09-23 18:21:43 | BROKER_STOP_LOSS | 23.2 | 7.56 | 2.0 | 0.05 | 1.42 | -1.04 | A | SHORT_USD |
| 1547 | AUD_USD | SELL | trend | 2026-09-23 18:00:33 | 2026-09-23 21:05:31 | BROKER_STOP_LOSS | 185.0 | 6.53 | 2.0 | 0.84 | 1.70 | -1.07 | C | LONG_USD |
| 1546 | USD_CHF | SELL | trend | 2026-09-23 18:28:02 | 2026-09-23 20:50:24 | BROKER_STOP_LOSS | 142.4 | 7.53 | 2.0 | 0.57 | 1.35 | -1.00 | C | SHORT_USD |
| 1548 | USD_JPY | BUY | swing_trend | 2026-09-23 21:08:44 | 2026-09-23 21:10:01 | BROKER_STOP_LOSS | 1.3 | 4.90 | 2.0 | 0.00 | 0.98 | -1.08 | A | LONG_USD |
| 1549 | EUR_USD | SELL | swing_trend | 2026-09-23 21:10:46 | 2026-09-23 21:21:49 | BROKER_STOP_LOSS | 11.1 | 4.11 | 2.0 | 0.05 | 1.26 | -1.00 | A | LONG_USD |
| 1550 | EUR_USD | SELL | swing_trend | 2026-09-23 21:22:58 | 2026-09-23 21:35:20 | BROKER_STOP_LOSS | 12.4 | 4.21 | 2.0 | 0.00 | 0.90 | -1.02 | A | LONG_USD |
| 1553 | AUD_USD | BUY | swing_trend | 2026-09-23 22:02:41 | 2026-09-23 23:34:00 | BROKER_STOP_LOSS | 91.3 | 3.76 | 2.0 | 0.35 | 2.07 | -1.01 | B | SHORT_USD |
| 1552 | USD_JPY | SELL | mean_reversion | 2026-09-23 22:05:44 | 2026-09-23 23:32:43 | BROKER_STOP_LOSS | 87.0 | 7.68 | 2.0 | 0.77 | 1.04 | -1.00 | C | SHORT_USD |
| 1559 | AUD_USD | BUY | swing_breakout | 2026-09-23 23:56:21 | 2026-09-24 00:22:24 | BROKER_STOP_LOSS | 26.1 | 2.87 | 2.0 | 0.56 | 2.44 | -1.01 | C | SHORT_USD |
| 1557 | USD_CAD | BUY | swing_mean_reversion | 2026-09-24 00:05:30 | 2026-09-24 01:20:46 | BOT_PROFIT_PROTECTION | 75.3 | 2.69 | 2.0 | 1.82 | 2.00 | 1.23 |  | LONG_USD |
| 1566 | USD_JPY | SELL | swing_mean_reversion | 2026-09-24 00:11:36 | 2026-09-24 00:26:22 | BROKER_TAKE_PROFIT | 14.8 | 8.80 | 2.0 | 1.73 | 0.30 | 2.01 |  | SHORT_USD |
| 1562 | EUR_USD | SELL | swing_mean_reversion | 2026-09-24 00:21:46 | 2026-09-24 00:25:04 | BROKER_STOP_LOSS | 3.3 | 2.44 | 2.0 | 0.00 | 1.07 | -0.98 | A | LONG_USD |
| 1551 | EUR_USD | SELL | swing_trend | 2026-09-24 00:21:46 | 2026-09-24 00:30:05 | BOT_PROFIT_PROTECTION | 8.3 | 3.99 | 2.0 | 1.35 | 1.05 | 1.15 |  | LONG_USD |
| 1563 | AUD_USD | SELL | swing_breakout | 2026-09-24 00:23:49 | 2026-09-24 00:24:41 | BROKER_STOP_LOSS | 0.9 | 3.37 | 2.0 | 0.00 | 2.08 | -1.01 | A | LONG_USD |
| 1588 | USD_CHF | BUY | swing_breakout | 2026-09-24 00:26:52 | 2026-09-24 01:00:23 | BROKER_STOP_LOSS | 33.5 | 3.05 | 2.0 | 1.28 | 1.87 | -1.02 | D | LONG_USD |
| 1587 | USD_JPY | BUY | swing_mean_reversion | 2026-09-24 00:28:54 | 2026-09-24 00:53:28 | BROKER_STOP_LOSS | 24.6 | 10.38 | 2.0 | 0.79 | 2.75 | -1.01 | C | LONG_USD |
| 1601 | USD_JPY | SELL | scalp | 2026-09-24 00:55:20 | 2026-09-24 05:48:44 | BROKER_STOP_LOSS | 293.4 | 20.64 | 2.0 | 1.06 | 1.05 | -1.00 | D | SHORT_USD |
| 1589 | EUR_USD | SELL | swing_breakout | 2026-09-24 01:00:25 | 2026-09-24 01:08:00 | BROKER_STOP_LOSS | 7.6 | 3.15 | 2.0 | 0.00 | 1.05 | -1.02 | A | LONG_USD |
| 1590 | USD_CHF | BUY | swing_trend | 2026-09-24 01:02:28 | 2026-09-24 01:08:00 | BROKER_STOP_LOSS | 5.5 | 3.32 | 2.0 | 0.00 | 1.48 | -0.99 | A | LONG_USD |
| 1591 | AUD_USD | SELL | swing_mean_reversion | 2026-09-24 01:08:34 | 2026-09-24 01:10:57 | BROKER_STOP_LOSS | 2.4 | 3.69 | 2.0 | 0.00 | 1.95 | -1.00 | A | LONG_USD |
| 1592 | AUD_USD | SELL | swing_mean_reversion | 2026-09-24 01:11:37 | 2026-09-24 01:30:01 | BROKER_STOP_LOSS | 18.4 | 3.83 | 2.0 | 0.94 | 1.54 | -1.07 | C | LONG_USD |
| 1593 | AUD_USD | SELL | swing_trend | 2026-09-24 01:31:57 | 2026-09-24 01:34:14 | BROKER_STOP_LOSS | 2.3 | 4.38 | 2.0 | 0.00 | 1.30 | -1.00 | A | LONG_USD |
| 1594 | USD_CHF | BUY | swing_breakout | 2026-09-24 01:38:04 | 2026-09-24 01:53:18 | BROKER_STOP_LOSS | 15.2 | 4.19 | 2.0 | 0.21 | 1.58 | -1.00 | A | LONG_USD |
| 1597 | AUD_USD | SELL | scalp | 2026-09-24 02:00:25 | 2026-09-24 02:33:14 | BROKER_STOP_LOSS | 32.8 | 7.67 | 2.0 | 0.65 | 1.58 | -1.08 | C | LONG_USD |
| 1596 | GBP_USD | SELL | swing_trend | 2026-09-24 02:05:30 | 2026-09-24 02:29:37 | BROKER_STOP_LOSS | 24.1 | 6.47 | 2.0 | 0.28 | 1.10 | -1.04 | B | LONG_USD |
| 1598 | EUR_USD | SELL | swing_breakout | 2026-09-24 02:30:54 | 2026-09-24 02:42:51 | BROKER_STOP_LOSS | 12.0 | 5.66 | 2.0 | 0.00 | 1.02 | -1.01 | A | LONG_USD |
| 1595 | EUR_USD | SELL | swing_mean_reversion | 2026-09-24 02:30:54 | 2026-09-24 03:00:24 | BOT_PROFIT_PROTECTION | 29.5 | 3.43 | 2.0 | 1.37 | 0.96 | 1.11 |  | LONG_USD |
| 1599 | AUD_USD | SELL | scalp | 2026-09-24 02:33:57 | 2026-09-24 03:02:30 | BROKER_STOP_LOSS | 28.6 | 8.21 | 2.0 | 0.00 | 1.44 | -1.00 | A | LONG_USD |
| 1603 | GBP_USD | SELL | swing_mean_reversion | 2026-09-24 02:45:08 | 2026-09-24 06:10:26 | BROKER_STOP_LOSS | 205.3 | 7.43 | 2.0 | 1.13 | 1.10 | -1.00 | D | LONG_USD |
| 1612 | AUD_USD | SELL | trend | 2026-09-24 03:03:26 | 2026-09-24 07:52:00 | BROKER_STOP_LOSS | 288.6 | 7.93 | 2.0 | 1.08 | 1.45 | -1.00 | D | LONG_USD |
| 1600 | USD_CHF | SELL | swing_trend | 2026-09-24 03:05:29 | 2026-09-24 04:03:44 | BROKER_STOP_LOSS | 58.3 | 5.17 | 2.0 | 0.43 | 1.41 | -1.01 | B | SHORT_USD |
| 1606 | USD_CAD | SELL | swing_mean_reversion | 2026-09-24 04:15:34 | 2026-09-24 07:26:18 | BROKER_STOP_LOSS | 190.7 | 4.36 | 2.0 | 1.28 | 1.63 | -1.01 | D | SHORT_USD |
| 1602 | EUR_USD | BUY | swing_trend | 2026-09-24 06:00:13 | 2026-09-24 06:09:36 | BROKER_TAKE_PROFIT | 9.4 | 3.62 | 2.0 | 1.49 | 0.44 | 1.99 |  | SHORT_USD |
| 1604 | USD_CHF | SELL | swing_mean_reversion | 2026-09-24 06:10:24 | 2026-09-24 06:41:05 | BROKER_STOP_LOSS | 30.7 | 3.69 | 2.0 | 0.84 | 1.63 | -1.00 | C | SHORT_USD |
| 1605 | USD_JPY | BUY | swing_breakout | 2026-09-24 06:41:55 | 2026-09-24 07:11:36 | BROKER_STOP_LOSS | 29.7 | 14.22 | 2.0 | 0.00 | 0.97 | -1.00 | A | LONG_USD |
| 1611 | GBP_USD | BUY | swing_trend | 2026-09-24 06:42:56 | 2026-09-24 08:50:03 | BOT_PROFIT_PROTECTION | 127.1 | 6.39 | 2.0 | 1.97 | 0.52 | 1.83 |  | SHORT_USD |
| 1607 | USD_JPY | BUY | mean_reversion | 2026-09-24 07:14:27 | 2026-09-24 07:32:06 | BROKER_STOP_LOSS | 17.6 | 13.72 | 2.0 | 0.49 | 1.12 | -1.01 | B | LONG_USD |
| 1608 | USD_CAD | SELL | swing_breakout | 2026-09-24 07:28:41 | 2026-09-24 07:32:01 | BROKER_STOP_LOSS | 3.3 | 5.15 | 2.0 | 0.00 | 1.40 | -1.01 | A | SHORT_USD |
| 1610 | USD_JPY | BUY | swing_breakout | 2026-09-24 07:34:47 | 2026-09-24 07:45:33 | BROKER_STOP_LOSS | 10.8 | 12.32 | 2.0 | 0.11 | 1.09 | -1.00 | A | LONG_USD |
| 1609 | USD_CHF | SELL | swing_breakout | 2026-09-24 07:34:48 | 2026-09-24 07:36:22 | BROKER_STOP_LOSS | 1.6 | 6.67 | 2.0 | 0.00 | 1.38 | -1.00 | A | SHORT_USD |
| 1613 | USD_CAD | SELL | swing_trend | 2026-09-24 07:37:51 | 2026-09-24 09:10:23 | BOT_PROFIT_PROTECTION | 92.5 | 5.36 | 2.0 | 1.55 | 0.99 | 0.91 |  | SHORT_USD |
| 1614 | EUR_USD | BUY | swing_mean_reversion | 2026-09-24 07:53:06 | 2026-09-24 08:16:03 | BROKER_STOP_LOSS | 23.0 | 6.74 | 2.0 | 0.34 | 0.93 | -0.99 | B | SHORT_USD |
