IMPLEMENTATION STATUS:
PASS

TRIGGER-SIDE GUARD IMPLEMENTED:
YES

BUY RULE:
bid > SL

SELL RULE:
ask < SL

ZERO CLEARANCE:
SKIP

ADDITIONAL BUFFER:
NONE

SAME PRICING SNAPSHOT:
YES

ATR CHANGED:
NO

TP CHANGED:
NO

INTENDED 2R CHANGED:
NO

POSITION SIZING CHANGED:
NO

SPREAD FILTER ADDED:
NO

M5 FALLBACK ADDED:
NO

CLIENTPRICE.TIME REJECTION ADDED:
NO

ORDER CANCEL CLASSIFICATION:
YES

STOP_LOSS_ON_FILL_LOSS REASON PRESERVED:
YES

BLIND RETRY ADDED:
NO

19 HISTORICAL CANCEL CASES BLOCKED:
19/19

5 SUCCESSFUL CONTROLS ALLOWED:
5/5

FOCUSED TESTS:
120 passed / 0 failed / 0 skipped

FULL TEST SUITE:
580 passed / 0 failed / 0 skipped

PRODUCTION CODE CHANGED:
YES

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

READY FOR CONTROLLED DEPLOYMENT:
YES

## 1. Files changed

Production:

- `forex_bot/entry_geometry.py` — trigger-side clearance helpers; both-side book validation; skip after rounded SL
- `forex_bot/oanda_exec.py` — OrderCreate outcome classification and typed errors
- `forex_bot/bot_loop.py` — skip-before-OrderCreate; explicit cancel / outcome handling

Tests:

- `tests/test_execution_headroom.py` — new (44 tests)
- `tests/test_entry_execution_geometry.py` — existing successful-geometry books tightened so `sl_d > spread` (previously several fixtures had zero/negative clearance)

Reports:

- `reports/decision_quality/execution_headroom_implementation.md` (this file)

No `.env`, no database writes, no Docker rebuild/restart, no OANDA write endpoints.

## 2. Exact trigger-side implementation

`REQUIRED_SL_TRIGGER_CLEARANCE = 0.0`. No pip/spread/ATR buffer.

```
BUY:  trigger_side = bid
      trigger_clearance = bid - rounded_SL
      submit iff clearance > 0   (bid > SL)

SELL: trigger_side = ask
      trigger_clearance = rounded_SL - ask
      submit iff clearance > 0   (ask < SL)
```

Helpers: `classify_book_price`, `sl_trigger_side`, `sl_trigger_price`, `sl_trigger_clearance`, `has_sl_trigger_clearance`, `sl_trigger_clearance_skip_reason`.

Skip reason: `insufficient_sl_trigger_clearance`.

## 3. Where the guard occurs

Live broker path is unchanged except for the new check:

1. `try_begin_order_submission` (existing DB reserve)
2. one `fetch_entry_pricing` (existing dedicated PricingInfo GET)
3. `resolve_live_entry_geometry` on that quote
4. existing orientation / precision
5. **new** trigger-side check on the rounded SL
6. if skip → no OrderCreate
7. else exactly one `execute_oanda_market_open`

No work was added between a passing guard and OrderCreate except the existing geometry info log.

## 4. Same snapshot

Bid, ask, executable reference, SL/TP, and trigger clearance all come from the single `quote` passed into `resolve_live_entry_geometry`. `resolve` does not fetch pricing. `evaluate` calls `fetch_entry_pricing` once.

## 5. BUY behavior

Executable reference remains ask. Orientation still requires `SL < ask < TP`. Submission additionally requires `bid > SL`. A BUY that is valid versus ask but already through bid is skipped.

## 6. SELL behavior

Executable reference remains bid. Orientation still requires `TP < bid < SL`. Submission additionally requires `ask < SL`.

## 7. Zero-clearance behavior

`clearance <= 0` (including exact equality) → skip. `has_sl_trigger_clearance(0.0)` is False.

## 8. Rounding behavior

The guard uses the rounded SL that will be sent to OANDA, not the unrounded `ask − sl_d` / `bid + sl_d` relation. A fixture where raw clearance is positive and rounded clearance is zero skips.

