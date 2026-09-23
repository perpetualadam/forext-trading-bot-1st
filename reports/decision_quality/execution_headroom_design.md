DESIGN VERDICT:
Policy A — exact trigger-side validity precheck, invalid or zero clearance → SKIP — is the only candidate that targets the proven OANDA STOP_LOSS_ON_FILL_LOSS mechanism without changing ATR stops, TP, intended 2R, or position sizing. Offline replay on the reconstructable post-deploy book (M1 MBA close proxy + submitted SL/TP): Policy A would have blocked 19/19 cancellations and allowed 5/5 successful controls (false-skip 0). All 19 reconstructed clearances were negative (median −6.2 pips; max −2.1). All 5 successful clearances were positive (min +0.30 pips; median +1.20). No cancellation had positive clearance. No successful fill had non-positive clearance. Therefore current evidence supports exact validity only. An extra positive buffer is not justified: a 0.5-pip, 1.0-pip, or 10%-of-stop buffer would have false-skipped 2 of 5 historical fills. Policies C and D prevent the same 19 cancels only by widening risk (median 2.82×) and destroying or relocating 2R; that is a strategy/risk-model change, not an execution fix. Policy E (skip if sl_d ≤ spread) agreed with Policy A on this N=24 set but is mathematically equivalent only under the current BUY=ask / SELL=bid / SL=xref±sl_d construction and before rounding. Prefer the exact inequality. Policy A does not guarantee zero future STOP_LOSS_ON_FILL_LOSS: PricingInfo → OrderCreate is not atomic. It also does not improve strategy expectancy; the 19 never filled. Design only — not implemented.

CONFIDENCE:
HIGH on the inequality and on 19/19 + 5/5 under the M1 proxy.
MEDIUM on live PricingInfo equality with that proxy (snapshots were not persisted).

KNOWN CANCELLATIONS REPLAYED:
19

POLICY A CANCELS PREVENTED:
19/19

SUCCESSFUL CONTROLS REPLAYED:
5

POLICY A SUCCESSFUL CONTROLS ALLOWED:
5/5

POLICY A FALSE SKIPS:
0

EXACT TRIGGER-SIDE RULE:
BUY: entry=ask; SL trigger=bid; valid iff bid > SL; clearance = bid − SL
SELL: entry=bid; SL trigger=ask; valid iff ask < SL; clearance = SL − ask
Skip iff clearance ≤ 0. Do not widen SL/TP.

STOP>SPREAD EQUIVALENT:
CONDITIONAL

ADDITIONAL POSITIVE BUFFER JUSTIFIED:
NO

RECOMMENDED REQUIRED CLEARANCE:
0 (skip when trigger-side clearance ≤ 0)

ATR STOP CHANGED:
NO

TP CHANGED:
NO

INTENDED 2R CHANGED:
NO

POSITION SIZING CHANGED:
NO

MONETARY RISK CHANGED:
NO

PAPER/BACKTEST CHANGED:
NO

BLIND RETRY INTRODUCED:
NO

OANDA CANCEL CLASSIFICATION DESIGN:
Classify OrderCreate 201 as FILLED / CANCELLED / REJECTED / AMBIGUOUS_TRANSPORT_OUTCOME / MALFORMED_RESPONSE. Persist orderCancelTransaction.reason. No automatic retry.

HIGHEST-PRIORITY NEXT ACTION:
A

PRODUCTION IMPLEMENTATION:
NO

PRODUCTION CHANGES:
NO

DOCKER RESTART:
NO

OANDA WRITES:
NO

## 1. Scope and constraints

Design and offline-evaluate a live-entry execution-headroom rule for the 19 post-deploy FOK `STOP_LOSS_ON_FILL_LOSS` cancellations.

This report does not implement production trading code, change `.env`, write the database, rebuild/restart Docker, or call OANDA write endpoints. Isolated replay lives at `reports/decision_quality/_execution_headroom_replay.py` and `_execution_headroom_replay.json`.

