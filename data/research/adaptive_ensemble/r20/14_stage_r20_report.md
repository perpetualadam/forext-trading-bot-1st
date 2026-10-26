# STAGE R.20 — COMPLETE OFFLINE TRADING-CYCLE INTEGRATION REPORT

## 1. Executive summary and classification

Classification: `R20_OFFLINE_TWO_CYCLE_INTEGRATED`.

Application source modified: `forex_bot/bot_loop.py`.

The real single-iteration path `evaluate` executed. The real strategy selector, AI vote, and RL veto executed on cycle 1. Cycle 1 dispatched once to the inert adapter and recorded FILLED exposure. Cycle 2 read that same exposure and blocked before reservation. The UNRESOLVED two-cycle scenario passed. One market snapshot fed spread, BUY sizing, and the entry quote. Production eligibility stayed false. The production adapter stayed guarded.

Real broker calls: 0. PostgreSQL connections: 0. Network and DNS successes: 0. R.8–R.19 regressions passed. R.10 did not hit `WinError 5` in this run. The earlier R.19 file-lock limitation is still historical and unresolved.

| Scenario | Cycle 1 | Cycle 2 | Inert dispatches | Outcome |
|---|---|---|---|---|
| FILLED hold | Synthetic fill recorded | Existing exposure blocks | 1 total | PASS |
| UNRESOLVED hold | Ambiguous attempt recorded | Existing exposure blocks | 1 total | PASS |

Remaining limitations: no production-eligible decision, no broker or database proof, selector selected name was null, and restart-durable replay is NOT_EVALUATED.

## 2. Safety and scope

Offline only. `run_bot`, `main.py`, the production lifespan, OANDA, PostgreSQL, `.env`, and the network were not used. PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. Pre-stage `bot_loop.py` matched `9b6327045e29adc48f37ed81d13db44e216e24e71326284dc6c80079e2e74550`. `app.py`, `database.py`, and `orders.py` were unchanged. The `r20` directory was absent before this stage. R.19's `WinError 5` on the R.10 synthetic safety file is recorded and was not hidden.

## 4. Actual application cycle path

`evaluate` is the single-iteration entry used by `_cycle_symbols` and by the offline driver. With injected dependencies it delegates to `dispatch_production_iteration` and the shared decision. `run_bot` was not called. See `02_actual_cycle_path.md`.

## 5. Unified market snapshot

BUY uses the ask for sizing and for the entry quote. The observed spread uses the same bid and ask. The candle timestamp stays distinct from the quote timestamp. A differing injected mid was not used. See `03_market_snapshot_contract.md`.

## 6. Shared isolated state

Cycle 2 used the order, position, and exposure maps written by cycle 1. State was not reset between them. See `04_shared_state_contract.md`.

## 7. FILLED two-cycle execution trace

Cycle 1 at 2026-01-07T12:00:00Z consumed one EUR_USD snapshot, bid 1.09995 and ask 1.10005. Sizing used the ask, 1.10005. The selector ran, the AI vote was BUY, and the RL decision was BUY. Accepted equity was 10000. The inert adapter was called once. The order was recorded FILLED and the exposure hold was unconfirmed. Production eligibility was false.

Cycle 2 at 12:01 was offered a new quote and did not use it. It read `exposure_unconfirmed`, saw the local position, and returned `position_already_open` before reservation or dispatch. Inert calls: 0.

## 8. UNRESOLVED two-cycle execution trace

Cycle 1 called the inert adapter once and received an ambiguous result. Exposure stayed unconfirmed. The local order stayed PENDING with an unresolved intent. Cycle 2 returned `exposure_unconfirmed` with no reservation and no adapter call.

## 9. PARTIAL and reservation-failure scenarios

A partial inert fill kept `exposure_unconfirmed` after one adapter call. A reservation persistence failure blocked before any adapter call. See `07_failure_scenarios.md`.

## 10. Actual strategy, AI and RL invocation evidence

Cycle 1 set `selector_called`, `vote_wrapper_called`, and `rl_veto_called`. The selector's selected name was null. The supplied strategy name `scalp` was then used for the strategy gate. It was not activated for production. See `08_component_execution_evidence.json`.

## 11. Sizing, risk and eligibility results

Accepted equity, sizing equity, and the portfolio-cap equity were all 10000. Portfolio stop-risk passed for this small synthetic risk. Spread stayed `POLICY_UNAPPROVED`. Margin stayed `NOT_IMPLEMENTED`. `production_eligible` stayed false.

## 12. Order recording and exposure recovery

The FILLED order is in the in-memory book with `exposure_safety` unconfirmed. Cycle 2 discovered that state without a manually inserted hold. No caller token released it.

## 13. R.19 production-adapter regression

The production adapter refused a missing decision, the synthetic sealed decision, and a forged eligible copy. The substituted broker function received zero calls.

## 14. Source modifications

`forex_bot/bot_loop.py` is now `248269d4deaa79947cc039708815119cce800a0baffbd434aa56c708041beefd`. See `11_source_change_log.md`.

## 15. Test isolation

Socket and DNS barriers ran before imports. `AF_INET`, `AF_INET6`, and `AF_UNIX` were not permitted. No network success and no DNS success.

## 16. R.20 test results

30 collected, 30 passed, 0 failed, 0 skipped.

## 17. R.8–R.19 regressions

All suites exited 0. R.10 passed 69 with 5 skipped and did not raise `WinError 5` this time. Counts are in `10_prior_stage_regressions.json`.

## 18. Remaining integration gaps

Production provenance, margin, an approved spread policy, durable replay, and a real selector choice are still absent. See `12_remaining_gaps.md`.

## 19. Next three priorities

1. Keep the adapter closed until an authenticated account and quote can be sealed without a caller-supplied flag.
2. Decide how a null selector result should fail closed before any synthetic strategy name is accepted as the gate input.
3. Design restart-durable exposure recovery without claiming the in-memory maps are PostgreSQL.

## 20. Recommended next milestone

An offline selector-result and evidence-producer milestone. It should not contact OANDA or open PostgreSQL, and it should not mark a decision production-eligible.

## 21. Final integrity

See `13_final_integrity.json`. Protected hashes are unchanged. No git commit.

## 22. Final classification

`R20_OFFLINE_TWO_CYCLE_INTEGRATED`.

This does not authorise trading, broker orders, or a production-eligible decision.

## 23. Hard stop

STOP. R.21 was not started. `main.py` was not run. The production lifespan was not entered. `run_bot` was not executed. Strategies were not activated. Live orders were not enabled. OANDA was not contacted. PostgreSQL was not started. Nothing was deployed or migrated.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.

END OF STAGE R.20
