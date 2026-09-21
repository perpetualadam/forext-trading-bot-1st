# Live position-management price / MFE fix — design only

**Status:** DESIGN ONLY. No production code, `.env`, Docker, or OANDA writes in this task.  
**Depends on:** `reports/decision_quality/live_one_minute_close_investigation.md`

RECOMMENDED DESIGN:
For every `is_broker_backed` position, manage with a batched OANDA PricingInfo closeout bid/ask (the side the position can actually flatten), never the last M5 close. Seed live MFE at 0 at fill time; raise it only from post-fill closeout observations and from M5 bars whose start is ≥ fill time. Disable bot-side SL/TP exits on live broker positions (OANDA `stopLossOnFill` / `takeProfitOnFill` remain the hard exits). Keep paper / window_paper / backtest on candle closes. On restart, reset MFE to `max(0, current closeout pips)` — never reconstruct from a candle that began before the fill.

ROOT INVARIANT:
No pre-entry market movement may affect management of a live broker position.

BROKER PRICE SOURCE:
One process-wide `GET /v3/accounts/{id}/pricing?instruments=…` per `run_bot` cycle (all symbols with a broker-backed local position, or all six configured pairs if that is simpler). Use `closeoutBid` to manage a BUY and `closeoutAsk` to manage a SELL. Do not use OpenPositions `averagePrice` / `unrealizedPL`, TradeDetails entry price, or M5 close as the live management print.

LIVE SL/TP AUTHORITY:
OANDA is authoritative for hard SL/TP on broker-backed positions. The bot must not emit `sl_tp` / `PositionClose` from a local SL/TP comparison. Bot-initiated live closes remain **profit protection** and **weekend flatten** only. Paper / simulated / window_paper keep the existing candle SL/TP check.

MFE METHOD:
Combination: (1) each management cycle, `max_profit_pips = max(max_profit_pips, unrealized pips vs fill using closeout side)`; (2) after a candle whose **start ≥ fill epoch** completes, also allow that bar’s favourable extreme to raise MFE. Pre-entry bars and the partial entry bar are never used for high/low. Live open sets `max_profit_pips = 0` and `profit_protection_seeded = True` so the current overlapping-bar seed cannot run.

RESTART BEHAVIOUR:
In-memory MFE is lost. Reconcile import / new local row starts at MFE 0, then `max(0, current closeout unrealized)`. Underestimate a missed peak; never invent pre-entry profit from M5 OHLC. Do not persist MFE in v1.

EXPECTED OANDA REQUEST RATE:
**+0 or +1 GET per ~60s cycle** (one batched PricingInfo). Current cycle is already ~9–15 GETs (account + 6× M5 + reconcile). Still ≪ default limiter 10 rps / official 120 rps.

PRODUCTION CODE CHANGES REQUIRED:
See §11. Design names files/functions only — do not implement here.

TESTS REQUIRED:
See §9. Isolated unit tests reproducing 1589, 1597, 1621, 1629. No live OANDA.

RISKS / EDGE CASES:
See §12.

---

## 1. Current price for live position management

### What exists today (do not keep using it for live manage)

`evaluate()` does:

```text
raw = fetch_ohlcv(symbol, "M5", count)   # complete candles; forming bar usually dropped
price = raw["close"].iloc[-1]
record_mid(symbol, price)
# then SL/TP, seed_position_mfe, apply_profit_protection all use `price`
```

That `price` is the last **completed** M5 mid close. It can be 1–5 minutes old and is the value logged as `[OPEN] mid=` / `BROKER_CLOSE mid=`. It is not the fill and not a closeable quote.

New-entry hybrid / AI / indicators should **keep** this M5 series. Only the **existing-position** branch must stop using it as the management print.

### Existing OANDA reads — usable or not