Invariants that any future implementation must keep: dedicated PricingInfo GET immediately before OrderCreate; BUY=ask / SELL=bid; ATR risk distance unchanged; intended TP ≈ 2R; existing precision and orientation; no M5 fallback; fail closed on missing/malformed pricing; one OrderCreate; no blind retry; ClientPrice.time diagnostic only; paper / window_paper / simulated / backtest unchanged; existing-position management, profit protection, broker-exit accounting, portfolio caps, and USD-direction guard unchanged.

## 2. Established forensic evidence

From `stop_loss_on_fill_loss_forensic_audit.md` and `oanda_missing_orderfilltransaction_forensic_audit.md` (**PROVEN**, not reopened):

- 19 unique HTTP-successful FOK MARKET_ORDERs immediately cancelled
- reason on all 19: `STOP_LOSS_ON_FILL_LOSS`
- no fill, trade, residual position, local/broker ghost, or blind retry
- pre-submit orientation vs executable reference: 19/19 valid
- intended ~2R vs reconstructed distances: valid
- executable side correct (BUY≈ask, SELL≈bid); stale-M5 mid attach did not recur
- cancelled median stop 4.57 pips vs median M1 spread 10.2; max stop/spread 0.58
- successful controls median stop 5.10 vs median spread 3.7; min stop/spread 1.06
- latency / rate limiter / rounding / wrong-side were not the distinguisher

Book used for replay: last completed M1 MBA bid/ask close at or before the MARKET_ORDER time, plus submitted SL/TP from the transaction. Live PricingInfo bid/ask were computed in-process and **not persisted**. Label: **STRONG INFERENCE** on the M1 proxy, not a live snapshot.

## 3. OANDA trigger-side semantics

Official `OrderCancelReason.STOP_LOSS_ON_FILL_LOSS` (**PROVEN**, OANDA v20):

> Filling the Order would result in the creation of a Stop Loss Order that would have been filled immediately, closing the new Trade at a loss.

Official `OrderTriggerCondition.DEFAULT` (**PROVEN**, developer.oanda.com order-df):

> Trigger an Order the “natural” way: compare its price to the ask for long Orders and bid for short Orders.

A long trade’s attached SL is a **sell / short** stop → DEFAULT compares to the **bid**.  
A short trade’s attached SL is a **buy / long** stop → DEFAULT compares to the **ask**.

GSLO restriction confirms the natural sides: long GSLO may be DEFAULT or BID; short GSLO may be DEFAULT or ASK.

The bot does not send `triggerCondition` (`oanda_exec.py` `stopLossOnFill` is price + GTC only). DEFAULT applies. Transactions recorded `triggerMode=TOP_OF_BOOK`. CloseoutBid/Ask are flatten prices for existing-position management, not this comparator.

The 19 events have no `ORDER_FILL.price`. Prospective fill is not persisted. Do not invent one.

Exact validity inequalities at the book OANDA evaluates:

```
BUY:  entry_reference = ask
      SL_trigger      = bid
      valid           iff  bid > SL
      immediate-loss  iff  bid ≤ SL

SELL: entry_reference = bid
      SL_trigger      = ask
      valid           iff  ask < SL
      immediate-loss  iff  ask ≥ SL
```

Local `orientation_valid` only checks `SL < xref < TP` (BUY) or the inverse. That can pass while `bid ≤ SL`. **PROVEN** in `entry_geometry.py`.

Trigger-side relationship is not uncertain. Design may proceed.

## 4. Mathematical definition of trigger-side clearance

Using the **same** PricingInfo snapshot already used for executable geometry:

```
EXECUTABLE_REFERENCE:
  BUY  = ask
  SELL = bid

TRIGGER_SIDE_PRICE:
  BUY  = bid
  SELL = ask

INTENDED_SL, INTENDED_TP:
  existing construct_absolute_sl_tp + instrument precision
  BUY:  SL = round(ask − sl_d), TP = round(ask + 2·sl_d)
  SELL: SL = round(bid + sl_d), TP = round(bid − 2·sl_d)

INTENDED_RISK_DISTANCE = sl_d   (ATR × SL_ATR_MULT, unchanged)
SPREAD = ask − bid

TRIGGER_SIDE_CLEARANCE:
  BUY:  clearance = bid − SL
  SELL: clearance = SL − ask
```

