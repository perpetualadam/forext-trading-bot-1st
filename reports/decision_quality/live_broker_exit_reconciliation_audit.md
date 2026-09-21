BROKER EXIT ACCOUNTING VERDICT:
INCORRECT

CONFIDENCE:
HIGH

2125 CLOSE REASON:
STOP_LOSS

2133 CLOSE REASON:
STOP_LOSS

2137 CLOSE REASON:
STOP_LOSS

2161 CLOSE REASON:
STOP_LOSS

BOT POSITIONCLOSE INVOLVED:
NO

TRUE BROKER EXIT PRICE RECORDED LOCALLY:
NO

TRUE BROKER REALIZED PNL RECORDED LOCALLY:
NO

BROKER EXIT REASON RECORDED LOCALLY:
NO

PERFORMANCE STATISTICS ACCURATE FOR BROKER SL/TP EXITS:
NO

MANAGE PRICE PATH ACTIVE:
YES

LIVE BUY PRICE SOURCE:
OANDA PricingInfo closeoutBid (OANDA_CURRENT)

LIVE SELL PRICE SOURCE:
OANDA PricingInfo closeoutAsk (OANDA_CURRENT)

M5 FALLBACK POSSIBLE:
NO

OLD ONE-MINUTE BUG STILL POSSIBLE:
NO

PRODUCTION CHANGES MADE:
NO

---

## 1. Executive summary

All four named broker trades were **OANDA attached stop-loss fills**, not bot `PositionClose`, not take-profit, not profit-protection, and not weekend flatten.

Proven from OANDA `TradeDetails` + `TransactionDetails` (read-only):

| broker_id | symbol | close reason | hold |
|-----------|--------|--------------|------|
| 2125 | GBP_USD | `ORDER_FILL.reason=STOP_LOSS_ORDER` tx 2140 | 9m 18s |
| 2133 | USD_CHF | `ORDER_FILL.reason=STOP_LOSS_ORDER` tx 2146 | 10m 28s |
| 2137 | USD_JPY | `ORDER_FILL.reason=STOP_LOSS_ORDER` tx 2152 | 17m 02s |
| 2161 | USD_CAD | `ORDER_FILL.reason=STOP_LOSS_ORDER` tx 2164 | 6m 24s |

That is **not** the old ~61-second stale-M5 / overlapping-MFE `PositionClose` bug. Holds are minutes, not one candle cycle, and the closing transaction type is the attached SL order.

Local accounting of those exits is **wrong / missing**:

- Reconciliation Case D (`RECONCILE_ACTION=auto_fix`) saw OpenPositions flat, then `close_local_position(..., reason="reconcile_fix_broker_flat")`.
- That only pops the in-memory slot.
- It does **not** call `execute_trade`, `log_trade_pg`, `analytics.log_trade`, `snapshot_from_position`, or `update_equity`.
- Postgres `trades` has **no rows** for these four closes. Last trade row is `2026-09-21 09:37:19` — before 2125 opened.
- `exec_orders` has FILLED **opens** only.

So when OANDA closes via attached SL/TP, reconciliation **does not** import the true broker exit transaction or realized P&L.

`[MANAGE PRICE]` is implemented and should fire every evaluate cycle on broker-backed locals. It is `logger.info` on `forex_bot.bot_loop`. The live container is started as `uvicorn forex_bot.app:app` (not `main.py`), so root logging has **no handler** and Python `lastResort` is **WARNING**. INFO is discarded. Absence in Docker stdout does **not** mean the pricing path did not run.

Live BUY/SELL management prices remain `closeoutBid` / `closeoutAsk`. There is no M5 fallback for live SL/TP or profit protection.

---

## 2. Evidence table for broker IDs 2125 / 2133 / 2137 / 2161

Times: user/local clock is Europe/London BST (`TZ`). Docker timestamps are UTC. BST = UTC+1.

