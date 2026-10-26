# STAGE R.19 — OFFLINE PRODUCTION-DATA CONTRACT MAPPING AND EXECUTION-ADAPTER BOUNDARY ENFORCEMENT REPORT

## 1. Executive summary and classification

Classification: `R19_OFFLINE_ADAPTER_BOUNDARY_GUARDED`.

Gates A–M: A source-reviewed; B code modified and fail-closed; C actual adapter invoked with the broker substituted; D in-process binding guarded, restart durability NOT_EVALUATED; E account contract mapped; F market contract mapped; G margin missing and spread unapproved; H isolation held; I both tracks executed; J isolation held; K 178 PASS, 35 PARTIAL, 9 NOT_EVALUATED, 0 FAIL; L R.8–R.18 passed; M integrity held.

Application source modified: `forex_bot/bot_loop.py`.

R.19 tests: 222 collected, 213 executed, 213 passed, 0 failed, 9 skipped.

The actual `production_execution_adapter` was invoked offline. The real `execute_oanda_market_open` was replaced before invocation. The inert broker substitute was called 0 times. Real broker calls: 0.

Forged eligibility was rejected. Synthetic eligibility was rejected. A changed order intent was rejected. A stale decision was rejected. An in-process reused decision was rejected. No production-eligible decision was generated.

Synthetic BUY and SELL still reached the shared FakeBroker once. The actual strategy selector, AI vote, and RL veto executed. `run_bot` and the launcher did not execute. Network successes: 0. PostgreSQL connections: 0.

Recommended next action: a separate offline stage to define the authoritative evidence producer. Do not start it from this stage.

Labels: SOURCE-REVIEWED. CODE MODIFIED. ACTUAL PRODUCTION ADAPTER INVOKED OFFLINE. REAL BROKER FUNCTION SUBSTITUTED. INERT BROKER STUB NOT CALLED. PRODUCTION ELIGIBILITY DENIED. FORGED ELIGIBILITY REJECTED. SYNTHETIC ELIGIBILITY REJECTED. ORDER-INTENT MISMATCH REJECTED. REPLAY SAFETY in-process guarded, restart NOT_EVALUATED. ACCOUNT CONTRACT MAPPED. MARKET CONTRACT MAPPED. MARGIN SOURCE MISSING. SPREAD POLICY UNAPPROVED. ACTUAL STRATEGY SELECTOR EXECUTED. ACTUAL AI VOTE EXECUTED. ACTUAL RL VETO EXECUTED. SHARED INERT ADAPTER DISPATCH. BROKER NOT_EVALUATED. POSTGRESQL NOT_EVALUATED.

## 2. Safety and scope

Offline implementation and tests only. No `main.py`, lifespan, `run_bot`, OANDA client, broker order, PostgreSQL, `.env` read, market download, messaging, package install, Docker, deployment, migration, or git commit. PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. Pre-stage `bot_loop.py` hash matched `c25ea5dd2c616324bfc43356c9c372358c1374009c2a59ed4149e5ecc458d17e`. `app.py`, `database.py`, and `orders.py` hashes matched and were not edited. Protected hashes matched and were not edited. The `r19` directory was absent at the start.

## 4. Actual execution-boundary trace

The shared path seals a decision, reserves, and dispatches only to FakeBroker. `production_execution_adapter` is the only function that names `execute_oanda_market_open`. The legacy tail at line 1678 logs that it is not a dispatch path and returns. See `02_execution_boundary_trace.md`.

## 5. Production adapter fail-closed guard

The adapter refuses before the broker import. A caller dictionary is not authority. The final fallback is `production_authority_unavailable`, and the current producer cannot reach a passing seal because standing mandatory gaps stay non-PASS. See `03_production_adapter_guard.md`.

## 6. Actual adapter substitution tests

C01–C25 invoked the real adapter with the broker function replaced. Stub call count was 0 in every case. See `04_actual_adapter_substitution_tests.md`.

## 7. Order-intent binding and replay safety

Direction, instrument, quantity, stop, target, quote, execution kind, client id, and reservation id mismatches refuse. In-process reuse refuses. Restart durability was not executed and is NOT_EVALUATED. The adapter remains closed. See `05_order_binding_and_replay.md`.