Sign convention:

| clearance | Meaning |
|---|---|
| > 0 | intended SL is strictly inside the trigger side; technically valid at this snapshot |
| = 0 | no usable clearance; SL sits on the trigger price |
| < 0 | trigger-side price has already crossed the intended SL |

Also report:

- `clearance_pips = clearance / pip_size`
- `clearance / intended_risk_distance`
- `clearance / spread` where useful

Validity and safety headroom are different. Validity is `clearance > 0`. Safety headroom is how large that positive number is. They are not conflated below.

## 5. Policy A design

Immediately before OrderCreate, after existing `resolve_live_entry_geometry` succeeds:

1. Keep BUY=ask, SELL=bid, ATR `sl_d`, intended 2R, existing rounding and orientation.
2. Compute `TRIGGER_SIDE_CLEARANCE` on that same snapshot.
3. If `clearance > 0`: submit exactly one OrderCreate with the unchanged SL/TP.
4. If `clearance ≤ 0`: SKIP. Fail closed. No OrderCreate.
5. Do not widen SL. Do not move TP. Do not change ATR. Do not change 2R. Do not retry. Do not fall back to M5.

Required clearance for the production recommendation: **0**. Skip on `≤ 0`.

This is a technical OANDA-validity gate, not a spread filter and not an economic-quality filter.

## 6. Policy B control

Existing behavior: submit the geometrically oriented SL/TP and allow OANDA to cancel.

Replay: 19/19 would still be submitted; 19/19 would remain `STOP_LOSS_ON_FILL_LOSS`; 5/5 fills still allowed. Control only.

## 7. Policy C/D geometry-change consequences

Both start from the same trigger inequality. If `clearance ≤ 0`, they **widen SL** to the first valid tick inside the trigger side:

```
BUY:  SL_new = bid − 1 tick
SELL: SL_new = ask + 1 tick
```

tick = JPY 0.001 / others 0.00001.

**Policy C** keeps TP fixed.

On the 19 cancellations (M1 proxy):

| | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| resulting R | 0.54 | 0.58 | **0.71** | 1.02 | 1.16 |
| monetary-risk multiple vs intended sl_d | 1.73× | 1.97× | **2.82×** | 3.42× | 3.72× |

Intended 2R is lost. Risk distance becomes approximately the spread, not ATR×2.

**Policy D** recomputes `TP_new = xref ± 2 · (new risk)` to restore 2R.

| | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| TP move (pips) | 4.4 | 8.2 | **12.6** | 22.2 | 23.2 |
| risk multiple | same as C | | **2.82×** | | 3.72× |

Units are already computed from M5 mid + original ATR `sl_d` **before** PricingInfo (`bot_loop.py`). Widening SL without resizing increases account-currency stop risk by that same multiple. Resizing would be required to hold monetary risk constant. That is a strategy and risk-model change.

Neither C nor D is selected. Avoiding cancellation is not sufficient if strategy economics change.

## 8. Policy E simple spread relationship

Policy E: skip when `intended_risk_distance ≤ spread`.

Under **unrounded** current geometry:

```
BUY:  SL = ask − sl_d
      clearance = bid − (ask − sl_d) = sl_d − spread

SELL: SL = bid + sl_d
      clearance = (bid + sl_d) − ask = sl_d − spread
```

Therefore:

`sl_d > spread`  ⇔  `clearance > 0`

**EQUIVALENT ONLY UNDER CONDITIONS:**

1. BUY executable reference is ask and SELL is bid
2. SL is constructed as `xref ± sl_d` from that same snapshot
3. bid and ask are the same PricingInfo pair used for SL
4. rounding / precision does not flip the sign of `bid − round(ask − sl_d)` (BUY) or `round(bid + sl_d) − ask` (SELL)

