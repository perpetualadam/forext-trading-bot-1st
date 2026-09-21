IMPLEMENTATION STATUS:
PASS

ROOT CAUSE:
Live OrderCreate attached absolute SL/TP computed from the last M5 mid (`evaluate` `price`), so a later executable bid/ask fill inherited levels that no longer represented the intended ATR/2R distances. Decision-time R stayed 2.00; fill-based R collapsed (AUD_USD 2434 → 0.375R). The same stale-mid attach produced LOSING_TAKE_PROFIT / STOP_LOSS_ON_FILL_LOSS / TAKE_PROFIT_ON_FILL_LOSS (30 unfilled orders).

OLD ENTRY PRICE SOURCE:
Last completed M5 mid close (`raw["close"].iloc[-1]`), used as the absolute SL/TP anchor for `stopLossOnFill` / `takeProfitOnFill`.

NEW ENTRY PRICE SOURCE:
Dedicated OANDA PricingInfo GET immediately before OrderCreate. BUY reference = top-of-book **ask**. SELL reference = top-of-book **bid**. Distances unchanged (`sl_tp_distance_for_entry` + `TP_RISK_REWARD`).

BUY EXECUTABLE REFERENCE:
PricingInfo `asks[0].price` (market BUY pays the offer)

SELL EXECUTABLE REFERENCE:
PricingInfo `bids[0].price` (market SELL hits the bid)

BROKER-NATIVE DISTANCE ATTACHMENT:
SUPPORTED_NOT_USED (SL distance exists in the v20 schema; TP does not; current oandapyV20 helpers only accept `price` for both)

INTENDED R METHODOLOGY CHANGED:
NO

ATR STOP METHODOLOGY CHANGED:
NO

PROFIT PROTECTION CHANGED:
NO

POSITION MANAGEMENT PRICE CHANGED:
NO

BROKER EXIT ACCOUNTING CHANGED:
NO

PAPER/BACKTEST METHODOLOGY CHANGED:
NO

LIVE ORDER FAILS CLOSED WITHOUT FRESH QUOTE:
YES

AUD_USD 0.375R REGRESSION FIXED:
YES

LOSING_TAKE_PROFIT REGRESSION COVERED:
YES

STOP_LOSS_ON_FILL_LOSS REGRESSION COVERED:
YES

TAKE_PROFIT_ON_FILL_LOSS REGRESSION COVERED:
YES

BLIND ORDER RETRY INTRODUCED:
NO

FOCUSED TESTS:
89 passed / 0 failed (`test_entry_execution_geometry` 28 + live-management + broker-exit + execution-safety + reconcile)

FULL TEST SUITE:
519 passed / 0 failed / 0 skipped

DOCKER REBUILT:
NO

DOCKER RESTARTED:
NO

OANDA WRITES:
NO

DEPLOYED:
NO

---

## 1. Root-cause confirmation

The 24h forensic audit proved the 2R **formula** is correct at the M5 reference and wrong at the broker fill. Production `bot_loop.evaluate` did:

```
price = last M5 close
sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr)
broker_sl/tp = price ± sl_d / tp_d
OrderCreate(..., stopLossOnFill=broker_sl, takeProfitOnFill=broker_tp)
```

Local Position SL/TP were then recomputed from the **fill**. Broker attached levels stayed mid-anchored. AUD_USD 2434: mid 0.71198, SELL fill 0.71176, submitted SL/TP 0.71216/0.71161 → 0.375R.

This task only changes the **anchor** used for the submitted absolute prices on a live broker open.

## 2. Old live entry path

Callers of absolute SL/TP (unchanged except the live broker open block):

| Caller | Anchor | Changed? |
|---|---|---|
| `bot_loop.evaluate` live/`paper_broker` OrderCreate | **was M5 mid** | **Yes — executable ask/bid** |
| `bot_loop.evaluate` local Position after fill | fill ± distances | No |
| `bot_loop.evaluate` paper / window_paper / simulated | mid / sim fill ± distances | No |
| `backtest.py` | candle mid ± distances | No |
| `reconciliation` import fallback SL/TP | broker entry ± fallback distances | No |
| `live_manage` existing-position quotes | closeoutBid / closeoutAsk | No |
| `broker_exit` | TradeDetails / TransactionDetails | No |

