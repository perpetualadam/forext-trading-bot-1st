AUDIT VERDICT:
All unique missing-orderFillTransaction opens were HTTP-successful FOK market OrderCreates that OANDA immediately cancelled. Every client ID exists in broker history as MARKET_ORDER + ORDER_CANCEL. The cancel reason on all 19 is STOP_LOSS_ON_FILL_LOSS. No fill, trade, residual position, attached SL/TP, or pending entry order remained. Local handling raised ValueError because it requires orderFillTransaction on every successful OrderCreate. Official v20 docs say that field is only present when the order is immediately filled. The bot correctly refused to open a local live position and did not retry the same client ID. The logged message hid the actual cancel reason.

CONFIDENCE:
HIGH

AUDIT WINDOW UTC:
2026-09-22T21:06:03Z through 2026-09-22T21:40:44Z (Docker timestamps and exec_orders created_at). Local Europe/London BST = UTC+1: 22:06:04 through 22:40:44.

RAW LOG OCCURRENCES:
19

UNIQUE ORDERCREATE ATTEMPTS:
19

EXPECTED INITIAL COUNT:
17

ACTUAL UNIQUE COUNT:
19

PRIMARY ROOT CAUSE:
B

BROKER STATE CREATED DESPITE LOCAL FAILURE:
SOME

SUCCESSFUL FILLS MISCLASSIFIED:
0

DEFINITIVE BROKER REJECTIONS:
0

CREATE-THEN-CANCEL:
19

AMBIGUOUS WRITE OUTCOMES:
0

GHOST BROKER POSITIONS:
0

GHOST LOCAL POSITIONS:
0

BLIND ORDERCREATE RETRIES:
NO

DUPLICATE FILLS:
NO

LOSING_TAKE_PROFIT:
0

STOP_LOSS_ON_FILL_LOSS:
19

TAKE_PROFIT_ON_FILL_LOSS:
0

OTHER OANDA REASONS:
0

ORDERCREATE RESPONSE HANDLING CORRECT:
PARTIAL

CURRENT ERROR MESSAGE ADEQUATE:
NO

RECONCILIATION SAFETY ADEQUATE:
YES

HIGHEST-PRIORITY NEXT ACTION:
C

PRODUCTION CODE CHANGED:
NO

ENV CHANGED:
NO

DATABASE WRITES:
NO

DOCKER REBUILT:
NO

DOCKER RESTARTED:
NO

OANDA WRITES:
NO

## 1. Scope and safety constraints

Read-only forensic of live OrderCreate responses classified locally as `OANDA response missing orderFillTransaction`.

Not reopened: old ~61s management bug, manual-close attribution, stale-M5 MFE, broker-exit accounting project, ClientPrice.time >5s semantics, or the executable-price geometry implementation except where these cancels cite `STOP_LOSS_ON_FILL_LOSS`.

Safety observed: no production-code edit, no `.env` edit, no database writes, no Docker rebuild/restart/stop, no OrderCreate / PositionClose / TradeCRC / SL-TP replace. OANDA access was GET only (`AccountDetails`, `TransactionIDRange`, `OpenPositions`, `OrdersPending`). Postgres access was `SELECT` only.

## 2. Audit timeline

| Clock | Event |
|---|---|
| 20:52:51Z / 21:52 local | Last successful open before the cluster: USD_JPY SELL fill 3124 |
| 21:05:00Z | USD_JPY 3124 exits on broker SL (tx 3130). Not one of the 19. |
| 21:06:04Z / 22:06 local | First missing-fill OrderCreate (GBP_USD BUY cid-34ea03ff → MARKET_ORDER 3132 / CANCEL 3133) |
| 21:06:04Z–21:19:20Z | 15 create-then-cancel opens, ~1/minute, multiple symbols |
| 21:21:22Z / 22:21 local | Successful USD_JPY BUY fill 3163 (user-noted 22:21) |
| 21:23:24Z / 22:23 local | Successful USD_JPY BUY fill 3169 (user-noted 22:23) |
| 21:25:26Z, 21:29:31Z | Two further GBP_USD BUY create-then-cancels |
| 21:35:37Z / 22:35 local | Successful GBP_USD BUY fill 3183 (user-noted 22:35) |
| 21:38:41Z, 21:40:43Z | Two AUD_USD BUY create-then-cancels |
| 21:41:44Z / 22:41 local | Successful USD_JPY BUY fill 3191 |
| Read-only pull | lastTransactionID 3195; open broker position = GBP_USD long 3183 only |

