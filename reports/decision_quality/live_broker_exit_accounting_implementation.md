IMPLEMENTATION STATUS:
PASS

BROKER EXIT SOURCE:
OANDA_TRANSACTION

BROKER EXIT PRICE AUTHORITATIVE:
YES

BROKER REALIZED PNL AUTHORITATIVE:
YES

BROKER EXIT REASON AUTHORITATIVE:
YES

STOP LOSS ACCOUNTED:
YES

TAKE PROFIT ACCOUNTED:
YES

UNRESOLVED EXIT FAILS SAFE:
YES

DUPLICATE BOOKING PREVENTED:
YES

LIVE NAV DOUBLE-COUNT POSSIBLE:
NO

PAPER BEHAVIOUR CHANGED:
NO

LIVE MANAGEMENT PRICE LOGIC CHANGED:
NO

RUNNING DOCKER CONTAINER MODIFIED:
NO

OANDA WRITES PERFORMED:
NO

TEST RESULTS:
focused 76 passed (broker-exit accounting + reconcile + live-manage + execution-safety + logic-fixes)
full isolated suite 491 passed
1589/1597/1621/1629 live-manage regressions included and passing

---

## What changed

When `RECONCILE_ACTION=auto_fix` sees **broker flat + local broker-backed position**, Case D no longer `pop`s the slot and walks away.

New order:

1. Detect missing OpenPositions net.
2. `GET TradeDetails` for the local `broker_order_id` / `broker_trade_ids`.
3. `GET TransactionDetails` for `closingTransactionIDs[-1]`.
4. Validate the fill belongs to that trade (instrument + `tradesClosed[].tradeID`).
5. Require `state=CLOSED`, `currentUnits≈0`, real exit price, realizedPL (zero allowed), and an OANDA `reason` string.
6. Book **one** completed trade with broker price / P&L / reason / tx id.
7. Remove the local position and clear pending.

If any lookup step fails, the code **does not invent** a candle/mid close. It parks a pending-attribution record and retries on the next ~60s reconcile cycle.

## Files

| File | Change |
|------|--------|
| `forex_bot/broker_exit.py` | **new** resolver, reason map, pending state, one-shot book |
| `forex_bot/oanda_exec.py` | **new** read-only `fetch_transaction_details_sync` |
| `forex_bot/trading.py` | **new** `record_completed_trade(..., apply_equity=False)` — no `PositionClose` |
| `forex_bot/database.py` | tables `broker_exit_ledger`, `broker_exit_pending`; `log_trade_pg(closed_at=...)` |
| `forex_bot/reconciliation.py` | Case D uses attribution; retry pending; import clears pending; load on startup |
| `forex_bot/bot_loop.py` | new-entry block while attribution is pending (no manage-price change) |
| `tests/test_broker_exit_accounting.py` | **new** 2125/2133/2137/2161 + extra cases |
| `tests/test_reconcile_conflict.py` | Case D fail-safe + no live-DB writes |

Not touched: `live_manage.py`, profit-protection thresholds, RL, quant, sizing, SL/TP placement, `.env`, Docker.

## Reason map (from OANDA `ORDER_FILL.reason` only)

| OANDA reason | Local `exit_reason` |
|--------------|---------------------|
| `STOP_LOSS_ORDER`, `GUARANTEED_STOP_LOSS_ORDER` | `broker_stop_loss` |
| `TAKE_PROFIT_ORDER` | `broker_take_profit` |
| `MARKET_ORDER`, `MARKET_ORDER_TRADE_CLOSE` | `broker_manual_close` |
| `MARKET_ORDER_POSITION_CLOSEOUT`, `MARKET_ORDER_DELAYED_TRADE_CLOSE` | `broker_position_close` |
| anything else / empty | `broker_other` (empty fails closed — no book) |

Price proximity to local SL/TP is never used.

## Accounting path

`record_completed_trade` writes:

- `analytics.log_trade(realizedPL)` → trade count, win/loss, win rate, Sharpe **inputs**, analytics drawdown **inputs**
- strategy/meta PnL if the name exists
- Postgres `trades` row (`time` = broker `closeTime` when parseable)
- diagnostics: `exit_reason`, `oanda_reason`, `closing_transaction_id`, `broker_trade_id`, `realized_pl_account_ccy`, `broker_exit_source=OANDA_TRANSACTION`

