# First 5 minutes after live entry — read-only audit

READ-ONLY / RESEARCH-ONLY. Production code, `.env`, strategy, SMA/EMA/momentum/RL, ATR/SL/TP/profit protection, Docker, and OANDA writes were not changed. The live bot was not interrupted.

**Sample:** corrected live build, exits `>= 2026-09-21T22:00:04Z` (same trustworthy boundary as `live_trade_failure_diagnosis.md`). 218 eligible closed live trades; 212 scored (broker SL/TP + bot profit protection). 6 MANUAL excluded from expectancy.

**M1:** not present in cache, dump, or prior diagnostic pulls. Intra-minute buckets 0–1 / 1–2 / 2–3 / 3–4 / 4–5 cannot be measured. Finest available path is complete M5 bid/ask (prior diagnosis) plus bot tick MFE/MAE at the actual exit. Do not treat M5 as 1-minute precision.

---

5-MINUTE MAX HOLD EXISTS:
**NO**

ABNORMAL 300-SECOND EXIT CLUSTER:
**NO**

M5 ENTRY-CANDLE REGRESSION:
**NO**

CURRENT SL GEOMETRY CORRECT:
**YES**

BROKER/BOT EXIT CLASSIFICATION CORRECT:
**PARTIAL**

FIRST-5M LOSSES PRIMARILY:
**immediate adverse movement**

SIGNAL APPEARS LATE:
**YES**

OPPOSITE-SIGNED MOMENTUM EFFECT:
Opposite-signed last M5 (vs taken side) is common (130/212) and worse at +5m (hit 0.200 vs 0.392 aligned; mean R −0.391 vs −0.290; 31 vs 10 closed by 5m). The live gate is `|ret| > 0.0001` only; sign is not required. Not a 5-minute timer.

RL FIRST-5M EFFECT:
**insufficient data** — V2 shadow starts `2026-09-24T10:26:54Z`; last sample entry is `2026-09-24T07:53:06Z`. No overlap.

WORST SYMBOLS/STRATEGIES:
USD_CAD (40.9% closed-by-5m loss), USD_CHF (27.8%), `swing_breakout` (31.8% closed-by-5m loss; 5m hit 0.159)

CONFIRMED BUGS:
**none** in current production that close or modify live positions at ~5 minutes

POSSIBLE ISSUES:
- Same completed M5 is re-evaluated every ~60s; 3 same-bar same-side re-entries after a ≤5m SL
- Signal is frozen on the last *completed* M5, so a forming-bar reversal is invisible until the next close
- Research “spread” in the dump is `|executable_reference − M5 mid| × 2`, not live bid–ask; it must not be read as SL-inside-spread

SIGNAL-QUALITY FINDINGS:
Direction is already wrong at the first completed M5 after entry (5m hit 0.269, mean executable R −0.292). All 37 broker stops that died inside 5 minutes recorded bot MFE = 0.

DO ANY FINDINGS JUSTIFY A LIVE CODE CHANGE NOW:
**NO**

---

## EXPERIMENT

First-5-minute post-entry path: implementation, timing, data, execution, management — without assuming the directional model is the only cause.

PRODUCTION IMPACT: **NONE**

---

## 1. Time-based exit / management rules

Every production closer of a live OANDA position:

| Mechanism | File | Can close live? | Time-based? |
|---|---|---|---|
| Broker attached SL | OANDA `STOP_LOSS_ORDER` | Yes | No — price vs attached stop |
| Broker attached TP | OANDA `TAKE_PROFIT_ORDER` | Yes | No |
| Bot profit protection | `bot_loop.evaluate` → `apply_profit_protection` → `PositionClose` | Yes | No — MFE / giveback vs current closeout |
| Weekend flatten | `session_rules.flatten_for_weekend` (Friday, default 15 min before 21:00 UTC) | Yes | Calendar, not hold age |
| Local SL/TP on candle | `broker_sl_tp_hit` | **No** for broker-backed (`return False`) | n/a |
| `MIN_POSITION_HOLD_SEC` | `bot_loop._min_position_hold_sec` | Does **not** close | **Defers** bot SL/TP only; default / live `.env` = `0` |
| `RECONCILE_MAX_AGE_SEC=300` | `reconciliation.reconcile_is_stale` | **No** | Blocks **new entries** if reconcile older than 300s |
| `profit_protection.bar_seconds=300` | candle width for MFE reconstruction | No | M5 bar length, not a hold timeout |
| Telegram / halt / kill switch | entry block or rejected flatten | No (inbound flatten rejected) | n/a |
| Reconciliation auto-fix | local registry only | No OANDA write | n/a |