## 3. Unique affected requests

EXPECTED FROM INITIAL REVIEW: 17

ACTUAL COUNT FROM PRIMARY LOG: 19 timestamped Docker lines containing exactly `OANDA response missing orderFillTransaction`.

ACTUAL UNIQUE ORDERCREATE ATTEMPTS: 19

This path logs `logger.warning` only (no `alert()`). There is no 2× `logger.warning`+`alert()` inflation. Unique keys: one `exec_orders` row per event, unique `cid-…`, unique OANDA `requestID`, unique MARKET_ORDER id.

The initial “17” under-counted by two (the 21:38Z and 21:40Z AUD_USD attempts after the GBP fill).

RAW LOG OCCURRENCES: 19  
UNIQUE ORDERCREATE ATTEMPTS: 19

## 4. Current OrderCreate response-handling code

Path (unchanged this audit):

1. `bot_loop.evaluate` generates `cid-{uuid}` and `try_begin_order_submission` (memory + `exec_orders` PENDING).
2. Dedicated PricingInfo GET + `resolve_live_entry_geometry` (must succeed or skip before OrderCreate).
3. `_place_market_order_open_sync` (`oanda_exec.py`): FOK MarketOrder, `positionFill=OPEN_ONLY`, `stopLossOnFill` / `takeProfitOnFill`, `api.request(OrderCreate)`.
4. HTTP/transport exceptions become `[ORDER FAILED] OANDA OrderCreate (open) failed`.
5. Dict body → `_parse_open_fill`.
6. `_parse_open_fill` (lines 106–108): if `response.get("orderFillTransaction")` is missing/empty → `ValueError("OANDA response missing orderFillTransaction")`.
7. `bot_loop` except: `record_fill_failure()`, `mark_order_failed_or_cancelled` (`exec_orders` CANCELLED, metadata `reason=execution_failed`), `logger.warning("[ORDER FAILED] {symbol} open: {exc}")`, return. No local `[OPEN]`. No second `execute_oanda_market_open`.

Does the code assume every successful market OrderCreate response MUST contain `orderFillTransaction`? **YES.**

`orderCancelTransaction`, `orderRejectTransaction`, `relatedTransactionIDs`, `errorCode`, and `errorMessage` are not read on the open path.

## 5. OANDA documented response semantics

