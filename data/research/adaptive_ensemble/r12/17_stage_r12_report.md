# STAGE R.12 — SINGLE-ITERATION OFFLINE TRADING-LOOP INTEGRATION REPORT

## 1. Executive summary

Classification: **R12_OFFLINE_SINGLE_ITERATION_INTEGRATED**.

The real gate functions ran through `evaluate_one_instrument_iteration` with fake dependencies. A blocked permission path sent nothing to the fake broker. A simulated BUY and a simulated SELL reserved an in-memory order and reached `FakeBroker.submit` once. Outcome classification ran. R.8, R.9, R.10, and R.11 regressions passed. `run_bot` did not run. The normal launcher did not run. There were no broker requests, no network successes, and no PostgreSQL connections.

| Gate | Result |
| --- | --- |
| A Trace | SOURCE-REVIEWED |
| B Seam | CODE MODIFIED |
| C Fakes | SYNTHETICALLY TESTED |
| D Permission and strategy | PASS |
| E Market data | PASS, with recorded source gaps |
| F Risk and sizing | PASS, formulas unchanged |
| G Reservation | PASS |
| H Outcomes | SIMULATED BROKER DISPATCH |
| I Termination | PASS |
| J Tests | 123 collected, 118 passed, 5 skipped |
| K Isolation | PASS |
| L Integrity | PASS |

R.12 tests: collected 123, executed 118, passed 118, failed 0, skipped 5, NOT_EVALUATED 5 (J119–J123).

Recommended next action: stop. Do not start R.13.

## 2. Safety and scope

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

The edit is confined to `forex_bot/bot_loop.py`, new tests, and the hash pins that name `bot_loop.py`. Strategy objects, live-order authorisation, risk formulas, and broker execution code were not changed.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The r12 directory was absent before this stage. Pre-stage hashes matched. Protected files are unchanged.

## 4. Actual trading call graph

SOURCE-REVIEWED. `run_bot` is an infinite loop at line 2595 and was not called. `_evaluate_impl` loads real candles, manages an open position, then checks exposure, live permission, strategy, direction, size, reservation, and only then `execute_oanda_market_open`. The line-level order is in `02_actual_loop_call_graph.md`.

## 5. Single-iteration seam

CODE MODIFIED. `evaluate_one_instrument_iteration` calls those existing gates and returns one result. It does not sleep or schedule. Production `run_bot` does not yet delegate to it.

ACTUAL DECISION CODE EXECUTED WITH FAKE DEPENDENCIES.

## 6. Fake dependencies

Synthetic candles, a fixed clock, an injected vote, injected strategy flags, an injected balance, the existing in-memory reservation book, and `FakeBroker`. No OANDA client, no PostgreSQL, no market download.

## 7. Permission and strategy gates

The live-order gate blocks the normal path before the fake broker. Inactive, unknown, and missing strategies stop before sizing. Invalid, blank, and `NO_TRADE` directions stop at the direction gate. Simulated BUY and SELL reach the fake broker only inside the test harness. The six production strategies stay inactive. The production permission file was not written.

## 8. Market data and decision path

Empty candles, a missing close, and a non-finite price stop. Invalid timestamps and stale bars are hidden behind `missing_provenance` on an unsealed frame. Excessive spread, a malformed spread, and a short lookback are not hard blocks in the current source. A second symbol is stopped by the portfolio stop-risk cap. Session close and Friday flatten stop a new entry.

## 9. Risk and position sizing

`position_sizing` is the function that ran. Zero and negative balances do not dispatch. The unit cap and the gross notional cap are off by default. The portfolio stop-risk cap is on. Daily-loss and drawdown controls stay behind `DECISION_REPAIR_ACCOUNT_RISK` and were not enabled.

## 10. Reservation and dispatch

`try_begin_order_submission` reserves one in-memory order and the fake broker records one request. Duplicate client ids, pending, partial, unresolved, and historical FILLED holds do not dispatch. A persistence failure fail-closes before dispatch. A second client id does not bypass a hold.

## 11. Fake broker outcomes

SIMULATED BROKER DISPATCH. FILLED does not mean flat. Partial, timeout, ambiguous, and malformed responses keep an exposure hold. Rejection releases the reservation. No second request is created after an uncertain result. A fake flat token does not clear the hold. No close request was sent. Historical FILLED recovery still blocks after a synthetic restart snapshot.

## 12. Termination and cleanup

One iteration returns. Nothing is scheduled. The fake broker is closed, including after an exception. Repeated runs match. No production permission mutation, no real order, and no database connection.

## 13. Source modifications

`bot_loop.py` changed from `9fbb8c32…` to `e63696df64b5f8591eabec4747f1d05d486906342a6841f2c1d1e8266f6083c5`. `app.py`, `database.py`, and `orders.py` did not change. R.8, R.10, and R.11 hash pins were updated to the new `bot_loop.py` digest.

## 14. Test isolation

A raising socket subclass blocked `AF_INET`, `AF_INET6`, and `AF_UNIX`. DNS lookups raise. `dotenv` is stubbed. The r12 process recorded 2 blocked socket or DNS attempts and 1 dotenv stub call. Regression recorded 5 and 1. R.10 recorded 5 and 1. R.11 recorded 4 and 1. No Windows socket exception was allowed through.

## 15. Integration test results

J01–J118 PASS. J119–J123 NOT_EVALUATED. The per-test ledger is `12_integration_test_results.json`.

## 16. R.8–R.11 regressions

R.4–R.9: 120 passed, 7 skipped, 1 deselected. R.10: 69 passed, 5 skipped. R.11: 51 passed, 5 skipped. Pending, partial, unresolved, FILLED exposure, missing-position, and historical FILLED holds still block.

## 17. Remaining defects

The continuous loop does not call the seam. Synthetic data is not a live provenance seal. Spread and short lookback are not hard blocks. The default unit cap and gross notional cap are off. Daily-loss and drawdown checks are off. `confirm_exposure_flat` still treats the token `CONFIRMED_FLAT` as sufficient if another caller uses it. PostgreSQL and OANDA were not exercised.

## 18. Next three priorities

1. Keep the production loop unwired until a later authorised review.
2. Decide, without forging a live seal, how an explicitly synthetic frame should be labelled.
3. Leave the PostgreSQL engine test blocked until an isolated engine is separately authorised.

## 19. Recommended next stage

No next stage should start from this result. The offline seam is not a trading authorisation.

## 20. Final integrity

No launcher, no `run_bot`, no OANDA client, no broker request, no PostgreSQL connection, no Telegram or Discord connection, no DNS success, no `.env` read, no production permission change, no strategy activation, no package install, no Docker, no migration, and no git commit.

## 21. Final classification

**R12_OFFLINE_SINGLE_ITERATION_INTEGRATED**

This classification means the offline seam ran real decision gates and one fake broker dispatch. It does not mean the production loop, the broker, PostgreSQL, profitability, or live trading was verified.

## 22. Hard stop

R.12 is finished. R.13 does not start. `main.py` stays unrun. The lifespan stays unentered. `run_bot` stays uncalled. Strategies stay inactive. Live orders stay blocked. OANDA is not contacted. PostgreSQL is not started. Nothing is deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
