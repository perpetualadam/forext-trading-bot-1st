# POST-23:00 entry-geometry / diagnostics investigation

Manual-close attribution is taken as already audited (`live_24h_manual_close_attribution.md`). The four proven flatten manuals (2181, 2155, 2454, 2470) and EUR 2458 broker SL are not reopened. 24h class counts stay 47 / 7 / 45 / 6 / 0 / 0 / 2 / 10.

This note answers only the six post-deploy questions.

ENTRY GEOMETRY ACTIVE:
YES — on every filled post-deploy OrderCreate (2484, 2488, 2494, 2498)

STALE-QUOTE ROOT CAUSE:
OANDA PricingInfo `time` is last **price-update** time, not HTTP fetch time. `ENTRY_QUOTE_STALE_SEC=5` treats a just-fetched quiet-market quote as stale.

5s vs OANDA TIMESTAMP SEMANTICS:
MISMATCH

SUCCESS [ENTRY GEOMETRY] / [ENTRY FILL GEOMETRY] VISIBLE:
NO — `logger.info`; uvicorn lastResort is WARNING. Skips are visible because they are `logger.warning` + `alert()`.

DUPLICATE LINES:
LOGGING DUPLICATION ONLY (same event: `logger.warning` + `alert()`, and later evaluate cycles)

FORMER SL/TP-ON-FILL REJECTS AFTER 22:00:04Z:
0 (`LOSING_TAKE_PROFIT` / `STOP_LOSS_ON_FILL_LOSS` / `TAKE_PROFIT_ON_FILL_LOSS`)

OANDA WRITES THIS INVESTIGATION:
NO

DOCKER RESTARTED:
NO

---

## 1. Fresh executable entry geometry is active

Code path in the running image (`bot_loop` after `fill_path == "broker"`):

1. `fetch_fresh_entry_quote(symbol)` — dedicated PricingInfo GET
2. `resolve_live_entry_geometry(...)` — fail-closed; no M5 fallback
3. `stopLossOnFill` / `takeProfitOnFill` from `geom.sl` / `geom.tp`

Four fills after `BOT STARTED` 22:00:13Z. Postgres `exec_orders.metadata.executable_reference` equals the broker fill; submitted SL/TP are 2R around that reference, **not** around the logged M5 `mid`.

| trade | pair | side | M5 mid | executable_ref | fill | SL | TP | fill-based R | mid-based R (counterfactual) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2484 | GBP_USD | SELL | 1.33678 | **1.33686** | 1.33686 | 1.33732 | 1.33594 | **2.00** | 1.56 |
| 2488 | USD_JPY | SELL | 157.326 | **157.352** | 157.352 | 157.413 | 157.230 | **2.00** | 1.10 |
| 2494 | USD_JPY | SELL | 157.388 | **157.425** | 157.425 | 157.495 | 157.284 | **2.01** | 1.45 |
| 2498 | EUR_USD | SELL | 1.14636 | **1.14633** | 1.14633 | 1.14664 | 1.14571 | **2.00** | 2.21 |

If the old M5-mid attach were still live, fill-based R would not sit at 2.00 while `executable_reference == fill`. **PROVEN** the new attach ran on successful orders.

Local `CANCELLED` / `execution_failed` rows (EUR/CAD) are **pre-submit** fail-closed skips (`stale_quote`). They never reached OANDA. That is the intended gate, not a silent M5 fallback.

Later note (does not change the 24h table): USD_JPY 2494 was bot `PositionClose` at 22:15:31Z, PG `profit_protection`, hold 428s. That is after the “no PositionClose yet” snapshot in the attribution report.

---

## 2. Why fresh PricingInfo is classified stale

`_quote_usable` (`entry_geometry.py`):

```
age = now_wall_clock - quote.time_epoch
if age > ENTRY_QUOTE_STALE_SEC (5.0): return "stale_quote"
```

`quote.time_epoch` comes from PricingInfo `prices[].time` via `_to_epoch`. That field is the time of the **price**, not the response.

Live probe during this investigation (one GET, RTT ≈ 0.11s):

