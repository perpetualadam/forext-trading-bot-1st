POSTDEPLOY VERDICT:
The deployed live-entry geometry path is present and active. Successful post-start OrderCreates (GBP 2484, JPY 2488, later 2494 and EUR 2498) attached SL/TP to `exec_orders.metadata.executable_reference`, not the M5 mid. Fill-based R on 2484 and 2488 is 2.00. `stale_quote` skips are fail-closed as designed: a dedicated PricingInfo GET is made, then `prices[].time` (“when the Price was created”) is compared to `time.time()` with `age > 5`. Official OANDA docs plus the `since` filter (“price has changed after”) show that field is last price-object creation / last change, not HTTP fetch time. A just-fetched quiet-market quote can be tens of seconds “old.” Fail-closed is correct; the 5s test is not a semantically valid fetch-freshness test. Success `[ENTRY GEOMETRY]` / `[ENTRY FILL GEOMETRY]` are `logger.info` and invisible under uvicorn lastResort WARNING. Duplicate SKIP / BROKER EXIT lines are logging-only. 2491 booked once. No post-deploy LOSING_TAKE_PROFIT / STOP_LOSS_ON_FILL_LOSS / TAKE_PROFIT_ON_FILL_LOSS. Old ~61s bug not re-audited (dedicated result: NO).

CONFIDENCE:
HIGH on path-active, 2484/2488 attach, official timestamp semantics, fail-closed, logging gap, 2491 once. MEDIUM on exact quote ages of historical skips (not persisted).

AUDIT WINDOW UTC:
2026-09-21T22:00:13Z (BOT STARTED) through 2026-09-21T22:26:47Z (container `date -u` at audit). Last inspected transaction id 2504.

DEPLOYED ENTRY GEOMETRY CODE PRESENT:
YES

DEPLOYED ENTRY GEOMETRY PATH ACTIVE:
YES

LIVE BUY ENTRY REFERENCE:
ASK

LIVE SELL ENTRY REFERENCE:
BID

GBP_USD 2484 FILL-BASED R:
2.00

USD_JPY 2488 FILL-BASED R:
2.00

GBP_USD 2484 NEW GEOMETRY PROVEN:
YES

USD_JPY 2488 NEW GEOMETRY PROVEN:
YES

ENTRY CANDIDATES REACHING GEOMETRY:
7

FRESH QUOTES ACCEPTED:
4

STALE QUOTES REJECTED:
3

MISSING QUOTES REJECTED:
0

MALFORMED QUOTES REJECTED:
0

ROUNDING/ORIENTATION REJECTED:
0

SUCCESSFUL ORDERCREATE:
4

BROKER ORDER REJECTIONS:
0

LOSING_TAKE_PROFIT POSTDEPLOY:
0

STOP_LOSS_ON_FILL_LOSS POSTDEPLOY:
0

TAKE_PROFIT_ON_FILL_LOSS POSTDEPLOY:
0

STALE QUOTE ROOT CAUSE:
OANDA ClientPrice.time is last Price-created / last price-change time, not GET time. `age = time.time() - parse(prices[].time)`; reject if `age > 5`. Quiet books fail closed on a fresh HTTP GET.

OANDA PRICING TIMESTAMP SEMANTICS:
B/C — official: “The date/time when the Price was created.” Endpoint `since`: only prices whose time is later (i.e. the price has changed after). Not HTTP response time. Response-level `time` is the next-poll cursor and is unused by this code.

5S FRESHNESS TEST SEMANTICALLY VALID:
NO

FAIL-CLOSED BEHAVIOUR WORKING:
YES

M5 FALLBACK ON LIVE ENTRY:
NO

ENTRY GEOMETRY LOGGING ACTIVE:
PARTIAL (`logger.info` not on Docker stdout)

ENTRY FILL GEOMETRY LOGGING ACTIVE:
PARTIAL (`logger.info` not on Docker stdout)

DUPLICATE LOGS ARE EXECUTION DUPLICATES:
NO

BROKER EXIT 2491 BOOKED ONCE:
YES

