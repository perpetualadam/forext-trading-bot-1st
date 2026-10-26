# Stage R.25 — Enforced risk limits and execution safety

Classification: `R25_RISK_LIMITS_OFFLINE_ENFORCED`

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Existing dirty tree and R.24 evidence were left in place. No production configuration, strategy activation, broker contact, database service, commit, or rollback.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

## 1. Existing findings

The shared path is `evaluate` → `dispatch_production_iteration` → `evaluate_one_instrument_iteration`.

Before this stage, daily loss and drawdown existed only in `forex_bot/decision_repair/account_risk.py` and ran only when `DECISION_REPAIR_ACCOUNT_RISK` was on. That flag remains off. Its 2%, 3%, and 5% defaults were not promoted into production.

Gross notional (`MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV`, default 0) and portfolio stop-risk remain separate optional or sizing controls. They were not reused as the new account limits.

Account balance is authoritative when both balance and payload equity exist. Missing, non-finite, and non-positive equity already blocked. A missing account timestamp previously continued after setting `account_freshness_not_evaluated`.

Recovery holds already blocked before reservation: `exposure_unconfirmed`, `unresolved_intent`, and `active_reservation`.

## 2. Definitions and data sources

Daily loss. The UTC trading day comes from the injected `dependencies.now`. The baseline is the stored `day_baselines[day]` equity. Realised loss is the stored `realised_by_day[day]`. Total loss adds the injected unrealised P&L. A loss at or beyond `limit * baseline` blocks. A missing state file is not recreated and is not treated as zero.

Drawdown. The reference is the stored `peak_equity`. Current drawdown is `(peak - equity) / peak`. A new equity high is stored before the comparison. Drawdown at or beyond the configured fraction blocks.

Total exposure. Units are account-currency notional, `abs(units) * price`. The book includes open positions, PENDING, PARTIAL, and UNRESOLVED orders, plus FILLED orders only when that symbol has no open position. The proposed order is added. Equal to `equity * exposure_multiple` is allowed. Anything above it blocks. Missing price or units blocks.

Authoritative inputs are the explicit environment limits, the durable risk-state file, the accepted account snapshot, and the in-process order and position book. Missing, disabled, malformed, non-finite, stale, or unreadable inputs block. Disabled tokens are `0`, `0.0`, `off`, `disabled`, `false`, and `none`.

## 3. Source changes and hashes

| File | Change | SHA-256 |
|---|---|---|
| `forex_bot/execution_risk.py` | New fail-closed gate | `141e37e15d61806c1c3d28fb37e6cec3f9d2b5c30a25de979cc19e047799b69d` |
| `forex_bot/bot_loop.py` | Call the gate immediately before reservation | `99a69ebb3dba9d97b4a0e57f2aad01750e64e69269cc17d9ef96c29faa91beff` |
| `forex_bot/database.py` | Unchanged | `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6` |
| `forex_bot/orders.py` | Unchanged | `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4` |
| `forex_bot/app.py` | Unchanged | `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1` |
| `forex_bot/config.py` | Unchanged | `13db72c668f60a8a50bf148789070c29cb941be748a51b298bd7bcb2971f99fd` |
| `forex_bot/strategy_meta.py` | Unchanged | `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` |

Test-only files are `tests/test_r25_risk_limits.py`, `tests/r25_risk_harness.py`, `tests/r25_restart_driver.py`, and small helper updates in the R.12–R.23 offline harnesses so synthetic account freshness is explicit. Protected `bot_loop.py` pins in R.8, R.10, and R.11 match the hash above. R.15 J70 now expects `account_snapshot_timestamp_missing`.

## 4. Execution-path integration

The new phase is `execution_risk`. It runs after units and price exist and before `phases.append("reservation")`. A reason returns with `reservation_attempted` false and no broker call. A later `evaluate` reads the same state and returns the same reason.

Distinguishable reasons include `daily_loss_limit_unconfigured`, `daily_loss_limit_disabled`, `daily_loss_limit_malformed`, `daily_loss_limit_nonfinite`, `daily_loss_limit_invalid`, the same family for drawdown and exposure, `account_snapshot_timestamp_missing`, `account_unrealised_unavailable`, `daily_loss_baseline_missing`, `daily_realised_loss_limit`, `daily_total_loss_limit`, `drawdown_reference_missing`, `max_drawdown_limit`, `exposure_unreadable`, `total_exposure_limit`, `risk_state_missing`, `risk_state_unreadable`, `risk_state_malformed`, and `risk_state_inconsistent`.

Earlier account and recovery holds still return first. FILLED, UNRESOLVED, PENDING, and PARTIAL holds were not weakened.

## 5. Boundary and failure results

`tests/test_r25_risk_limits.py`: 10 passed, 0 failed, 0 skipped.

Covered: each limit inside its boundary; daily loss and drawdown exactly at and inside the boundary; exposure exactly at the cap and beyond it; missing, disabled, malformed, and non-finite limits; missing timestamp, stale snapshot, negative equity, missing unrealised; unrealised loss counted in total daily loss; open exposure plus a pending reservation; unreadable pending price; two evaluations after a failed check; failed state read; FILLED, UNRESOLVED, and PENDING holds.

## 6. Restart and persistence

`restart_trace.json` records separate OS processes.

Daily loss: writer PID 8000 recorded realised `-200` and exited. Reader PID 12188 then returned `daily_realised_loss_limit`, with 0 broker requests and no reservation.

Drawdown: writer PID 19720 evaluated at the peak and exited. Reader PID 13272 evaluated at 9400 and returned `max_drawdown_limit`, with 0 broker requests and no reservation.

A missing state file blocks with `risk_state_missing` and is not replaced by a fresh baseline.

## 7. Reservation and dispatch counts

Every blocked R.25 case recorded `reservation_attempted` false and `broker_requests` 0. The within-limit case and the exact exposure-cap case each dispatched once through the inert adapter. `production_eligible` stayed false. The drawdown writer is the only restart process that dispatched, and it did so while equity was at the stored peak.

## 8. Regression results

Final runner: `data/research/adaptive_ensemble/r25/20_run_offline_tests.py`. Every suite exit was 0.

| Suite | Result |
|---|---|
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

No failures. Skips are the pre-existing `NOT_EVALUATED` and PostgreSQL-not-evaluated markers. The one deselection is `test_h39_h40_restart_keeps_live_orders_blocked`. The historical R.10 OneDrive `WinError 5` did not recur on this run.

## 9. Unresolved limitations

There is no broker P&L ingest. Durable realised loss is written only through the explicit risk-state file.

Production has no enabled numeric thresholds. Unset limits block. The regression harness uses a synthetic peak of `1e12`, a drawdown multiple of `2`, and an exposure multiple of `1000` so older tests still reach their own assertions. Those fixtures are not live limits.

Conflicting payload equity still follows the accepted-snapshot rule from R.16. It is not a new block.

The R.24 reservation deadlock remains an outstanding engineering concern. Processes 10224 and 18916 competed for `NZD_USD`. PostgreSQL aborted one transaction after `insert_exec_order_pending_if_absent` took `pg_advisory_xact_lock` and then hit a relation deadlock between `RowExclusiveLock` and `AccessExclusiveLock` on relation 16428. The advisory lock is per symbol, while the following read and insert can still deadlock on the relation when lock order differs. No locking change was made. `database.py` is unchanged.

## 10. Classification

`R25_RISK_LIMITS_OFFLINE_ENFORCED`

All three controls have explicit definitions, synthetic inputs, fail-closed checks on the shared evaluate path before reservation, and passing offline tests including restart persistence and the R.8–R.24 regressions.

R.26 was not started.