| Field | 2125 | 2133 | 2137 | 2161 |
|-------|------|------|------|------|
| **Classification** | STOP_LOSS | STOP_LOSS | STOP_LOSS | STOP_LOSS |
| **Evidence class** | proven fact (OANDA tx) | proven fact | proven fact | proven fact |
| symbol | GBP_USD | USD_CHF | USD_JPY | USD_CAD |
| direction | BUY | BUY | BUY | BUY |
| units | 1 | 2 | 2 | 2 |
| strategy (open alert) | swing_breakout | swing_mean_reversion | scalp | swing_breakout |
| client_order_id | cid-165e826a8d14449bbef404da3d6f75e3 | cid-2738f5f307bd476f9002a066e3cd7e67 | cid-a58bcbe3b9cd4c2792d4bcfc85c51922 | cid-d82658f4eedb454aa84cf14c0006de43 |
| broker trade/order-fill id | 2125 | 2133 | 2137 | 2161 |
| entry time UTC | 2026-09-21T09:40:20.862Z | 2026-09-21T09:45:27.053Z | 2026-09-21T09:46:28.039Z | 2026-09-21T10:36:16.251Z |
| entry time BST | 10:40:20 | 10:45:27 | 10:46:28 | 11:36:16 |
| entry / trade.price | 1.33863 | 0.82328 | 157.281 | 1.40233 |
| local logged SL / TP | 1.33801 / 1.33987 | 0.82281 / 0.82423 | 157.20140 / 157.44020 | 1.40190 / 1.40319 |
| OANDA SL order id / price / state | 2127 / 1.33796 / FILLED | 2135 / 0.82277 / FILLED | 2139 / 157.214 / FILLED | 2163 / 1.40178 / FILLED |
| OANDA TP order id / price / state | 2126 / 1.33982 / CANCELLED | 2134 / 0.82419 / CANCELLED | 2138 / 157.453 / CANCELLED | 2162 / 1.40307 / CANCELLED |
| broker close time UTC | 2026-09-21T09:49:38.776Z | 2026-09-21T09:55:54.829Z | 2026-09-21T10:03:30.465Z | 2026-09-21T10:42:40.128Z |
| hold | 9m 18s | 10m 28s | 17m 02s | 6m 24s |
| actual broker exit price | 1.33794 | 0.82274 | 157.213 | 1.40178 |
| realizedPL (account CCY, GBP) | -0.0005 | -0.0010 | -0.0007 | -0.0006 |
| closing transaction ID | 2140 | 2146 | 2152 | 2164 |
| closing tx type / reason | ORDER_FILL / STOP_LOSS_ORDER | ORDER_FILL / STOP_LOSS_ORDER | ORDER_FILL / STOP_LOSS_ORDER | ORDER_FILL / STOP_LOSS_ORDER |
| units closed | -1 (full) | -2 (full) | -2 (full) | -2 (full) |
| local RECONCILE MISSING UTC | 09:50:23 | 09:56:25 | 10:04:26 | 10:43:36 |
| lag, broker close → reconcile drop | ~45s | ~30s | ~56s | ~56s |
| bot BROKER_CLOSE / PositionClose | none visible; none expected | same | same | same |
| Postgres trade row | **absent** | **absent** | **absent** | **absent** |
| analytics / equity-from-trades | **not recorded** | **not recorded** | **not recorded** | **not recorded** |

**Proven fact:** attached SL filled; attached TP cancelled; full trade closed; realized P&L and exit price exist on the broker.

**Proven fact:** local SL/TP printed at open are not identical to the attached OANDA SL/TP prices (JPY SL 157.20140 local vs 157.214 broker). Close prices match the **broker** SL fills, not the local printed SL.

**Unknown:** why OANDA attached SL prices differ from the bot-logged SL (spread/precision/`stopLossOnFill` rounding vs minimum distance). Not required to classify the close.

**Strong inference:** the ~30–56s reconcile lag is one `RECONCILE_INTERVAL_SEC=60` cycle after OpenPositions went flat.

---

## 3. Exact reconciliation code path

When OANDA attached SL/TP, does reconciliation currently import the TRUE broker exit transaction and realized P&L?

**NO**

### Call chain (deployed)