POSITION MANAGEMENT CHANGED BY ENTRY FIX:
NO

ATR METHODOLOGY CHANGED:
NO

INTENDED 2R METHODOLOGY CHANGED:
NO

PROFIT PROTECTION CHANGED:
NO

PAPER/BACKTEST METHODOLOGY CHANGED:
NO

OLD ONE-MINUTE BUG RECURRENCE:
NO
(already established by dedicated audit; not re-audited)

HIGHEST-PRIORITY NEXT ACTION:
B

PRODUCTION CODE CHANGED DURING THIS AUDIT:
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

---

## 1. Scope and safety constraints

Read-only production audit of post-23:00 live-entry geometry, PricingInfo freshness, stale skips, diagnostics, and on-fill reject recurrence.

Not done: code/`.env`/DB writes, Docker rebuild/restart/stop, OANDA order/close/SL-TP writes, threshold or strategy changes, 61s-bug redo, manual-close redo, directional research.

GET-only OANDA (`AccountDetails`, `TransactionIDRange`, `PricingInfo`) and Postgres `SELECT` / Docker inspect+logs / container `python -c` imports.

## 2. Authoritative deployment timeline

All times UTC unless marked BST.

| Event | UTC | Evidence |
|---|---|---|
| EUR 2458 broker SL | 21:58:46Z | `STOP_LOSS_ORDER` (not flatten) |
| JPY 2454 manual flatten | 21:59:34Z | `TRADE_CLOSE` — established |
| GBP 2470 manual flatten | 21:59:37Z | `TRADE_CLOSE` — established |
| Book flat | after 2470 | established |
| Container Created | 22:00:04.778Z | `docker inspect` |
| Started | 22:00:10.805Z | inspect |
| BOT STARTED | 22:00:13Z | log `23:00:13` BST, `exec=live_broker` |
| GBP 2484 open | 22:00:14.392Z | OANDA + `[OPEN]` |
| JPY 2488 open | 22:00:14.804Z | OANDA + `[OPEN]` |
| JPY 2488 SL | 22:06:29.529Z | tx 2491 `STOP_LOSS_ORDER` |
| EUR stale skip | 22:06:20.948Z | exec_orders CANCELLED + SKIP log 23:06:21 BST |
| CAD stale skip | 22:07:22.655Z | exec_orders + SKIP 23:07:22 BST |
| EUR stale skip | 22:08:23.293Z | exec_orders + SKIP 23:08:23 BST |
| JPY 2494 open | 22:08:23.870Z | fill |
| EUR 2498 open | 22:09:24.909Z | fill |
| JPY 2494 PP close | 22:15:31.667Z | `POSITION_CLOSEOUT`; log `BROKER_CLOSE` (PositionClose); hold 428s — **after** the earlier “no PositionClose yet” snapshot; does not change the 117-row 24h table |

Container clock at audit: `Mon Sep 21 22:26:47 UTC 2026` — no hour skew vs UTC.

## 3. Previously resolved findings not re-audited

- Old ~61s manage bug: dedicated result NO (`live_onemin_bug_recurrence_test.md`). Fast broker SL 2420/2430 are not recurrence.
- Manual flatten: 2181, 2155, 2454, 2470. EUR 2458 is broker SL. 24h classes 47/7/45/6/0/0/2/10. UNKNOWN 10 stay UNKNOWN.
- Pre-deploy M5-anchor defect and 30 on-fill rejects: accepted as historical context.

## 4. Deployed-code verification

`docker exec` import (not host files only):

| Check | Result |
|---|---|
| `/app/forex_bot/entry_geometry.py` | present (`inspect.getfile`) |
| `ENTRY_QUOTE_STALE_SEC` | 5.0 |
| `executable_entry_reference` BUY/SELL | ask / bid |
| `bot_loop` calls `fetch_fresh_entry_quote` + `resolve_live_entry_geometry` | yes |
| `live_manage.MANAGE_PRICE_STALE_SEC` | 90.0 |
| `closeout_manage_price` | closeout_bid / closeout_ask |
| `EXECUTION_MODE` in container | `live_broker` |
| `USE_ATR_STOPS` / `SL_ATR_MULT` | true / 2.0 |