**NOT EQUIVALENT** if SL is mid-anchored, uses closeout prices, uses a stale or other-instrument quote, or after independent SL rounding that crosses the trigger tick.

On this N=24 replay, Policy A and Policy E agreed on every event. Prefer Policy A: it is the comparison OANDA actually makes (rounded SL vs trigger side), not a ratio that can lose a tick.

## 9. 19-event replay

Book = M1 MBA close + submitted SL. Policy A skip if `clearance ≤ 0`.

| # | symbol | side | stop pips | spread pips | clearance pips | A | B | E | C/D modify |
|---|---|---|---|---|---|---|---|---|---|
| 1 | GBP_USD | BUY | 4.57 | 15.9 | −11.0 | SKIP | SUBMIT | SKIP | YES |
| 2 | USD_JPY | SELL | 4.87 | 10.0 | −5.1 | SKIP | SUBMIT | SKIP | YES |
| 3 | GBP_USD | BUY | 4.57 | 15.9 | −11.0 | SKIP | SUBMIT | SKIP | YES |
| 4 | AUD_USD | BUY | 2.63 | 7.1 | −4.5 | SKIP | SUBMIT | SKIP | YES |
| 5 | USD_JPY | SELL | 4.87 | 10.0 | −6.2 | SKIP | SUBMIT | SKIP | YES |
| 6 | AUD_USD | BUY | 2.63 | 7.3 | −4.7 | SKIP | SUBMIT | SKIP | YES |
| 7 | USD_CHF | SELL | 4.23 | 15.0 | −10.1 | SKIP | SUBMIT | SKIP | YES |
| 8 | USD_CHF | SELL | 4.23 | 15.0 | −11.4 | SKIP | SUBMIT | SKIP | YES |
| 9 | GBP_USD | BUY | 4.53 | 15.9 | −11.5 | SKIP | SUBMIT | SKIP | YES |
| 10 | USD_CAD | SELL | 4.27 | 7.8 | −3.1 | SKIP | SUBMIT | SKIP | YES |
| 11 | USD_CAD | SELL | 4.27 | 10.2 | −3.4 | SKIP | SUBMIT | SKIP | YES |
| 12 | GBP_USD | BUY | 4.63 | 15.6 | −10.6 | SKIP | SUBMIT | SKIP | YES |
| 13 | GBP_USD | BUY | 4.63 | 15.9 | −10.8 | SKIP | SUBMIT | SKIP | YES |
| 14 | GBP_USD | BUY | 4.63 | 15.9 | −11.0 | SKIP | SUBMIT | SKIP | YES |
| 15 | GBP_USD | BUY | 4.63 | 15.9 | −11.5 | SKIP | SUBMIT | SKIP | YES |
| 16 | GBP_USD | BUY | 4.83 | 8.6 | −3.5 | SKIP | SUBMIT | SKIP | YES |
| 17 | GBP_USD | BUY | 4.83 | 8.4 | −4.1 | SKIP | SUBMIT | SKIP | YES |
| 18 | AUD_USD | BUY | 2.90 | 6.8 | −3.9 | SKIP | SUBMIT | SKIP | YES |
| 19 | AUD_USD | BUY | 3.03 | 5.2 | −2.1 | SKIP | SUBMIT | SKIP | YES |

Policy A blocked **19/19**. Diagnosis holds on this book. Not forced: every reconstructed clearance was ≤ −2.1 pips.

## 10. Successful-control replay

| UTC cid | symbol | side | stop | spread | clearance pips | A | actual |
|---|---|---|---|---|---|---|---|
| cid-f0018527… | USD_JPY | SELL | 5.70 | 1.5 | +4.70 | SUBMIT | FILLED |
| cid-239ddf6d… | USD_JPY | BUY | 5.10 | 4.8 | +0.30 | SUBMIT | FILLED |
| cid-868759c8… | USD_JPY | BUY | 5.10 | 3.8 | +1.20 | SUBMIT | FILLED |
| cid-4ddd3a93… | GBP_USD | BUY | 4.80 | 2.5 | +3.00 | SUBMIT | FILLED |
| cid-0ff3d11b… | USD_JPY | BUY | 4.30 | 3.7 | +0.40 | SUBMIT | FILLED |