1. `forex_bot/app.py` `lifespan` starts `reconciliation_loop()` as its own asyncio task (not inside `run_bot`).
2. `reconciliation_loop` → `run_reconciliation_once()` → `reconcile_positions_log_only()`.
3. `reconcile_positions_log_only` (`forex_bot/reconciliation.py`):
   - `fetch_broker_positions_detail()` — GET OpenPositions. Instruments with `abs(net) < 1e-9` are omitted.
   - `_remember_broker_snapshot`
   - `_apply_position_convergence(broker_detail, pending)`
4. `_apply_position_convergence` Case D, only if `_may_auto_fix_local()`:
   - live env: `EXECUTION_MODE=live_broker`, `RECONCILE_ACTION=auto_fix` → **yes**
   - for each local `is_broker_backed` position whose instrument is missing or net≈0:
     - `posmod.close_local_position(sym, reason="reconcile_fix_broker_flat")`
     - `logger.warning("[RECONCILE BROKER POSITION MISSING] Closed local broker-backed %s | fix=%s/%s", ...)`

### What `close_local_position` does

`forex_bot/positions.py`:

- `positions.pop(symbol, None)`
- `logger.info("[RECONCILE FIX] Closed local position %s (%s)", symbol, reason)`
- returns the removed `Position`

It is **not** `bot_loop.evaluate` → `execute_trade` → `close_position`.

### What is **not** done

| Action | Called? |
|--------|---------|
| `execute_trade` | no |
| `oanda_exec.execute_oanda_market_close` / `PositionClose` | no |
| `log_trade_pg` / Postgres `trades` INSERT | no |
| `trade_diagnostics.snapshot_from_position` | no |
| `analytics.log_trade` | no |
| `update_equity(pnl)` | no |
| `rl_agent.update` | no |
| `fetch_trade_details_sync` on the vanished trade | no |
| TransactionDetails / transactions/sinceid | no helper exists |

`fetch_trade_details_sync` **is** used on Case C **import** (open broker trade IDs from OpenPositions). When the instrument is already flat, OpenPositions has no `tradeIDs`, so the closed trade is never looked up.

### Reconciliation mode

- `RECONCILE_ACTION=auto_fix` (container)
- `RECONCILE_INTERVAL_SEC=60`
- `RECONCILE_ADJUST_UNITS=false`
- `reconcile_fixes_total` on `/system` was **6** after this session (the four named IDs plus a later USD_CHF and a later USD_CAD of the same pattern)

### Direct answer

**When OANDA closes a position through attached SL/TP, does reconciliation currently import the TRUE broker exit transaction and realized P&L?**

**NO.** It deletes the local slot and logs a generic missing-position warning.

---

## 4. Broker transaction evidence

Read-only queries used **existing** `fetch_trade_details_sync` plus one-off `oandapyV20.endpoints.transactions.TransactionDetails` (library already installed; **no helper added to the repo**). No writes.

### 2125 GBP_USD

- Trade state `CLOSED`, `averageClosePrice=1.33794`, `realizedPL=-0.0005`
- SL 2127 FILLED @ 1.33796; TP 2126 CANCELLED
- Tx 2140: `type=ORDER_FILL` `reason=STOP_LOSS_ORDER` `price=1.33794` `pl=-0.0005` `units=-1` `orderID=2127`
- `tradesClosed[0].tradeID=2125`

### 2133 USD_CHF

- `averageClosePrice=0.82274`, `realizedPL=-0.0010`
- SL 2135 FILLED @ 0.82277; TP 2134 CANCELLED
- Tx 2146: `STOP_LOSS_ORDER` `price=0.82274` `pl=-0.0010` `units=-2`

### 2137 USD_JPY

- `averageClosePrice=157.213`, `realizedPL=-0.0007`
- SL 2139 FILLED @ 157.214; TP 2138 CANCELLED
- Tx 2152: `STOP_LOSS_ORDER` `price=157.213` `pl=-0.0007` `units=-2`

### 2161 USD_CAD

- `averageClosePrice=1.40178`, `realizedPL=-0.0006`
- SL 2163 FILLED @ 1.40178; TP 2162 CANCELLED
- Tx 2164: `STOP_LOSS_ORDER` `price=1.40178` `pl=-0.0006` `units=-2`

**Not inferred from disappearance.** Reason comes from `ORDER_FILL.reason`.

