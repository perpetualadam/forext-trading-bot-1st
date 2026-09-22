IMPLEMENTATION STATUS:
PASS

ROOT CAUSE:
Live entry treated OANDA ClientPrice `prices[].time` as the age of the PricingInfo HTTP fetch. Official semantics: that field is when the Price object was created / last changed. A just-completed PricingInfo GET during a quiet book can therefore return a last-change timestamp older than five seconds. The fail-closed skip (`stale_quote`) was mechanically correct and did not fall back to M5, but it was keyed on the wrong freshness concept.

OLD FRESHNESS RULE:
Reject when `now - parse(ClientPrice.time) > ENTRY_QUOTE_STALE_SEC` (5.0). Also reject missing `ClientPrice.time` and clock skew `< -2s`.

OLD RULE SEMANTICALLY VALID:
NO

NEW FRESHNESS MODEL:
A dedicated PricingInfo GET must succeed immediately before OrderCreate. The response must contain the requested instrument and a finite, positive executable reference (BUY=ask, SELL=bid). Orientation after broker rounding must remain valid. ClientPrice.time is retained as last-change diagnostics only. No extra request-duration reject is applied: the existing OANDA connect/read timeout already bounds a hung GET.

CLIENTPRICE.TIME NOW INTERPRETED AS:
PRICE_LAST_CHANGE_TIME

CLIENTPRICE.TIME ALONE CAN REJECT ENTRY:
NO

FRESH PRICING GET STILL REQUIRED:
YES

FAILED PRICING GET FAILS CLOSED:
YES

MISSING INSTRUMENT FAILS CLOSED:
YES

MALFORMED EXECUTABLE PRICE FAILS CLOSED:
YES

M5 FALLBACK INTRODUCED:
NO

BUY ENTRY REFERENCE:
ASK

SELL ENTRY REFERENCE:
BID

ATR METHODOLOGY CHANGED:
NO

INTENDED 2R CHANGED:
NO

POSITION MANAGEMENT CHANGED:
NO

PROFIT PROTECTION CHANGED:
NO

BROKER EXIT ACCOUNTING CHANGED:
NO

PAPER/BACKTEST CHANGED:
NO

BLIND ORDER RETRY INTRODUCED:
NO

FOCUSED TESTS:
118 passed, 0 failed (`tests/test_entry_execution_geometry.py`, `tests/test_live_position_management.py`, `tests/test_broker_exit_accounting.py`, `tests/test_execution_safety.py`, `tests/test_reconcile_conflict.py`, `tests/test_oanda_v20_congruence.py`)

FULL TEST SUITE:
536 passed, 0 failed, 0 skipped (`python -m pytest -q --tb=line`, 32.85s)

DOCKER REBUILT:
NO

DOCKER RESTARTED:
NO

OANDA WRITES:
NO

DEPLOYED:
NO

## 1. Proven root cause

Post-deploy audit (`live_entry_geometry_postdeploy_audit.md`) established:

- Executable-price geometry is working (GBP_USD 2484 and USD_JPY 2488 fill-based R = 2.00).
- BUY attaches to ask, SELL attaches to bid.
- `LOSING_TAKE_PROFIT` / `STOP_LOSS_ON_FILL_LOSS` / `TAKE_PROFIT_ON_FILL_LOSS` post-deploy = 0.
- Several candidates were skipped with `reason=stale_quote` after a dedicated PricingInfo GET.

The skip compared wall-clock now to `prices[].time`. Official OANDA documentation describes ClientPrice.time as “the date/time when the Price was created.” The PricingInfo `since` filter returns only prices whose time is later (i.e. the price has changed after that instant). That is last-change time, not HTTP-response time.

Therefore a quiet-market book can produce a fresh GET whose last tick is tens of seconds old. The 5-second test answered the wrong question.

## 2. Old semantics (traced path, pre-edit)

| Step | Location | Behaviour |
|---|---|---|
| PricingInfo GET begins | `fetch_fresh_entry_quote` → `oanda_client.fetch_pricing_snapshot([symbol])` | Dedicated GET immediately before OrderCreate. Cycle snapshot not used. |
| HTTP call | `fetch_pricing_snapshot` → `_oanda_request` → `pricing.PricingInfo` | Connect/read timeout `(15s, 15s)` default. Exceptions swallowed; empty dict returned. |
| ClientPrice.time parsed | `fetch_pricing_snapshot` → `_to_epoch(p.get("time"))` → `ManageQuote.time_epoch` | Last-change timestamp stored. |
| quote_age calculated | `quote_age_sec(quote, now)` = `now - time_epoch` | Treated as fetch freshness. |
| stale_quote emitted | `_quote_usable` if `age > 5` | Also `missing_quote_time`, `quote_clock_skew`. |
| bid/ask selected | `executable_entry_reference` | BUY=ask, SELL=bid. |
| OrderCreate | `bot_loop.evaluate` → `execute_oanda_market_open` | Only after geometry resolve succeeds. Single request. No M5 fallback. |

