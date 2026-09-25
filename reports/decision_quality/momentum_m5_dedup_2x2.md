# Momentum alignment × one-decision-per-M5 — frozen 2×2

RESEARCH ONLY. Production trading code, `.env`, Docker, quant stub, RL, V2 shadow, ATR/SL/TP, profit protection, sizing, portfolio limits, and strategy routing were not changed. No OANDA calls. No orders. The live bot was not restarted.

Machine-readable artifact: `reports/decision_quality/_momentum_m5_dedup_results.json`.

---

BASELINE REPRODUCTION:
**PASS**

A0 first-qualifying stub-allow events match the frozen Stage 1 directional-quality baseline exactly.

| | This run | Stage 1 |
|---|---:|---:|
| Events | 14104 | 14104 |
| TRAIN | 7052 | 7052 |
| VALID | 3528 | 3528 |
| TEST | 3524 | 3524 |
| TRAIN ≤ | `2026-02-27 07:47:30Z` | same |
| VALID ≤ | `2026-05-29 02:10:00Z` | same |

A0 is `current_stub_allow`: SMA side exists AND `|ret_1| > 0.0001` AND ATR > 0. Sample rows match `_quant_stub_vote`. Threshold was not changed.

The 2×2 occupancy cells below are the live-like one-position 2×ATR / 2R book-price engine. They are **not** the Stage 1 first-qual event count (14,104). First-qual is the signal-layer control only.

---

## Frozen specification

**FACTOR A — momentum gate** (SMA direction never reversed)

| | Rule |
|---|---|
| A0 CURRENT | `abs(last M5 mid return) > 0.0001` |
| A1 ALIGNED | BUY requires `ret_1 > 0.0001`; SELL requires `ret_1 < -0.0001` |

**FACTOR B — decision frequency**

| | Rule |
|---|---|
| B0 CURRENT | Occupancy (one position / symbol). After a **first-forward-bar SL**, a second new-entry may use the **same** `(symbol, completed M5 timestamp)`. Second fill is modelled at the stop price and managed from the next complete bar (no M1). |
| B1 ONE/M5 | Causal key `(symbol, completed_M5_candle_timestamp)`. The first new-entry decision consumes that key. A fast SL **cannot** spawn another entry on that candle. The next *completed* M5 is a new key. |

B1 is **not** a 5-minute cooldown after a loss.

M1 data: **unavailable**. First-5m MFE/MAE are the first post-entry **M5** trigger-side high/low vs executable entry.

Strategy labels: **not reconstructed**. Production `select_strategy` is RNG/meta; Stage 1 already declined to invent historical labels.

Live trades were scored **after** this specification was frozen. They did not set the threshold, cells, or symbols.

---

## 2×2 OVERALL

Occupancy economics (2×ATR SL, 2R TP, bid/ask). All four cells remain **negative**.

| | CURRENT VOTING (B0) | ONE/M5 (B1) |
|---|---|---|
| **CURRENT MOM (A0)** | n=21595 BUY=10987 SELL=10608 WR=0.223 exp R=**−0.331** PF=0.574 tot R=−7156 +5m hit=0.205 | n=21591 BUY=10867 SELL=10724 WR=0.210 exp R=**−0.370** PF=0.531 tot R=−7999 +5m hit=0.206 |
| **ALIGNED MOM (A1)** | n=19873 BUY=10045 SELL=9828 WR=0.218 exp R=**−0.346** PF=0.557 tot R=−6881 +5m hit=0.198 | n=19303 BUY=9750 SELL=9553 WR=0.210 exp R=**−0.370** PF=0.532 tot R=−7139 +5m hit=0.201 |

SE of mean R is about 0.008–0.009 (n≈19k–22k). Differences of 0.01–0.04 R are detectable as point estimates and still **less negative / more negative**, not profitable.

---

## TRAIN

| Cell | n | BUY | SELL | WR | exp R | PF | tot R | +5m hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A0/B0 | 10644 | 5419 | 5225 | 0.227 | −0.320 | 0.586 | −3405 | 0.211 |
| A1/B0 | 9845 | 4976 | 4869 | 0.223 | −0.332 | 0.573 | −3269 | 0.205 |
| A0/B1 | 10742 | 5397 | 5345 | 0.213 | −0.360 | 0.542 | −3872 | 0.208 |
| A1/B1 | 9573 | 4829 | 4744 | 0.216 | −0.353 | 0.550 | −3375 | 0.205 |

---

## VALIDATION

| Cell | n | BUY | SELL | WR | exp R | PF | tot R | +5m hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A0/B0 | 5260 | 2696 | 2564 | 0.233 | −0.300 | 0.609 | −1576 | 0.227 |
| A1/B0 | 4893 | 2492 | 2401 | 0.226 | −0.323 | 0.583 | −1581 | 0.210 |
| A0/B1 | 5166 | 2615 | 2551 | 0.222 | −0.334 | 0.570 | −1728 | 0.231 |
| A1/B1 | 4772 | 2428 | 2344 | 0.215 | −0.355 | 0.548 | −1694 | 0.213 |