OANDA reason vocabulary that would distinguish future cases:

| `reason` | Classify as |
|----------|-------------|
| `STOP_LOSS_ORDER` | STOP_LOSS |
| `TAKE_PROFIT_ORDER` | TAKE_PROFIT |
| `MARKET_ORDER` / `MARKET_ORDER_TRADE_CLOSE` / `MARKET_ORDER_POSITION_CLOSEOUT` | BOT_PROFIT_PROTECTION or WEEKEND_FLATTEN or MANUAL — need `orderID` / client extensions / who placed the market close |
| other | BROKER/OTHER |

These four are unambiguously `STOP_LOSS_ORDER`.

---

## 5. Local database / accounting evidence

### Postgres `trades`

```
COUNT = 1329
MAX(time) = 2026-09-21 09:37:19.852267
```

No row with entry 1.33863 / 0.82328 / 157.281 / 1.40233 after 09:40 UTC.

`log_trade_pg` only runs from `execute_trade`. Reconcile never calls it.

### Postgres `exec_orders`

Opens are present (FILLED, `broker_order_id` 2125/2133/2137/2161). No close/fill-exit rows. The table models entry orders, not SL fills.

### Postgres `reconcile_metadata`

Persists last run success/mismatch counts only. No per-trade close attribution.

### In-memory after drop

`close_local_position` forgets entry, SL, TP, `broker_order_id`, MFE, diagnostics. The next evaluate can open a **new** live trade on the same symbol (observed: GBP_USD 2143 at 09:52:34 UTC after 2125 was dropped).

### Container restart context

`forexttradingbot1st-bot-1` created **2026-09-21 10:40:11 BST**. 2125 opened 9 seconds later. In-process `analytics.trades` starts empty on restart. Even bot-closed trades from the previous process are gone from RAM (they remain in Postgres if `execute_trade` logged them). These four never reached Postgres.

---

## 6. Performance-statistics impact

| Surface | Source | Broker SL/TP exit effect |
|---------|--------|--------------------------|
| Postgres `trades` | `log_trade_pg` via `execute_trade` | **Missing trade** |
| `diagnostics.exit_reason` / `exit_price` / closed_at | diagnostics snapshot at `execute_trade` | **Missing** |
| `analytics.trades` / win rate / win count | `analytics.log_trade(pnl)` | **Not appended** — four losses omitted |
| Sharpe inputs | `analytics.sharpe()` = mean/std of `analytics.trades` | **Biased** (fewer observations; losses omitted) |
| `analytics.drawdown()` | `BASE_BALANCE + cumsum(trades)` | **Understated** vs true closed-trade path |
| Telegram / dashboard sharpe/winrate | same analytics object | **Wrong** after restart + missing closes |
| `current_equity()` / BOT STARTED equity | `state.broker_nav` from AccountSummary.NAV | **Approximately correct** (broker NAV) |
| `update_equity(pnl)` | only `execute_trade` | **Not called**; next NAV overwrite still tracks broker |
| Docker `Account NAV: 97.30 GBP` | `portfolio_exposure` via `alert()`/`print` | **Too coarse** (2 dp). `/system` NAV was 97.2959. Four P&Ls sum to **-0.0028 GBP** and do not change the printed 97.30 |

**Defect, quantified:**

- Four completed broker trades totaling **GBP −0.0028** realized P&L never became closed-trade rows.
- Win/loss count, win rate, Sharpe-from-trades, and analytics drawdown omit them.
- Displayed **NAV equity** still follows OANDA (not missing the cash), so a user watching NAV can think P&L is “in equity” while trade history / win rate say the trades never existed.
- After a process restart, analytics is empty anyway; Postgres is the durable ledger — and it also missed them.

A broker-side close **can disappear from local trade state without being represented as a completed trade.** That is the accounting defect.

---

## 7. OANDA transaction semantics

### Smallest reliable existing read-only method

Already in tree: `forex_bot.oanda_exec.fetch_trade_details_sync(trade_id)`  
`GET /v3/accounts/{id}/trades/{tradeSpecifier}`

Works on **CLOSED** trades. For these four it returned `state`, `price`, `averageClosePrice`, `realizedPL`, `openTime`, `closeTime`, `closingTransactionIDs`, SL/TP order id/price/state.

