# Live one-minute broker closes — read-only investigation

**Scope:** current production code + existing live logs / Postgres `trades.diagnostics`.  
**Not done:** no code or `.env` changes, no Docker restart, no bot stop, no OANDA write, no backtest, no `[CLOSE DECISION]` logging implementation.

ROOT CAUSE:
The next `evaluate()` cycle (~60s) manages the existing local position and issues an explicit OANDA `PositionClose`. The manage price is the last M5 candle close from `fetch_ohlcv` (logged as `mid=`), not the live bid/ask and not the later broker fill. Three of the four examples closed because profit-protection treated a reconstructed M5 *high* as MFE, activated at 67% of original TP, then saw current pips (from that stale M5 close) far below the protected threshold. The fourth (USD_JPY `broker_id=1629`) closed because the same stale M5 close was already below the fill-based local SL (`exit_reason=sl_tp`). AI/RL/quant never ran on these cycles.

CONFIDENCE:
HIGH

ARE THESE CLOSES INTENDED BY CURRENT CODE?
YES

ARE BROKER SL/TP ORDERS RESPONSIBLE?
NO

IS RL INVOLVED?
NO

IS PROFIT PROTECTION INVOLVED?
YES (1589, 1597, 1621) / NO (1629)

Evidence classes used below:

| Class | What it is |
|---|---|
| **Code proves** | Current `forex_bot` source |
| **Logs prove** | Docker `bot` logs + `/system` + Postgres `trades.diagnostics` (read-only SELECT) |
| **Hypothesis** | Mechanism that fits both, but the exact M5 bar used for MFE was not persisted |

---

## 1. Exact close call graph

Production paths that can flatten a **live** OANDA position:

| File | Function | Caller | Close condition | Invokes OANDA `PositionClose`? | Runs every ~60s? |
|---|---|---|---|---|---|
| `forex_bot/bot_loop.py` | `evaluate` existing-`pos` branch | `run_bot` per symbol | `sl_tp_hit` **or** `weekend_flat` **or** `protect_hit` | Yes, via `execute_trade` when `pos.execution_kind=="live"` | Yes — after each `Config.TRADE_INTERVAL` (60) |
| `forex_bot/trading.py` | `execute_trade` | `evaluate` (close only) | `execution_kind=="live"` **always** sends a close; it does not decide *whether* to close | Yes → `execute_oanda_market_close` | Only when `evaluate` already decided to close |
| `forex_bot/oanda_exec.py` | `execute_oanda_market_close` → `_place_market_order_sync` | `execute_trade` | Broker flatten of the instrument long/short units | Yes — `PositionCloseRequest` / `positions.PositionClose` | Same as above |
| `forex_bot/positions.py` | `close_position` | `evaluate` after successful `execute_trade` | Local registry drop only | No | After a decided close |
| `forex_bot/reconciliation.py` | `_apply_position_convergence` | `app.reconciliation_loop` (~60s) | `RECONCILE_ACTION=auto_fix` + broker already flat → `close_local_position` | **No** (explicit: “Never sends broker orders”) | Yes, but cannot explain `BROKER_CLOSE` |
| `forex_bot/execution.py` | `halt_trading` / `KILL_SWITCH` | `POST /halt`, env | Blocks **new entries only** | No | n/a |
| `forex_bot/telegram_commands.py` | inbound commands | `telegram_inbound_loop` | Read-only; `halt` / `flatten` rejected | No | n/a |
| `forex_bot/backtest.py` | `evaluate`-like close | backtest runner | Not the live process | No | n/a |

**Live manage-open-first graph (the only live `PositionClose` path):**