| Existing read | Already called | Contains a current executable price? | Use for live manage? |
|---|---|---|---|
| `fetch_ohlcv` M5 | Yes, every symbol / cycle | Last completed mid close only | **No** — this is the bug |
| `fetch_account_summary` | Yes, once per `run_bot` cycle | NAV / balance; no per-pair quote | No |
| `reconciliation.fetch_broker_positions_detail` (OpenPositions) | Yes, ~60s | `averagePrice` = **entry**; `unrealizedPL` is account-ccy P&L, not a clean FX print | **No** as a price |
| `oanda_exec.fetch_trade_details_sync` | On reconcile import | Entry, `openTime`, SL/TP orders; no mark/closeout | Open-time / SL presence only |
| `state.last_mid` | Written from M5 close | Same stale series | No for live manage |
| OANDA PricingInfo | **Not implemented** | Bid/ask + `closeoutBid` / `closeoutAsk` + `time` | **Yes — add one batched GET** |

There is no existing safe live management print. OpenPositions/TradeDetails cannot substitute without inventing a price from P&L.

### Proposed source and semantics

**Endpoint (read-only):**  
`GET /v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,…`  
Library: `oandapyV20.endpoints.pricing.PricingInfo` (same stack as candles/orders).  
New wrapper: `forex_bot/oanda_client.py` → `fetch_pricing_snapshot(symbols) -> dict[str, ManageQuote]`.  
Call site: `run_bot()` **once** per cycle, before the symbol loop (same pattern as `fetch_account_summary`). Pass the snapshot into `evaluate` or store it in `state` for that cycle only.

**`ManageQuote` fields:**

| Field | Meaning |
|---|---|
| `bid` / `ask` | Top-of-book |
| `closeout_bid` / `closeout_ask` | OANDA closeout prints (what flatten uses) |
| `mid` | `(closeout_bid + closeout_ask) / 2` — logging / notional only |
| `time_utc` | Quote time from the response |
| `tradeable` | If false, treat as unavailable |

**Management print `current_price` (live / paper_broker / reconcile_import):**

| Local side | Close action | Price |
|---|---|---|
| BUY | sell to flatten | `closeout_bid` |
| SELL | buy to flatten | `closeout_ask` |

A mid is **not** appropriate for SL/TP or PP decisions: it is not executable and would overstate BUY MFE / understate BUY giveback. Mid may be logged beside the closeout print.

**If the snapshot is missing, stale (> 90s), or the instrument is not tradeable:** fail closed for **price-dependent** live decisions this cycle:

- do **not** fall back to M5 close
- do **not** fire PP close
- do **not** fire bot SL/TP (see §4)
- weekend flatten may still run (calendar, not a price path)
- log `[MANAGE PRICE] source=UNAVAILABLE`

M5 candles remain on the cycle for ATR(14), new-entry routing, and paper manage.

---

## 2. MFE tracking

### Required start state (live / broker-backed)

At the moment the local `Position` is created from a broker fill (or a reconcile import):

```text
max_profit_pips = 0
profit_protection_seeded = True
profit_protection_active = False
profit_protection_exit_pips = None
```

Setting `profit_protection_seeded = True` is load-bearing: today’s `seed_position_mfe` no-ops only when that flag is set. If it stays `False`, the next `evaluate` will call `reconstruct_mfe_from_ohlcv` on the overlapping M5 (1589 / 1597 / 1621).

Fill epoch = `orderFillTransaction.time` when present, else `datetime.utcnow()` (today’s `open_position` clock). Reconcile import already prefers TradeDetails `openTime` (`reconciliation._parse_oanda_open_time`).

### How MFE may increase after the trade exists

**Chosen method: C — combination**

| Update | When | Rule |
|---|---|---|
| Cycle observation | Every manage cycle with a valid closeout quote | `mfe = max(mfe, unrealized_profit_pips(symbol, side, fill, closeout_price))` |
| Fully post-entry M5 | Candle **start ≥ fill_epoch** and `complete=true` | `mfe = max(mfe, extreme_favourable_pips(... bar high/low))` |
| Partial entry M5 | `bar_start < fill_epoch < bar_end` | **Ignore OHLC** (unknown intra-bar order; no lookahead) |
| Pre-entry M5 | `bar_end ≤ fill_epoch` | **Ignore** |

`apply_profit_protection` already ratchets MFE from `current` and never decreases it. After the live seed is 0 + `seeded=True`, that path is valid **if and only if** `current_price` is the closeout print, not the M5 close.