That is enough for price, P&L, timestamps, and a **strong** SL vs TP hint (`stopLossOrder.state=FILLED` + `takeProfitOrder.state=CANCELLED`).

To **prove** reason (required by this audit’s bar): one more GET that is **not** wrapped in-repo:

`GET /v3/accounts/{id}/transactions/{transactionID}`  
`oandapyV20.endpoints.transactions.TransactionDetails`

Fields that resolved these four:

- `type` (`ORDER_FILL`)
- `reason` (`STOP_LOSS_ORDER`)
- `id`, `time`, `instrument`, `units`, `price`, `pl`, `orderID`
- `tradesClosed[].tradeID`, `units`, `realizedPL`, `price`

Also sufficient, not used here: `GET .../transactions/sinceid` or `idrange` filtered by instrument/time.

### Would OpenPositions have been enough?

**No.** After close it simply omits the instrument. No reason, price, or P&L.

---

## 8. Race / partial-close analysis

### Observed sequence (matches the asked N / N+1 race)

```
cycle N:   local broker-backed pos exists; OpenPositions has the instrument
between:   attached SL ORDER_FILL
cycle N+1: OpenPositions omits instrument
           reconciliation Case D: BROKER POSITION MISSING → pop local
           evaluate: pos is gone → may open a new trade
```

Reconcile and `run_bot` are **concurrent tasks**. Reconcile does **not** run inside `evaluate`. A close can be dropped before the next manage cycle.

### Can reconciliation retrieve the close transaction before deleting the local position?

**Yes, safely, with the ID it already has.** Local `Position.broker_order_id` / `broker_trade_ids` is the open fill/trade id (2125, …). `fetch_trade_details_sync` returned CLOSED details immediately after the fact in this audit (minutes to hours later). OANDA closed-trade visibility was not a problem.

**Strong inference:** the same GET would have worked in the Case D branch before `pop`.

Races to design around (not implemented):

| Race | Risk |
|------|------|
| Transaction not yet visible | Low here; if it happens, retry next reconcile cycle and **do not** pop until attributed, or pop but keep a pending-attribution record |
| OpenPositions already flat, local still open | This is the current Case D — safe to read TradeDetails first |
| PricingInfo snapshot | Irrelevant to close attribution |
| Multiple reconcile cycles | Today: first cycle pops; later cycles see nothing. If attribution is added, need an idempotency key (`closingTransactionIDs[0]`) so P&L is not double-counted |
| Retry / timeout | Fetch fail today still pops (no P&L). Fail-closed would be: do not pop if TradeDetails fails |
| Duplicate accounting | If evaluate also `PositionClose`s (PP/weekend) **and** Case D later runs, bot path records the trade; Case D would no-op because local is already gone. Inverse (broker SL first, then bot close) is what we saw: Case D only, no row |
| Manual close | Same Case D hole; reason would be a market/closeout fill, not SL |
| Partial reduction | See below |

### Partial close / netting

OANDA is **per-account / per-instrument netting** plus **per-trade IDs**.

This bot:

- One local slot per symbol (`positions` dict).
- Opens use `positionFill=OPEN_ONLY`.
- `RECONCILE_ADJUST_UNITS` is **false** in the live container, so Case D does not shrink a local row to a remaining net; it only drops when broker net≈0.
- Does **not** assume multiple simultaneous trades on one instrument.

**Proven fact:** these four were **full** single-trade closes (`initialUnits` == closed units; `currentUnits=0`; one `closingTransactionID` each). Mapping “instrument missing on OpenPositions” → “that one local trade is gone” was correct **this time**.

**Do not assume that always.** If two trades existed on one instrument, OpenPositions flat means the **net** is zero, not “one TradeDetails id explains the whole P&L.” Future attribution should iterate `broker_trade_ids` (comma-separated) and each `closingTransactionIDs[]`, not one instrument → one tx.

---

## 9. `[MANAGE PRICE]` logging explanation

### Implementation