**DEPLOYED ENTRY GEOMETRY CODE PRESENT: YES. PATH ACTIVE: YES.**

## 5. Live broker-entry path trace

Only when `open_fill_path(symbol) == "broker"` (after hybrid/risk/session gates and `try_begin_order_submission`):

1. Signal M5 last close → `price` / side / ATR → `sl_tp_distance_for_entry` (unchanged).
2. Dedicated `fetch_pricing_snapshot([symbol])` — not the cycle batch.
3. Fail-closed `_quote_usable` (missing / not tradeable / missing time / skew < −2s / `age > 5`).
4. BUY ref = ask; SELL ref = bid.
5. `SL/TP = ref ± distances`, 5dp / JPY 3dp, orientation check.
6. One `OrderCreate`. No M5 fallback. No blind retry.
7. Local Position still fill ± distances. Paper/sim never enter this block.

## 6. OANDA PricingInfo request path

`oanda_client.fetch_pricing_snapshot` → `GET /v3/accounts/{id}/pricing?instruments=…` → `ManageQuote.time_epoch = _to_epoch(p.get("time"))` i.e. **`prices[].time`**, not the response-level poll cursor `time`.

Entry does **not** reuse `state["pricing_snapshot"]`. Cycle refresh still exists for manage (90s).

## 7. BUY/SELL executable-price semantics

Official closeoutBid/Ask: “never used to open a new position.” Entry uses top-of-book ask/bid. Manage still uses closeoutBid (BUY flatten) / closeoutAsk (SELL flatten). **PROVEN** in deployed modules. Do not conflate.

## 8. GBP_USD 2484 reconstruction

| Field | Value | Evidence grade |
|---|---|---|
| Signal / open UTC | 22:00:14.392Z | OANDA fill time **PROVEN** |
| Side | SELL | **PROVEN** |
| Strategy / horizon | swing_trend / swing | `[OPEN]` **PROVEN** |
| M5 mid | 1.33678 | `[OPEN]` + exec_orders `mid` **PROVEN** |
| ATR | UNKNOWN | not logged |
| Risk distance price | 0.00046 (xref − computed from SL−xref) | **STRONG INFERENCE** from submitted SL and xref |
| Risk pips | 4.6 | **PROVEN** vs pip 0.0001 |
| PricingInfo GET timestamp | UNKNOWN | not persisted |
| Raw `prices[].time` | UNKNOWN | not persisted |
| bid / ask / spread / quote age | UNKNOWN | not persisted; do not invent from fill |
| Selected executable_reference | 1.33686 | exec_orders metadata **PROVEN** |
| Rounded SL / TP | 1.33732 / 1.33594 | OANDA `stopLossOnFill` / `takeProfitOnFill` **PROVEN** |
| Expected R vs xref | 2.00 | (1.33686−1.33594)/(1.33732−1.33686) **PROVEN** |
| Fill | 1.33686 | **PROVEN** |
| Fill vs xref | 0.00 | **PROVEN** |
| Fill-based risk / reward / R | 4.6 pips / 9.2 pips / **2.00** | **PROVEN** |

Why this is **new geometry**, not “R happened to be 2”:

- Deployed broker-open block is the only writer of `executable_reference` / `submitted_sl` / `submitted_tp`.
- xref **≠** mid (1.33686 vs 1.33678).
- Mid-anchored SL would be 1.33678+0.00046 = **1.33724**, not 1.33732.
- Deployed SELL reference is **bid** (code **PROVEN**). That the stored xref was that bid is **STRONG INFERENCE** (code path + SELL fill equals xref). Raw bid snapshot **UNKNOWN**.

Accepted ⇒ at resolve time `age ≤ 5` (boundary: `>` rejects). Exact age **UNKNOWN**.

## 9. USD_JPY 2488 reconstruction