```
run_bot()                                    # forex_bot/bot_loop.py
  sleep Config.TRADE_INTERVAL                # 60s hardcoded
  for symbol in Config.SYMBOLS:
    evaluate(symbol)
      fetch_ohlcv(symbol, "M5", count)       # skips candles with complete=false
      price = raw["close"].iloc[-1]          # last included M5 close
      pos = get_position(symbol)
      if pos is not None:                    # *** AI / RL / hybrid never reached ***
        seed_position_mfe(pos, price, raw)
        pp = apply_profit_protection(pos, price, ohlcv=raw)
        sl_tp_hit = (BUY: price<=SL or price>=TP)
        protect_hit = pp.should_close and protection_close_allowed
        weekend_flat = flatten_for_weekend() # Friday lead only
        if sl_tp_hit or weekend_flat or protect_hit:
          [min-hold applies ONLY to sl_tp_hit without weekend/PP]
          close_fill_path(...) == "broker"
          alert BROKER_CLOSE mid=price       # pre-fill local mid
          close_reason = sl_tp | weekend_flatten | profit_protection
          execute_trade(..., execution_kind="live", exit_price=price)
            oanda_exec.execute_oanda_market_close
              PUT .../positions/{instrument}/close
          close_position(symbol)
          rl_agent.update(...)               # learns after the fact; did not decide
        return                               # no new-entry / AI / RL this cycle
```

`execute_trade`’s “live always PositionClose” behaviour is **close-execution**, not “close existing before opening.” New entries run only when `pos is None`.

### Ruled-out live closers (code)

| Candidate | Verdict | Why |
|---|---|---|
| Signal reversal / strategy label change | Does not close | Existing-`pos` branch `return`s before `select_strategy` / `ai.vote` |
| Quant no longer allows BUY / proposes SELL | Does not close | Same — `ai.vote` not called |
| RL SKIP / opposite side | Does not close | `rl_agent.decide` not called; RL only `update`s after a close |
| Hybrid routing / horizon change | Does not close | Routing is new-entry only |
| Volatility filter | Does not close | `volatility_ok` is new-entry only (`bot_loop.py`) |
| Session / live window | Does not close existing | Session/weekend block **new opens** when `pos is None` |
| Weekend flatten | Not these trades | Friday-only (`session_rules.flatten_for_weekend_at`); 2026-09-20 is Sunday |
| USD-direction guard | Does not close | New-entry skip only (`usd_direction_guard_decision`) |
| Portfolio notional / risk caps | Do not close | New-entry skips only |
| Max hold / timeout | Not implemented | `MIN_POSITION_HOLD_SEC` *defers* SL/TP closes; default live env `0` |
| Kill switch / halt | Do not close | `pre_trade_entry_blocked_reason` is after the manage `return` |
| Reconciliation | Does not `PositionClose` | Local-only auto-fix; `/system` showed no mismatch at inspect time |
| Stale-position import | Does not close these | Would import/adjust local state, not flatten broker |
| Generic “close before evaluate” | Does not exist | Manage-then-return; no flatten-before-open |

---

## 2. broker_id=1621 trace

**What logs prove**

| Step | Timestamp (container log) | Evidence |
|---|---|---|
| Open fill | 2026-09-20 23:06:26.679 | `[EXECUTION] BROKER_FILL USD_JPY open fill=156.75700 units≈2.0000 id=1621` |
| Open local | 23:06:26.681 | `[OPEN] USD_JPY BUY units=2.00 entry=156.75700 mid=156.73600 SL=156.69880 TP=156.87340 kind=live broker_order=true broker_id=1621 strategy=swing_trend horizon=legacy` |
| Next cycle decide-close | 23:07:27.437 | `[EXECUTION] BROKER_CLOSE USD_JPY mid=156.73600 (PositionClose; local mid is pre-fill only)` |
| Broker flatten fill | 23:07:27.559 | `[CLOSE] [OANDA LIVE] BUY USD_JPY size 2.0 PnL 0.00 entry=156.75700 exit=156.76600` |
| Stored reason | 23:07:27.554 | Postgres `diagnostics.exit_reason = "profit_protection"` |

**Call chain for 1621 (source lines)**

