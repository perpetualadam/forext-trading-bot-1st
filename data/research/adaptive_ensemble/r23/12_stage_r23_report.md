# STAGE R.23 — PROCESS-RESTART VERIFICATION AND OFFLINE-STORE ISOLATION REPORT

## 1. Classification

`R23_OFFLINE_PROCESS_RESTART_AND_STORE_ISOLATED`

## 2. Safety and scope

No production launcher, lifespan, `run_bot`, OANDA client, broker order, PostgreSQL connection, network success, credential read, or deployment. Two short-lived local Python processes ran the offline driver only. The dirty tree was preserved. Git was not committed, reset, or rolled back.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. `r23` was absent at the start. The pre-edit `database.py` hash was `c6f761104a3ff3fb36a23aa0e90a9f6516c4c802ed233319151c2b27875ff563`. R.22 had recovered inside one interpreter, and the JSON store was selected by `EXEC_ORDER_OFFLINE_STORE` alone.

## 4. Process A and Process B

The parent launched the interpreter directly, waited for Process A to exit, then launched Process B. Each child installed socket, DNS, and dotenv barriers before importing the application. Process B used `initialise_application`, which calls `read_offline_exec_orders`, `select_rows_for_recovery`, and `ingest_recovery_snapshot`.

## 5. FILLED restart result

Process A PID 820 exited 0 and dispatched once. Process B PID 9832 exited 0, recovered FILLED order `cid-086196846cdf4a4ba2ed12707ffebd29` from `db_recovery`, and blocked on `exposure_unconfirmed` with zero dispatches. Store SHA-256 `91393e0804234d3ee8cbf08bc3d3e14711f9054cc995fb9ae1e2de18a1277010`.

## 6. UNRESOLVED restart result

Process A PID 3108 exited 0 and dispatched once. Process B PID 14156 exited 0, recovered UNRESOLVED order `cid-10870c09a18248e08d9f9018452fa07c`, and blocked on `exposure_unconfirmed` with zero dispatches. Store SHA-256 `503ff813487288aff6e1bdf05a1d5f30585af1817ac26094a33a52a520b3daf0`.

| Scenario | Separate processes | Recovered status | Process B dispatches | Result |
|---|---|---|---|---|
| FILLED | Yes | FILLED | 0 | PASS |
| UNRESOLVED | Yes | UNRESOLVED | 0 | PASS |

## 7. Offline-store selection boundary

`offline_exec_order_store_path` returns only an armed path. The environment variable does not select the store. Arming requires context `isolated_offline_test` and a path under the R.22 or R.23 research directory. A production-eligibility flag is ignored. Production sources do not arm the store. The JSON record does not make production eligibility true.

## 8. Negative isolation tests

Missing, corrupt, truncated, unreadable, and duplicate stores fail closed. A write failure refuses dispatch. Traversal and paths outside the approved roots are refused. A stale variable and a production context do not arm the store. The production adapter rejects a synthetic decision, a reused decision, and a forged eligibility flag with zero broker-stub calls.

## 9. Source changes

Application change: `forex_bot/database.py`, post-stage SHA-256 `e543a84e0a137fbd2387a5e1b85aad52b71988a4abf2bfd0f1ddb7afe217e064`.

`bot_loop.py` remains `a8b455dad91c464df8ba030b7f119f3c1795ce289e21b83de0af771309823ac2`. `orders.py` remains `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4`. `app.py` remains `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1`.

The R.22 tests now arm the store. The R.10 database hash pin matches the new file. Safety assertions were not weakened.

## 10. R.23 test results

15 passed, 0 failed, 0 skipped, 0 deselected, exit 0. Parent barrier: 3 blocked attempts, 1 dotenv stub. Broker calls 0. PostgreSQL connections 0.

## 11. R.8–R.22 regressions

All exited 0. Regression 120 passed, 7 skipped, 1 deselected. R.10 69/5. R.11 51/5. R.12 118/5. R.13 81/6. R.14 143/5. R.15 165/6. R.16 135/6. R.17 174/9. R.18 203/9. R.19 213/9. R.20 30. R.21 24 on its own runner. R.22 20 on its own runner. No `WinError 5`.

## 12. Remaining gaps

JSON recovery is not PostgreSQL durability and is not broker integration. The production process was not started; the production boundary is the selection function and the source check. The historical R.10 file-replace denial remains a known limitation and did not recur. Standing eligibility gaps remain, and production eligibility stayed false.

## 13. Recommended next milestone

A later stage can decide whether a real PostgreSQL recovery proof is in scope. This stage does not authorise that work.

## 14. Final integrity

Classification `R23_OFFLINE_PROCESS_RESTART_AND_STORE_ISOLATED`. Both scenarios used distinct processes, recovered through application startup, and blocked the second order. The environment variable cannot select the JSON store. No prohibited operation occurred.

## 15. Hard stop

**STOP.**

Do not begin R.24. Do not run `main.py`, `run_bot`, or the production lifespan. Do not contact OANDA. Do not place practice or live orders. Do not start or connect to PostgreSQL. Do not deploy or migrate databases. Do not enable live trading. Do not roll back.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

**END OF STAGE R.23**