- Formatter: `forex_bot/live_manage.py` `format_manage_price_line`
- Emitter: `forex_bot/bot_loop.py` `evaluate`, **every** broker-backed open-position cycle, `logger.info(...)`
- Logger: `logging.getLogger("forex_bot.bot_loop")` (module logger)
- Level: **INFO**
- Not gated on `POSITION_LOG` (that only gates `[POSITION]`)
- Not only exceptional cycles
- `[CLOSE DECISION]` is also `logger.info` and only on an actual bot close path

### Why Docker stdout has zero `[MANAGE PRICE]` lines

**Proven fact** inside the running container:

```
root_level 30
root_handlers 0
bot_loop effective level 30
lastResort: StreamHandler stderr WARNING (30)
```

Dockerfile `CMD` is `uvicorn forex_bot.app:app ...`. That does **not** run `main.py` `logging.basicConfig(INFO)`. Uvicorn attaches handlers to `uvicorn*` loggers only. Application INFO has no handler; Python lastResort is WARNING.

What **does** reach stdout:

- `alert()` → `print(...)` (OPEN, BROKER_FILL, Account NAV, Telegram)
- `logger.warning` (RECONCILE BROKER POSITION MISSING)

`[MANAGE PRICE]`, `[POSITION]`, `[ORDER CLOSE]`, `[PERFORMANCE]` are INFO → **silent**.

**Absence in captured Docker stdout does not mean the pricing path did not run.** It means the diagnostic is in the wrong sink / level for this process entrypoint.

`POSITION_LOG=1` cannot help until INFO is actually handled.

---

## 10. PricingInfo path verification

Deployed container imports `forex_bot.live_manage` (`PRICE_SOURCE_OANDA_CURRENT`, `broker_sl_tp_hit` → False).

`run_bot` (`bot_loop.py`):

```
fetch_account_summary()
_refresh_pricing_snapshot()    # one batched GET
for s in Config.SYMBOLS:
    evaluate(s)
sleep(TRADE_INTERVAL)          # default 60; TRADE_INTERVAL unset in container
```

`_refresh_pricing_snapshot` → `fetch_pricing_snapshot(Config.SYMBOLS)` → `GET /v3/accounts/{id}/pricing?instruments=EUR_USD,GBP_USD,...` **once per cycle**, then `set_pricing_snapshot`.

Not per-symbol PricingInfo. Not per-position. Failure → empty dict + `logger.exception` (would be ERROR/visible). No `pricing snapshot failed` in this session’s logs.

`evaluate` for `is_broker_backed(pos)`:

- `resolve_broker_manage_price(quote, direction)`
- BUY → `closeout_bid`; SELL → `closeout_ask`
- stale `> 90s` / missing / non-tradeable → `(None, UNAVAILABLE)`
- **no M5 close used as manage price**
- if `manage_price is None`: skip `apply_profit_protection`; force `protect_hit=False`
- `sl_tp_hit = broker_sl_tp_hit(pos)` → **always False**

Paper/backtest still use candle close (`PRICE_SOURCE_PAPER_CANDLE`).

**MANAGE PRICE PATH ACTIVE: YES** — deployed code + `evaluate` kept running (NAV every ~60s; new opens after these closes; `/system` `last_bot_cycle_utc` current). Stdout cannot show the line; code/tests prove the price source.

---

## 11. Old-bug regression verification

Checked against deployed source + `tests/test_live_position_management.py` (passed). No historical backtest rerun.

| Invariant | Status |
|-----------|--------|
| Live open `max_profit_pips=0` | **yes** — `open_position(..., max_profit_pips=0.0)` |
| Live open `profit_protection_seeded=True` | **yes** — `fill_path == "broker"` |
| `seed_position_mfe` returns `"already"` and does not import overlapping-bar MFE | **yes** |
| Live reconstruct uses `include_partial_entry_bar=False` | **yes** — evaluate + `raise_mfe_from_post_entry_ohlcv` |
| Partial/pre-entry candle excluded | **yes** — `candle_vs_fill` + tests 1589/1597/1621 |
| Stale M5 cannot fire live SL/TP | **yes** — `broker_sl_tp_hit` always False |
| Live PP current pips from closeout manage price | **yes** — only when quote available |
| No M5 fallback when PricingInfo missing | **yes** for SL/TP and PP |
| These four were not 61s bot closes | **yes** — 6–17 min, `STOP_LOSS_ORDER` |