1. `run_bot` loop (`bot_loop.py` ~802–827) wakes ~61s later (`23:06:26` → `23:07:27`).
2. `evaluate("USD_JPY")` (`bot_loop.py` 204+): `fetch_ohlcv` → `price = 156.736` (same M5 close as the open-cycle `mid=`).
3. `get_position("USD_JPY")` finds the live BUY 2 opened 61s earlier.
4. `seed_position_mfe` + `apply_profit_protection` (`profit_protection.py`).
5. Postgres snapshot at close:

   | Field | Value |
   |---|---|
   | `exit_reason` | `profit_protection` |
   | `exited_on_profit_protection` | true |
   | `original_tp_pips` | 11.64 |
   | `trigger_percent` | 0.67 → activation at **7.80 pips** |
   | `mfe_pips` / `mfe_at_activation_pips` | **11.9** |
   | `max_tp_progress` | 1.022 (MFE already past TP distance) |
   | `atr_at_activation_pips` | 3.3 |
   | `atr_giveback_at_activation_pips` | 1.65 (= 0.5 × 3.3) |
   | `protected_exit_at_activation_pips` | 10.25 (= 11.9 − 1.65) |
   | `realised_pips` (vs stored `exit_price` 156.766) | +0.9 |
   | `mae_pips` | 3.0 |

6. `sl_tp_hit` using manage mid 156.736: `156.736 <= 156.6988` is false and `156.736 >= 156.8734` is false. Weekend Sunday is false. **`protect_hit` is the branch that fired.**
7. Min-hold does not apply to profit-protection (`bot_loop.py` 249–262). Live env `MIN_POSITION_HOLD_SEC=0` anyway.
8. `close_reason = "profit_protection"` (`bot_loop.py` 319–322).
9. `execute_trade(..., execution_kind="live")` (`trading.py` 391–398) → `execute_oanda_market_close` (`oanda_exec.py` 301–321) → `_place_market_order_sync` PositionClose (`oanda_exec.py` 124–169).
10. `[CLOSE] [OANDA LIVE] ... exit=156.76600` is the **broker fill**, not the decision price. Decision price was `mid=156.736`.
11. `evaluate` `return`s. Next cycle (23:08:28) can open `1629` because local pos is gone.

**Current pips used by PP at decision time (code + logs):**

`unrealized_profit_pips(USD_JPY, BUY, 156.757, 156.736) = (156.736 − 156.757) / 0.01 = −2.1 pips`.

`should_close` is `active and current <= threshold` (`profit_protection.py` 608): **−2.1 ≤ 10.25**.

**Hypothesis (MFE 11.9):** a 61-second live BUY from 156.757 to a broker exit of 156.766 never printed +11.9 pips. 11.9 pips implies an M5 *high* ≈ 156.876. `reconstruct_mfe_from_ohlcv` counts `extreme_favourable_pips` from any candle whose `[start, start+300s]` overlaps or follows `open_time`. That high is pre-entry and/or intra-bar noise, not the position’s live MFE. The forming M5 (23:05–23:10 at a 23:06:26 open) is the only bar that both overlaps entry and still exists at 23:07:27 if incomplete candles are present; the previous completed 23:00–23:05 bar ends before entry and should be skipped if times parse as OANDA start-of-bar. The exact bar was not logged.

---

## 3. Conditions capable of closing a live position

Only three booleans in `evaluate` can request a live flatten:

1. **`sl_tp_hit`** — last included M5 **close** vs *local* SL/TP (close-only, not high/low). Proven for `1629`.
2. **`protect_hit`** — MFE ≥ 67% of original TP distance, then current pips ≤ MFE − ATR×0.5 (ratchet never loosens). Proven for `1589`, `1597`, `1621`.
3. **`weekend_flat`** — Friday, last `WEEKEND_FLATTEN_MINUTES` (default 15) before 21:00 UTC. **Ruled out** for 2026-09-20.

Then `execute_trade` live → PositionClose.

---

## 4. Why ~60 seconds

| Interval | Source | Default / live value |
|---|---|---|
| Main evaluation loop | `Config.TRADE_INTERVAL = 60` (`config.py` 49); `await asyncio.sleep(Config.TRADE_INTERVAL)` (`bot_loop.py` 827) | **60s, hardcoded** (not env) |
| Reconciliation | `RECONCILE_INTERVAL_SEC` (`app.py` 67) | live `60` — does **not** PositionClose |
| M5 candle roll | `fetch_ohlcv(..., "M5")` | 300s — these four closes happened *inside* the same M5 as the open (`mid=` unchanged) |
| Profit-protection retry | `PROFIT_PROTECTION_CLOSE_RETRY_SEC` | default 30s; first close allowed immediately |
| Min hold | `MIN_POSITION_HOLD_SEC` | live `0` |