`300` / `5*60` / `timedelta(minutes=5)` hits that are **not** exits: M5 bar width, reconcile entry-gate age, research/test fixtures, Telegram backoff cap.

IS THERE ANY 5-MINUTE MAX HOLD:
**NO**

IS THERE ANY RULE THAT CAN INDIRECTLY CAUSE A CLOSE AT ~5 MINUTES:
**NO** as a hold-timeout. A trade *can* close near 5 minutes because (a) the broker stop is hit, (b) profit protection fires, or (c) the next completed M5 is the first bar the bot may use for post-entry MFE. None of those is “close when age ≥ 300s”.

---

## 2. Entry timing within the M5 candle

### Live path (current source)

```
last completed M5 (fetch_ohlcv, price=M, complete=true only)
  → compute_indicators on that series (forming bar excluded)
  → last mid close = signal price
  → _quant_stub_vote (SMA fast vs slow + |ret_1| > 0.0001 + ATR > 0)
  → RL same-side gate (SKIP / opposite side blocks)
  → dedicated PricingInfo GET (not the cycle snapshot)
  → resolve_live_entry_geometry (BUY=ask, SELL=bid; SL/TP around executable)
  → OrderCreate MARKET + stopLossOnFill / takeProfitOnFill
  → fill (~0.23s after exec_orders.created_at)
```

| Question | Answer |
|---|---|
| Completed or forming candle? | **Completed only.** `fetch_ohlcv` skips `complete=false`. |
| Timestamp used for indicators | OANDA M5 **start** of last complete bar; `price = close.iloc[-1]` (mid) |
| Completeness check | Yes |
| Entry just after M5 boundary? | Sometimes. Median fill is **117s** into the forming bar (mean 129s). 8.5% within 15s of the close; 10.8% in the last 60s of the forming bar. Cycle is `TRADE_INTERVAL=60`. |
| Stale previous candle? | The last *complete* M5 is used until the next one completes — up to ~5 minutes of reuse. That is intentional no-lookahead, not a fetch bug. |
| Duplicate evaluation? | **Yes.** Same completed M5 is re-voted every ~60s while `pos is None`. One open position per symbol; evaluate returns before a second entry. After a fast SL, the same bar can fire again (3 observed same-bar same-side re-entries). |
| Entry candle contaminate indicators? | **No.** Forming bar is not in `fetch_ohlcv`. |
| One-bar lag? | **Yes, by design.** Signal never sees the forming M5. |

Order latency (exec_orders `created_at` → `filled_at`, n=168): mean **0.23s**, max **0.30s**. Not a 5-minute delay.

`PRICE_SOURCE_POST_ENTRY_CANDLE` is a leftover constant and is **never returned**. Live manage is `OANDA_CURRENT` closeout or `UNAVAILABLE` (no M5 fallback).

---

## 3. First 5-minute price path

**M1 unavailable.** Report uses (1) hold-time bins, (2) uncensored executable +5m close (BUY vs bid, SELL vs ask), (3) bot MFE/MAE.

### Hold bins (scored n=212)

| Bin | n | % |
|---|---:|---:|
| 0–60s | 7 | 3.3 |
| 60–120s | 8 | 3.8 |
| 120–180s | 9 | 4.2 |
| 180–240s | 7 | 3.3 |
| 240–300s | 10 | 4.7 |
| 300–360s | 3 | 1.4 |
| 360–600s | 17 | 8.0 |
| 10–30m | 63 | 29.7 |
| >30m | 88 | 41.5 |

Median hold **22.0 min**. 41/212 (19.3%) close inside 5 minutes.

Closed inside 5 minutes (n=41): win rate **0.098**, mean R **−0.773**, PF **0.167**. Classes: 37 BROKER_STOP_LOSS, 3 BOT_PROFIT_PROTECTION, 1 BROKER_TAKE_PROFIT.

### Uncensored +5m executable (all scored)

| | |
|---|---|
| n | 212 |
| dir hit | **0.269** |
| mean R | **−0.292** |
| median R | −0.344 |

Direction is already wrong at the first completed M5 after entry, including trades that later lasted longer.

### Immediate vs reversal

Broker SL (n=154), bot MFE at exit:

| Path | n | % of SL |
|---|---:|---:|
| Immediate (MFE < 0.25R) | 91 | 59.1 |
| Mixed (0.25–0.5R) | 23 | 14.9 |
| Initial profit then SL (MFE ≥ 0.5R) | 40 | 26.0 |

**All 37 broker stops that closed inside 5 minutes have bot MFE = 0.** They never printed a favourable tick the bot recorded. MAE on those 37: mean 1.42R (stop fill + noise).