It does **not** call `execute_trade` / `execute_oanda_market_close`.

`apply_equity=False` so `update_equity` is skipped. Live `current_equity()` already uses OANDA NAV; adding the same `realizedPL` would double-count. Paper Case E is unchanged (paper locals are never sent through this path).

## Idempotency

Stable key: `(closing_transaction_id, broker_trade_id)`.

- In-process set `_booked`
- Postgres `broker_exit_ledger` PRIMARY KEY (smallest schema change)
- Reload on startup via `load_broker_exit_state_from_db()`

Same close seen twice → one Postgres trade / one analytics append.

Restart: ledger hit prevents a second book. In-memory `analytics.trades` is still process-local (existing architecture — this change does not reload historical PnL into RAM).

## Failure / retry

Unresolved cases (`timeout`, missing TradeDetails, delayed tx, malformed fill, trade still OPEN, missing realizedPL, no trade id):

- Local slot is **removed from `positions`** (broker-flat is authoritative for exposure — no PP/`PositionClose` on a ghost).
- `broker_exit_pending` keeps the position snapshot.
- `broker_exit_open_blocked_reason(symbol)` blocks **live and paper** new entries on that instrument.
- Log: `[RECONCILE BROKER EXIT PENDING] symbol=… broker_id=… reason=…` at reconcile cadence, not every second.
- Next cycle retries. A later successful tx books and clears pending.
- If OpenPositions later shows a **new** net on that symbol, pending is cleared and Case C import proceeds.

No fake completed trade on lookup failure.

## Partial / netting

Production still guarantees **one local slot per symbol** and opens with `OPEN_ONLY`. That is tested, not assumed silently.

- `state != CLOSED` or `currentUnits != 0` → `trade_not_fully_closed`, no book.
- Multiple comma-separated `broker_trade_ids`: **all** must fully close before the slot is completed.
- OpenPositions flat is not treated as “one mystery transaction.”

## Logging

On success (WARNING so it reaches Docker stdout under uvicorn lastResort):

```
[BROKER EXIT] symbol=… broker_id=… transaction_id=… reason=… oanda_reason=…
entry=… exit=… units=… realized_pl=… closed_at=… source=OANDA_TRANSACTION

[RECONCILE BROKER EXIT CONFIRMED] symbol=… broker_id=… transaction_id=…
```

The old generic `Closed local broker-backed` line is no longer the only evidence. Unresolved Case D logs `awaiting broker exit tx` plus PENDING.

`[MANAGE PRICE]` INFO visibility is **not** changed (documented future: attach a root INFO handler). BUY=`closeoutBid` / SELL=`closeoutAsk` untouched.

## Tests

Four live incidents (2125/2133/2137/2161): broker disappears → tx resolved → `STOP_LOSS_ORDER` → broker exit/P&L stored → local gone → no `PositionClose` → second reconcile does not duplicate.

Also: take-profit, manual, position-closeout, unknown reason, lookup failure, delayed visibility, malformed tx, partial OPEN trade, SELL + zero P&L, missing realizedPL, two trade IDs with one still open, `log_only` unchanged, in-memory + ledger idempotency.

Live-manage 1589/1597/1621/1629 still pass.

All OANDA calls in tests are mocked. Ledger/pending SQL is stubbed so the **running** Postgres is not written.

## Safety confirmations

- Running container `forexttradingbot1st-bot-1` still **Up** from `2026-09-21 10:40:11 +0100 BST` — not rebuilt, not restarted.
- No `.env` edits.
- No deploy.

## Remaining limitations

- This code is **not in the running container** until a future rebuild the operator chooses.
- Historical 2125/2133/2137/2161 rows are **not** backfilled (no live writes this task).
- Process-local Sharpe/win-rate still start empty after a restart; Postgres is the durable ledger.
- A vanished trade with **no** local broker id stays pending and blocks that symbol until a new broker position is imported or the pending row is cleared.
- If Postgres is down, idempotency is in-memory only until the next successful ledger insert.

## Not deployed