## 3. New live entry path

Only when `open_fill_path == "broker"` (real OANDA OrderCreate: `live_broker` or `paper_broker` inside the live window):

```
signal M5 mid → side / ATR → sl_d, tp_d          # unchanged
reserve client_order_id
GET PricingInfo for this symbol                  # new, immediately before send
BUY ref = ask ; SELL ref = bid
round SL/TP with existing 5dp / JPY 3dp rules
require SL < ref < TP  (BUY)  or  TP < ref < SL (SELL)
[ENTRY GEOMETRY] log
OrderCreate once (no retry)
[ENTRY FILL GEOMETRY] log  (diagnostic actual_R vs fill)
local Position SL/TP still fill ± sl_d/tp_d      # paper-consistent; no post-fill broker rewrite
```

If the quote is missing, stale (>5s), untradeable, missing a time, missing the executable side, or rounding inverts orientation: **do not send**. Release the reserved client_order_id. Log `[ENTRY GEOMETRY SKIP]`. No M5 fallback.

## 4. OANDA executable-price semantics

Existing-position management uses **liquidation** prices:

- manage BUY (flatten long) → `closeoutBid`
- manage SELL (flatten short) → `closeoutAsk`

New entry is the **opposite** transaction:

- market BUY pays the offer → `asks[0].price`
- market SELL hits the bid → `bids[0].price`

AUD_USD 2434 filled at `0.71176`, which was the recorded bid, not `closeoutAsk` (`0.71251`). Using closeout prices for entry would re-introduce displacement. **PROVEN** from the fill `fullPrice` fields and standard v20 PricingInfo meaning.

## 5. Broker-native distance-order investigation

| Mechanism | SL | TP | Used? |
|---|---|---|---|
| Official v20 `StopLossDetails.distance` | Documented (price **or** distance) | n/a | No |
| Official v20 `TakeProfitDetails` | n/a | **price only** | — |
| oandapyV20 `StopLossDetails` | constructor is `price` only | — | Current client |
| oandapyV20 `TakeProfitDetails` | — | `price` only | Current client |
| `TrailingStopLossDetails.distance` | trailing, not fixed 2R TP | no | Unsuitable |

Verdict: **SUPPORTED_NOT_USED** for SL distance; **UNSUPPORTED** for TP distance. Atomic fill-relative SL **and** TP cannot be expressed in one OrderCreate with this client/API pair. A second Trade CRC write after fill would be a race and is forbidden here. Fresh PricingInfo + absolute prices is the chosen path.

## 6. Risk-distance preservation

`sl_tp_distance_for_entry` is untouched (`USE_ATR_STOPS`, `SL_ATR_MULT`, fallback pips, `MIN_STOP_DISTANCE_PRICE`). `TP_RISK_REWARD` remains `2.0`. `intended_tp_distance(sl_d) == sl_d * TP_RISK_REWARD`. No new multipliers, floors, or R filters.

## 7. Final SL/TP construction

```
BUY:  SL = round(ask - sl_d)   TP = round(ask + tp_d)
SELL: SL = round(bid + sl_d)   TP = round(bid - tp_d)
```

`tp_d` is whatever `sl_tp_distance_for_entry` already returned (normally `2 * sl_d`).

## 8. Precision / rounding

Reuses the existing convention (`JPY` → 3 decimals, else 5). No instrument-metadata fetch. After rounding, orientation is re-checked against the rounded executable reference. If a tick of rounding collapses SL/ref/TP, the order is skipped (fail closed), not sent inverted.

## 9. Freshness / fail-closed

| Rule | Value |
|---|---|
| Snapshot | New `fetch_pricing_snapshot([symbol])` — not the 60s cycle batch |
| Max age | `ENTRY_QUOTE_STALE_SEC = 5.0` |
| Missing quote / empty GET | skip |
| `time` absent | skip (cannot prove freshness) |
| Clock skew &lt; −2s | skip |
| `tradeable=false` | skip |
| Missing bid (SELL) or ask (BUY) | skip |
| Invalid distances | skip |
| Invalid orientation after rounding | skip |

Cycle-start `ManageQuote` objects are intentionally ignored for entry. Management still uses the batched snapshot with 90s stale tolerance — unchanged.

## 10. AUD_USD forensic regression