`OLD ONE-MINUTE BUG STILL POSSIBLE: NO` for live broker-backed SL/TP and the overlapping-MFE PP seed.

Residual (not this incident, Monday, not SL):

- Weekend flatten can still `PositionClose` and, if the quote is missing, the **logged** exit print uses leftover M5 `price`. The fill would still be a broker market close, not a fake SL.
- Paper/simulated still candle-SL/TP by design.

---

## 12. Smallest recommended future fix (do not implement)

Do **not** change live management price logic. The hole is **Case D accounting**.

Before `close_local_position` in `_apply_position_convergence` Case D:

1. Read `pos.broker_order_id` / `broker_trade_ids`.
2. `fetch_trade_details_sync(trade_id)` (already exists).
3. If `closingTransactionIDs`, GET `TransactionDetails` (new thin read wrapper).
4. Map `reason` → `STOP_LOSS` / `TAKE_PROFIT` / `MANUAL` / `OTHER`.
5. Persist a completed trade with broker `averageClosePrice` / `realizedPL` / `closeTime` / tx id — **without** `PositionClose`.
6. Idempotency on `closingTransactionIDs[0]` so a later cycle cannot double-book.
7. If TradeDetails fails: **do not** pretend the trade completed; keep or quarantine the local row and retry.

Ideal logs (not implemented):

```
[BROKER EXIT] symbol=GBP_USD broker_id=2125 reason=STOP_LOSS
entry=1.33863 exit=1.33794 units=1 realized_pl=-0.0005
transaction_id=2140 closed_at=2026-09-21T09:49:38Z source=OANDA_TRANSACTION

[RECONCILE BROKER EXIT CONFIRMED] GBP_USD broker_id=2125 reason=STOP_LOSS
```

Keep `[RECONCILE BROKER POSITION MISSING]` only when the close cannot be attributed.

Also: attach a root INFO handler in the uvicorn entrypoint (or emit `[MANAGE PRICE]` via `alert()`/`print`) so Docker stdout matches the design. Logging-only; not required to fix P&L.

---

## 13. Tests / checks performed

Isolated, no orders, no Docker rebuild/restart, no `.env` edits, no DB writes, no backtests:

- `pytest tests/test_live_position_management.py tests/test_reconcile_conflict.py tests/test_execution_safety.py` → **48 passed**
- `test_case_d_auto_fix_drops_broker_backed_when_broker_flat` confirms pop-only Case D
- `test_closeout_side_buy_vs_sell`, `test_missing_or_stale_quote_is_unavailable`, `test_1629_stale_m5_cannot_trip_fill_based_sl`
- Docker logs (read-only): 0 `MANAGE PRICE`, 0 `BROKER_CLOSE`, 0 `CLOSE DECISION`, 6 `RECONCILE BROKER POSITION MISSING`
- Postgres `SELECT` on `trades`, `exec_orders`, `reconcile_metadata`
- `GET /system` (live process)
- Read-only OANDA `TradeDetails` + `TransactionDetails` for 2125/2133/2137/2161
- Container logging lastResort = WARNING

### Fact / inference / unknown

| Item | Class |
|------|--------|
| Four closes are OANDA `STOP_LOSS_ORDER` fills | proven fact |
| No bot `BROKER_CLOSE` / `execute_trade` live close for these IDs | proven fact (alert/`print` would have shown; Postgres would have a row) |
| No SL/TP modify path exists after entry (only `stopLossOnFill` at open) | proven fact (code) |
| Case D drops local without P&L | proven fact |
| `[MANAGE PRICE]` filtered by uvicorn/lastResort | proven fact |
| Live manage price is closeoutBid/Ask | proven fact (code + tests) |
| Evaluate ran while these four were open | strong inference (6–17 min lives, no OHLCV warnings, subsequent opens) |
| Why attached SL prices ≠ local printed SL | unknown |
| Exact intra-bar tick path to SL | unknown (not needed; fill tx is sufficient) |

PRODUCTION CHANGES MADE: **NO**
