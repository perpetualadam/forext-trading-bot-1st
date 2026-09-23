AUDIT VERDICT:
The 19 FOK cancellations are the same population as the missing-orderFillTransaction audit. All 19 remain STOP_LOSS_ON_FILL_LOSS create-then-cancels with no fill, trade, ghost, or retry. They are not a wrong-side bug and not a recurrence of stale-M5 mid attach. Reconstructed executable references match contemporaneous M1 executable sides (BUY≈ask, SELL≈bid). ATR×2 stop distances (median 4.57 pips) were smaller than contemporaneous M1 spreads (median 10.2 pips) on every cancellation (stop/spread max 0.58). Successful controls in the same window had similar latency and similar-or-slightly-larger stops, but narrower spreads (median 3.7 pips) and stop/spread min 1.06. Local orientation only checks SL versus the executable reference, not versus the SL trigger side (BUY bid / SELL ask). When stop distance ≤ spread, that check still passes and OANDA cancels. Quote→broker latency is ~150–250 ms and does not distinguish cancel from fill.

CONFIDENCE:
HIGH

CANCELLATIONS ANALYSED:
19

ALL OANDA REASON:
STOP_LOSS_ON_FILL_LOSS

PRIMARY MECHANISM:
L

EXECUTABLE REFERENCE CORRECT:
YES

PRE-SUBMISSION SL ORIENTATION VALID:
19/19 versus reconstructed executable reference (SL < xref < TP for BUY; TP < xref < SL for SELL). Trigger-side clearance versus contemporaneous M1 bid/ask: 0/19.

INTENDED ~2R GEOMETRY VALID PRE-SUBMISSION:
YES versus reconstructed distances (TP−SL = 3 × sl_d). Successful controls fill-R median 1.98.

MEDIAN CANCELLED STOP DISTANCE:
4.57 pips (N=19)

MEDIAN SUCCESSFUL STOP DISTANCE:
5.10 pips (N=5)

MEDIAN CANCELLED SPREAD:
10.2 pips (N=19; M1 MBA close, not persisted PricingInfo)

MEDIAN SUCCESSFUL SPREAD:
3.7 pips (N=5; same M1 method)

MEDIAN CANCELLED STOP/SPREAD:
0.36 (N=19; max 0.58)

MEDIAN SUCCESSFUL STOP/SPREAD:
1.34 (N=5; min 1.06)

MEDIAN CANCELLED QUOTE→ORDERCREATE:
UNKNOWN (not logged). Upper bound reserve→MARKET_ORDER median 157.5 ms (N=19).

MEDIAN SUCCESSFUL QUOTE→ORDERCREATE:
UNKNOWN. Upper bound reserve→fill-tx median 164.3 ms (N=5).

RATE LIMITER CONTRIBUTORY:
NO as the distinguisher (INCONCLUSIVE as a small additive delay inside the ~160 ms bound)

POST-QUOTE CODE DELAY CONTRIBUTORY:
NO as the distinguisher

ROUNDING CONTRIBUTORY:
NO

HIGH-VOLATILITY CLUSTER:
YES (wide M1 spreads). Named 21:00 UTC release: INCONCLUSIVE.

WRONG PRICE-SIDE BUG:
NO

OLD STALE-M5 GEOMETRY DEFECT RECURRED:
NO

SUCCESSFUL FILL MISCLASSIFICATION:
0

GHOST POSITIONS:
0

BLIND RETRIES:
0

OBSERVABILITY GAP CONFIRMED:
YES

HIGHEST-PRIORITY NEXT ACTION:
G

PRODUCTION CHANGES:
NO

DOCKER RESTART:
NO

OANDA WRITES:
NO

## 1. Scope

Read-only mechanism audit of the 19 post-deployment FOK `STOP_LOSS_ON_FILL_LOSS` cancellations. Not a code change. Not a retry/filter implementation. Not a reopening of ClientPrice.time freshness, broker-exit accounting, the ~61s bug, or manual-close attribution.