## 8. Production account contract mapping

Account id, environment, currency, NAV, balance, and available margin have a source interface on `fetch_account_summary`. That function was not called. Margin used, closeout, GBP spread-bet compatibility, and acquisition time are missing. Local books and the risk file are fallbacks, not broker evidence. See `06_production_account_contract.md`.

## 9. Market-data contract mapping

Bid/ask, quote time, candles, lookback, and `fetch_pricing_snapshot` / `fetch_ohlcv` were mapped. Production provenance is missing. Spread units are price. See `07_market_data_contract.md`.

## 10. Margin and spread requirements

Future production eligibility needs broker margin fields and an approved spread policy bound to the same quote as the order. No numeric threshold was added. See `08_margin_and_spread_requirements.md`.

## 11. Synthetic/production isolation

Synthetic completion is separate from production eligibility. Forged and synthetic records cannot open the production adapter. Strategies stay inactive and live permission stays disabled. See `09_synthetic_production_isolation.md`.

## 12. Offline end-to-end integration

I01–I35 ran. Shared-path scenarios used the real selector, vote, and RL agent. Adapter scenarios used the substituted broker and received zero stub calls. See `10_offline_integration_results.md`.

## 13. Exposure and order safety

FILLED is not flat. `confirm_exposure_flat` returns false. Timeout, ambiguous, and partial outcomes hold exposure. A failed reservation is not permission. No second broker-open path was added.

## 14. Source modifications

`forex_bot/bot_loop.py` post-stage SHA-256 `9b6327045e29adc48f37ed81d13db44e216e24e71326284dc6c80079e2e74550`. Tests and hash pins were updated. `orders.py`, `database.py`, and `app.py` were unchanged. See `14_source_change_log.md`.

## 15. Test isolation

Socket and DNS barriers were installed before imports. `AF_INET`, `AF_INET6`, and `AF_UNIX` were not permitted. Blocked constructor counts were recorded. No network or DNS success. See `11_test_isolation_preflight.json`.

## 16. Integration test ledger

222 records. 178 PASS, 35 PARTIAL, 9 NOT_EVALUATED, 0 FAIL. PARTIAL rows are the account and market source map plus in-process replay durability (K080). K214–K222 are NOT_EVALUATED. See `12_test_ledger.json`.

## 17. R.8–R.18 regressions

Regression 120 passed, 7 skipped, 1 deselected. R.11 through R.18 matched their prior pass counts. R.10 failed once because Windows denied replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json` (`WinError 5`). The same suite then passed: 69 passed, 5 skipped. No safety assertion was weakened. R.18 K018 now requires stable eligibility fields and a unique client-order id. See `13_prior_stage_regressions.json`.

## 18. Remaining defects

No production evidence producer exists. Durable replay prevention is unproven. Margin and spread policy are absent. Quote basis is split between bid/ask, sizing price, and an empty shared-path entry quote. See `15_remaining_integration_gaps.md`.

## 19. Next three priorities

1. Define the authenticated account snapshot fields, including GBP spread-bet compatibility, without calling the broker until a later authorised stage.
2. Bind one quote to spread, sizing, and the broker entry argument, and keep numeric spread `POLICY_UNAPPROVED` until a policy source exists.
3. Design durable single-use reservation state. Keep the adapter closed until that state and the evidence producer both exist.

## 20. Recommended next stage

An offline evidence-producer design stage. It should specify the fields that a future seal may contain and should not contact OANDA, open PostgreSQL, or mark any decision production-eligible.

## 21. Final integrity

See `16_final_integrity.json`. No prohibited operation remained in force at the end. The first R.10 file-replace denial was environmental and the retry passed.

## 22. Final classification

`R19_OFFLINE_ADAPTER_BOUNDARY_GUARDED`.

This does not mean a production-eligible decision can be generated, that OANDA execution works, that margin or spread policy is approved, that PostgreSQL was engine-tested, that broker-flat release works, or that trading is authorised.

## 23. Hard stop

STOP. R.20 was not started. `main.py` was not run. The production lifespan was not entered. `run_bot` was not executed. Strategies were not activated. Live orders were not enabled. OANDA was not contacted. PostgreSQL was not started. Nothing was deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.

END OF STAGE R.19