Are losing trades wrong immediately, or do they work then reverse?
**Wrong immediately** for the first-5m SL pile. Longer SL trades include some giveback (40 with MFE ≥ 0.5R), but that is not the 5-minute phenomenon.

---

## 4. Stop-loss distance audit

Live geometry (current `entry_geometry.py`):

- BUY reference = **ask**; SELL = **bid**
- SL/TP = ATR distances (`SL_ATR_MULT` default 2, TP = 2R) re-anchored to that reference
- JPY formatted to 3 decimal places; others 5
- SL trigger: BUY vs **bid**, SELL vs **ask**; skip if clearance ≤ 0
- Dedicated PricingInfo GET immediately before OrderCreate; last-change age is not a reject
- Live manage: BUY flatten on **closeout bid**, SELL on **closeout ask**

Scored geometry (n=212):

| | mean | median | min | max |
|---|---:|---:|---:|---:|
| SL pips | 6.04 | 5.39 | 1.78 | 20.64 |
| ATR pips | 3.14 | 2.82 | 0.80 | 10.54 |
| SL / ATR | **1.93** | 1.90 | 1.28 | 3.77 |
| Initial R | **2.00** | 2.00 | 2.00 | 2.00 |

Pip conversion check vs stored SL price: **0 JPY mismatches, 0 non-JPY mismatches**. USD_JPY mean SL 9.54 pips uses pip=0.01.

BUY vs SELL SL/ATR: 1.96 vs 1.91. No side-inverted geometry.

SL < 2 pips: **1** trade (AUD_USD, small ATR). That is 2×ATR in a quiet tape, not a pip-scale bug.

“SL inside spread” (30 trades) uses the **research proxy** `|exec − M5 mid| × 2`. That proxy includes M5-to-tick displacement (max 90.2 “pips” on USD_JPY) and is **not** the live bid–ask. Live attach does not use M5 mid.

First-5m MAE vs SL: for the 37 SL deaths inside 5m, MAE ≈ 1.0–2.5R. That is the broker stop filling, not a stop sitting inside a 1-pip spread.

CURRENT SL GEOMETRY CORRECT: **YES**

---

## 5. Broker SL vs bot close

Taxonomy on the 218-row sample (local `exit_reason` + OANDA reason/type):

| Class | n |
|---|---:|
| BROKER_STOP_LOSS | 154 |
| BOT_PROFIT_PROTECTION | 44 |
| BROKER_TAKE_PROFIT | 14 |
| MANUAL | 6 |
| BOT_POSITION_CLOSE | 0 |
| RECONCILIATION | 0 |
| UNKNOWN | 0 |

`broker_sl_tp_hit` is hard-false for broker-backed locals. After the management fix the bot must not flatten because a stale M5 crossed SL/TP. Bot live closes in this sample are profit-protection `PositionClose` only.

### Every 4–6 minute close (240–360s), inspected

| id | pair | side | hold s | class | OANDA evidence | R | MFE R |
|---:|---|---|---:|---|---|---:|---:|
| 1536 | GBP_USD | SELL | 241 | BOT_PROFIT_PROTECTION | local `profit_protection`; no `oanda_reason` | +1.67 | 1.81 |
| 1386 | AUD_USD | SELL | 245 | BOT_PROFIT_PROTECTION | local `profit_protection` | +0.96 | 1.81 |
| 1502 | GBP_USD | SELL | 246 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.01 | 0.00 |
| 1508 | GBP_USD | SELL | 255 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.04 | 0.00 |
| 1530 | USD_JPY | SELL | 255 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.03 | 0.00 |
| 1409 | USD_CAD | SELL | 255 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.05 | 0.00 |
| 1387 | USD_CHF | SELL | 278 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.05 | 0.00 |
| 1376 | USD_CHF | SELL | 289 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.01 | 0.00 |
| 1397 | AUD_USD | SELL | 290 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −0.99 | 0.00 |
| 1410 | USD_CHF | SELL | 294 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.19 | 0.00 |
| 1382 | AUD_USD | SELL | 305 | BOT_PROFIT_PROTECTION | local `profit_protection` | +1.78 | 1.82 |
| 1453 | USD_JPY | BUY | 313 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −1.00 | 0.20 |
| 1590 | USD_CHF | BUY | 332 | BROKER_STOP_LOSS | `STOP_LOSS_ORDER` / `ORDER_FILL` | −0.99 | 0.00 |

Ten of thirteen are **OANDA stop fills**, not bot `PositionClose`. Three are profit-protection winners (MFE ~1.8R). No 4–6 minute close is an unlabeled time-stop.