Old (M5-anchored) vs fill 0.71176 / SL 0.71216 / TP 0.71161 → fill R ≈ **0.375**. **PROVEN** in `test_aud_usd_forensic_old_r_and_new_geometry`.

New: same `sl_d=0.00018`, `tp_d=0.00036`, executable SELL = 0.71176 → SL 0.71194, TP 0.71140, expected R ≈ 2.00, fill-based R &gt; 1.8. Orientation `TP < bid < SL`.

## 11. Three OANDA rejection regressions

| Reason | Stale-mid setup | New geometry |
|---|---|---|
| LOSING_TAKE_PROFIT | SELL mid TP already above current bid | TP rebuilt below bid |
| STOP_LOSS_ON_FILL_LOSS | BUY mid SL already above current ask | SL rebuilt below ask |
| TAKE_PROFIT_ON_FILL_LOSS | BUY mid TP already below current ask | TP rebuilt above ask |

No catch-and-retry of OrderCreate. Prevention is pre-submit construction + orientation check.

## 12. Paper / simulation preservation

`live_broker_geometry_required(fill_path)` is true only for `"broker"`. Paper / window_paper / simulated / backtest still call `construct_absolute_sl_tp` against mid or the sim fill. `paper_broker` sends a real practice OrderCreate and therefore uses the same executable-price path.

## 13. Existing live-management preservation

`live_manage.py` not edited. Tests still assert BUY manage = closeoutBid, SELL manage = closeoutAsk, and that those differ from entry ask/bid. 1589 / 1597 / 1621 / 1629 suite included in the focused run and still passing.

## 14. Broker-exit-accounting preservation

`broker_exit.py`, `reconciliation.py` Case D, and `test_broker_exit_accounting.py` untouched and passing.

## 15. Logging added

```
[ENTRY GEOMETRY] symbol= side= signal_mid= executable_reference= price_source=OANDA_PRICING
  atr= risk_distance_pips= sl= tp= expected_r= spread_pips= quote_age_ms=
[ENTRY FILL GEOMETRY] symbol= side= reference= fill= fill_delta_pips= sl= tp=
  actual_risk_pips= actual_reward_pips= actual_r= broker_id= transaction_id=
[ENTRY GEOMETRY SKIP] symbol= side= reason= fail_closed=true (no broker OrderCreate; no M5 fallback)
```

No secrets. Fill-based `actual_r` is diagnostic only; attached SL/TP are not rewritten after fill.

## 16. Focused tests

`tests/test_entry_execution_geometry.py` covers A–V as specified (BUY/SELL anchor, AUD 0.375R, three reject geometries, missing/stale/malformed quote, rounding, JPY/non-JPY, orientation, paper/sim/mid vs broker, paper_broker, manage-price isolation, no retry, no R/spread filter). Plus existing live-management, broker-exit, execution-safety, and reconcile suites.

## 17. Full regression results

```
519 passed in 37.15s
```

0 failed, 0 skipped. Previous suite was 491; +28 are the new geometry tests.

## 18. Remaining limitations

- PricingInfo → OrderCreate → fill is still a race. This fix does **not** guarantee fill-based 2R.
- Wide spreads can still make the economic R poor even when orientation is valid. No spread filter was added.
- Local Position SL/TP remain fill-anchored (pre-existing). Broker attached levels are executable-anchored. Live SL/TP closes stay broker-authoritative (`broker_sl_tp_hit` False).
- **COUNTERFACTUAL** (not live P/L): using each historical fill as the executable side (SELL fill = bid, BUY fill = ask in this export), all **15** recorded &lt;1R fills and all **3** &lt;0.5R fills re-anchor to ≥1R / ≥0.5R with the same `sl_d`. The **30** rejects have no persisted bid/ask; they are prevented by construction when a fresh quote exists, but cannot be counted as observed preventions.
- Directional edge is unchanged. Do not treat this as a profitability fix.

## 19. Deployment recommendation

Repo only. Do **not** rebuild or restart Docker from this task. After a later authorized deploy, re-measure fill-based R, reject reasons, and SL/TP frequency on new live data before considering filters.

PRODUCTION CHANGES ON THE RUNNING CONTAINER: NO  
OANDA WRITES: NO  
DOCKER REBUILT / RESTARTED: NO  
DEPLOYED: NO