### Trade-offs

| Method | Pros | Cons |
|---|---|---|
| **A. Cycle quotes only** | Strictly post-fill; simple; no candle-order ambiguity | 60s sampling can miss an intra-cycle peak (under-protect) |
| **B. Fully post-entry candles only** | Captures intra-bar extremes after the entry bar completes | First complete post-entry M5 can be ~4–9 minutes after fill; first minutes have MFE 0 unless combined with A |
| **C. Combination (recommended)** | First-minute PP uses real closeout pips; later bars can raise MFE without using the entry bar | Slightly more code; still underestimates a peak that occurred intra-cycle and pulled back before both the next quote and a completed post-entry bar |

**A alone** would still have stopped 1589 / 1597 / 1621 (closeout pips were ~0 or negative; MFE would stay ~0; 67% TP cannot fire). **C** preserves the intended “MFE is the best favourable excursion since entry” once enough post-entry data exists, without violating the invariant.

Do **not** reconstruct initial MFE from any M5 whose interval began before the fill.

MAE (`max_adverse_pips`) must use the same bar filter. Today `reconstruct_mae_from_ohlcv` uses the same overlap rule and would invent pre-entry adverse excursion the same way.

---

## 3. Partial entry candle

OANDA M5 `time` is the **start** of the bar. Bar length = 300s.

```text
fill at 23:06:26
bar 23:00:00–23:05:00  →  pre_entry      (bar_end 23:05:00 ≤ fill)
bar 23:05:00–23:10:00  →  partial_entry  (start < fill < end)
bar 23:10:00–23:15:00  →  post_entry     (start ≥ fill)
```

Proposed helper (e.g. `profit_protection.candle_vs_fill(bar_start_epoch, fill_epoch, bar_seconds=300) -> "pre_entry" | "partial_entry" | "post_entry"`):

```text
if bar_end <= fill_epoch:          pre_entry
elif bar_start < fill_epoch:       partial_entry
else:                              post_entry   # bar_start >= fill_epoch
```

| Class | High/low → MFE/MAE | Close → live current pips | Close → paper current pips |
|---|---|---|---|
| pre_entry | No | No | Unchanged (paper still uses last complete close) |
| partial_entry | **No** (no intra-bar ordering) | No | Unchanged |
| post_entry | Yes, once `complete` | No (live uses PricingInfo) | Yes |

The 23:05–23:06:25 range **must not** count, even if that bar later completes and its official high was printed before the fill. We cannot know whether the high was pre- or post-fill without ticks; the invariant forbids guessing.

Live current pips never come from any of these three closes; they come from PricingInfo.

---

## 4. SL/TP responsibility

Broker already attaches GTC `stopLossOnFill` / `takeProfitOnFill` on the live MarketOrder (`oanda_exec._place_market_order_open_sync`). Local SL/TP are then rebuilt from the **fill** (`bot_loop.py` 712–717). Reconcile can re-read broker SL/TP via pending orders / TradeDetails.

### Design A — OANDA authoritative (recommended)

For `is_broker_backed(pos)`:

- `sl_tp_hit = False` always in `evaluate`
- Hard stop / target = broker orders already on the trade
- If OANDA fills SL/TP, the book goes flat; `reconciliation` Case D (`close_local_position`, `reconcile_fix_broker_flat`) drops the ghost local row. **No bot `PositionClose`.**
- Bot `PositionClose` remains only for `protect_hit` and `weekend_flat`

**Failure safety:** If the process dies, broker SL/TP still protect. That is a stronger guarantee than a bot check that was using a stale M5 close.

**Duplicate-close risk:** Today the bot can `PositionClose` while broker SL/TP are still working (1629). Removing bot SL/TP for live eliminates that race.

**Network:** A missed pricing GET cannot cause a false SL (there is no bot SL). PP fail-closes if price is unavailable.

**Reconcile:** Already designed as broker-truth, never sends flatten. Fits A.

