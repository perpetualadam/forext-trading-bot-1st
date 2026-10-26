# STAGE R.13 — OFFLINE PRODUCTION-LOOP WIRING AND EXPOSURE-RELEASE SAFETY REPAIR REPORT

## 1. Executive summary

Classification: **R13_OFFLINE_LOOP_WIRED_AND_RELEASE_SAFE**.

`_evaluate_impl` and `evaluate` both call `dispatch_production_iteration`, which delegates to `evaluate_one_instrument_iteration`. The offline driver executed that boundary. Simulated BUY and SELL each reached `FakeBroker` once. A plain `CONFIRMED_FLAT` token no longer clears uncertain exposure. `run_bot` did not run. The launcher did not run. Broker requests, network successes, and PostgreSQL connections are zero.

| Gate | Result |
| --- | --- |
| A Trace | SOURCE-REVIEWED |
| B Shared path | SHARED PRODUCTION PATH WIRED |
| C Driver | OFFLINE DISPATCH BOUNDARY EXECUTED |
| D Flat-token repair | CODE MODIFIED |
| E Release failures | SYNTHETICALLY TESTED; success NOT_EVALUATED |
| F Prior regressions | PASS |
| G Tests | 87 collected, 81 passed, 6 skipped |
| H Isolation | PASS |
| I Discipline | PASS |
| J Integrity | PASS |

R.13 tests: collected 87, executed 81, passed 81, failed 0, skipped 6, NOT_EVALUATED 6 (G41, G83–G87).

Recommended next action: stop. Do not start R.14.

## 2. Safety and scope

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

Edits are in `bot_loop.py` and `database.py`, plus tests and hash pins. Strategy defaults, risk formulas, sizing formulas, and `oanda_exec.py` were not changed.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The r13 directory was absent. Pre-stage hashes matched. Protected files are unchanged.

## 4. Production versus offline call graph

Before this stage, `run_bot` reached `_evaluate_impl`, and tests reached `evaluate_one_instrument_iteration` separately. The new-entry broker call lived only in `_evaluate_impl`.

After this stage, a new entry in `_evaluate_impl` calls `dispatch_production_iteration`. The offline driver calls `evaluate(symbol, dependencies)`, which calls the same function and does not enter the candle fetch or the loop. The old `execute_oanda_market_open` tail remains in source and is not reached, because the shared decision does not return the continuation sentinel.

## 5. Shared decision refactor

SHARED PRODUCTION PATH WIRED. There is one decision implementation. Production dependencies use `simulation=False` and no broker. Test dependencies may set `simulation=True` and a `FakeBroker`. The live-order gate, inactive-strategy gate, direction gate, sizing, exposure holds, and reservation logic are the existing functions.

## 6. Offline loop driver

OFFLINE DISPATCH BOUNDARY EXECUTED. G01–G20 passed through `dispatch_production_iteration`. Permission block produced zero fake requests. BUY and SELL produced one each. The coroutine driver does not schedule another iteration. This is not a continuous-loop run.

## 7. Exposure-release trust boundary

CODE MODIFIED. `confirm_exposure_flat` returns false for every caller-supplied argument. It does not query a broker and it does not delete the hold. No fake authority object was added.

## 8. Release failure tests

SYNTHETICALLY TESTED. Token, flag, dictionary, fake response, wrong symbol, stale data, incomplete data, conflicting quantities, timeouts, rejections, partial closes, a missing position object, and repeated attempts all leave the hold. Authoritative release is NOT_EVALUATED.

## 9. R.8–R.12 regressions

R.4–R.9: 120 passed, 7 skipped, 1 deselected. R.10: 69 passed, 5 skipped. R.11: 51 passed, 5 skipped. R.12: 118 passed, 5 skipped. The R.9 flat-token test now requires the hold to remain.

## 10. Source modifications

`bot_loop.py` is now `2585b550085e47b84dd0d353b207709797d28abca28b7bb1ee4d3e956c0c8732`. `database.py` is now `53e1e81827d6456743a1154d1636c05e6acbcfb340dae438912900c46c2d0ff4`. `app.py` and `orders.py` are unchanged.

## 11. Test isolation

Raising socket subclass. No `AF_INET`, `AF_INET6`, or `AF_UNIX`. R.13 recorded 3 blocked attempts and 1 dotenv stub call. Regression recorded 5 and 1. R.10 recorded 5 and 1. R.11 recorded 4 and 1. R.12 recorded 2 and 1.

## 12. Integration test results

G01–G40 and G42–G82 PASS. G41 and G83–G87 NOT_EVALUATED. The ledger is `09_integration_test_results.json`.

SIMULATED BROKER DISPATCH occurred only inside the fake broker. Real broker request count is zero.

## 13. Remaining defects

The continuous loop was not run. The old broker tail is not reached. Strategy selection, the live AI vote, and RL are not inside the shared function. No broker-flat release exists. Recovery SQL can still omit a row whose stored marker is `CONFIRMED_FLAT`. PostgreSQL and OANDA were not exercised.

## 14. Next three priorities

1. Leave `run_bot` unwired to a live broker until a separate authorisation.
2. Do not invent an offline flat-release authority.
3. Keep the PostgreSQL engine test blocked until an isolated engine is authorised.

## 15. Recommended next stage

No next stage should start from this result. Wiring the offline boundary is not permission to trade.

## 16. Final integrity

No launcher, no lifespan, no `run_bot`, no OANDA client, no broker request, no PostgreSQL connection, no messaging connection, no DNS success, no `.env` read, no strategy activation, no production permission change, no package install, no Docker, no migration, and no git commit.

## 17. Final classification

**R13_OFFLINE_LOOP_WIRED_AND_RELEASE_SAFE**

This means the production dispatch boundary calls the shared decision, the offline driver executed that boundary, and a caller-supplied flat token cannot clear exposure. It does not mean the continuous loop ran, PostgreSQL was engine-tested, broker reconciliation occurred, or a legitimate exposure release was verified.

## 18. Hard stop

R.13 is finished. R.14 does not start. `main.py` stays unrun. The lifespan stays unentered. `run_bot` stays uncalled. Strategies stay inactive. Live orders stay blocked. OANDA is not contacted. PostgreSQL is not started. Nothing is deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