Manage-path callers of `fetch_pricing_snapshot` were unchanged (still swallow errors). Existing-position management still uses closeoutBid / closeoutAsk with its own 90s stale window.

## 3. Correct OANDA timestamp interpretation

| Field | Meaning | Use now |
|---|---|---|
| HTTP GET completion | This bot just obtained a PricingInfo response | **Primary live-entry safety** |
| Request duration (`perf_counter`) | How long that GET took | Observability only |
| `ClientPrice.time` | When OANDA last created / changed that Price | Diagnostic `price_time` / `price_last_change_age_ms` |
| Response-level `time` | Next-poll cursor | Unused (unchanged) |

`5S FRESHNESS TEST SEMANTICALLY VALID: NO` remains the established finding. This task does not enlarge the 5-second threshold; it stops using last-change age as a reject.

## 4. New freshness model

Separated explicitly:

**A. FETCH FRESHNESS** — did this bot just successfully obtain a PricingInfo response for the instrument immediately before OrderCreate?

**B. PRICE LAST-CHANGE AGE** — how long ago did OANDA say this instrument price last changed?

Live-entry safety is A plus executable-price validity:

1. Dedicated `fetch_entry_pricing(symbol)` immediately before OrderCreate.
2. `raise_on_error=True` so a failed GET is not collapsed into an empty snapshot.
3. Fail closed on GET failure, timeout, missing instrument, missing/malformed executable bid or ask, non-tradeable, invalid distances, or orientation collapse after rounding.
4. No cache. No reuse of the cycle-start snapshot. No M5 mid fallback.
5. ClientPrice.time is never an independent reject.

`ENTRY_QUOTE_STALE_SEC = 5.0` remains as a historical constant and is **not** a reject gate. `resolve_live_entry_geometry(..., max_age_sec=...)` ignores that argument.

## 5. Request timing

Measured with a monotonic clock (`time.perf_counter`):

- `request_started_mono`
- `response_received_mono`
- `request_duration_ms`
- `fetch_age_ms` (monotonic age of this fetch object at resolve)

Existing project bound:

- `OANDA_CONNECT_TIMEOUT_SEC` default 15.0
- `OANDA_HTTP_TIMEOUT_SEC` default 15.0
- Applied on every REST call via `request_params.timeout`

HTTP timeout is not quote freshness. A GET that completes inside the configured timeout and returns a valid executable quote is usable even if `ClientPrice.time` is old.

No additional request-duration reject was added. There is no evidence for a second 5-second (or other invented) wall-time cap on top of the existing timeout/failure handling. Reason `pricing_request_too_slow` is **not** implemented.

If the GET raises a timeout-class error, the skip reason is `pricing_timeout`. Other GET failures are `pricing_request_failed`. Existing `_oanda_request` transient retries are unchanged transport resilience, not a new OrderCreate retry.

## 6. ClientPrice.time diagnostic treatment

Retained. Renamed in logs and geometry fields so they cannot be read as HTTP-fetch age:

| Old / misleading | New |
|---|---|
| `quote_age_ms` (`now - ClientPrice.time`) | `price_last_change_age_ms` |
| (none) | `request_duration_ms` |
| (none) | `fetch_age_ms` |
| (none) | `price_time` (RFC3339 from `time_epoch`) |

Missing `ClientPrice.time` no longer rejects. The last-change fields are then `n/a` / `None`.

## 7. Fail-closed cases

| Condition | Reason |
|---|---|
| PricingInfo GET exception (non-timeout) | `pricing_request_failed` |
| PricingInfo GET timeout | `pricing_timeout` |
| GET succeeded, instrument absent | `instrument_missing` |
| SELL and bid missing | `executable_bid_missing` |
| BUY and ask missing | `executable_ask_missing` |
| Non-finite / non-numeric / ≤0 executable price | `malformed_price` |
| `tradeable=false` | `not_tradeable` |
| Rounding collapses SL/ref/TP | `invalid_orientation_after_rounding` |
| Invalid risk/reward distances | `invalid_risk_distance` / `invalid_reward_distance` |

`stale_quote`, `missing_quote_time`, and `quote_clock_skew` are no longer emitted by live-entry geometry.

A successfully fetched valid ClientPrice is **not** rejected solely because `ClientPrice.time` is more than five seconds old.

## 8. Entry geometry preservation

Unchanged construction:

```
BUY:  SL = round(ask - sl_d)   TP = round(ask + tp_d)
SELL: SL = round(bid + sl_d)   TP = round(bid - tp_d)
```

`sl_tp_distance_for_entry`, ATR path, `TP_RISK_REWARD = 2.0`, and precision (JPY 3dp, else 5dp) are untouched.

Regression proofs:

- GBP_USD 2484-style SELL: mid 1.33678, executable 1.33686, SL 1.33732, TP 1.33594, expected/fill R ≈ 2.00. Mid-anchored SL would be 1.33724.
- USD_JPY 2488-style SELL: mid 157.326, executable 157.352, SL 157.413, TP 157.230, expected/fill R ≈ 2.00. Mid-anchored SL would be 157.387.
- AUD_USD stale-M5 0.375R forensic: still re-anchors to the executable bid.
- LOSING_TAKE_PROFIT / STOP_LOSS_ON_FILL_LOSS / TAKE_PROFIT_ON_FILL_LOSS orientation tests preserved.

## 9. Logging semantics

`[ENTRY GEOMETRY]` now includes:

`signal_mid` `executable_reference` `price_source` `bid` `ask` `spread_pips` `request_duration_ms` `price_time` `price_last_change_age_ms` `risk_distance_pips` `sl` `tp` `expected_r`

`[ENTRY FILL GEOMETRY]` unchanged in meaning: `fill` `fill_delta_pips` `actual_risk_pips` `actual_reward_pips` `actual_r`.

`[ENTRY GEOMETRY SKIP]` still fail-closed, no M5 fallback. Reasons are the precise codes above.

No secrets. Duplicate `logger.warning` + `alert()` on skip is pre-existing logging duplication and was not refactored.

## 10. Regression tests

`tests/test_entry_execution_geometry.py` now proves:

| ID | Claim | Result |
|---|---|---|
| A | Fresh GET + ClientPrice.time 1s old → ACCEPT | pass |
| B | Fresh GET + last-change 10s + valid bid/ask → ACCEPT | pass |
| C | Fresh GET + last-change 60s is not rejected on time alone | pass |
| D | Failed PricingInfo GET → `pricing_request_failed` | pass |
| E | Timeout → `pricing_timeout` | pass |
| F | Instrument missing → `instrument_missing` | pass |
| G | Bid missing for SELL → `executable_bid_missing` | pass |
| H | Ask missing for BUY → `executable_ask_missing` | pass |
| I | Non-finite executable price → `malformed_price` | pass |
| J | Zero/negative executable price → `malformed_price` | pass |
| K | Rounding breaks orientation → fail closed | pass |
| L | BUY uses ask | pass |
| M | SELL uses bid | pass |
| N | GBP_USD 2484-style ≈ 2R | pass |
| O | USD_JPY 2488-style ≈ 2R | pass |
| P | AUD_USD stale-M5 still executable-anchored | pass |
| Q | No M5 fallback on live broker entry | pass |
| R–U | paper / window_paper / simulated / backtest unchanged | pass |
| V | paper_broker / practice still require executable geometry (`fill_path==broker`) | pass |
| W | Existing-position management BUY closeoutBid / SELL closeoutAsk | pass |
| X | Broker-exit accounting suite unchanged and passing | pass |
| Y | Single OrderCreate; no blind retry | pass |
| Z | ClientPrice.time diagnostic only | pass |

Also preserved: the three historical on-fill reject geometries, no R/spread filter, no cooldown.

## 11. Full-suite result

```
536 passed in 32.85s
```

0 failed, 0 skipped. Previous geometry-implementation suite was 519; the increment is the freshness-semantics cases.

Files touched for this fix: `forex_bot/entry_geometry.py`, `forex_bot/oanda_client.py` (`raise_on_error` on PricingInfo GET only), `forex_bot/bot_loop.py` (use `fetch_entry_pricing`), `tests/test_entry_execution_geometry.py`. Not touched: ATR/trading distances, RL, profit protection, `live_manage.py`, `broker_exit.py`, reconciliation Case D, `.env`, Docker.

## 12. Remaining limitations

- This does **not** eliminate movement between PricingInfo → OrderCreate → actual fill. That race still exists.
- The executable-price geometry fix remains the mitigation for the stale-M5 reject class.
- This task only corrects treating `ClientPrice.time` as HTTP-response freshness.
- Wide spreads can still make economic R poor. No spread/R filter was added.
- `_oanda_request` may retry transient transport errors; wall time for a successful GET can therefore exceed one 15s read timeout. That is existing client behaviour, not a new freshness rule.
- Success `[ENTRY GEOMETRY]` / `[ENTRY FILL GEOMETRY]` remain `logger.info` and can still be invisible under uvicorn lastResort WARNING. Not redesigned here.

## 13. Controlled deployment recommendation

Repo only. Do **not** rebuild or restart Docker from this task.

When a later authorized deploy is approved:

1. Confirm skip reasons: quiet books should no longer emit `stale_quote`.
2. Confirm failed GET / missing instrument / malformed bid/ask still fail closed with the new reason codes.
3. Re-measure fill-based R on new opens (2484/2488-style attach must remain).
4. Confirm `LOSING_TAKE_PROFIT` / `STOP_LOSS_ON_FILL_LOSS` / `TAKE_PROFIT_ON_FILL_LOSS` stay at zero.
5. Confirm no M5 fallback and no extra OrderCreate.

PRODUCTION CHANGES ON THE RUNNING CONTAINER: NO  
OANDA WRITES: NO  
DOCKER REBUILT / RESTARTED: NO  
DEPLOYED: NO