Official [Order Endpoints](https://developer.oanda.com/rest-live-v20/order-ep/) POST `/v3/accounts/{accountID}/orders`:

| HTTP | Meaning | Typical body |
|---|---|---|
| 201 | “The Order was created as specified” | `orderCreateTransaction` always. `orderFillTransaction` **only when immediately filled**. `orderCancelTransaction` **only when immediately cancelled**. Optional reissue fields. `relatedTransactionIDs`, `lastTransactionID`. |
| 400 | “The Order specification was invalid” | `orderRejectTransaction` + related IDs |

`orderFillTransaction` is **not** guaranteed on every HTTP-successful market order. A FOK market order that cannot be booked with its on-fill SL/TP is a documented 201 create-then-cancel.

Official `OrderCancelReason` includes `STOP_LOSS_ON_FILL_LOSS`: “Filling the Order would result in the creation of a Stop Loss Order that would have been filled immediately, closing the new Trade at a loss.”

Distinguish:

- HTTP success (201) ≠ filled
- filled = `orderFillTransaction` present
- created then cancelled = `orderCreateTransaction` + `orderCancelTransaction`
- transport ambiguity = no interpretable body / exception after the write may already have been accepted

## 6. Raw response evidence

The raw HTTP OrderCreate JSON was **not persisted** in application logs, `exec_orders.metadata`, or structured diagnostics. `ENTRY GEOMETRY` / `[ORDER SENT]` are `logger.info` and are not on Docker stdout under uvicorn lastResort WARNING.

Broker reconstruction is from OANDA transaction history (GET), which outranks the local error text:

Each of the 19 produced a `MARKET_ORDER` (`reason=CLIENT_ORDER`, `timeInForce=FOK`, `positionFill=OPEN_ONLY`, `clientExtensions.id=cid-…`, `stopLossOnFill` + `takeProfitOnFill`) and, **at the identical timestamp**, an `ORDER_CANCEL` whose `orderID` is that MARKET_ORDER id and whose `reason` is `STOP_LOSS_ON_FILL_LOSS`.

No `ORDER_FILL`, `MARKET_ORDER_REJECT`, `orderReissue*`, or `TRADE_CLIENT_EXTENSIONS_MODIFY` is attached to those client IDs.

HTTP status was not captured. Presence of MARKET_ORDER + ORDER_CANCEL (not MARKET_ORDER_REJECT) is **STRONG INFERENCE** of HTTP 201 rather than 400. Request IDs are on the MARKET_ORDER transactions.

## 7. OANDA transaction correlation

Chain for every affected request (**PROVEN**):

```
OrderCreate HTTP (FOK, OPEN_ONLY, SL/TP on fill)
→ MARKET_ORDER (orderCreateTransaction)
→ ORDER_CANCEL reason=STOP_LOSS_ON_FILL_LOSS
→ no ORDER_FILL
→ no trade ID
→ no STOP_LOSS_ORDER / TAKE_PROFIT_ORDER
```

Successful interleaved opens used the same chain except step 2 is ORDER_FILL + ON_FILL SL/TP.

## 8. Client-ID correlation

Every reserved `cid-` is unique (`uuid4`). All 19 appear on OANDA MARKET_ORDER `clientExtensions.id`. None appear on an ORDER_FILL. None appear on open trades, closed-trade fills, or pending entry orders.

HIGH-PRIORITY pattern (all 19):

```
LOCAL RESULT = FAILED (missing orderFillTransaction)
CLIENT ID EXISTS IN BROKER TRANSACTION HISTORY
```

Residual broker object for those IDs: **none**. History-only create+cancel.

No client ID was reused for a second OrderCreate.

## 9. Per-event forensic table

Times: UTC = Docker / OANDA; local = BST (UTC+1). Horizon: UNKNOWN (not persisted on cancelled rows). Bid/ask/spread/PricingInfo RTT/executable_reference: UNKNOWN (info logs not on stdout; cancel metadata is only mid/strategy/reason). HTTP status: UNKNOWN (201 inferred). `relatedTransactionIDs`: UNKNOWN not persisted; create+cancel IDs listed. Broker trade ID: none. Later reconcile action: none.

| # | UTC | local | symbol | side | units | strategy | horizon | client ID | OANDA request ID | HTTP | create tx | fill tx | cancel tx | OANDA reason | related (inferred) | trade | local | broker state | reconcile | class | conf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 21:06:04.122Z | 22:06:04 | GBP_USD | BUY | 1 | swing_trend | UNKNOWN | cid-34ea03ffe3fa486ab98e7bad36d45252 | 133609059983600024 | UNKNOWN | 3132 | none | 3133 | STOP_LOSS_ON_FILL_LOSS | 3132,3133 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B CREATE_THEN_CANCEL | HIGH |
| 2 | 21:06:04.479Z | 22:06:04 | USD_JPY | SELL | 2 | swing_trend | UNKNOWN | cid-8f55b3f86c5d4f2b918f5ee1d56baef0 | 133609059983600316 | UNKNOWN | 3134 | none | 3135 | STOP_LOSS_ON_FILL_LOSS | 3134,3135 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 3 | 21:07:05.565Z | 22:07:05 | GBP_USD | BUY | 1 | swing_trend | UNKNOWN | cid-6d0d82b0369e4f10b370dca4802b0af2 | 133609060239500270 | UNKNOWN | 3136 | none | 3137 | STOP_LOSS_ON_FILL_LOSS | 3136,3137 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 4 | 21:08:07.020Z | 22:08:07 | AUD_USD | BUY | 3 | swing_mean_reversion | UNKNOWN | cid-03209f355b264a10b11548a57443d6a7 | 133609060499591424 | UNKNOWN | 3138 | none | 3139 | STOP_LOSS_ON_FILL_LOSS | 3138,3139 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 5 | 21:09:08.073Z | 22:09:08 | USD_JPY | SELL | 2 | scalp | UNKNOWN | cid-3ac32014576e44ea986041bc7c85b447 | 133609060755489170 | UNKNOWN | 3140 | none | 3141 | STOP_LOSS_ON_FILL_LOSS | 3140,3141 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 6 | 21:09:08.439Z | 22:09:08 | AUD_USD | BUY | 3 | swing_mean_reversion | UNKNOWN | cid-cb964084bab6490b87f5606bebbaee98 | 115594662246496806 | UNKNOWN | 3142 | none | 3143 | STOP_LOSS_ON_FILL_LOSS | 3142,3143 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 7 | 21:10:09.931Z | 22:10:10 | USD_CHF | SELL | 2 | swing_trend | UNKNOWN | cid-eee7fdf92db44f61864421b14ff0ab19 | 115594662502390297 | UNKNOWN | 3144 | none | 3145 | STOP_LOSS_ON_FILL_LOSS | 3144,3145 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 8 | 21:11:11.135Z | 22:11:11 | USD_CHF | SELL | 2 | swing_mean_reversion | UNKNOWN | cid-84c40a5c859e4bed8c20118ef9cf5cd7 | 115594662762477704 | UNKNOWN | 3146 | none | 3147 | STOP_LOSS_ON_FILL_LOSS | 3146,3147 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 9 | 21:12:11.821Z | 22:12:12 | GBP_USD | BUY | 1 | swing_mean_reversion | UNKNOWN | cid-74595fd264cd484db786041a46582036 | 133609061523183947 | UNKNOWN | 3148 | none | 3149 | STOP_LOSS_ON_FILL_LOSS | 3148,3149 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 10 | 21:12:12.425Z | 22:12:12 | USD_CAD | SELL | 2 | swing_mean_reversion | UNKNOWN | cid-ac380f6a32914d59a20e8a2dbc9ee488 | 133609061527378731 | UNKNOWN | 3150 | none | 3151 | STOP_LOSS_ON_FILL_LOSS | 3150,3151 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 11 | 21:13:13.626Z | 22:13:14 | USD_CAD | SELL | 2 | swing_trend | UNKNOWN | cid-683e7c2d6f0a404ea4387efb01892d6d | 115594663274254489 | UNKNOWN | 3152 | none | 3153 | STOP_LOSS_ON_FILL_LOSS | 3152,3153 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 12 | 21:15:15.373Z | 22:15:15 | GBP_USD | BUY | 1 | swing_trend | UNKNOWN | cid-e6afc545a3d844529fc229dec57cceec | 133609062295063523 | UNKNOWN | 3154 | none | 3155 | STOP_LOSS_ON_FILL_LOSS | 3154,3155 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 13 | 21:16:16.571Z | 22:16:17 | GBP_USD | BUY | 1 | swing_trend | UNKNOWN | cid-bdb651433a0a4403b6802c46a466d733 | 133609062550958894 | UNKNOWN | 3156 | none | 3157 | STOP_LOSS_ON_FILL_LOSS | 3156,3157 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 14 | 21:18:18.741Z | 22:18:19 | GBP_USD | BUY | 1 | swing_breakout | UNKNOWN | cid-b2db42bf9263435983665c6b4df3b4ea | 133609063062752598 | UNKNOWN | 3158 | none | 3159 | STOP_LOSS_ON_FILL_LOSS | 3158,3159 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 15 | 21:19:19.918Z | 22:19:20 | GBP_USD | BUY | 1 | swing_trend | UNKNOWN | cid-8bde28710212487b9d9df455a32fe8a8 | 115594664809570849 | UNKNOWN | 3160 | none | 3161 | STOP_LOSS_ON_FILL_LOSS | 3160,3161 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 16 | 21:25:26.872Z | 22:25:27 | GBP_USD | BUY | 1 | swing_mean_reversion | UNKNOWN | cid-57588c279fc2440d8f4c24abd12c09e2 | 151623463369195024 | UNKNOWN | 3172 | none | 3173 | STOP_LOSS_ON_FILL_LOSS | 3172,3173 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 17 | 21:29:31.216Z | 22:29:31 | GBP_USD | BUY | 1 | swing_mean_reversion | UNKNOWN | cid-4fc845893cd149e4b6d7590920e95fac | 97580268867465531 | UNKNOWN | 3174 | none | 3175 | STOP_LOSS_ON_FILL_LOSS | 3174,3175 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 18 | 21:38:41.245Z | 22:38:41 | AUD_USD | BUY | 3 | swing_trend | UNKNOWN | cid-ba84f573b35b4a16a5b91ff3012bb632 | 97580271174761099 | UNKNOWN | 3186 | none | 3187 | STOP_LOSS_ON_FILL_LOSS | 3186,3187 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |
| 19 | 21:40:43.579Z | 22:40:44 | AUD_USD | BUY | 3 | swing_breakout | UNKNOWN | cid-3c886c582acb4550b413eb2f08c125bb | 97580271686586787 | UNKNOWN | 3188 | none | 3189 | STOP_LOSS_ON_FILL_LOSS | 3188,3189 | none | FAILED/CANCELLED | MARKET_ORDER+CANCEL only | none | B | HIGH |

Attached SL/TP on the MARKET_ORDER (broker, **PROVEN**):

| # | SL | TP |
|---|---|---|
| 1 | 1.33478 | 1.33615 |
| 2 | 157.379 | 157.233 |
| 3 | 1.33478 | 1.33615 |
| 4 | 0.71182 | 0.71261 |
| 5 | 157.379 | 157.233 |
| 6 | 0.71182 | 0.71261 |
| 7 | 0.82032 | 0.81905 |
| 8 | 0.82025 | 0.81898 |
| 9 | 1.33492 | 1.33628 |
| 10 | 1.40634 | 1.40506 |
| 11 | 1.40642 | 1.40514 |
| 12 | 1.33492 | 1.33631 |
| 13 | 1.33492 | 1.33631 |
| 14 | 1.33495 | 1.33634 |
| 15 | 1.33499 | 1.33638 |
| 16 | 1.33419 | 1.33564 |
| 17 | 1.33426 | 1.33571 |
| 18 | 0.71174 | 0.71261 |
| 19 | 0.71172 | 0.71263 |

Orientation of submitted levels vs side is internally consistent (BUY SL < TP; SELL TP < SL). Signal mids from `exec_orders`: GBP 1.3347 / 1.33448 / 1.33462 / 1.33427; JPY 157.37; AUD 0.71173 / 0.71148 / 0.71166; CHF 0.82065; CAD 1.4063.

## 10. Actual OANDA cancellation/rejection reasons

All 19 share one official reason:

| Reason | Count |
|---|---|
| STOP_LOSS_ON_FILL_LOSS | 19 |
| LOSING_TAKE_PROFIT | 0 |
| TAKE_PROFIT_ON_FILL_LOSS | 0 |
| other | 0 |

Not inferred from missing fill. Taken from `ORDER_CANCEL.reason` on the broker ledger.

## 11. Broker-state creation check

Created: MARKET_ORDER transaction + ORDER_CANCEL transaction for every event (**PROVEN**).

Not created: trade, fill, residual working order, position, attached SL/TP (**PROVEN** by transaction chain + current OpenPositions/OrdersPending).

`BROKER STATE CREATED DESPITE LOCAL FAILURE: SOME` = history entries exist; no live broker exposure from these 19.

## 12. Ghost broker-position check

OpenPositions at pull: GBP_USD long 1 unit, trade 3183, SL 3185 / TP 3184 pending. That is the **successful** 21:35:37Z fill (`cid-4ddd3a933d47430aa4af478ebeef0267`), not a failed cid.

No RECONCILE CONFLICT / IMPORT / ORDER IMPORT in the 2-hour Docker window. No unexpected broker trade IDs tied to the 19 cids. No later broker exit for a trade that lacked a normal local `[OPEN]`.

GHOST BROKER POSITIONS: 0

## 13. Ghost local-position check

Failed path does not call `finalize_order_fill` or emit `[OPEN]`. `exec_orders` are CANCELLED with `filled_units` null. `trades` has no rows for these cids. No local live open was created.

GHOST LOCAL POSITIONS: 0

Expected safe behaviour (no confirmed fill → no broker-backed local open) is what occurred.

## 14. Retry / idempotency check

- One MARKET_ORDER per cid
- One unique requestID per event
- `evaluate` still has a single `execute_oanda_market_open`
- No second OrderCreate for a failed cid

BLIND ORDERCREATE RETRIES OBSERVED: NO  
DUPLICATE BROKER FILLS OBSERVED: NO

The intended “no blind retry after ambiguous write” held. These writes were not ambiguous: the 201 body existed and contained a cancel, which the parser discarded.

## 15. Reconciliation behaviour

After each cancel the account had no new position in that instrument from that write. The next cycle could legally emit a **new** cid for the same symbol. That is not a conflicting reopen of an unknown live trade.

EUR_USD 3118 was already open before the cluster and closed at 21:30:32Z via PositionCloseout (3176/3177) — unrelated.

RECONCILIATION SAFETY ADEQUATE: YES for these 19 (no residual broker trade to import, no local ghost to remove).

The general timeout-after-write gap was **not exercised**. Do not treat this audit as proof that ambiguous transport is safe.

## 16. Temporal clustering

| Metric | Value |
|---|---|
| First | 2026-09-22T21:06:04Z / 22:06:04 local |
| Last | 2026-09-22T21:40:43Z / 22:40:44 local |
| Duration | 34 minutes 39 seconds |
| Per minute | 1 or 2 (cycle cadence; two symbols in the same evaluate pass) |
| Per symbol | GBP_USD 9, AUD_USD 4, USD_JPY 2, USD_CHF 2, USD_CAD 2 |
| Per side | BUY 13, SELL 6 |

Not one symbol, not one strategy, not one horizon proxy. Not a total API outage. Clustered on a ~1-minute evaluate loop while OANDA cancelled each FOK open for the same SL-on-fill reason.

## 17. Successful-fill comparison

Verified from primary logs + OANDA + `exec_orders`:

| When | Symbol | Fill tx | Local |
|---|---|---|---|
| Before cluster | USD_JPY 20:52:51Z | 3124 | `[OPEN]` |
| During | USD_JPY 21:21:22Z / 22:21 | 3163 | `[OPEN]` |
| During | USD_JPY 21:23:24Z / 22:23 | 3169 | `[OPEN]` |
| During | GBP_USD 21:35:37Z / 22:35 | 3183 | `[OPEN]` |
| After last fail | USD_JPY 21:41:44Z / 22:41 | 3191 | `[OPEN]` |

Failures and successes are interleaved. **Inference, not proof:** not a total OANDA outage, not a persistent account lock, not globally malformed SL/TP construction. The same path can fill when the broker accepts the on-fill SL.

Successful GBP 3183 fill-based geometry: fill 1.33461, SL 1.33413, TP 1.33557 → R = 2.00 (**PROVEN**). Same intended 2R as the post-deploy geometry fix.

## 18. Entry-geometry relationship

These 19 are exactly the historical reject class `STOP_LOSS_ON_FILL_LOSS`, now observed **after** executable-price geometry (BUY=ask, SELL=bid) is in production.

That does **not** mean the geometry path was skipped: OrderCreate included `stopLossOnFill` / `takeProfitOnFill` with internally oriented prices. The broker still judged that attaching that SL would immediately close the new trade at a loss.

PricingInfo → OrderCreate race: possible, but bid/ask at GET time were not persisted. **HYPOTHESIS**, not proven: risk distance vs live spread / SL trigger side (BUY SL vs bid, SELL SL vs ask, `triggerMode=TOP_OF_BOOK`) can make an ask/bid-anchored SL immediately executable. No priceBound was set on these MARKET_ORDERs.

Do not add a price bound, spread filter, or retry from this audit.

## 19. Diagnostic / observability assessment

`OANDA response missing orderFillTransaction` is an **OBSERVABILITY GAP**.

The 201 body (reconstructed from the ledger) contained the information needed to classify the outcome: `orderCreateTransaction`, `orderCancelTransaction.reason=STOP_LOSS_ON_FILL_LOSS`, related IDs, client ID, request ID. The parser only tested for `orderFillTransaction` and threw.

CURRENT ERROR MESSAGE ADEQUATE: NO

A future diagnostic should preserve HTTP status, request ID, client ID, create/cancel/fill IDs, and cancel/reject reason. Not implemented here.

## 20. Root-cause classification

PRIMARY: **B. GENUINE BROKER REJECTIONS, LOCAL MESSAGE TOO GENERIC**

Secondary (not a second independent cause of the 19 outcomes): the parser treats a documented 201 create-then-cancel as a generic failure (**A** / handling gap). No successful fill was misclassified (**C=0**). No transport failure (**D=0**). Entry-geometry race/spread may explain *why* the broker chose STOP_LOSS_ON_FILL_LOSS (**E** = HYPOTHESIS only).

Counts:

| Class | N |
|---|---|
| DEFINITIVE_BROKER_REJECTION (HTTP 400 / no MARKET_ORDER) | 0 |
| CREATE_THEN_CANCEL | 19 |
| SUCCESSFUL_FILL_MISCLASSIFIED | 0 |
| PENDING_ORDER_CREATED | 0 |
| AMBIGUOUS_WRITE_OUTCOME | 0 |
| RESPONSE_PARSING_DEFECT (fill present, parser missed it) | 0 |
| TRANSPORT_OR_PROTOCOL_FAILURE | 0 |
| OTHER | 0 |
| INSUFFICIENT_EVIDENCE | 0 |

ORDERCREATE RESPONSE HANDLING CORRECT: PARTIAL — fail-closed locally was right; reason classification was wrong.

## 21. Remaining uncertainties

- Raw HTTP JSON / status / headers were not stored.
- Bid, ask, spread, `request_duration_ms`, and executable_reference at PricingInfo time are UNKNOWN for the 19.
- Why OANDA judged each SL immediately in-the-money is not proven (spread vs sl_d vs tick movement).
- Horizon not on cancelled `exec_orders`.
- Ambiguous-write (timeout after POST accepted) was not observed.

## 22. Single highest-priority next action

**C. HANDLE ORDER-CANCEL RESPONSE EXPLICITLY**

Do not implement it in this task. Do not blindly retry OrderCreate. A later change should treat `orderCancelTransaction` as a first-class 201 outcome, log the official reason, and keep fail-closed / no local open / no retry.

The return of `STOP_LOSS_ON_FILL_LOSS` despite executable-price geometry is a follow-on investigation, not this next action, and must not become a silent retry or a new filter in this report.

PRODUCTION CHANGES ON THE RUNNING CONTAINER: NO  
OANDA WRITES: NO  
DOCKER REBUILT / RESTARTED: NO  
DEPLOYED: NO
