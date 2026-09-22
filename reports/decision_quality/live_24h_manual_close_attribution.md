# Manual-close attribution correction (20–21 Sep 2026 + POST-23:00 deploy)

MANUAL-CLOSE CORRECTION VERDICT:
The original 24h audit over-attributed `MARKET_ORDER_POSITION_CLOSEOUT` to the bot and left the two 11:41Z `TRADE_CLOSE` rows as an unproven hypothesis. Bot live closes use only OANDA `PositionClose` (fill reason `MARKET_ORDER_POSITION_CLOSEOUT`) and never `TradeClose`. Every `MARKET_ORDER_TRADE_CLOSE` in this period is therefore **not** a bot `PositionClose`. Combined with the user’s flatten-before-rebuild statement and the Docker recreate clocks, the 11:41Z pair and the 21:59Z pair are **RESTART/FLATTEN_MANUAL_CLOSE**. They stay in broker reconciliation and are excluded from profit-protection, early-exit, hold-time, and “did the 61s bug recur” statistics. Ten 09:13–09:39Z `POSITION_CLOSEOUT` rows have **no** local `exit_reason` and are **UNKNOWN** — not proven manual, not proven bot. POST-23:00 (container `2026-09-21T22:00:04Z` / 23:00:04 BST): the book was flattened by two `TRADE_CLOSE` fills at 21:59:34Z / 21:59:37Z, **before** `BOT STARTED`. The EUR stop 78s earlier is a broker SL, not a flatten. After start: no bot `PositionClose`, no `TRADE_CLOSE`, one broker SL (2488). The old ~61s bug is not visible in the post-deploy sample.

CONFIDENCE:
HIGH on TRADE_CLOSE / SL / TP / PG-backed PP. HIGH that UNKNOWN must not be scored as bot PP. HIGH that POST-23:00 flatten is user/manual, not bot.

PRODUCTION CHANGES MADE:
NO

OANDA WRITES PERFORMED:
NO

DOCKER RESTARTED:
NO

---

## 0. Why the original classes were unsafe

`oanda_exec._place_market_order_sync` is the only live flatten path. It sends `PositionCloseRequest` with **no** `clientExtensions`. The bot never calls `TradeClose`.

Therefore:

| OANDA fill reason | What it can be | What it cannot prove alone |
|---|---|---|
| `STOP_LOSS_ORDER` | Broker attached SL | — |
| `TAKE_PROFIT_ORDER` | Broker attached TP | — |
| `MARKET_ORDER_POSITION_CLOSEOUT` | Bot `PositionClose` **or** user UI “close position” | Bot vs user |
| `MARKET_ORDER_TRADE_CLOSE` | User / OANDA TradeClose API | Bot `PositionClose` (impossible) |

No close `MARKET_ORDER` in the dump has `clientExtensions.tag=forex_bot` or a `cid-*`. Client IDs **cannot** separate bot from user on closes. Attribution requires logs, Postgres `diagnostics.exit_reason`, API shape, and restart clocks — and **UNKNOWN** when those disagree or are missing.

Restart proximity is **not** used as the sole proof of a manual close.

---

## 1. Restart / flatten clocks (UTC)

| Event | UTC | Evidence |
|---|---|---|
| OLD_MANAGEMENT_BUILD_END / NEW_MANAGEMENT_BUILD_START | 2026-09-21 09:40:11 | Prior container created 10:40:11 BST; first new-build fill 2125 at 09:40:20Z |
| Broker-exit rebuild | 2026-09-21 11:41:55 | Then-current container start; `BOT STARTED` 11:41:57Z |
| **POST-23:00 deploy** | **2026-09-21 22:00:04** | `docker inspect` Created=`2026-09-21T22:00:04Z` Started=`22:00:10Z` (23:00:04 / 23:00:10 BST) |
| POST-23:00 BOT STARTED | 2026-09-21 22:00:13 | Log `23:00:13` Europe/London BST |

User statement (this task): some live positions were **manually closed to flatten before restart/rebuild**. That is used only as context, never as a substitute for transaction evidence.

---

## 2. Eight-class rules used