**Narrow fallback (optional, same PR if cheap):** if reconcile/TradeDetails shows a broker-backed trade with **no** SL or **no** TP (`sl_source` / pending empty), log `[RISK] broker SL/TP missing` and then allow bot SL/TP using the **closeout** print only — never M5. Default path (SL/TP present, as in the four examples) stays A.

### Design B — keep redundant bot SL/TP with a valid price

Would have stopped 1629’s *false* SL (closeout 156.834 was not ≤ 156.7738) but keeps a second flatten path racing the broker. Extra closes, extra `BROKER_CLOSE` noise, harder forensics.

### Recommendation

**A.** Paper / window_paper / simulated / backtest: **no change** — they have no broker SL/TP; candle SL/TP stays.

Out of scope for this smallest fix (do not implement now): broker SL/TP are still computed from the **pre-fill M5 mid** at order send (`bot_loop.py` 634–640), then local levels from fill. That can leave broker SL/TP tighter/looser than local. Separate follow-up; do not replace working SL/TP in this change.

---

## 5. Profit protection (methodology preserved, path corrected)

Keep current defaults / live unset env:

| Parameter | Value | Role |
|---|---|---|
| Trigger | 67% of original TP distance | Activation only |
| Giveback | 0.5 × M5 ATR(14) | Distance subtracted from MFE |
| Fallback | 4 pips if ATR invalid | Not the live giveback |
| Clamp | 0.5–30 pips | Unchanged |
| Ratchet | `max(prev, MFE − giveback)` | Never loosens |

**What changes is the inputs, not the formula.**

| Input | Today (live) | After |
|---|---|---|
| MFE seed | Overlapping M5 high/low vs fill | 0 at fill; then post-fill only |
| Current pips | Last M5 close vs fill | Closeout bid (BUY) / ask (SELL) vs fill |
| Activation | Can fire from pre-entry high | Only if **post-entry** MFE ≥ 67% TP |
| Giveback ATR | M5 ATR(14) on the candle series | **Unchanged** — ATR is a volatility statistic, not the trade’s path |
| BUY/SELL | Same `unrealized_profit_pips` | Same helper; price must be the closeout side |

ATR(14) **may** include bars from before the fill. That is the existing methodology (“giveback = 0.5 × M5 ATR(14)”), not a reconstruction of the trade’s excursion. The invariant applies to **MFE, activation, current pips, and bot SL/TP**, not to wiping the ATR lookback.

Min-hold already does not block PP (`bot_loop.py` 249–262). Leave that as-is.

If PricingInfo is unavailable: `protect_hit = False` this cycle (fail closed). Do not evaluate PP against M5 close.

---

## 6. Broker request load

**Today per ~60s (live):**

| Call | Count |
|---|---|
| AccountSummary | 1 |
| InstrumentsCandles M5 | 6 |
| OpenPositions + OrdersPending (± TradeDetails) | ~2–8 |
| **Total** | **~9–15 GETs / 60s ≈ 0.15–0.25 rps** |

**Added:** 1× `PricingInfo` with up to six instruments in the query string.

| Policy | Extra GETs / cycle |
|---|---|
| Always snapshot all `Config.SYMBOLS` | +1 |
| Snapshot only symbols with `is_broker_backed` local pos | +1 if any open, else +0 |

Prefer **always-six, one GET**: constant, cacheable for the cycle, useful for `record_mid` / notional without six extra calls.

Do **not** call PricingInfo inside `evaluate` per symbol (that would be +6).

Limiter: `oanda_rate_limit.acquire_oanda_rest_slot` default **10 rps**, hard cap **120**. +1 GET/minute is noise. PricingInfo must go through `_oanda_request` / `acquire_oanda_rest_slot` like other reads.

No new writes. No extra PositionClose.

---

## 7. Restart / reconciliation

Positions live only in `forex_bot.positions.positions` (in-memory). There is **no** persisted `max_profit_pips`. After process restart:

1. Reconcile may `import_position_from_broker` (`execution_kind=reconcile_import`, `open_time` from TradeDetails when present, SL/TP from broker if found).
2. New `Position()` defaults `max_profit_pips=0`, `profit_protection_seeded=False`.
3. **Today** the next `evaluate` runs `seed_position_mfe(..., ohlcv=raw)` and can invent pre-entry MFE again.