Safety: no production edits, no `.env` writes, no database writes, no Docker rebuild/restart, no OANDA writes. Additional OANDA access was GET `InstrumentsCandles` (M1 MBA, M5 mid) plus the prior GET transaction pull.

## 2. Established facts from previous audits

From `oanda_missing_orderfilltransaction_forensic_audit.md` (**PROVEN**, re-checked):

- 19 unique OrderCreates; all HTTP-successful FOK MARKET_ORDERs immediately cancelled
- reason on all 19: `STOP_LOSS_ON_FILL_LOSS`
- no ORDER_FILL, trade, residual position, pending entry, local/broker ghost, or blind retry
- local `missing orderFillTransaction` is an observability gap only
- executable-price geometry is the live attach path (BUY=ask, SELL=bid, intended ~2R)
- ClientPrice.time is last-change, not fetch age (not reopened)

Container env (read-only `printenv`): `USE_ATR_STOPS=true`, `SL_ATR_MULT=2.0`, `EXECUTION_MODE=live_broker`. `OANDA_MAX_REQUESTS_PER_SEC` unset → default 10 RPS. `SL_FALLBACK_PIPS` unset → 20 pips only if ATR unused.

## 3. Exact 19-event population

Same 19 client IDs and tx chains as the prior audit. All 19 still `STOP_LOSS_ON_FILL_LOSS`. No discrepancy.

| # | UTC | local BST | symbol | side | cid | MO | CXL | strategy | horizon |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 21:06:04.122Z | 22:06:04 | GBP_USD | BUY | cid-34ea03ffe3fa486ab98e7bad36d45252 | 3132 | 3133 | swing_trend | UNKNOWN |
| 2 | 21:06:04.479Z | 22:06:04 | USD_JPY | SELL | cid-8f55b3f86c5d4f2b918f5ee1d56baef0 | 3134 | 3135 | swing_trend | UNKNOWN |
| 3 | 21:07:05.565Z | 22:07:06 | GBP_USD | BUY | cid-6d0d82b0369e4f10b370dca4802b0af2 | 3136 | 3137 | swing_trend | UNKNOWN |
| 4 | 21:08:07.020Z | 22:08:07 | AUD_USD | BUY | cid-03209f355b264a10b11548a57443d6a7 | 3138 | 3139 | swing_mean_reversion | UNKNOWN |
| 5 | 21:09:08.073Z | 22:09:08 | USD_JPY | SELL | cid-3ac32014576e44ea986041bc7c85b447 | 3140 | 3141 | scalp | UNKNOWN |
| 6 | 21:09:08.439Z | 22:09:08 | AUD_USD | BUY | cid-cb964084bab6490b87f5606bebbaee98 | 3142 | 3143 | swing_mean_reversion | UNKNOWN |
| 7 | 21:10:09.931Z | 22:10:10 | USD_CHF | SELL | cid-eee7fdf92db44f61864421b14ff0ab19 | 3144 | 3145 | swing_trend | UNKNOWN |
| 8 | 21:11:11.135Z | 22:11:11 | USD_CHF | SELL | cid-84c40a5c859e4bed8c20118ef9cf5cd7 | 3146 | 3147 | swing_mean_reversion | UNKNOWN |
| 9 | 21:12:11.821Z | 22:12:12 | GBP_USD | BUY | cid-74595fd264cd484db786041a46582036 | 3148 | 3149 | swing_mean_reversion | UNKNOWN |
| 10 | 21:12:12.425Z | 22:12:12 | USD_CAD | SELL | cid-ac380f6a32914d59a20e8a2dbc9ee488 | 3150 | 3151 | swing_mean_reversion | UNKNOWN |
| 11 | 21:13:13.626Z | 22:13:14 | USD_CAD | SELL | cid-683e7c2d6f0a404ea4387efb01892d6d | 3152 | 3153 | swing_trend | UNKNOWN |
| 12 | 21:15:15.373Z | 22:15:15 | GBP_USD | BUY | cid-e6afc545a3d844529fc229dec57cceec | 3154 | 3155 | swing_trend | UNKNOWN |
| 13 | 21:16:16.571Z | 22:16:17 | GBP_USD | BUY | cid-bdb651433a0a4403b6802c46a466d733 | 3156 | 3157 | swing_trend | UNKNOWN |
| 14 | 21:18:18.741Z | 22:18:19 | GBP_USD | BUY | cid-b2db42bf9263435983665c6b4df3b4ea | 3158 | 3159 | swing_breakout | UNKNOWN |
| 15 | 21:19:19.918Z | 22:19:20 | GBP_USD | BUY | cid-8bde28710212487b9d9df455a32fe8a8 | 3160 | 3161 | swing_trend | UNKNOWN |
| 16 | 21:25:26.872Z | 22:25:27 | GBP_USD | BUY | cid-57588c279fc2440d8f4c24abd12c09e2 | 3172 | 3173 | swing_mean_reversion | UNKNOWN |
| 17 | 21:29:31.216Z | 22:29:31 | GBP_USD | BUY | cid-4fc845893cd149e4b6d7590920e95fac | 3174 | 3175 | swing_mean_reversion | UNKNOWN |
| 18 | 21:38:41.245Z | 22:38:41 | AUD_USD | BUY | cid-ba84f573b35b4a16a5b91ff3012bb632 | 3186 | 3187 | swing_trend | UNKNOWN |
| 19 | 21:40:43.579Z | 22:40:44 | AUD_USD | BUY | cid-3c886c582acb4550b413eb2f08c125bb | 3188 | 3189 | swing_breakout | UNKNOWN |