| Class | Proven when |
|---|---|
| 1. BROKER_STOP_LOSS | `ORDER_FILL.reason=STOP_LOSS_ORDER` |
| 2. BROKER_TAKE_PROFIT | `ORDER_FILL.reason=TAKE_PROFIT_ORDER` |
| 3. BOT_PROFIT_PROTECTION | `POSITION_CLOSEOUT` **and** Postgres `exit_reason=profit_protection` (bot `execute_trade` booked the close) |
| 4. BOT_WEEKEND_FLATTEN | Friday flatten window **and** local `weekend_flatten`. **n=0** (Sun–Mon sample) |
| 5. BOT_OTHER_POSITION_CLOSE | `POSITION_CLOSEOUT` **and** Postgres `exit_reason=sl_tp` (local SL/TP `PositionClose`, including 1629) |
| 6. USER_MANUAL_CLOSE | `TRADE_CLOSE` **not** at a proven rebuild flatten. **n=0** inside the 24h window |
| 7. RESTART/FLATTEN_MANUAL_CLOSE | `TRADE_CLOSE` (bot cannot issue it) **and** fill ≤120s before a proven container create **and** user flatten-before-rebuild context |
| 8. UNKNOWN | `POSITION_CLOSEOUT` with **no** local `exit_reason` / `[ORDER CLOSE]` / `[BROKER_CLOSE]` |

`TRADE_CLOSE` is never labelled bot. `POSITION_CLOSEOUT` is never labelled manual solely because it sits near a restart.

---

## 3. Original 24h sample (21:05:12Z 20 Sep → 21:21:47Z 21 Sep)

117 completed exits. Broker counts unchanged: 47 SL / 7 TP / 61 PositionClose fills / 2 TradeClose fills.

### 3.1 Corrected class counts

| Class | n | RealizedPL | Notes |
|---|---:|---:|---|
| BROKER_STOP_LOSS | 47 | −0.0369 | Unchanged |
| BROKER_TAKE_PROFIT | 7 | +0.0073 | All OLD build |
| BOT_PROFIT_PROTECTION | 45 | +0.0038 | 35 OLD (32 of those 46–90s; 3 longer) + 10 NEW (≥19 min, all winners) |
| BOT_WEEKEND_FLATTEN | 0 | — | Not Friday |
| BOT_OTHER_POSITION_CLOSE | 6 | −0.0051 | PG `sl_tp`: 1607, 1617, 1629, 1643, 1731, 1869 |
| USER_MANUAL_CLOSE | 0 | — | No off-restart TradeClose in window |
| RESTART/FLATTEN_MANUAL_CLOSE | 2 | −0.0004 | 2181 AUD, 2155 USD_JPY at 11:41Z |
| UNKNOWN | 10 | +0.0004 | 09:13–09:39Z PositionClose, no PG |

### 3.2 Proven restart/flatten manuals (in-sample)

| trade | pair | side | close UTC | hold s | PL | OANDA | Why not bot |
|---|---|---|---|---:|---:|---|---|
| 2181 | AUD_USD | BUY | 2026-09-21T11:41:00Z | 895 | +0.0001 | `MARKET_ORDER_TRADE_CLOSE` | Bot has no TradeClose path; 55s before 11:41:55Z recreate; no PG row |
| 2155 | USD_JPY | BUY | 2026-09-21T11:41:10Z | 5541 | −0.0005 | `MARKET_ORDER_TRADE_CLOSE` | Same; 45s before recreate; no PG row |

`broker_exit.py` maps `MARKET_ORDER_TRADE_CLOSE` → `broker_manual_close`. That mapping matches this evidence. These two were **not** booked locally (pre-ledger container).

**Not** reclassified as flatten: **2143 GBP_USD** `POSITION_CLOSEOUT` at 11:40:19Z (−95s). Postgres `exit_reason=profit_protection`, hold 6466s, PL +0.0005. Restart proximity alone is insufficient. Class = **BOT_PROFIT_PROTECTION**.

### 3.3 UNKNOWN (do not score as bot or manual)

All `MARKET_ORDER_POSITION_CLOSEOUT`, no `clientExtensions`, **no** Postgres `exit_reason` after the last old-build booked close (2033 at 08:37:19Z). Docker logs from that container are gone.