Policy A allowed **5/5**. False-skip rate **0%** on this control set.

The two tightest successful clearances are +0.30 and +0.40 pips (JPY BUY, stop/spread 1.06 and 1.16). Exact validity still allows them. A 0.5-pip “safety” buffer would not.

## 11. Expanded historical replay

Reliable reconstructable live-broker attempts with contemporaneous bid/ask **and** executable-price geometry: **N=24** (19 cancel + 5 fill).

Pre-geometry-fix `STOP_LOSS_ON_FILL_LOSS` rows from the 24h forensic audit used M5-mid attach, a different defect. They are excluded. Live PricingInfo snapshots are not in `exec_orders`. Missing books were not manufactured.

## 12. False-positive / false-negative matrix

Policy A on N=24 (M1 proxy):

|  | Actual STOP_LOSS_ON_FILL_LOSS | Actual fill |
|---|---|---|
| SKIP | 19 TRUE BLOCK | 0 FALSE BLOCK |
| SUBMIT | 0 FALSE ALLOW | 5 TRUE ALLOW |

Rates: true-block 19/19; false-allow 0/19; true-allow 5/5; false-skip 0/5.

Do not overstate: N is small and the book is a completed-bar proxy.

## 13. Positive-clearance distribution

Cancelled trigger-side clearance (pips), N=19:

| min | p10 | p25 | median | p75 | max |
|---|---|---|---|---|---|
| −11.50 | −11.42 | −11.00 | **−6.20** | −4.00 | −2.10 |

Successful trigger-side clearance (pips), N=5:

| min | p10 | p25 | median | p75 | max |
|---|---|---|---|---|---|
| **+0.30** | +0.34 | +0.40 | **+1.20** | +3.00 | +4.70 |

Cancels with positive clearance: **0**  
Fills with non-positive clearance: **0**

Small positive clearance that still filled: yes — +0.30 and +0.40 pips.

## 14. Whether extra headroom buffer is justified

Validity vs safety headroom were tested separately.

Candidate extra buffers, same replay:

| required clearance | cancels blocked | successful false skips |
|---|---|---|
| exact `> 0` | 19/19 | 0/5 |
| +0.1 pip | 19/19 | 0/5 |
| +0.5 pip | 19/19 | **2/5** |
| +1.0 pip | 19/19 | **2/5** |
| 10% of intended stop | 19/19 | **2/5** |

Current data contain only:

- clearance ≤ 0 → cancellation
- clearance comfortably or barely > 0 → fill

There is **no** observed `STOP_LOSS_ON_FILL_LOSS` with positive snapshot clearance. A tiny-positive-clearance cancel class does not exist in this sample.

**NO ADDITIONAL BUFFER JUSTIFIED BY CURRENT EVIDENCE.**

A 0.1-pip cushion happens to keep 0 false skips on N=5. That is still an arbitrary value. It is not selected “for safety.”

The race remains (section 17). That is not evidence for a pip buffer.

## 15. Position-sizing consequences

Current order of work (**PROVEN** in `bot_loop.py`):

1. `sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr)` from M5 ATR
2. `units = position_sizing(...)` and portfolio / USD-direction guards using that `sl_d`
3. `try_begin_order_submission` (DB)
4. PricingInfo + `resolve_live_entry_geometry` (re-anchor same `sl_d` to ask/bid)
5. OrderCreate

Policy A only SKIPS. Units, `sl_d`, and TP are unchanged on allowed orders. Monetary risk unchanged.

Policies C/D widen SL after units are fixed → account stop risk rises by ~1.7–3.7× on the 19. Flagged. Do not change sizing in this design.