Horizon is not persisted on cancelled `exec_orders`. Units and strategy are from that table (**PROVEN**).

## 4. OANDA STOP_LOSS_ON_FILL_LOSS semantics

Official `OrderCancelReason` (**PROVEN**):

> Filling the Order would result in the creation of a Stop Loss Order that would have been filled immediately, closing the new Trade at a loss.

These 19 have no `ORDER_FILL.price`. The prospective fill price is **not persisted**. Do not invent one.

What can be stated from official order-trigger rules and the attached `stopLossOnFill`:

- A long trade’s SL is a **sell** stop. DEFAULT trigger: short/sell orders compare to the **bid**.
- A short trade’s SL is a **buy** stop. DEFAULT trigger: long/buy orders compare to the **ask**.
- Transactions record `stopLossOnFill.triggerMode=TOP_OF_BOOK` (broker-populated). That is top-of-book, not closeout.
- CloseoutBid/Ask are the existing-position flatten prices. They are not the documented SL-on-fill comparator.

Therefore the cancel condition, for this FOK + `stopLossOnFill.price` path:

| Side | Entry fill (market) | SL trigger side | Immediate-loss if |
|---|---|---|---|
| BUY | ask | bid | bid ≤ SL at the prospective fill |
| SELL | bid | ask | ask ≥ SL at the prospective fill |

If SL is built as `ask − sl_d` (BUY) or `bid + sl_d` (SELL), that inequality is true with **zero subsequent movement** whenever `sl_d ≤ ask − bid` (spread).

Local `orientation_valid` only requires `SL < executable_reference < TP` (BUY) or the SELL inverse. That can be true while SL is already through the trigger side. **PROVEN** in code.

FOK: `TimeInForce.FOK` on `MarketOrderRequest`. The MARKET_ORDER and its on-fill SL/TP are accepted or the whole order is cancelled in one batch (`MARKET_ORDER` and `ORDER_CANCEL` share the timestamp). FOK was not changed and should not be changed from this audit.

LOSING_TAKE_PROFIT: 0  
TAKE_PROFIT_ON_FILL_LOSS: 0  
The broker isolated the failure to the stop side.

