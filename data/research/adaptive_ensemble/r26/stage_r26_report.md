# Stage R.26 — Broker account reconciliation and durable risk data

Classification: `R26_BROKER_RISK_RECONCILIATION_OFFLINE_INTEGRATED`

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. R.25 evidence and the dirty tree were left in place. No OANDA connection, production configuration, strategy activation, database service, commit, or rollback.

This classification covers synthetic injected snapshots only. Live OANDA account data was not validated.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

## 1. Existing broker-data findings

`fetch_account_summary` in `forex_bot/oanda_client.py` is a live GET of AccountSummary. It was not called. It treats NAV as equity and substitutes `balance` when NAV is missing. The reconciliation boundary does not use that substitution.

The shared path is `evaluate` → `dispatch_production_iteration` → `evaluate_one_instrument_iteration`. R.25 `execution_risk` runs immediately before reservation. Account balance remains the accepted sizing equity when both balance and a payload equity field exist. There is no broker transaction ledger in this repository. Open positions and orders used by R.25 exposure live in process memory unless a durable book is stored.

## 2. Field definitions and unresolved contracts

| Field | Meaning | Source |
|---|---|---|
| Account id and currency | Must match the expected id, the expected currency, and the durable state | Injected snapshot |
| NAV | Broker equity used for daily loss, drawdown, and the exposure cap | Snapshot `NAV`. Balance is stored and is not substituted |
| Balance | Separate cash figure | Snapshot `balance` |
| Unrealised | Open-position P&L in account currency | Snapshot `unrealised` or `unrealizedPL`. Missing is not zero |
| Realised | Sum of accepted `trade_pl` events and exact reversals, by UTC day | Durable `realised_by_day` |
| Day baseline | Stored day-start equity. An explicit `day_start_nav` may fill a missing day. A different value conflicts | Durable state |
| Peak | Highest accepted NAV. Later snapshots may raise it and cannot lower it | Durable `peak_equity` |
| Exposure | Account-currency notional of reconciled positions and outstanding orders, plus the proposed order | Snapshot positions and orders |

Unresolved, and therefore not invented:

- This repository does not define an OANDA identity such as `NAV == balance + unrealizedPL`. Differing NAV and balance are kept. A second equity field that disagrees with NAV is a conflict.
- Transaction names such as ORDER_FILL, DAILY_FINANCING, and TRANSFER_FUNDS are not parsed. Financing, fees, transfers, and unknown amounts fail closed with `pnl_classification_unresolved`.
- Sequence gaps are enforced only when an event or snapshot carries sequence information. Absent sequence evidence is recorded and is not treated as proof of a complete ledger.
- The live fetch path still substitutes balance for a missing NAV. That function was left unchanged and is outside this boundary.

## 3. Reconciliation and durable state

`forex_bot/account_reconciliation.py` accepts only `provenance = injected_synthetic`. It validates identity, currency, timestamp, finite values, and snapshot order, then plans the whole event batch. One temp-file write plus `os.replace` publishes the document. A validation failure or a held `.lock` file does not write. Duplicate event ids do not change totals. A repeated identical snapshot does not lower the peak. A missing or corrupt state file is not replaced with a flat book.

The offline harness attestation is `synthetic_offline`. It lets the existing R.25 suites reach their own assertions. It is not a broker feed. Production state without that attestation, or without a verified snapshot, blocks with `account_unreconciled`.

## 4. Source hashes

| File | Role | SHA-256 |
|---|---|---|
| `forex_bot/account_reconciliation.py` | New boundary | `73e2b24bb17f576c5eabb1e4a730483ef89c87d8e419034a5a9c7bf2b4f7164a` |
| `forex_bot/execution_risk.py` | Before `141e37e15d61806c1c3d28fb37e6cec3f9d2b5c30a25de979cc19e047799b69d`; after the attestation, durable exposure, and file lock | `8ffa0ef4b38ded1f0aa72362352d0935f43071b4df85f4531be014c889d09661` |
| `forex_bot/bot_loop.py` | Before `99a69ebb3dba9d97b4a0e57f2aad01750e64e69269cc17d9ef96c29faa91beff`; reconciliation phase added before `execution_risk` | `dc7c229fe09c9c2adafdcc1ed4c96c9ad534a67758773069049d3d4c5ce02683` |
| `forex_bot/oanda_client.py` | Unchanged | `6d7d5d2b6ce1c228af0629c3e2a8b674b02965c57d1a3ed41c3b4015e531ca2b` |
| `forex_bot/database.py` | Unchanged | `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` |

## 5. Evaluate integration

The new phase is `account_reconciliation`. It runs after the existing account, strategy, and recovery gates and before `execution_risk` and `reservation`. A verified snapshot supplies NAV, unrealised P&L, and its timestamp to `entry_risk_block`. Balance remains available for the earlier sizing gate and is not copied over NAV. Blocked results leave `reservation_attempted` false.

## 6. Account, P&L, and exposure results

`tests/test_r26_broker_reconciliation.py`: 9 passed, 0 failed, 0 skipped.

Covered: valid account and currency; wrong account; wrong currency; missing NAV while balance is present; stale and future snapshots; non-finite and contradictory equity; duplicate and older snapshots; save failure; new, duplicate, and reordered events; sequence gaps; financing, fees, transfers, and corrections; reversals; exact and beyond daily-loss and drawdown boundaries; a new peak and a later decline; open, pending, partial, unresolved, and filled-already-in-position exposure; missing and stale conversion prices; converted USD_JPY notional; a proposed order at and above the cap; repeated evaluation after a failed check; corrupt and missing state; a held lock. FILLED exposure holds still return `exposure_unconfirmed` before reconciliation.

## 7. Separate-process restart

`restart_trace.json`:

- Loss: writer PID 20428 stored realised `-200` and exited. Reader PID 8772 returned `daily_realised_loss_limit` with 0 broker requests.
- Drawdown: writer PID 11464 raised the peak to `11000` and exited. Reader PID 7348 returned `max_drawdown_limit`. The peak stayed `11000`.
- Exposure: reader PID 13800, started after the writer exited, returned `total_exposure_limit` from the stored pending order `pend-restart`.
- Duplicate: reader PID 10576 replayed the same event. Realised stayed `-50` and the ledger kept one event id.

## 8. Reservation and dispatch

Every blocked case recorded `reservation_attempted` false, `broker_requests` 0, and `production_eligible` false. Allowed synthetic cases dispatched once through the inert adapter, including the drawdown writer at the new peak and the duplicate replay. `production_eligible` stayed false.

## 9. Regressions

Runner: `data/research/adaptive_ensemble/r26/20_run_offline_tests.py`. Every suite exit was 0. No failures.

| Suite | Result |
|---|---|
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 regression | 120 passed, 7 skipped, 1 deselected |
| R.10 | 69 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

Skips are the existing `NOT_EVALUATED` markers. The deselection is `test_h39_h40_restart_keeps_live_orders_blocked`.

## 10. Remaining blockers

Live OANDA account and transaction data have not been read. Financing, fees, and cash transfers have no authoritative inclusion rule, so they block. Sequence continuity is enforced only when the injected records carry sequence numbers. The live AccountSummary helper still substitutes balance when NAV is absent; the new boundary does not call it.

The R.24 reservation deadlock remains open. Processes 10224 and 18916 competed for `NZD_USD`, and PostgreSQL aborted one transaction inside `insert_exec_order_pending_if_absent` on a `RowExclusiveLock` / `AccessExclusiveLock` deadlock. No locking change was made.

No production risk thresholds were enabled. R.27 was not started.