PARTIAL classification: profit-protection rows often lack `oanda_reason` because they are booked on the evaluate path, not `broker_exit`’s `MARKET_ORDER_POSITION_CLOSEOUT` map. Labels still match local `exit_reason` and are not SL/TP.

---

## 6. M5 entry-candle regression

Previous defect (pre-`2026-09-21T22:00:04Z`): manage used last M5 mid; MFE could include the partial entry bar; profit protection could flatten a new trade in ~61s.

**Current source still:**

| Guard | Status |
|---|---|
| `include_partial_entry_bar=False` for broker-backed seed + raise | Yes (`bot_loop.py` manage branch) |
| `raise_mfe_from_post_entry_ohlcv` never uses the entry bar | Yes |
| Fresh executable closeout | Yes — `resolve_broker_manage_price`; no M5 fallback |
| BUY uses closeout **bid** | Yes |
| SELL uses closeout **ask** | Yes |
| Pre-entry M5 high/low excluded from live MFE | Yes (`candle_vs_fill` → skip `pre_entry` and `partial_entry`) |
| Stale M5 cannot trip local SL/TP | Yes — `broker_sl_tp_hit` is always false |

Tests still encode the 1621/1629 cases (`tests/test_live_position_management.py`). Prior recurrence report: **0** new-build bot 45–90s PositionClose.

Live logs (read-only, last 30 minutes): two positions open (EUR_USD SELL, AUD_USD SELL); no `BROKER_CLOSE` / `[CLOSE DECISION]` in that slice. `MANAGE PRICE` lines were not in the retrieved slice (possible logging-driver gap). No stale-M5 close signature.

M5 ENTRY-CANDLE REGRESSION: **NO**

---

## 7. M5 signal lag

Pre-entry move is signed **in the taken direction** from M5 executable closes (same convention as the prior diagnosis). −10m and +1m / +10m are **not** in the artifact.

| Horizon | BUY mean pips/R | SELL mean | ALL |
|---|---|---|---|
| −5m (pips) | −0.30 | −0.84 | **−0.62** |
| −15m (pips) | −1.06 | −1.33 | −1.22 |
| −30m (pips) | −0.39 | −0.47 | −0.44 |
| +5m (R) | −0.25 | −0.32 | **−0.29** |
| +15m (R) | −0.31 | −0.28 | −0.29 |
| +30m (R) | −0.32 | −0.25 | −0.28 |
| +60m (R) | −0.40 | −0.02 | −0.18 |

Last completed bar is more often **against** the SMA side (opposite 130 vs aligned 79). That is lag: SMA still points the old way after the last bar reversed.

If “late” means “already moved our way, then mean-reverts”:

| | n |
|---:|---:|
| Aligned then +5m loss | 48 |
| Aligned then +5m win | 31 |
| Opposite then +5m loss | 103 |
| Opposite then +5m win | 26 |

Aligned chase-then-fail is 48/79 (61%). Opposite-then-fail is 103/130 (79%). Combined with SMA using only completed mids and a 60s cycle, **the directional signal is late and/or wrong**. Fill latency (0.23s) is not the lag.

All six symbols have negative mean pre5 except USD_JPY mean +0.73 (median still −0.60). All six have negative mean +5m R. Worst +5m hit: USD_CAD 0.182, USD_CHF 0.222.

SIGNAL APPEARS LATE: **YES**

---

## 8. Absolute-momentum gate (research only — rule not changed)

Live stub: direction from SMA; allow if `|ret_1| > 0.0001` and ATR > 0. Sign of `ret_1` is **not** required.

Proxy used here: signed pre-entry 5m executable move vs taken side (last complete M5, same bar as `ret_1`).

| | ALIGNED (last bar with us) | OPPOSITE (last bar against us) |
|---|---:|---:|
| n | 79 | 130 |
| win rate | 0.304 | 0.254 |
| mean R | −0.290 | **−0.391** |
| PF | 0.592 | 0.485 |
| 5m hit | **0.392** | **0.200** |
| 15m hit | 0.392 | 0.338 |
| 60m hit | 0.494 | 0.423 |
| mean MFE R | 0.717 | 0.598 |
| mean MAE R | 1.232 | 1.348 |
| closed by 5m | 10 | **31** |
| SL share | 69.6% | 74.6% |

Opposite-signed momentum is associated with **more early failures**. Both groups still lose. This does **not** authorize flipping the gate.

---

## 9. RL first-5m

V2 shadow: 235 observe-only rows, `2026-09-24T10:26:54Z`–`12:02:32Z`. Model is `v2_none` / always `proposed_action=SKIP`. RL on those candidates: BUY 95, SELL 70, SKIP 70; agree 94, veto 141.