| Field | Value | Grade |
|---|---|---|
| Open UTC | 22:00:14.804Z | **PROVEN** |
| Side | SELL | **PROVEN** |
| Strategy / horizon | trend / legacy | **PROVEN** |
| M5 mid | 157.326 | **PROVEN** |
| ATR | UNKNOWN | |
| Risk vs xref | 0.061 (6.1 pips) | **PROVEN** from SL−xref |
| xref | 157.352 | **PROVEN** |
| SL / TP | 157.413 / 157.230 | **PROVEN** |
| Expected R vs xref | 2.00 | **PROVEN** |
| Fill | 157.352 | **PROVEN** |
| Fill vs xref | 0 | **PROVEN** |
| Fill-based R | **2.00** | **PROVEN** |
| Bid/ask/age | UNKNOWN | |

Mid-anchored SL would be 157.326+0.061 = **157.387**, not 157.413. **NEW GEOMETRY PROVEN: YES.**

Later exit 2491: `STOP_LOSS_ORDER` at **157.413** = attached SL. Hold ~375s. Not PositionClose. **PROVEN.**

## 10. All post-deployment entry candidates

Counted only rows that reserved a `client_order_id` then hit `resolve_live_entry_geometry` (exec_orders created_at ≥ 22:00:13Z). Earlier gates (no signal, notional cap, etc.) are excluded.

| UTC | symbol | side | strategy | mid | result |
|---|---|---|---|---:|---|
| 22:00:14.239 | GBP_USD | SELL | swing_trend | 1.33678 | FRESH_QUOTE_ACCEPTED + ORDERCREATE_SUCCEEDED (2484) |
| 22:00:14.627 | USD_JPY | SELL | trend | 157.326 | FRESH_QUOTE_ACCEPTED + ORDERCREATE_SUCCEEDED (2488) |
| 22:06:20.948 | EUR_USD | SELL | swing_trend | 1.14636 | STALE_QUOTE_REJECTED |
| 22:07:22.655 | USD_CAD | BUY | swing_trend | 1.40338 | STALE_QUOTE_REJECTED |
| 22:08:23.293 | EUR_USD | SELL | swing_trend | 1.14636 | STALE_QUOTE_REJECTED |
| 22:08:23.710 | USD_JPY | SELL | swing_mean_reversion | 157.388 | FRESH_QUOTE_ACCEPTED + ORDERCREATE_SUCCEEDED (2494) |
| 22:09:24.750 | EUR_USD | SELL | swing_mean_reversion | 1.14636 | FRESH_QUOTE_ACCEPTED + ORDERCREATE_SUCCEEDED (2498) |

Totals: 7 geometry-stage; 4 accepted+filled; 3 stale; 0 missing/malformed/orientation; 0 broker on-fill rejects.

By symbol: EUR 1 accept / 2 stale; JPY 2/0; GBP 1/0; CAD 0/1; AUD 0; CHF 0.

Quote timestamp / age / bid / ask on skip rows: **UNKNOWN** (not stored). Horizon on skips: UNKNOWN in exec_orders (strategy only).

No further exec_orders after 22:09:24 through 22:26:47Z.

## 11. Stale-quote implementation trace

`_quote_usable` (`entry_geometry.py`):

| Item | Value |
|---|---|
| Field | `prices[i].time` → `ManageQuote.time_epoch` |
| Parse | `_to_epoch`: `Z`→`+00:00`, ns truncated to 6 frac digits, naive→UTC |
| Comparison clock | `time.time()` (Unix epoch; container `date -u` matches UTC) |
| Age | `now - time_epoch` |
| Threshold | `ENTRY_QUOTE_STALE_SEC = 5.0` |
| Boundary | **`age > 5` rejects**; `age == 5` accepts |
| Skew | `age < -2` → `quote_clock_skew` |

Checked and **not** found as the skip cause: UTC/local mix on the quote string; DST; failed `Z` parse (that would be `missing_quote_time`); reuse of cycle snapshot for entry; wrong instrument key (per-symbol GET); write-path delay after GET of many seconds (GET is immediately before resolve).