## 16. R:R consequences

| Policy | intended R | resulting R | SL | TP |
|---|---|---|---|---|
| A | ~2 | unchanged (~2 vs xref) | unchanged | unchanged |
| B | ~2 | n/a (cancel) or ~2 on fills | unchanged | unchanged |
| C | ~2 | median **0.71** on the 19 | widened | fixed → R collapses |
| D | ~2 | ~2 by construction | widened | moved median **12.6 pips** |
| E | ~2 | unchanged on allows | unchanged | unchanged |

## 17. Technical validity vs economic quality

Policy A answers only: *can this exact intended stop be attached under the current executable book?*

A technically valid trade can still be economically poor when the spread is a large fraction of ATR. That is a separate, unresolved expectancy question. This design does not add a spread filter, pair disable, or event filter.

Skipping the 19 would have prevented rejected OrderCreates. Those 19 never filled, so skipping them removes **zero** realized P/L. Broker-rejection prevention ≠ trading-performance improvement. Do not claim profitability improvement.

## 18. Proposed production pseudocode

Design only. Do not implement.

```
fetched = fetch_entry_pricing(symbol)          # existing dedicated GET
if fetched.skip_reason:
    SKIP fail_closed                           # existing
geom, skip = resolve_live_entry_geometry(...)  # existing; BUY=ask, SELL=bid
if geom is None:
    SKIP fail_closed                           # existing

if geom.side == "BUY":
    trigger_side = "bid"
    trigger_price = geom.bid
    clearance = geom.bid - geom.sl
else:
    trigger_side = "ask"
    trigger_price = geom.ask
    clearance = geom.sl - geom.ask

if geom.bid is None or geom.ask is None:
    SKIP fail_closed reason=missing_trigger_side
if not finite(clearance):
    SKIP fail_closed reason=malformed_price

REQUIRED_CLEARANCE = 0                         # evidence-supported
if clearance <= REQUIRED_CLEARANCE:
    SKIP reason=insufficient_sl_trigger_clearance
    log fields below
    no OrderCreate, no M5 fallback, no retry
else:
    OrderCreate exactly once with geom.sl / geom.tp
    no blind retry on later cancel
```

Preserve existing fail-closed reasons: `pricing_request_failed`, `pricing_timeout`, `instrument_missing`, `executable_ask_missing`, `executable_bid_missing`, `malformed_price`, `not_tradeable`, `invalid_orientation_after_rounding`. ClientPrice.time remains diagnostic. Do not reject solely because last-change age > 5s.

## 19. Proposed logging / observability

Pre-submit skip (new reason; do not reuse `stale_quote`):

```
[ENTRY GEOMETRY SKIP]
reason=insufficient_sl_trigger_clearance
symbol=... side=...
bid=... ask=... spread=... spread_pips=...
executable_reference=...
trigger_side=bid|ask trigger_price=...
SL=... TP=...
risk_distance_pips=...
trigger_clearance_pips=...
required_clearance_pips=0
intended_R=...
price_time=...
price_last_change_age_ms=...
pricing_request_duration_ms=...
fail_closed=true
```

Broker response classification (replace generic `missing orderFillTransaction`):

| Class | Condition | Action |
|---|---|---|
| FILLED | `orderFillTransaction` present with trade | existing fill path |
| CANCELLED | `orderCancelTransaction` present | log; mark failed/cancelled; **no retry** |
| REJECTED | HTTP error / orderRejectTransaction | existing fail; **no retry** |
| AMBIGUOUS_TRANSPORT_OUTCOME | transport error after write may have been accepted | existing reconcile; **no blind retry** |
| MALFORMED_RESPONSE | 201 body missing fill and cancel | fail closed; **no retry** |

Cancel log:

```
[ORDER CANCEL]
symbol=... side=... cid=...
create_tx=... cancel_tx=...
reason=STOP_LOSS_ON_FILL_LOSS
related_transaction_ids=...
```

Design only. Not implemented here.

## 20. Deterministic future test plan