---

## TEST

| Cell | n | BUY | SELL | WR | exp R | PF | tot R | +5m hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A0/B0 | 5691 | 2872 | 2819 | 0.206 | −0.382 | 0.518 | −2175 | 0.175 |
| A1/B0 | 5135 | 2577 | 2558 | 0.202 | −0.396 | 0.504 | −2031 | 0.174 |
| A0/B1 | 5683 | 2855 | 2828 | 0.193 | −0.422 | 0.477 | −2399 | 0.177 |
| A1/B1 | 4958 | 2493 | 2465 | 0.194 | −0.418 | 0.482 | −2070 | 0.181 |

TEST is worse than TRAIN/VALID in every cell. No cell flips sign out of sample.

---

## MOMENTUM ALIGNMENT EFFECT

Occupancy expectancy delta (A1 minus A0):

| Split | A1/B0 − A0/B0 | A1/B1 − A0/B1 |
|---|---:|---:|
| TRAIN | **−0.012** | +0.008 |
| VALID | **−0.023** | −0.020 |
| TEST | **−0.013** | +0.005 |
| OVERALL | −0.015 | +0.001 |

A1 does **not** improve A0 under current voting on valid or test. Under one/M5 the TEST bump (+0.005) is tiny, still negative, and VALID is worse. Event-level (no occupancy) +5m hit is 0.216 (A1) vs 0.218 (A0) overall — A1 throws away 49% of candidates for no directional gain.

The live-sample aligned/+5m gap (0.392 vs 0.200) does **not** appear on the historical cache. Do not use the live point estimate to claim a historical momentum-alignment edge.

---

## ONE-DECISION-PER-M5 EFFECT

Occupancy expectancy delta (B1 minus B0):

| Split | A0/B1 − A0/B0 | A1/B1 − A1/B0 |
|---|---:|---:|
| TRAIN | **−0.041** | **−0.021** |
| VALID | **−0.035** | **−0.032** |
| TEST | **−0.040** | **−0.022** |
| OVERALL | −0.039 | −0.024 |

B1 is **more negative** on every split, both A0 and A1. Occupancy n is almost unchanged (A0/B1 retention 0.9998 vs A0/B0) because blocking a same-candle re-entry frees the slot for a later unique M5. This is substitution, not a small cherry-picked subset.

---

## INTERACTION

A1/B1 minus A0/B0 expectancy: TRAIN −0.033, VALID −0.055, TEST −0.035.

The combination is worse than either factor alone in the helpful direction. There is no positive interaction. Combining them does not rescue the control.

---

## CANDIDATE RETENTION

| | Event-level unique M5 | Occupancy n vs A0/B0 |
|---|---:|---:|
| A0 | 236828 (100%) | 1.000 |
| A1 | 120604 (**50.9%**) | 0.920 (A1/B0) / 0.894 (A1/B1) |
| A1 removed | **116224** | — |

A1 looks “selective” by cutting half the bars. After occupancy the remaining book is still ~89–92% as large and **more negative**. This is not better selection. It is coverage loss without an edge.

---

## SAME-CANDLE RE-ENTRY FINDINGS

Historical A0 occupancy:

| | n |
|---|---:|
| First-bar SL opportunities (B1 book) | 3382 |
| Same-candle re-entries taken (B0) | 2472 |
| Re-entry win rate | 0.240 |
| Re-entry mean R | **−0.279** |
| Parent (the fast SL) mean R | **−1.000** |
| Direction vs parent | always same (SMA not reversed) |

Re-entries are independently **losing** (not a hidden winner). They are not *more* damaging than ordinary occupancy entries (control mean R −0.331). Removing them makes the book **worse** because B1 replaces them with later unique-bar trades that lose more.

They are **not** a 5-minute max-hold. They are the mechanical consequence of: last completed M5 still current + occupancy freed after a first-bar stop.

Live descriptive B1 suppressions: 25 scored trades shared a `(symbol, last completed M5)` with an earlier fill (more than the three previously flagged fast-SL repeats, because any exit inside the candle’s remaining life can free the slot). Counterfactual of dropping those 25: mean R **−0.442** vs live A0 **−0.352** — also worse. Not training data.

---

## SYMBOL STABILITY

Occupancy overall. USD_CAD and USD_CHF stay the weakest. A1 does not repair them. Do not exclude them.