**Safe v1 restart (recommended, smallest):**

```text
on import / first live manage after create:
  max_profit_pips = max(0, current_closeout_unrealized_pips)
  profit_protection_seeded = True
  do not call reconstruct_mfe_from_ohlcv / reconstruct_mae_from_ohlcv
    unless the bar start >= fill_epoch
```

| Situation after downtime | Result |
|---|---|
| Now +8 pips, never saw the +20 peak | MFE = 8 (underestimate; PP may not be active) |
| Now −2 pips | MFE = 0; PP inactive |
| M5 high during downtime was pre- or intra-entry-bar | Ignored |
| Broker SL/TP still on the trade | Still protect the hard stop |

**Do not persist MFE in v1.** A new table/column that is not write-filtered would reintroduce pre-entry values. Closed-trade `trades.diagnostics` is historical and must not be replayed onto a new local row.

If persistence is added later: write only after `price_source` is `OANDA_CURRENT` or `POST_ENTRY_CANDLE`, keyed by `broker_order_id` / trade id, never by symbol alone.

`import_position_from_broker` should set `profit_protection_seeded=True` (or the first manage must use the live seed path). Leaving the flag false is how restart re-breaks.

---

## 8. Paper / window_paper / backtest

| Path | Entry price | Manage price | PP? | Same temporal bug? |
|---|---|---|---|---|
| `EXECUTION_MODE=paper` in `evaluate` | Candle close or sim from that close | Same M5 close series | Yes (`seed` + `apply`) | Entry and manage share the candle clock. Overlapping-bar MFE vs a close-as-entry is a **simulation convention**, not fill-vs-stale-bar. **Leave it.** |
| `window_paper` | Same | Same | Yes | Same — paper-like; **leave it.** |
| `backtest.py` | Candle / sim | Candle close | **No PP** (SL/TP + weekend only) | Research methodology; **do not add live pricing.** |
| `paper_broker` / `live` / `reconcile_import` | Broker fill | Must change | Yes | **This fix.** Gate on `is_broker_backed(pos)`, not on `TRADING_MODE` alone. |

`is_broker_backed` already treats `execution_kind in {live, reconcile_import}` and `broker_order=True` as broker-backed, and never treats paper-like rows as such (`execution.py`).

Do not change `reconstruct_mfe_from_ohlcv` default behaviour for paper tests such as `test_restart_reconstructs_mfe_from_candle_highs`. Add an explicit flag (e.g. `include_partial_entry_bar=False`) used only on the broker-backed path.

---

## 9. Test plan

New module (suggested): `tests/test_live_position_management.py`.  
Pure unit tests; inject quotes / OHLCV / `Position`; **no** network, **no** `execute_oanda_market_close`.  
`conftest.py` already forces `EXECUTION_MODE=paper` for the suite — tests should construct `execution_kind="live"` / `broker_order=True` explicitly.

### Fixtures (from live rows)

| id | Side | Fill | Local SL | Local TP | Stale M5 close | M5 high used as fake MFE | Broker close print | Expected after fix |
|---|---|---|---|---|---|---|---|---|
| 1589 | BUY | 1.14803 | 1.14769 | 1.14871 | 1.14800 | 5.1 pips above fill | 1.14783 | no PP, no SL; MFE 0 or ≈ current closeout only |
| 1597 | BUY | 1.14806 | 1.14771 | 1.14875 | 1.14810 | 4.8 pips | 1.14790 | same |
| 1621 | BUY | 156.757 | 156.6988 | 156.8734 | 156.736 | 11.9 pips (high ≈ 156.876) | 156.766 | no PP; MFE ≈ max(0, closeout vs 156.757) |
| 1629 | BUY | 156.832 | 156.7738 | 156.9484 | 156.736 | n/a (PP inactive) | 156.834 | **no `sl_tp`**; stale close below SL is ignored |

Partial-bar fixture for 1621: M5 start `23:05:00`, fill `23:06:26`, high 156.876, close 156.736.

### Required assertions