| instrument | quote age vs `time.time()` | 5s entry gate | 90s manage gate |
|---|---:|---|---|
| USD_JPY | 1.00s | pass | pass |
| AUD_USD | 1.56s | pass | pass |
| USD_CAD | 9.50s | **stale** | pass |
| GBP_USD | 9.83s | **stale** | pass |
| EUR_USD | 12.08s | **stale** | pass |
| USD_CHF | 46.86s | **stale** | pass |

The HTTP call was fresh. Four of six quotes still failed a 5s age check. That matches the Docker skips (`EUR_USD` / `USD_CAD` `reason=stale_quote`) and the later EUR fill at 22:09:24Z when that pair’s last tick was young enough.

This is **not** “PricingInfo failed” (`missing_quote`) and **not** clock skew (`quote_clock_skew` needs age < −2s).

---

## 3. The 5-second criterion vs OANDA timestamp semantics

OANDA v20 `Price.time` is when that price was **created / last updated**. In a quiet book it can sit still for tens of seconds while `GET /pricing` succeeds immediately.

`ENTRY_QUOTE_STALE_SEC=5` therefore measures **last-tick age**, not fetch freshness.

Manage-path `MANAGE_PRICE_STALE_SEC=90` uses the same `time` field and is consistent with that semantics. The entry gate is an order of magnitude tighter, so overnight / thin pairs fail closed even though the GET is current.

`_to_epoch` parsing (ns → µs, `Z` → UTC) is consistent with OANDA RFC3339. No parse bug is required to explain the skips.

---

## 4. Why `[ENTRY GEOMETRY]` / `[ENTRY FILL GEOMETRY]` are missing on successes

Those two lines are `logger.info` on `forex_bot.bot_loop`. The process is `uvicorn forex_bot.app:app`. Root logging has no INFO handler; Python lastResort is **WARNING**. Same class of invisibility as `[MANAGE PRICE]`.

What **is** visible:

| Line | Level / channel | Seen |
|---|---|---|
| `[ENTRY GEOMETRY SKIP] … stale_quote` | `logger.warning` + `alert()` | Yes |
| `[EXECUTION] BROKER_FILL` / `[OPEN]` | `alert()` | Yes |
| `[ENTRY GEOMETRY]` / `[ENTRY FILL GEOMETRY]` | `logger.info` only | No |

Success geometry **ran** (exec_orders + broker SL/TP prove it). It was not printed.

---

## 5. Duplicate diagnostic lines

Same event, two emitters:

| Event | Emitters |
|---|---|
| geometry skip | `logger.warning(format_entry_geometry_skip)` **and** `alert(msg)` |
| `[BROKER EXIT]` | `logger.warning(line)` **and** `alert(line)` |

`alert()` always `print`s `[INFO] <local datetime>: …`. `logger.warning` prints the bare tag. That is **duplication**, not a second OrderCreate or a second booking (ledger keys are idempotent).

Repeats minutes later (`23:06`, `23:07`, `23:08`) are **new evaluate cycles** (`TRADE_INTERVAL` 60s), not double-logging of one skip.

---

## 6. Former SL/TP-on-fill rejection reasons

Window: 22:00:04Z → lastTransactionID 2504.

| OANDA `ORDER_CANCEL.reason` | n |
|---|---:|
| `LINKED_TRADE_CLOSED` | 3 (linked SL/TP cancelled after 2488 SL and 2494 PositionClose) |
| `LOSING_TAKE_PROFIT` | **0** |
| `STOP_LOSS_ON_FILL_LOSS` | **0** |
| `TAKE_PROFIT_ON_FILL_LOSS` | **0** |

Local `exec_orders` CANCELLED rows are fail-closed **before** OrderCreate (`stale_quote` → `execution_failed`). They are not the old on-fill reject class.

---

## Implications (no implementation in this pass)

- Geometry attach is live and working on fills.
- The skip rate is dominated by a 5s last-tick gate that does not match PricingInfo fetch freshness.
- Observability of successful attach/fill-R is still INFO-filtered under uvicorn.
- Do not treat stale skips as “geometry not deployed.”
- Do not treat duplicate SKIP / BROKER EXIT prints as double broker actions.