## 9. Pricing failure behavior

Missing/NaN/infinite/zero/negative bid or ask → fail closed (`executable_*_missing` or `malformed_price`). PricingInfo failure / timeout / instrument missing unchanged. No M5 fallback. No reconstructed missing side.

## 10. OrderCreate outcome classifier

`classify_order_create_response` on an HTTP-successful body:

| Priority | Condition | Outcome |
|---|---|---|
| 1 | usable `orderFillTransaction.price` | FILLED |
| 2 | `orderCancelTransaction` present, no usable fill | CANCELLED |
| 3 | `orderRejectTransaction` | REJECTED |
| 4 | otherwise | MALFORMED_RESPONSE |

`classify_order_create_transport_error`:

- `V20Error` 400–499 except 408 → REJECTED
- timeout / connection / 408 / 5xx / other transport → AMBIGUOUS_TRANSPORT_OUTCOME

Fill wins if both fill and cancel were present (not observed in the 19).

## 11. CANCELLED behavior

Raises `OrderCreateCancelled` after one `api.request`. Logs `[ORDER CANCEL]` with cid, create_tx, cancel_tx, reason, related IDs. `bot_loop` marks the reserved order failed/cancelled and returns. No local position. No second OrderCreate. The generic `missing orderFillTransaction` string is not used on this path.

## 12. REJECTED behavior

`OrderCreateRejected` for `orderRejectTransaction` or client HTTP 4xx (except 408). Same fail-closed, no retry.

## 13. AMBIGUOUS_TRANSPORT_OUTCOME behavior

`OrderCreateAmbiguous` for timeout / connection / 5xx. Existing conservative handling: mark failed, `record_fill_failure`, no retry. Reconcile remains the recovery path.

## 14. MALFORMED_RESPONSE behavior

`OrderCreateMalformed` when the 201/body cannot be classified. No assumed “broker did nothing.” No retry.

## 15. Retry safety

`_place_market_order_open_sync` still contains exactly one `api.request`. Cancel / reject / malformed / ambiguous tests assert call count remains 1. `evaluate` still has one `execute_oanda_market_open` and no retry loop.

## 16. 19 historical cancellation regression cases

Fixtures use submitted SL/TP and the forensic M1 bid/ask book. All 19 have `clearance <= 0`, resolve to `insufficient_sl_trigger_clearance`, and `_may_submit` is False (OrderCreate would not be called).

## 17. 5 successful control regression cases

Same method. All 5 have `clearance > 0` and resolve allows submission. Intended R remains ~2.

## 18. Focused-test results

`tests/test_execution_headroom.py` + `tests/test_entry_execution_geometry.py` + `tests/test_execution_safety.py` + `tests/test_logic_fixes.py`:

**120 passed / 0 failed / 0 skipped**

(`test_execution_headroom.py` alone: 44 tests.)

## 19. Full-suite results

**580 passed / 0 failed / 0 skipped**

## 20. ATR / TP / 2R / sizing unchanged

`sl_tp_distance_for_entry` and `construct_absolute_sl_tp` are untouched. The guard does not rewrite SL/TP. Units are still computed before PricingInfo. Invalid clearance skips; it does not resize.

## 21. Paper / backtest unchanged

`live_broker_geometry_required` is still only `fill_path == "broker"`. Paper / window_paper / simulated / backtest still mid-anchor. Existing-position management still uses closeoutBid / closeoutAsk. Profit protection, broker-exit accounting, reconciliation, portfolio caps, and USD-direction guard were not edited.

## 22. Remaining limitations

The pre-submit guard eliminates orders already invalid at the PricingInfo snapshot.

It cannot guarantee that:

PricingInfo → validation → OrderCreate → OANDA processing

will see zero book movement. Future `STOP_LOSS_ON_FILL_LOSS` cancellations remain possible if the trigger side crosses SL after validation.

No speculative buffer was added. Current evidence still supports required clearance `> 0` only.

Live PricingInfo bid/ask are still not persisted on skip/cancel rows; the new skip log includes them when geometry exists.

## 23. Deployment readiness

All listed acceptance criteria hold. Ready for a separate controlled deployment task.

This task did not deploy, restart Docker, or call OANDA write endpoints.