A. BUY, normal spread, `bid > SL` → submit  
B. SELL, normal spread, `ask < SL` → submit  
C. BUY, `SL < ask` (orientation valid) but `bid ≤ SL` → skip  
D. SELL, `SL > bid` but `ask ≥ SL` → skip  
E. exact zero clearance → skip  
F. tiny positive clearance (e.g. +0.3 pip, historical JPY BUY) → submit  
G. all 19 historical cancellation reconstructions → skip  
H. 5 successful controls → submit  
I. JPY pip / 3dp tick  
J. non-JPY pip / 5dp tick  
K. rounding: unrounded valid, rounded SL onto trigger → skip; opposite → still submit  
L. missing bid → fail closed  
M. missing ask → fail closed  
N. malformed / non-finite / non-positive price → fail closed  
O. PricingInfo failure → fail closed  
P. PricingInfo timeout → fail closed  
Q. ClientPrice.time old, GET succeeded → not rejected for timestamp alone  
R. no M5 fallback  
S. no OrderCreate when precheck fails  
T. exactly one OrderCreate when precheck passes  
U. no blind retry after broker cancel  
V. `orderCancelTransaction` classified as CANCELLED  
W. paper unchanged  
X. window_paper unchanged  
Y. simulated / backtest unchanged  
Z. existing-position management unchanged  
AA. profit protection unchanged  
AB. broker-exit accounting unchanged  
AC. portfolio risk guards unchanged  
AD. USD-direction guard unchanged  

## 21. Policy comparison table

| POLICY | 19 CANCELS PREVENTED | SUCCESSFUL CONTROLS ALLOWED | FALSE SKIPS | CHANGES SL | CHANGES TP | CHANGES R | CHANGES MONETARY RISK | REQUIRES RESIZING | STRATEGY CHANGE? | IMPLEMENTATION COMPLEXITY | EVIDENCE SUPPORT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A exact trigger skip | 19/19 | 5/5 | 0 | NO | NO | NO | NO | NO | NO | low (one inequality on existing snapshot) | HIGH vs proven mechanism |
| B submit anyway | 0/19 | 5/5 | 0 | NO | NO | NO | NO | NO | NO | none | control |
| C widen SL, keep TP | 19/19 | 5/5 | 0 | YES | NO | YES (median R 0.71) | YES (median 2.82×) | YES to hold $ risk | YES | medium | prevents cancel by changing economics |
| D widen SL, recompute 2R TP | 19/19 | 5/5 | 0 | YES | YES | NO (forced 2R) | YES (median 2.82×) | YES | YES | medium | same |
| E sl_d > spread | 19/19 | 5/5 | 0 | NO | NO | NO | NO | NO | NO | low | equivalent only under current geometry; loses rounding |

Factual tradeoff: A and E match on this sample; A is the exact OANDA comparison. C/D prevent cancels by changing the trade. B changes nothing.

## 22. Remaining uncertainties

- Live PricingInfo bid/ask/spread at T1 for the 19 (M1 proxy only)
- Whether any future cancel will occur with `clearance > 0` after a post-quote adverse tick
- Exact bot ATR series vs reconstructed ATR14
- Economic quality of technically valid wide-spread entries (out of scope)
- Named 21:00 UTC event (still INCONCLUSIVE)

These do not block recommending exact validity. They do block inventing a buffer.

## 23. Single evidence-supported next action

**A. IMPLEMENT EXACT TRIGGER-SIDE VALIDITY PRECHECK, INVALID → SKIP**

NO ADDITIONAL BUFFER JUSTIFIED BY CURRENT EVIDENCE.

Do not implement in this task. When implemented later: required clearance = 0; skip if `clearance ≤ 0`; keep ATR, 2R, sizing, FOK, no retry; add the cancel-classification logs as a companion observability change; persist bid/ask/clearance so the next race can be measured rather than guessed.

PRODUCTION CHANGES: NO  
DOCKER RESTART: NO  
OANDA WRITES: NO