Rate-limiter / RTT (prior live GET ~0.11s) cannot turn a brand-new `time` into >5s. They can only add to an already-old `prices[].time`.

## 12. OANDA PricingInfo timestamp semantics

Official [Pricing Definitions](https://developer.oanda.com/rest-live-v20/pricing-df/): ClientPrice.`time` = **“The date/time when the Price was created.”**

Official [Pricing Endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/) `since`: *“Only prices … with a time later than this filter (**i.e. the price has changed after** the since time) will be provided.”*

Response body `time`: *“The DateTime value to use for the `since` parameter in the next poll.”* — poll cursor, **not** used by this bot.

Classification: **B** (instrument price last changed) **and C** (that Price object’s created time). **Not A** (HTTP response generated).

Live GET during the prior probe (RTT 0.11s): EUR age 12.1s, GBP 9.8s, CAD 9.5s, CHF 46.9s vs JPY 1.0s / AUD 1.6s — same HTTP, different `prices[].time`. **PROVEN** a fresh GET ≠ age≤5.

**5S FRESHNESS TEST SEMANTICALLY VALID: NO.** It tests last Price-created age, not whether the GET returned a currently executable book. Fail-closed on that test is still safer than M5 fallback.

## 13. EUR_USD stale skip (~23:06 BST)

| Field | Value |
|---|---|
| Evaluate UTC | 22:06:20.948Z (exec_orders created_at) / log 23:06:21.081 BST |
| Side | SELL |
| M5 mid | 1.14636 |
| Strategy | swing_trend |
| Raw quote time / age / bid / ask | UNKNOWN |
| OrderCreate | **NO** — local CANCELLED `execution_failed`; no OANDA CLIENT_ORDER at this time |
| M5 fallback | **NO** — skip text and no broker order |

Root cause: **OANDA_TIMESTAMP_SEMANTICS** (STRONG INFERENCE from code + official docs + live age probe). Exact age that night: UNKNOWN. Not TIMESTAMP_PARSE_ERROR / TIMEZONE_ERROR / CACHED_SNAPSHOT (entry uses a dedicated GET).

A later EUR SELL at 22:09:24Z **accepted** (2498) — same mid 1.14636 — shows the gate is last-tick age, not a permanent EUR block.

## 14. USD_CAD stale skip (~23:07 BST)

| Field | Value |
|---|---|
| Evaluate UTC | 22:07:22.655Z / log 23:07:22.780 BST |
| Side | BUY |
| M5 mid | 1.40338 |
| OrderCreate | **NO** |
| M5 fallback | **NO** |
| Quote fields | UNKNOWN |

Root cause: **OANDA_TIMESTAMP_SEMANTICS** (same as §13). Live probe CAD age 9.5s on a fresh GET is consistent, not a reconstruction of this event’s book.

## 15. Quote-age distribution

Historical skip ages: **UNKNOWN** (not logged). Cannot fill ≤1s … >60s buckets without inventing data.

Live one-GET probe (later, not those events): 2 instruments ≤2s, 3 in 5–30s, 1 in 30–60s. Illustrative only.

## 16. Fail-closed behaviour

Working as specified: stale → no OrderCreate, no M5 attach, reservation cancelled, `[ENTRY GEOMETRY SKIP]`. **EXPECTED SAFE BEHAVIOUR.** Separate from whether the 5s definition is the right usability test.

## 17. Post-deploy SL/TP rejection search

22:00:04Z–id 2504: `LOSING_TAKE_PROFIT` 0, `STOP_LOSS_ON_FILL_LOSS` 0, `TAKE_PROFIT_ON_FILL_LOSS` 0. Cancels are `LINKED_TRADE_CLOSED` only.

**NO RECURRENCE OBSERVED IN THIS POST-DEPLOYMENT SAMPLE.** Not a claim of permanent eradication.

## 18. ENTRY GEOMETRY diagnostic audit

Emitted as `logger.info(format_entry_geometry_line)` after accept. Process: `uvicorn forex_bot.app:app`. No `basicConfig`; lastResort = WARNING. Docker stdout has **zero** `[ENTRY GEOMETRY]` lines.

Metadata (`executable_reference`, submitted SL/TP) **is** in Postgres `exec_orders` for accepts. That is the retrievable success record.

**OBSERVABILITY GAP** on stdout. Path not missing.

## 19. ENTRY FILL GEOMETRY diagnostic audit

Same: `logger.info` only. Not on stdout. Fill + xref + SL/TP recoverable from OANDA + exec_orders.

**OBSERVABILITY GAP.**

## 20. Duplicate-log investigation

| Line | Emitters |
|---|---|
| `[ENTRY GEOMETRY SKIP]` | `logger.warning` (bare) **and** `alert()` → print `[INFO] <BST>: …` |
| `[BROKER EXIT]` | `logger.warning(line)` **and** `alert(line)` |

`alert()` is print+Telegram, not a second OrderCreate. 60s later SKIPs are new cycles.

**LOGGING_DUPLICATION_ONLY.**

## 21. Broker-exit 2491 regression

| Check | Result |
|---|---|
| Symbol / trade / tx | USD_JPY / 2488 / 2491 |
| OANDA reason | `STOP_LOSS_ORDER` |
| Entry / exit / PL | 157.352 / 157.413 / −0.0006 |
| Ledger rows | **1** `(2491, 2488)` |
| `trades` rows | **1** `broker_stop_loss` |
| PositionClose | **NO** |
| `record_completed_trade(..., apply_equity=False)` | no NAV apply on this path |
| Local | reconcile `[RECONCILE BROKER EXIT CONFIRMED]` |

Entry-geometry work did not interfere. **BOOKED ONCE: YES.**

## 22. Existing-position management regression

Deployed `live_manage`: closeoutBid / closeoutAsk, 90s, no M5 fallback, `broker_sl_tp_hit` False. PP / MFE seeding not imported by `entry_geometry` except `pip_size` / `_to_epoch`. 2494 PP close at 428s is the new manage path (`OANDA_CURRENT`), not the 61s bug.

**POSITION MANAGEMENT CHANGED BY ENTRY FIX: NO.**

## 23. Paper / simulated / backtest isolation

`resolve_live_entry_geometry` only inside `fill_path == "broker"`. Paper / window_paper / simulated use the mid/sim block. `live_broker_geometry_required` is `fill_path == "broker"` only. `paper_broker` would use the same broker-safe attach because it sends OrderCreate — consistent. Backtest untouched.

## 24. Findings by classification

| Finding | Class |
|---|---|
| Executable ask/bid attach live on fills; 2484/2488 fill-R 2.00 | EXPECTED SAFE BEHAVIOUR / production fix working |
| stale_quote fail-closed, no M5, no OrderCreate | EXPECTED SAFE BEHAVIOUR |
| 5s test uses Price-created time, not fetch time | EXECUTION ROBUSTNESS ISSUE |
| Success geometry logs invisible | OBSERVABILITY GAP |
| Duplicate SKIP / BROKER EXIT prints | OBSERVABILITY GAP (not double execution) |
| Zero on-fill rejects in this sample | EXPECTED SAFE BEHAVIOUR (sample-limited) |
| Directional edge | STRATEGY RESEARCH QUESTION — out of scope |
| Exact skip quote ages | INSUFFICIENT EVIDENCE |

## 25. Remaining uncertainties

- Raw bid/ask/`prices[].time` for 2484/2488/skips (not persisted).
- ATR at those decisions.
- Whether a 6s-old last tick is economically stale enough to refuse — research, not proven here.
- On-fill reject eradication beyond this window.

## 26. Single highest-priority next action

**B. PRICING TIMESTAMP SEMANTICS FIX JUSTIFIED.**

Fail-closed is right. The criterion `now - prices[].time ≤ 5s` is not a valid test of “this GET returned a usable executable book.” Official OANDA semantics plus a same-GET multi-pair age spread prove it. Do not implement in this audit. Observability (E) is real but secondary: successes are already reconstructable from exec_orders + OANDA.