All four gaps are 61 seconds (`:33:50→:34:51`, `:41:57→:42:58`, `:06:26→:07:27`, `:08:28→:09:29`). That is one `run_bot` sleep plus the next symbol sweep, not a separate position-management task.

---

## 5. AI / RL interaction with existing positions

**Current implementation (not the older audit memory):** when a local position exists, `evaluate` manages it and **returns** (`bot_loop.py` 225–366). Quant vote, RL gate, volatility, USD-direction, and hybrid routing do not run.

| Question | Can it close a BUY on the next minute? | Path |
|---|---|---|
| Quant no longer allows BUY? | **No** | `ai.vote` is after the existing-`pos` `return` |
| Quant proposes SELL? | **No** | Same; no flatten-on-reversal |
| RL returns SKIP? | **No** | `rl_agent.decide` not called; SKIP only blocks *new* entries (`bot_loop.py` 433–435) |
| RL returns SELL? | **No** | RL gate only blocks a *new* open when `rl_action != ai direction` (`437–444`); it does not flip or flatten |
| Strategy label changes? | **No** | `select_strategy` is new-entry only; strategy name does not set side (`decision_quality/live_path.py`) |
| Volatility becomes unsafe? | **No** | `volatility_ok` is new-entry only (`bot_loop.py` 384–386) |

`execute_trade` close-only: live closes **always** PositionClose *after* `evaluate` already chose to close. It is not a hidden “close existing before opening” on the entry path.

---

## 6. Profit-protection assessment

**Intended design (code defaults; live PP env vars unset → these defaults):**

- Enabled (`PROFIT_PROTECTION_ENABLED` default true)
- Activate at 67% of original TP distance
- Giveback = M5 ATR(14) × 0.5, clamped [0.5, 30]
- Protected exit = max(previous, MFE − giveback) — never loosens
- Does not move broker/local SL/TP
- Min-hold does **not** block a PP close

**The four trades**

| broker_id | Pair | `exit_reason` | MFE pips | 67% of TP | Threshold | Decision mid | Current pips at mid | Broker exit pips | PP involved? |
|---|---|---|---|---|---|---|---|---|---|
| 1589 | EUR_USD | `profit_protection` | 5.1 | 4.58 of 6.84 | 4.35 | 1.14800 | −0.3 | −2.0 | **Yes** |
| 1597 | EUR_USD | `profit_protection` | 4.8 | 4.63 of 6.91 | 4.0 | 1.14810 | +0.4 | −1.6 | **Yes** |
| 1621 | USD_JPY | `profit_protection` | 11.9 | 7.80 of 11.64 | 10.25 | 156.736 | −2.1 | +0.9 | **Yes** |
| 1629 | USD_JPY | `sl_tp` | 4.4 | 7.80 of 11.64 | n/a (inactive) | 156.736 | −9.6 vs fill | +0.2 | **No** |

1589 / 1597 / 1621 **did** trigger the written PP logic: MFE ≥ 67% TP and current (from manage mid) ≤ threshold. They did **not** do so because the live trade had given back 67% of a real run-up. Broker-realised excursion was −2.0 / −1.6 / +0.9 pips. MFE 5.1 / 4.8 / 11.9 is reconstructed candle-high MFE, then compared to a stale M5 close.

1629 is **not** PP. It is stale-mid SL: manage `156.736 <= local SL 156.7738`.

---

## 7. Broker SL/TP vs bot-side close

**Code proves broker SL/TP are attached on open.** `_place_market_order_open_sync` sets `stopLossOnFill` / `takeProfitOnFill` GTC (`oanda_exec.py` 190–215). `evaluate` precomputes those from the **same stale mid** (`bot_loop.py` 634–649), then **rebuilds local SL/TP from the fill** (`712–717`).