1. **No pre-entry / partial-bar MFE:** `reconstruct` / `seed` with `include_partial_entry_bar=False` leaves MFE 0 when only the 23:05 bar exists; high 156.876 must not appear.
2. **Stale M5 cannot trip fill-based SL:** 1629 inputs + manage price = closeout 156.834 → `sl_tp_hit` is false for broker-backed (design A). Same inputs with paper kind may still trip SL (proves paper unchanged).
3. **PP cannot activate from pre-entry movement:** 1589 / 1597 / 1621 reconstructed MFE + stale close → `should_close` is false when seed is live-safe and current is closeout.
4. **Genuine post-entry favourable movement can activate PP:** BUY fill 1.10000, TP +10 pips, closeout later +6.8 pips (≥ 6.7) → `active` true, `should_close` false if still above threshold.
5. **Genuine giveback can close after activation:** after activation, closeout drops to MFE − 0.5×ATR → `should_close` true.
6. **SELL is symmetric:** short fill, post-entry low raises MFE; closeout ask used as current; partial-bar low ignored.
7. **Restart / import does not manufacture MFE:** `import_position_from_broker` + overlapping M5 high + current closeout −1 pip → MFE 0, PP inactive, `profit_protection_seeded` true.
8. **Paper unchanged:** existing `tests/test_profit_protection.py` (including `test_restart_reconstructs_mfe_from_candle_highs`) still pass without rewriting candle-overlap defaults.
9. **Pricing helper:** BUY→closeoutBid, SELL→closeoutAsk; missing snapshot → no PP close, no fallback to M5.
10. **Candle classifier:** the three 23:00 / 23:05 / 23:10 bars vs fill 23:06:26 map to pre / partial / post.
11. **Logging helpers (optional in same PR):** format `[CLOSE DECISION]` and `[MANAGE PRICE]` contain `price_source=` in `{OANDA_CURRENT, POST_ENTRY_CANDLE, PAPER_CANDLE, UNAVAILABLE}`.

Keep `tests/test_oanda_v20_congruence.py` style for PricingInfo request shape if a body builder is added (no live call).

---

## 10. Logging

### Manage-price line (every broker-backed manage cycle)

```text
[MANAGE PRICE] symbol=USD_JPY broker_id=1621 side=BUY
source=OANDA_CURRENT|POST_ENTRY_CANDLE|PAPER_CANDLE|UNAVAILABLE
current_price=156.766 closeout_bid=156.766 closeout_ask=156.770
m5_close=156.736 m5_time=2026-09-20T23:00:00Z
fill=156.757 fill_time=2026-09-20T23:06:26Z
current_pips=+0.9 mfe_pips=0.9 tp_progress=0.08
```

`POST_ENTRY_CANDLE` is only for the MFE ratchet from a completed post-entry bar, not for `current_price`. Live `current_price` source is `OANDA_CURRENT` or `UNAVAILABLE`. Paper manage uses `PAPER_CANDLE`.

### Close-decision line (immediately before `execute_trade` on the manage-close branch)

```text
[CLOSE DECISION] symbol=USD_JPY broker_id=1621 reason=profit_protection
entry=156.757 current_price=156.766 price_source=OANDA_CURRENT
sl=156.6988 tp=156.8734 mfe_pips=8.2 tp_progress=0.70
protected_exit_pips=6.5 trigger=protect_hit
sl_tp_hit=false weekend_flat=false protect_hit=true
current_side=BUY proposed_side=n/a rl_action=n/a
```

`reason` / `trigger` stay in `{sl_tp, weekend_flatten, profit_protection, close}` plus the boolean that fired. `proposed_side` / `rl_action` stay `n/a` on the manage path (AI/RL still do not run).

Do not rely on Telegram `[CLOSE] [OANDA LIVE] exit=` as the decision price; that remains the PositionClose fill.

---

## 11. Production code changes required (names only)