The 218-trade sample ends before shadow starts. No filled-trade RL agree/veto split exists.

RL FIRST-5M EFFECT: **insufficient data**

---

## 10. Symbol / strategy concentration

First-5m is **universal in direction** (every symbol 5m hit ≤ 0.35) and **concentrated in how fast the stop is hit**.

| Symbol | n | closed-by-5m loss | % | 5m hit | mean R |
|---|---:|---:|---:|---:|---:|
| EUR_USD | 35 | 3 | 8.6 | 0.229 | +0.138 |
| GBP_USD | 24 | 3 | 12.5 | 0.250 | −0.282 |
| USD_JPY | 48 | 6 | 12.5 | 0.354 | −0.302 |
| AUD_USD | 47 | 6 | 12.8 | 0.298 | −0.399 |
| USD_CHF | 36 | 10 | **27.8** | 0.222 | −0.649 |
| USD_CAD | 22 | 9 | **40.9** | **0.182** | **−0.729** |

| Strategy | n | closed-by-5m loss | % | 5m hit | mean R |
|---|---:|---:|---:|---:|---:|
| scalp | 22 | 2 | 9.1 | 0.409 | −0.130 |
| mean_reversion | 28 | 3 | 10.7 | 0.393 | −0.227 |
| swing_mean_reversion | 48 | 8 | 16.7 | 0.271 | −0.252 |
| swing_trend | 51 | 10 | 19.6 | 0.196 | −0.332 |
| trend | 19 | 0 | 0.0 | 0.368 | −0.445 |
| swing_breakout | 44 | 14 | **31.8** | **0.159** | **−0.633** |

SELL dies inside 5m slightly more often (19.4% vs 14.8% BUY). BUY still has worse overall mean R. Strategy label is the hybrid route; **side still comes from the SMA stub**.

---

## 11. Round-number hold times

±15s windows around 60 / 120 / 180 / 240 / 300 / 360 seconds:

| Mark | n | % of scored |
|---:|---:|---:|
| 60s | 3 | 1.4 |
| 120s | 4 | 1.9 |
| 180s | 3 | 1.4 |
| 240s | 8 | 3.8 |
| **300s** | **5** | **2.4** |
| 360s | 4 | 1.9 |

Trades with `|hold − 300| ≤ 2s`: **0**.

The 240s bump is the 4-minute broker-stop / PP group above, not a 300s timer. Do not confuse “closed on the first completed M5 after entry” with a max-hold rule.

ABNORMAL 300-SECOND EXIT CLUSTER: **NO**

---

## 12. Final classification

| Class | Finding |
|---|---|
| **A. CONFIRMED IMPLEMENTATION BUG** | None in current production that explains first-5m losses. The old stale-M5 manage / partial-bar MFE defect is still fixed. |
| **B. POSSIBLE IMPLEMENTATION ISSUE** | Same completed M5 re-voted every 60s (3 same-bar re-entries after fast SL). Forming-bar invisible by design. Research spread proxy is not live bid–ask. PP rows often lack OANDA reason. |
| **C. SIGNAL / DIRECTION QUALITY ISSUE** | Primary. 5m hit 0.269; 37/37 sub-5m SL have MFE=0; SMA lags last bar; opposite-signed last bar is worse; USD_CAD / USD_CHF / `swing_breakout` concentrate fast stops. |
| **D. NORMAL MARKET / STOP BEHAVIOUR** | A 2×ATR broker stop filling within 5 minutes is normal once direction is immediately wrong. Those 10 four-to-six-minute SL rows are OANDA `STOP_LOSS_ORDER` fills. |
| **E. INSUFFICIENT DATA** | No M1 path; no −10m / +1m / +10m; no RL overlap with the corrected live sample. |

Do not describe strategy weakness as a software bug. Do not describe the old (already fixed) M5 manage defect as still live.

---

DO ANY FINDINGS JUSTIFY A LIVE CODE CHANGE NOW:
**NO**

If a later task wants to *validate* (not deploy) a change, the only evidence-backed research questions are: (1) whether forbidding opposite-signed last-bar entries reduces early SL without killing the already-weak aligned set; (2) whether blocking same-M5 re-entry after a fast SL is hygiene. Neither is authorized here. Neither is a 5-minute max-hold.

FILES CHANGED:
- `reports/decision_quality/first_5m_post_entry_audit.md`
- `reports/decision_quality/_first_5m_post_entry_audit.py`
- `reports/decision_quality/_first_5m_post_entry_audit.json`

PRODUCTION FILES CHANGED:
**NONE**

DEPLOY:
**NO**

STOP.