| Symbol | A0/B0 n / exp R / +5m | A1/B0 | A0/B1 | A1/B1 |
|---|---|---|---|---|
| EUR_USD | 3390 / −0.304 / 0.214 | −0.323 / 0.204 | −0.341 / 0.214 | −0.336 / 0.211 |
| GBP_USD | 3499 / −0.337 / 0.228 | −0.344 / 0.209 | −0.347 / 0.227 | −0.350 / 0.212 |
| USD_JPY | 2808 / −0.209 / 0.269 | −0.222 / 0.256 | −0.226 / 0.270 | −0.231 / 0.261 |
| AUD_USD | 3906 / −0.347 / 0.210 | −0.354 / 0.209 | −0.392 / 0.218 | −0.394 / 0.209 |
| USD_CAD | 3530 / **−0.337** / **0.176** | **−0.377** / 0.168 | **−0.387** / 0.172 | **−0.416** / 0.167 |
| USD_CHF | 4462 / **−0.406** / **0.160** | **−0.414** / 0.165 | **−0.468** / 0.158 | **−0.443** / 0.165 |

Every symbol, every cell: negative expectancy.

---

## BUY/SELL STABILITY

| Cell | BUY n / exp R / +5m | SELL n / exp R / +5m |
|---|---|---|
| A0/B0 | 10987 / −0.335 / 0.206 | 10608 / −0.328 / 0.205 |
| A1/B0 | 10045 / −0.340 / 0.200 | 9828 / −0.352 / 0.197 |
| A0/B1 | 10867 / −0.374 / 0.206 | 10724 / −0.367 / 0.205 |
| A1/B1 | 9750 / −0.363 / 0.201 | 9553 / −0.377 / 0.200 |

Alignment behaves the same on both sides: slightly worse or unchanged, never a stable side-specific rescue.

---

## FIRST-5M EFFECT

M5 resolution only. Occupancy first post-entry bar extremes vs executable entry.

| Cell | +5m hit | +5m mean R | first-5m MFE pips | first-5m MAE pips |
|---|---:|---:|---:|---:|
| A0/B0 | 0.205 | −0.426 | +0.16 | 4.15 |
| A1/B0 | 0.198 | −0.421 | +0.09 | 4.14 |
| A0/B1 | 0.206 | −0.399 | −0.06 | 4.30 |
| A1/B1 | 0.201 | −0.384 | −0.01 | 4.22 |

TEST +5m hit stays 0.17–0.18 in every cell. Alignment does not fix immediate adverse movement. MAE ≈ 4 pips on the first M5 while MFE is near zero — same shape as the live “MFE=0 then SL” pile, without inventing 1-minute precision.

Event-level executable +15/+30/+60m stay negative for A0 and A1 on TRAIN, VALID, and TEST (overall A0 60m mean R −0.316; A1 −0.32 range).

---

## LIVE DESCRIPTIVE CROSS-CHECK — NOT TRAINING DATA

Applied only after the historical cells were frozen. `ret_1` is not stored on live rows; A1 uses signed pre-entry 5m executable move > 0 (same proxy as the first-5m audit). Exact 0.0001 cannot be applied live.

| | n | WR | mean R | PF | +5m hit |
|---|---:|---:|---:|---:|---:|
| Live A0 (scored) | 212 | 0.274 | −0.352 | 0.524 | 0.269 |
| Live A1 (aligned proxy) | 79 | 0.304 | −0.290 | 0.592 | 0.392 |
| Live B1 kept | 187 | 0.235 | −0.442 | 0.433 | 0.241 |
| Live A1∩B1 kept | 69 | 0.232 | −0.464 | 0.408 | 0.348 |

Live A1 looks less negative. Historical A1 does not. The live n=79 set is the same descriptive slice already published; it was **not** used to choose A1. Live B1 is worse. Neither live slice authorizes a code change.

---

## V2 FORWARD VALIDATION

**INSUFFICIENT DATA**

253 observe-only rows (`2026-09-24T10:26:54Z`–`12:13:42Z`). No fills. `proposed_action` is SKIP. Gate rates (not economics): A0 253, A1 121 (retention 0.478). Not combined with historical results.

---

FINAL CLASSIFICATION FOR MOMENTUM ALIGNMENT:
**A) NO EVIDENCE OF IMPROVEMENT**

FINAL CLASSIFICATION FOR ONE-DECISION-PER-M5:
**A) NO EVIDENCE OF IMPROVEMENT**

FINAL CLASSIFICATION FOR COMBINATION:
**A) NO EVIDENCE OF IMPROVEMENT**

Classification C would not authorize deployment even if it had been selected.

All occupancy cells remain **negative**. Where B0 is less negative than B1, that is **less negative**, not profitable. Effects that fail VALID or TEST are unstable; here the factors fail in the wrong direction.

DO ANY RESULTS JUSTIFY A LIVE CODE CHANGE NOW:
**NO**

FILES CHANGED:
- `forex_bot/decision_quality/momentum_m5_dedup.py`
- `tests/test_momentum_m5_dedup_research.py`
- `reports/decision_quality/_momentum_m5_dedup_run.py`
- `reports/decision_quality/_momentum_m5_dedup_results.json`
- `reports/decision_quality/momentum_m5_dedup_2x2.md`

PRODUCTION FILES CHANGED:
**NONE**

DEPLOY:
**NO**

STOP.