| trade | pair | close UTC | hold s | PL | vs 09:40:11Z |
|---|---|---|---:|---:|---|
| 1949 | AUD_USD | 09:13:33 | 4610 | +0.0003 | −26.6 min |
| 2051 | USD_CAD | 09:20:36 | 953 | +0.0001 | −19.6 min |
| 2045 | GBP_USD | 09:20:41 | 1202 | 0 | −19.5 min |
| 1917 | USD_JPY | 09:20:45 | 6260 | 0 | −19.4 min |
| 2075 | USD_JPY | 09:36:16 | 858 | +0.0005 | −3.9 min |
| 2085 | GBP_USD | 09:37:10 | 183 | 0 | −3.0 min |
| 2089 | AUD_USD | 09:39:34 | 266 | 0 | −37 s |
| 2101 | GBP_USD | 09:39:39 | 88 | 0 | −32 s |
| 2079 | USD_CHF | 09:39:42 | 1064 | −0.0002 | −29 s |
| 2105 | USD_JPY | 09:39:46 | 33 | −0.0003 | −25 s |

2101 is 88s (old-bug **time** bucket) but has no PG `profit_protection` → **UNKNOWN**, not counted in the 61s-bug total. 2105 is 33s — not the 61s signature.

The 09:39:34–46 burst (four symbols, ~4s apart) is compatible with one `evaluate()` loop **or** a fast UI flatten. Bot was still **opening** 2101/2105 at 09:38:11Z / 09:39:12Z, so this is not a clean “account already flat” story. **UNKNOWN.**

The 09:20:36–45 burst is **not** flatten-before-restart: the bot opened 2075 at 09:21:57Z afterwards.

### 3.4 Strategy-exit stats (manuals excluded; UNKNOWN excluded from PP / bot-close frequency)

| Metric | Include manuals / UNKNOWN-as-bot (old audit) | Corrected |
|---|---|---|
| Completed exits (broker) | 117 | 117 (reconciliation unchanged) |
| Strategy-scored exits | 117 | 115 (drop 2181, 2155) |
| Bot PositionClose proven | 61 | **51** (45 PP + 6 sl_tp). 10 UNKNOWN not counted |
| Old 46–90s PP bug proven | 33 + 1629 = 34 | **32 PP + 1629 sl_tp = 33**. 2101 unknown |
| New-build PP proven | 10 | **10** (unchanged; all PG `profit_protection`, holds 19–213 min, PL **+0.0088**) |
| New-build 46–90s PositionClose | 0 | **0** (among proven bot closes) |
| New-build TradeClose | 2 counted as “other broker” | **2 manuals**, excluded from PP / early-exit / hold |

New-build PP IDs (keep): 2129, 2143, 2213, 2223, 2251, 2297, 2301, 2317, 2357, 2361.

Old ~61s bug **after the 09:40:11Z manage fix**: still **absent** among proven bot closes. The two 11:41Z manuals are TradeClose, not the 61s PositionClose pattern.

---

## 4. POST-23:00 deployment (required before judging new-build exits)

### 4.1 Pre-start book (21:50Z–22:00:04Z)

| Time UTC | tx | What | Class | Hold | PL |
|---|---|---|---|---:|---:|
| 21:50:01 | 2470 open | GBP_USD SELL `CLIENT_ORDER` tag=`forex_bot` | bot entry | — | 0 |
| 21:58:46 | 2473 fill | EUR_USD 2458 `STOP_LOSS_ORDER` | **BROKER_STOP_LOSS** | 1562 s | −0.0006 |
| 21:59:34 | 2475/2476 | USD_JPY **2454** `TRADE_CLOSE` | **RESTART/FLATTEN_MANUAL_CLOSE** | 1915 s | −0.0003 |
| 21:59:37 | 2479/2480 | GBP_USD **2470** `TRADE_CLOSE` | **RESTART/FLATTEN_MANUAL_CLOSE** | 575 s | −0.0002 |
| 22:00:04 | — | container Created | — | — | — |
| 22:00:13 | — | `BOT STARTED` equity=97.28 | — | — | — |

EUR 2458 stopped **78s before** recreate. That is a broker SL (PG `broker_stop_loss` / close_tx 2473). **Not** a flatten. Do not fold it into manual or bot-early-exit stats.

JPY 2454 and GBP 2470:

- `MARKET_ORDER.reason=TRADE_CLOSE`, `tradeClose.units=ALL`
- no `clientExtensions`
- 30s and 27s **before** Created=22:00:04Z
- **no** Postgres `profit_protection` / `sl_tp` / `weekend_flatten` row
- **no** `[ORDER CLOSE] PositionClose` (previous container logs discarded on recreate)
- bot code cannot emit this API

**PROVEN RESTART/FLATTEN_MANUAL_CLOSE.** Exclude from PP, bot PositionClose frequency, 61s-bug, and strategy hold-time. **Include** in account P/L (−0.0005 combined).

After those two TradeCloses the account was flat going into the 23:00 BST rebuild (EUR already SL’d).

### 4.2 Post-start behaviour (22:00:13Z → last_id 2500 ~22:09:24Z)

| Time UTC | trade | Event | Class |
|---|---|---|---|
| 22:00:14 | 2484 | GBP_USD SELL open (`cid-d1a5…`, tag forex_bot) | bot entry |
| 22:00:14 | 2488 | USD_JPY SELL open | bot entry |
| 22:06:29 | 2488 | `STOP_LOSS_ORDER` exit 157.413, PL −0.0006, hold ~375s | **BROKER_STOP_LOSS** |
| 22:08:23 | 2494 | USD_JPY SELL open | bot entry |
| 22:09:24 | 2498 | EUR_USD SELL open | bot entry |

Current-container logs through the same window: `[BROKER_FILL]` opens, `[ENTRY GEOMETRY SKIP] stale_quote`, `[BROKER EXIT] … broker_stop_loss` for 2488. **Zero** `[ORDER CLOSE]`, **zero** `[BROKER_CLOSE]`, **zero** `POSITION_CLOSEOUT`, **zero** `TRADE_CLOSE` after 22:00:04Z.

| Post-23:00 question | Answer |
|---|---|
| User/manual flatten at the boundary? | **Yes — 2454 and 2470 at 21:59:34–37Z** |
| Did the bot flatten the old book? | **No** |
| Recurrence of the ~61s PositionClose bug? | **No** in this window (no PositionClose at all) |
| Bot PP / weekend flatten after start? | **None observed** |
| First post-deploy exit? | Broker SL on 2488 at 6m 15s, booked `broker_exit_ledger` / PG `broker_stop_loss` |

Entry-geometry skips (`stale_quote`, fail-closed, no M5 fallback) are a **new-entry** gate, not an exit class.

---

## 5. Claims that change

| Old statement | Corrected |
|---|---|
| MANUAL_CLOSE = 0 proven | **4 proven flatten manuals**: 2181, 2155 (11:41Z) and 2454, 2470 (21:59Z). First two are inside the 24h count window. |
| 2 TradeCloses = OTHER_BROKER_CLOSE / hypothesis | **RESTART/FLATTEN_MANUAL_CLOSE** |
| 61 PositionClose = all bot | **51 proven bot** (45 PP + 6 sl_tp) + **10 UNKNOWN** |
| 34× ~61s old bug | **33 proven** (32 PP + 1629). 2101 (88s, no PG) is UNKNOWN |
| New PP 10 | **Unchanged** after dropping manuals |
| Closeout P/L −0.0009 “protective” | Still **not** protective; additionally, 2 TradeClose manuals are **outside** that −0.0009 (they are the −0.0004 TradeClose bucket) |

---

## 6. Reconciliation vs strategy scoring

Keep in **broker / account** totals: all 117 in-sample exits + the two 21:59Z flatten closes + EUR 2458 SL + 2488 SL.

Drop from **PP / bot early-exit / bot PositionClose frequency / strategy hold-time / 61s-bug recurrence**:

- 2181, 2155, 2454, 2470 (proven manuals)
- 10 UNKNOWN PositionCloses (do not treat as bot PP or as proven flatten)

---

## 7. Sources (read-only)

- OANDA `TransactionIDRange` GET (existing dump ids 861–2460 + pull 2440–2500). No order create/cancel/replace.
- `docker inspect` current `forexttradingbot1st-bot-1` Created=22:00:04Z.
- Current-container logs since 22:00Z.
- Postgres `SELECT` on `trades` (`exit_reason`, `broker_trade_id`).
- Source: `oanda_exec._place_market_order_sync` (PositionClose only); `broker_exit._OANDA_REASON_MAP`.

Account identifiers are not written into this report.