So broker protective prices and local protective prices can differ when fill ≠ mid.

**These four closes are B — explicit bot `PositionClose`.**

| Check | Result |
|---|---|
| Log wording | `[EXECUTION] BROKER_CLOSE ... (PositionClose; local mid is pre-fill only)` is emitted *before* `execute_trade` only on the manage-close branch |
| Telegram / `[CLOSE] [OANDA LIVE] exit=` | Broker PositionClose fill (`trading.py` uses `exit_px_model` from `execute_oanda_market_close`) |
| Postgres `exit_reason` | `profit_protection` or `sl_tp` from `evaluate`, not an OANDA SL/TP fill reason |
| Exit vs band | Broker fills sit inside local SL/TP; a broker SL/TP fill would print at/through those prices |
| If OANDA had already flattened | `PositionClose` would error and `evaluate` would `return` *before* `close_position`; these rows logged successful PnL/exit |

Broker SL/TP remaining on the open trade is **not** what flattened these four.

---

## 8. Mid-versus-fill (separate from the close)

`[OPEN]` logs **both**:

- `mid=` → `price = raw["close"].iloc[-1]` at `evaluate` time = last included M5 **close** (`bot_loop.py` 212, 750)
- `entry=` / `BROKER_FILL fill=` → OANDA market-open fill

They are **not** contemporaneous bid/ask vs fill. Do **not** call the gap “slippage” unless comparing the fill to a quote at send/fill time (`finalize_order_fill` metadata has `expected_mid` / `slippage_signed` against this same M5 close).

| Example | mid (M5 close) | fill | Notes |
|---|---|---|---|
| GBP_USD 1617 23:04:24 | 1.33870 | 1.33937 | 6.7 pips; local SL 1.33877 is **above** that mid |
| USD_JPY 1621 23:06:26 | 156.736 | 156.757 | 2.1 pips; **same mid still logged at close 23:07:27** |
| USD_JPY 1629 23:08:28 | 156.736 | 156.832 | 9.6 pips; same M5 still not rolled |
| EUR_USD 1589 | 1.14800 | 1.14803 | almost equal; mid unchanged at close |

`BROKER_CLOSE` repeats: “local mid is pre-fill only.” The close `exit=` on `[OANDA LIVE]` is the later PositionClose fill.

---

## 9. Safety-feature verification (current live process)

Read-only: `GET /system` (2026-09-20 23:14 UTC) + `docker compose exec` non-secret env + current source.

| Feature | Active? | Evidence |
|---|---|---|
| Six-pair universe | **Yes** | `FOREX_SYMBOLS=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`; `/system.symbols` matches |
| Live broker execution | **Yes** | `EXECUTION_MODE=live_broker`, `TRADING_MODE=live`, `PAPER_TRADING=false`, `broker_orders_enabled=true`, host `api-fxtrade.oanda.com` |
| Broker-attached SL/TP | **Yes** | `stopLossOnFill` / `takeProfitOnFill` on MarketOrder; `/system` pending orders 6 |
| Client IDs / duplicate protection | **Yes** | `generate_client_order_id` + `try_begin_order_submission`; logs `cid=cid-…`; `PERSIST_EXEC_ORDERS=1` |
| USD-direction max = 2 | **Yes** | `MAX_SAME_USD_DIRECTION_POSITIONS=2` (code default 2) |
| Portfolio gross-notional cap | **Yes** | `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV=0.06`; `/system` cap ≈ 7.82 USD on NAV 97.31 GBP |
| Portfolio risk cap | **Yes** | `MAX_PORTFOLIO_RISK_PCT=0.02` (code default 0.05 if unset; live is 0.02) |
| Volatility filter | **Yes** | `volatility_ok` still on the **new-entry** path |
| Reconciliation | **Yes** | `RECONCILE_ACTION=auto_fix`, interval 60s, last success true, mismatch 0 |
| OANDA timeout / retry / rate limit | **Yes** (defaults) | connect/read 15s, `OANDA_MAX_RETRIES` default 6, limiter default 10 rps / hard cap 120 |
| Profit protection | **Yes** (defaults) | env unset → enabled, 67%, ATR×0.5, period 14 — confirmed in `diagnostics.settings` |
| Kill / halt | Off | `/system` `kill_switch_env=false`, `halted_runtime=false` |

