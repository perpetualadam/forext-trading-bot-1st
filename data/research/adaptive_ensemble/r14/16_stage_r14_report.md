# STAGE R.14 — OFFLINE PRODUCTION DECISION-PATH CONTINUITY AND AI/RL INTEGRATION REPAIR REPORT

## 1. Executive summary

Classification: `R14_OFFLINE_DECISION_PATH_INTEGRATED`.

Gates A–K passed within the offline scope. `forex_bot/bot_loop.py` is the only application module modified. R.14 tests: 148 collected, 143 executed, 143 passed, 0 failed, 5 skipped. The five skips are J143–J147 and are NOT_EVALUATED. The ledger has 142 PASS and 5 NOT_EVALUATED.

The actual strategy selector, the actual `AIEnsemble.vote` wrapper, and the actual `RLAgent.decide` veto ran on the shared path. Synthetic BUY and SELL each reached FakeBroker once. An RL SKIP blocked dispatch. Permission and exposure holds blocked dispatch. Exactly one production execution adapter is source-reachable and was not invoked. The legacy tail cannot dispatch. `run_bot` did not execute. The launcher did not execute. Real broker requests: 0. Network successes: 0. PostgreSQL connections: 0.

Recommended next action: stop. Do not start R.15.

## 2. Safety and scope

No application start, no lifespan, no `run_bot`, no OANDA client, no PostgreSQL, no `.env` read, no network success, no DNS success, no package install, no Docker, no migration, no deployment, and no git commit. Production deployment remains NO-GO. Practice orders and live trading are not authorised. Rollback is NO-GO.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. Pre-stage hashes matched. The R.14 directory was absent at the start. Protected files are unchanged.

## 4. Source continuity trace

SOURCE-REVIEWED. `evaluate` with dependencies returns `dispatch_production_iteration`. `_evaluate_impl` calls that same boundary and returns unless the status is `continue_existing_production_broker`. The shared function never returns that status. The old tail was therefore unreachable. Its direct broker call has been removed.

## 5. Shared decision refactor

CODE MODIFIED. The shared function calls `select_strategy` or `select_deterministic`, `AIEnsemble.vote`, and `RLAgent.decide` when the scenario reaches those stages. Permission, position, and exposure stay before them. The fake broker is the only test dispatch.

## 6. Actual strategy selection

ACTUAL STRATEGY SELECTOR EXECUTED. The six names are inactive labels and lookback choices. They are not six independent signals. Production activation flags were not changed.

## 7. Actual AI vote

ACTUAL AI VOTE EXECUTED. The production wrapper aggregated the injected voter. Empty voters fail closed. A non-canonical supplied direction is rejected before the ensemble's BUY tie-break can be traded.

## 8. Actual RL veto

ACTUAL RL VETO EXECUTED. The existing `decide` method is a simple action veto. It has no confidence. SKIP and a conflicting side stop the order before reservation.

## 9. Offline end-to-end tests

SIMULATED BROKER DISPATCH. BUY and SELL reached FakeBroker once through the existing gates. Veto, permission, exposure, reservation, and invalid votes did not. A missing account still follows the existing equity fallback and is not a new hard block.

## 10. Execution adapter continuity

PRODUCTION EXECUTION CONTINUITY: SOURCE-VERIFIED ONLY. One `execute_oanda_market_open` reference, inside `production_execution_adapter`. It was not called. This is not broker-verified.

## 11. Exposure safety

Caller-supplied CONFIRMED_FLAT tokens, verified flags, and fabricated dictionaries do not release. Historical FILLED and open reservations hold. No new flat-release authority. Broker-flat release is NOT_EVALUATED.

## 12. Source modifications

`bot_loop.py` post-stage hash `91953e58f9ab131399dd3ec84ebd5217161cfbc773022b42a58154597639528f`. Hash pins in the R.8, R.10, and R.11 tests were updated. Two source-order assertions now require the legacy tail to contain no broker open. That is a stronger check.

## 13. Test isolation

Socket and DNS barriers stayed in place. Blocked constructor attempts: R.14 1, regression 5, R.10 5, R.11 4, R.12 2, R.13 3. Each suite recorded one dotenv stub call. No network or DNS success.

## 14. Integration test results

R.14: 143 passed, 5 skipped. Selector evidence on 90 records, vote wrapper on 73, RL veto on 60. Summed fake requests across tests: 44. Production adapter invocations: 0.

## 15. R.8–R.13 regressions

Regression 120 passed, 7 skipped, 1 deselected. R.10: 69/5. R.11: 51/5. R.12: 118/5. R.13: 81/6. No failures.

## 16. Remaining defects

A permission-blocked production call returns before the selector, vote, and veto. Those functions run on the offline continuation of the same shared function. The legacy classification code remains unreachable. Missing account data is not a hard block. Strategies are not independent. RL has no timeout of its own.

## 17. Next three priorities

1. Keep the broker adapter uncalled until a separately authorised broker test exists.
2. Decide later whether a permission-blocked production call should record selector, vote, and RL without dispatching.
3. Leave broker-flat release unimplemented until there is an authorised broker-flat source.

## 18. Recommended next stage

Do not begin another stage from this result. The next stage needs a separate authorisation. It should not be a trading start.

## 19. Final integrity

SHARED PRODUCTION PATH WIRED. SIMULATED BROKER DISPATCH. PRODUCTION EXECUTION CONTINUITY SOURCE-VERIFIED ONLY. PostgreSQL, OANDA, the production loop, broker-flat release, and profitability are NOT_EVALUATED.

## 20. Final classification

`R14_OFFLINE_DECISION_PATH_INTEGRATED`

This does not mean the continuous loop ran, production market data was used, PostgreSQL was engine-tested, OANDA was contacted, real broker execution was tested, broker-flat release works, the strategies are independent or profitable, or trading is authorised.

## 21. Hard stop

STOP. R.15 is not started. `main.py` was not run. The production lifespan was not entered. `run_bot` was not executed. Strategies were not activated. Live orders were not enabled. OANDA was not contacted. PostgreSQL was not started. Nothing was deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