## 5. Entry geometry reconstruction

PricingInfo bid/ask/closeout, `price_time`, `request_duration_ms`, and `fetch_age_ms` were computed in-process (`logger.info`) and **not retained** on Docker stdout or on cancelled `exec_orders` rows.

Recovered:

| Field | Source | Status |
|---|---|---|
| signal M5 mid | `exec_orders.metadata.mid` | PROVEN |
| requested SL/TP | MARKET_ORDER `stopLossOnFill` / `takeProfitOnFill` | PROVEN |
| intended R | `TP_RISK_REWARD=2` + `tp_d=2*sl_d` | PROVEN as design |
| reconstructed sl_d | `(TP−SL)/3` BUY; `(SL−TP)/3` SELL | STRONG INFERENCE (2R + rounding) |
| reconstructed xref | BUY `SL+sl_d`; SELL `SL−sl_d` | STRONG INFERENCE |
| live PricingInfo bid/ask | not persisted | UNKNOWN |
| M1 MBA close at last completed minute | OANDA GET | PROVEN as candle, proxy for book |

Reconstructed xref versus last completed M1 executable side (BUY vs ask close, SELL vs bid close):

Typical \|xref − M1 exec\| ≤ 0.5 pips (AUD #4/#6/#18/#19 at 0.0–0.03; JPY #2 at +0.03). Outliers: JPY #5 −1.07 pips, CAD #11 +2.53 pips. **STRONG INFERENCE** that the bot used the correct executable side.

BUY reconstructed xref is above signal mid; SELL reconstructed xref is below signal mid. That is ask/bid versus M5 mid, not a side inversion.

Stale-M5 counterfactual: a mid-anchored BUY SL would be `mid − sl_d`. Event 1: mid 1.33470, sl_d 0.00046 → mid-SL 1.33424. Submitted SL **1.33478**. **OLD STALE-M5 GEOMETRY DEFECT RECURRED: NO.**

Pre-submission orientation versus reconstructed xref: **19/19 valid**. Not an implementation defect in BUY/SELL selection.

## 6. Stop headroom

Versus reconstructed xref (this is sl_d, by construction):

| | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| cancelled stop/headroom pips | 2.63 | 4.23 | 4.57 | 4.63 | 4.87 |

Versus contemporaneous M1 trigger side (BUY: bid−SL; SELL: SL−ask):

| | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| cancelled trigger headroom pips | −11.5 | −11.0 | −6.2 | −4.0 | −2.1 |

**19/19 negative.** The requested SL was already through the M1 trigger side. Classification: **STRONG_EVIDENCE_HEADROOM_CONSUMED** on the M1 proxy (not a live PricingInfo snapshot). Movement after PricingInfo is not required to explain the sign.

## 7. Timing reconstruction

`try_begin_order_submission` (DB INSERT) happens **before** PricingInfo. MARKET_ORDER.time is T4. T0–T3 and T6 were not logged.

| Interval | Cancelled N=19 | Successful N=5 |
|---|---|---|
| PricingInfo request ms | UNKNOWN | UNKNOWN |
| quote → OrderCreate ms | UNKNOWN | UNKNOWN |
| reserve(created_at) → broker tx ms | min 150.7 / med 157.5 / max 248.2 | min 158.2 / med 164.3 / max 238.5 |
| T4 vs T5 | identical timestamps | n/a (fill, not cancel) |

T4 and T5 are the same instant on every cancel (**PROVEN**). Independently timestamped clocks are not sub-millisecond comparable; the 150–250 ms bound is only `timestamptz` minus RFC3339.

**PROVEN:** cancelled and successful writes occupy the same ~160 ms envelope. Latency does not separate the populations.

## 8. Price-movement reconstruction

No tick tape and no persisted PricingInfo. Evidence used: last completed M1 MBA bar at or before T4, plus reconstructed xref.

Because reconstructed xref already sits on the M1 executable side and sl_d < M1 spread on all 19, the cancel is explained by **book width versus stop distance**, not by a measured adverse walk after T1.

Per-event movement class: **STRONG_EVIDENCE_HEADROOM_CONSUMED** (trigger-side already through SL on the M1 bar). Not PROVEN_HEADROOM_CONSUMED against the live snapshot (snapshot UNKNOWN).

## 9. Successful control population

Same audit neighbourhood, broker-confirmed fills:

| UTC | symbol | side | cid | trade | xref | SL | TP | fill |
|---|---|---|---|---|---|---|---|---|
| 20:52:51Z | USD_JPY | SELL | cid-f0018527cf024210bf211e9df62dd1ea | 3124 | 157.374 | 157.431 | 157.261 | 157.374 |
| 21:21:22Z | USD_JPY | BUY | cid-239ddf6d18aa4f8d8a4d179949dd5c5f | 3163 | 157.463 | 157.412 | 157.564 | 157.463 |
| 21:23:24Z | USD_JPY | BUY | cid-868759c88fbf4106b7a450820dcd636d | 3169 | 157.444 | 157.393 | 157.545 | 157.444 |
| 21:35:37Z | GBP_USD | BUY | cid-4ddd3a933d47430aa4af478ebeef0267 | 3183 | 1.33461 | 1.33413 | 1.33557 | 1.33461 |
| 21:41:44Z | USD_JPY | BUY | cid-0ff3d11b90464e358a077106d229d8eb | 3191 | 157.421 | 157.378 | 157.508 | 157.421 |

Fill equals `executable_reference` on all five (`fill_delta_pips=0`). Fill-based R 1.98–2.02.

## 10. Cancelled vs successful statistics

Values use only known numbers. Spreads are M1 MBA closes (same method both sides).

| Metric | Cancelled | Successful |
|---|---|---|
| ORDER COUNT | 19 | 5 |
| STOP PIPS min/p25/med/p75/max | 2.63 / 4.23 / **4.57** / 4.63 / 4.87 (N=19) | 4.30 / 4.80 / **5.10** / 5.10 / 5.70 (N=5) |
| SPREAD PIPS | 5.2 / 8.1 / **10.2** / 15.9 / 15.9 (N=19) | 1.5 / 2.5 / **3.7** / 3.8 / 4.8 (N=5) |
| STOP/SPREAD | 0.28 / 0.29 / **0.36** / 0.49 / 0.58 (N=19) | 1.06 / 1.16 / **1.34** / 1.92 / 3.80 (N=5) |
| PRICINGINFO REQUEST MS | UNKNOWN | UNKNOWN |
| QUOTE → ORDERCREATE MS | UNKNOWN | UNKNOWN |
| RESERVE → BROKER TX MS | 150.7 / — / **157.5** / — / 248.2 (N=19) | 158.2 / 159.5 / **164.3** / 178.3 / 238.5 (N=5) |
| FILL DELTA PIPS | n/a (no fill) | 0 / 0 / **0** / 0 / 0 (N=5) |

Complete separation on stop/spread: cancelled max 0.58 < successful min 1.06.

## 11. Stop-distance analysis

Cancelled stops are slightly tighter (median 4.57 vs 5.10) and include AUD at 2.63–3.03 pips. They are **not** a different order of magnitude from successful JPY/GBP stops (4.3–5.7).

`sl_d /` reconstructed M5 ATR14 median 2.32 (N=19) matches `USE_ATR_STOPS` × `SL_ATR_MULT=2` within ATR-definition error. These are ATR stops, not 20-pip fallback (**STRONG INFERENCE**).

Conclusion: cancellations are **not** explained by “stops too tight” versus successful stops alone. They are concentrated where **stop < spread**.

## 12. Spread analysis

Cancelled M1 spreads 5.2–15.9 pips (GBP often 15.6–15.9). Successful M1 spreads 1.5–4.8.

Relative measure (stop/spread) separates the sets completely. Absolute spread also separates (cancelled min 5.2 > successful median 3.7).

No spread filter is recommended for implementation in this task.

## 13. Latency analysis

Reserve→broker medians 157.5 vs 164.3 ms. Overlapping ranges. **PROVEN** that cancellations are not the slow tail.

PricingInfo duration and quote→OrderCreate specifically: **UNKNOWN**.

## 14. Symbol / side / strategy concentration

Window OrderCreates (20:52Z–21:41Z): 24 = 19 cancel + 5 fill.

| Symbol | Cancels | Fills | Cancel rate |
|---|---|---|---|
| GBP_USD | 9 | 1 | 9/10 |
| AUD_USD | 4 | 0 | 4/4 |
| USD_JPY | 2 | 4 | 2/6 |
| USD_CHF | 2 | 0 | 2/2 |
| USD_CAD | 2 | 0 | 2/2 |

Side: BUY 13 / SELL 6 among cancels. Strategies mixed (swing_trend, swing_mean_reversion, swing_breakout, scalp). Not JPY-only, not one strategy.

USD-direction: mixed (GBP/AUD BUY = long quote USD; JPY/CHF/CAD SELL = short USD).

## 15. Temporal clustering

First cancel 21:06:04Z / 22:06:04 local. Last 21:40:43Z / 22:40:44 local. Duration 34 m 39 s. 1–2 events per minute (evaluate cadence).

Successes interleaved: JPY 21:21, 21:23; GBP 21:35; JPY 21:41. Rules out total OANDA outage and universally malformed geometry. Weakens “account locked” / persistent 400-style reject.

## 16. Market-event context

M1 spreads of 5–16 pips on majors are themselves a wide-book regime (**PROVEN** in candles).

Public calendars for 2026-09-22 show Fed speeches (Williams/Jefferson morning ET; Barkin 13:00 ET = 17:00 UTC) and no FOMC decision (Sep 15–16). The cluster is 21:06 UTC (17:06 ET). No authoritative 21:00 UTC print was verified. **HIGH-VOLATILITY CLUSTER: YES** from spreads; **named event: INCONCLUSIVE**. No session/event filter proposed.

## 17. Rounding analysis

JPY 3 dp, others 5 dp. Stop distances 2.6–4.9 pips. One tick is 0.1 pip (non-JPY) or 0.1 pip (JPY at 0.001). Rounding cannot flip sl_d from 4.6 pips to below a 10-pip spread.

ROUNDING_PRIMARY: 0  
ROUNDING_CONTRIBUTORY: 0  
ROUNDING_IMMATERIAL: 19

## 18. Post-PricingInfo code path

Order of work in `evaluate` broker branch:

1. `generate_client_order_id` + `try_begin_order_submission` (**DB write**, before quote)
2. `fetch_entry_pricing` → PricingInfo GET (`acquire_oanda_rest_slot`)
3. `resolve_live_entry_geometry` (local)
4. `logger.info` geometry line
5. `execute_oanda_market_open` → thread → `acquire_oanda_rest_slot` → `api.request(OrderCreate)`

After the quote: no extra model call, no reconcile, no `alert()`, no `sleep` except the limiter. Hybrid/RL/sizing/`alert([HYBRID])` run **before** the broker block.

Avoidable post-quote work: info log + second limiter acquire + HTTP. Not a multi-second stall. **POST-QUOTE CODE DELAY CONTRIBUTORY: NO** as the cancel distinguisher.

## 19. Rate-limiter analysis

Process-wide lock, default 10 RPS (100 ms). Shared by candles, account, reconcile, PricingInfo, and OrderCreate. OrderCreate **can** wait after a fresh quote if another REST call consumed the next slot.

Two-symbol minutes (GBP then JPY at 21:06) imply four REST calls (2× GET + 2× POST) inside ~350 ms, consistent with ~100 ms spacing.

Measured reserve→tx still ~150 ms including the PricingInfo GET. Limiter wait is at most a fraction of that. **RATE LIMITER CONTRIBUTORY: NO** as the reason 19 cancelled and 5 filled.

## 20. HTTP / client latency

`get_api()` reuses a process-global oandapyV20 `API` (requests Session). Timeouts re-applied; the client is not rebuilt per OrderCreate. No evidence of per-write DNS/TLS setup. **HTTP/CONNECTION DELAY: not the distinguisher.**

## 21. FOK semantics

`timeInForce=FOK`, `positionFill=OPEN_ONLY`, absolute `stopLossOnFill.price` + `takeProfitOnFill.price`. FOK + SL-on-fill-loss → MARKET_ORDER + ORDER_CANCEL, no leftover working order. Do not change FOK from this audit.

## 22. Root-cause determination

PRIMARY: **L. MULTIPLE CONTRIBUTING CAUSES**

| Code | Role | Label |
|---|---|---|
| F. SPREAD / EXECUTION-SIDE EFFECT | sl_d < contemporaneous spread; SL already through trigger side | STRONG INFERENCE (M1); mechanism matches official cancel reason |
| E. STOP DISTANCES TOO SMALL RELATIVE TO THAT BOOK | ATR×2 ≈ 2.6–4.9 pips vs 5–16 pip spreads; vs successful stops only slightly smaller | STRONG INFERENCE |
| H. OANDA SL-ON-FILL SEMANTICS | trigger side ≠ executable entry side | PROVEN in docs + 19 reasons |
| Local orientation gap | validates vs ask/bid, not vs bid/ask trigger | PROVEN in code |
| A. MARKET MOVEMENT AFTER QUOTE | not required if sl_d ≤ spread at T1; T1 spread UNKNOWN | HYPOTHESIS as extra |
| B/C/D latency | same ~160 ms as fills | NOT supported as distinguisher |
| G rounding | ≤0.1 pip | NOT supported |
| Wrong executable side / stale M5 | xref tracks ask/bid; SL ≠ mid-SL | NOT supported |
| K wide-spread cluster | M1 widths | STRONG INFERENCE; named news INCONCLUSIVE |

## 23. Observability gap

Confirmed. The 201 body had `orderCancelTransaction.reason=STOP_LOSS_ON_FILL_LOSS`. The parser only tested `orderFillTransaction`. Separate from the mechanism. Do not implement logging here. A later change should also persist PricingInfo bid/ask/spread and trigger-side headroom — those fields are what this audit had to reconstruct.

## 24. Remaining uncertainty

- Live PricingInfo bid/ask/spread/duration at T1 for the 19
- Exact bot ATR series (reconstructed ATR14 is a proxy; ratio ~2.3 vs configured 2.0)
- Horizon
- Whether any millisecond-scale adverse tick after T1 added to an already-negative trigger headroom
- Named macro print at 21:06 UTC

## 25. One justified next action

**G. DESIGN EVIDENCE-BASED EXECUTION HEADROOM MECHANISM**

Do not implement it now. Do not add an arbitrary pip/ATR/spread buffer, cooldown, or retry.

The measured condition is:

```
BUY:  sl_d ≤ ask − bid  → bid ≤ ask − sl_d = SL  → STOP_LOSS_ON_FILL_LOSS
SELL: sl_d ≤ ask − bid  → ask ≥ bid + sl_d = SL  → STOP_LOSS_ON_FILL_LOSS
```

Any later design must use the **live PricingInfo spread / trigger side at T1**, fail closed without OrderCreate when trigger-side clearance is already non-positive, keep ATR methodology and intended 2R unless a separate evidence-based sizing change is approved, and keep no blind retry.

Observability (`orderCancelTransaction`) remains justified but is not this action.

PRODUCTION CHANGES ON THE RUNNING CONTAINER: NO  
OANDA WRITES: NO  
DOCKER REBUILT / RESTARTED: NO  
DEPLOYED: NO