| File | Function / site | Change |
|---|---|---|
| `forex_bot/oanda_client.py` | **new** `fetch_pricing_snapshot` | Batched PricingInfo GET; parse closeout bid/ask; `_oanda_request` + rate limiter |
| `forex_bot/state.py` | **new** cycle cache or `record_manage_quote` | Hold one snapshot per `run_bot` iteration |
| `forex_bot/bot_loop.py` | `run_bot` | Fetch snapshot once before `for s in Config.SYMBOLS` |
| `forex_bot/bot_loop.py` | `evaluate` existing-`pos` branch | Broker-backed: `current_price` from snapshot closeout side; `sl_tp_hit = False` (design A); PP/weekend unchanged in structure; no M5 fallback; `[MANAGE PRICE]` / `[CLOSE DECISION]` |
| `forex_bot/bot_loop.py` | live `open_position(...)` | `open_time` from fill transaction time if present; `max_profit_pips=0`; `profit_protection_seeded=True` |
| `forex_bot/oanda_exec.py` | `_parse_open_fill` | Also return fill `time` (optional 5th value or small struct) |
| `forex_bot/profit_protection.py` | **new** `candle_vs_fill` | pre / partial / post |
| `forex_bot/profit_protection.py` | `reconstruct_mfe_from_ohlcv` / `reconstruct_mae_from_ohlcv` | Parameter `include_partial_entry_bar` (default **True** for paper); live passes False → only `post_entry` |
| `forex_bot/profit_protection.py` | `seed_position_mfe` | If broker-backed (or `include_partial_entry_bar=False`): seed `max(0, current)` only; never overlapping OHLC |
| `forex_bot/positions.py` | `import_position_from_broker` | `profit_protection_seeded=True`; MFE 0 (first manage applies current closeout) |
| `forex_bot/execution.py` | `is_broker_backed` | No semantic change; this is the gate |
| `forex_bot/backtest.py` | — | **No change** |
| `forex_bot/reconciliation.py` | import path only | Rely on `import_position_from_broker` seed flags; still no PositionClose |

**Do not change:** quant / RL / hybrid / volatility / USD-direction / notional caps / ATR giveback formula / `TRADE_INTERVAL` / paper evaluate manage price.

---

## 12. Risks / edge cases

| Risk | Mitigation |
|---|---|
| PricingInfo fails / weekend / halt | Fail closed on PP; weekend flatten still allowed; broker SL/TP still on the book |
| Quote older than 90s | Treat as `UNAVAILABLE` |
| Instrument not `tradeable` | Same |
| Spread widening | Closeout side is conservative vs mid; PP/MFE slightly harder to activate — acceptable |
| Missed intra-cycle MFE peak | Method C + 60s sample; underestimate vs false activate |
| Restart missed peak | Underestimate; broker SL/TP remain |
| Ghost local after broker SL fill | Existing reconcile Case D; bot must not `PositionClose` on stale SL |
| `paper_broker` practice fills | Same gate as live (`is_broker_backed`) |
| Two locals / one broker | Unchanged one-slot-per-symbol rule |
| Broker SL/TP sized from pre-fill mid | Separate defect; not this PR |
| Existing unit tests that assume overlapping-bar seed | Keep default `include_partial_entry_bar=True` |
| Extra GET rejected / 429 | Shared limiter + existing retry in `_oanda_request` |

---

## 13. Mapping to the four confirmed closes

After this design, with the **historical** quotes and candles:

| broker_id | Today | After |
|---|---|---|
| 1589 | PP from MFE 5.1 vs mid 1.14800 | MFE ~0; closeout ~1.14783; no activation |
| 1597 | PP from MFE 4.8 | Same |
| 1621 | PP from MFE 11.9 vs mid 156.736 | Partial-bar high ignored; closeout 156.766 → ~+0.9 pips; 0.9 < 7.80 trigger |
| 1629 | `sl_tp` because 156.736 ≤ 156.7738 | No bot SL/TP; closeout 156.834 inside band; stays open unless broker SL/TP or later valid PP |

That is the intended outcome: those four `PositionClose`s do not happen. Genuine post-entry MFE + giveback, and Friday flatten, still can.

---

## 14. Implementation note

This document is the implementation spec. Do not apply it until explicitly asked. Do not restart the live bot or change `.env` as part of the design task.
