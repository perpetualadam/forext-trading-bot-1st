# STAGE R.24 — OFFLINE STARTUP RECOVERY FAIL-CLOSED REPAIR REPORT

## 1. Classification

`R24_OFFLINE_RECOVERY_FAIL_CLOSED_REPAIRED`

## 2. Baseline integrity

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The four application hashes matched the R.23 baseline before the edit. Existing R.24 plans and diagnoses were left in place.

## 3. Defect reproduction

`load_open_orders_from_db_into_memory` already blocked `evaluate` when the inert connection was missing. `read_durable_recovery` and a raised `fetch_exec_orders_open_for_recovery` did not set `_process_fail_closed`. `evaluate` then passed the exposure gate. A successful empty query was already `[], True`, distinct from `[], False`.

## 4. Repair summary

Those two recovery functions now fail-close on a missing connection or a failed query, and clear only that flag after a readable recovery completes. Exposure holds stay. `evaluate` already honours the flag and returns `recovery_unreadable` before reservation.

## 5. Scenario results

| Outcome | `evaluate` |
|---|---|
| Connection unavailable | `recovery_unreadable`, no reservation, no dispatch |
| Query failure | `recovery_unreadable`, no reservation, no dispatch |
| Explicit `[], False` | `recovery_unreadable`, no reservation, no dispatch |
| Empty success | Not `recovery_unreadable` |
| FILLED | `exposure_unconfirmed` |
| UNRESOLVED | `exposure_unconfirmed` |
| PENDING and PARTIAL | `active_reservation` |

A later readable recovery clears the failure flag and leaves a genuine FILLED hold in place. `confirm_exposure_flat` does not clear the failure. Repeated evaluations stay blocked.

## 6. R.24 tests

14 passed, 0 failed, 0 skipped, 0 deselected, exit 0.

## 7. R.8–R.23 regressions

All exited 0. Regression 120 passed, 7 skipped, 1 deselected. R.10 69/5. R.11 51/5. R.12 118/5. R.13 81/6. R.14 143/5. R.15 165/6. R.16 135/6. R.17 174/9. R.18 203/9. R.19 213/9. R.20 30. R.21 24. R.22 20. R.23 15.

## 8. Source hashes

`forex_bot/database.py` changed from `e543a84e0a137fbd2387a5e1b85aad52b71988a4abf2bfd0f1ddb7afe217e064` to `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6`.

`bot_loop.py`, `orders.py`, and `app.py` are unchanged.

## 9. Safety and isolation

Broker calls: 0. PostgreSQL connections: 0. The one `psycopg2.connect` call in the tests was the patched refusal. Network and DNS successes: 0. `.env` was not read. The production lifespan, `run_bot`, and OANDA were not entered. Production eligibility stayed false.

## 10. Remaining PostgreSQL blocker

The approved binaries are still `postgres` 18.1 and `initdb` 18.0. No isolated cluster exists. This repair does not prove PostgreSQL persistence or recovery against a server.

## 11. Final integrity

The offline failure path was reproduced and repaired. Empty success stays distinct. Outstanding exposure still blocks. Prior offline regressions passed. No prohibited operation occurred.

## 12. Hard stop

**STOP.**

Do not resume PostgreSQL execution. Do not repair or reinstall PostgreSQL. Do not start R.25. Do not run `main.py`, `run_bot`, or the production lifespan. Do not contact OANDA. Do not place practice or live orders. Do not deploy. Do not roll back.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

**END OF R.24 OFFLINE RECOVERY FAIL-CLOSED REPAIR**