---

## 10. Missing logging that blocked a one-line reconstruction from Telegram alone

What **was** enough once Postgres was read: `diagnostics.exit_reason`, MFE, threshold, settings.

What Telegram / `[EXECUTION] BROKER_CLOSE` did **not** show:

- `reason=` (`evaluate` logger.info `[CLOSE] … reason=%s` exists in code but did not appear in `docker compose logs` for these events; the alert is `[CLOSE] [OANDA LIVE] … exit=<broker fill>`)
- `sl_tp_hit` / `protect_hit` / `weekend_flat` booleans
- Manage mid vs broker fill as two named fields on one line
- Last M5 bar `time` / `complete` / high / low used for seed
- Reconstructed MFE vs live unrealised pips
- Quant / RL values (correctly absent — they did not run)

Without `trades.diagnostics`, the user-visible `exit=` inside SL/TP looks like a mystery close.

---

## Worked numbers for the other two EUR_USD examples

**1589** BUY 1.14803 / SL 1.14769 / TP 1.14871. Next mid still 1.14800. TP 6.84 pips; 67% = 4.58; seeded MFE 5.1; giveback 0.75; threshold 4.35; current −0.3 → PP close. Broker fill 1.14783 (−2.0 pips), still above SL.

**1597** BUY 1.14806 / SL 1.14771 / TP 1.14875. Mid 1.14810. MFE 4.8 ≥ 4.63; threshold 4.0; current +0.4 → PP close. Broker fill 1.14790.

**1629** (not PP): mid 156.736 ≤ SL 156.7738 because local SL is fill-based (156.832 − 5.82 pips) while manage price is still the older M5 close. `close_reason` prefers `sl_tp` when both could be true (`bot_loop.py` 319).

---

## Smallest diagnostic improvement (not implemented)

Emit one machine-readable line **immediately before** `execute_trade` on the manage-close branch, using values already in scope:

```
[CLOSE DECISION] symbol=USD_JPY broker_id=1621 reason=profit_protection trigger=protect_hit
current_side=BUY proposed_side=n/a rl_action=n/a
sl_tp_hit=false weekend_flat=false protect_hit=true
manage_mid=156.736 manage_bar_time=... manage_bar_complete=...
entry=156.757 sl=156.6988 tp=156.8734
current_pips=-2.1 mfe=11.9 mae=3.0 tp_progress=1.022
pp_active=true pp_threshold=10.25 atr_pips=3.3 giveback=1.65
seed_source=ohlcv|current min_hold_sec=0 age_sec=61
```

That is sufficient to reconstruct every future live close without a Postgres join. Do not implement in this task.

---

## What is proven vs hypothesized

**Code + logs prove**

- Only `evaluate`’s existing-position branch can emit these `BROKER_CLOSE` lines.
- 1589 / 1597 / 1621 stored `exit_reason=profit_protection` with MFE ≥ 67% TP and current-from-mid below threshold.
- 1629 stored `exit_reason=sl_tp` with PP inactive; manage mid was below local SL.
- AI/RL/quant/volatility/strategy/USD-guard/halt did not participate.
- Broker SL/TP fills are not the closer.
- Timing is `TRADE_INTERVAL=60`.
- Logged `mid` is the evaluate M5 close; `[OANDA LIVE] exit=` is the PositionClose fill.

**Hypothesis (fits diagnostics, bar not persisted)**

- PP MFE is the high of an M5 candle that overlaps `open_time` (`reconstruct_mfe_from_ohlcv`), including price action from *before* the fill.
- For 1621, that is most likely the forming 23:05–23:10 bar if it was present in `raw`, or a completed bar treated as overlapping.
- Same stale M5 close is why 1629’s fill-based SL looks “already hit” one minute later even though the live market (156.834) is not near SL/TP.
