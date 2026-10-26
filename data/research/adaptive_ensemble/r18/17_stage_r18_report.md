# STAGE R.18 — OFFLINE MANDATORY-RISK EVIDENCE AND FAIL-CLOSED ENTRY ELIGIBILITY REPORT

## 1. Executive summary and classification

Classification: **R18_OFFLINE_ENTRY_ELIGIBILITY_INTEGRATED**.

This classification records the offline eligibility contract. It does not mean an approved spread policy exists, margin is verified, production provenance is verified, or trading is authorised.

Gates A–M are complete for the offline shared path. Application source modified: `forex_bot/bot_loop.py`.

R.18 tests: collected 212, executed 203, passed 203, failed 0, skipped 9. Ledger: 203 PASS, 0 PARTIAL, 9 NOT_EVALUATED, 0 FAIL.

Mandatory missing evidence blocks. A missing quote timestamp is `MISSING_EVIDENCE` and does not reach reservation. An unapproved spread policy blocks production eligibility and is not a spread pass. Missing margin evidence blocks production eligibility and is `NOT_IMPLEMENTED`. Disabled gross, unit, and account-risk controls remain disabled and are recorded as `DISABLED`.

Synthetic BUY and SELL each reach the inert adapter once. That completion is not production eligibility: `production_eligible` stays false. The strategy selector, `AIEnsemble.vote`, and `RLAgent.decide` executed. The production adapter was not invoked. `run_bot` and the launcher did not execute. Real broker requests: 0. Network successes: 0. PostgreSQL connections: 0.

Recommended next action: stop.

SOURCE-REVIEWED. CODE MODIFIED. MANDATORY GATE BLOCK VERIFIED OFFLINE. OPTIONAL GATE DISABLED. POLICY_UNAPPROVED. MISSING_EVIDENCE. NOT_IMPLEMENTED. SYNTHETIC CONTRACT EXECUTED. PRODUCTION ELIGIBILITY DENIED. ACTUAL STRATEGY SELECTOR EXECUTED. ACTUAL AI VOTE EXECUTED. ACTUAL RL VETO EXECUTED. INERT ADAPTER DISPATCH. PRODUCTION ADAPTER SOURCE-VERIFIED. PRODUCTION ACCOUNT PROVENANCE NOT_EVALUATED. PRODUCTION MARKET PROVENANCE NOT_EVALUATED. POSTGRESQL NOT_EVALUATED. BROKER NOT_EVALUATED.

## 2. Safety and scope

Offline source and tests only. `main.py` was not run. The production lifespan was not entered. `run_bot` was not executed. No OANDA client was constructed. `execute_oanda_market_open` was not called. PostgreSQL was not started. `.env` was not read. No package was installed. No Docker, WSL, or VM was used. No git commit, reset, or rollback was made.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The r18 directory was absent at the start. Pre-stage hashes matched. Protected hashes still match. Post-stage `bot_loop.py` is `c25ea5dd2c616324bfc43356c9c372358c1374009c2a59ed4149e5ecc458d17e`.

## 4. Mandatory-risk policy inventory

See `02_mandatory_risk_inventory.md`. Structural quotes, lookback, the account snapshot, portfolio stop-risk, and exposure holds are mandatory and enforced. Numeric spread is mandatory and unapproved. Margin is mandatory and not implemented. Gross notional, the unit cap, and daily loss are optional and disabled at the existing defaults.

## 5. Canonical gate-result contract

`PASS` is an evaluation that succeeded. Missing, unapproved, disabled, and unimplemented states stay distinct. Unknown statuses become `BLOCK`. A later pass cannot erase an earlier failure. `verified=True` does not authenticate a gate.

## 6. Single entry-eligibility decision

`_seal_entry_gates` runs before reservation and adapter dispatch. Production eligibility is false while any mandatory gate is not `PASS`. The isolated synthetic contract can continue only when entry-scoped gates pass or an optional gate is explicitly `DISABLED`. The caller cannot set eligibility.

## 7. Spread and quote-freshness handling

Missing bid, missing ask, crossed quotes, non-finite spread, and negative spread block. A missing quote timestamp blocks. Stale and future timestamps use the existing 90-second window. No numeric threshold was invented. Spread remains `POLICY_UNAPPROVED`, which denies production eligibility. A fresh synthetic timestamp can pass the harness window and still leaves production quote provenance as `MISSING_EVIDENCE`.

## 8. Margin-evidence handling

Margin is `NOT_IMPLEMENTED`. Equity, a caller margin field, and `verified=True` do not make it a pass. No broker margin request is made.

## 9. Optional and disabled controls

Zero gross and unit caps stay disabled. The account-risk flag stays off. Enabled test configurations still block breaches. Disabled controls are not described as production protection.

## 10. Structured risk-gate decision records

Every result carries `risk_decision` with the mandatory, disabled, missing, unapproved, and unimplemented lists, plus the blocking reasons. The record is deterministic and serialisable. It does not store payload secrets, create orders, or grant permission.

## 11. Synthetic-versus-production separation

A valid isolated BUY or SELL sets `synthetic_contract` to `completed` and `production_eligible` to false. Production context does not reach the adapter. The production adapter stays withheld.

## 12. Offline end-to-end results

The scenario table is in `10_offline_end_to_end_results.md`. Exposure holds, account failures, quote failures, and enabled-cap breaches make zero adapter calls. Valid synthetic BUY and SELL make one each.

## 13. Exposure, account and order safety

FILLED, PENDING, PARTIAL, and UNRESOLVED holds still block. Missing and unverified accounts still block. Accepted equity stays the sizing and portfolio-cap equity. `confirm_exposure_flat` still returns false. Uncertain adapter outcomes do not retry.

## 14. Source modifications

`forex_bot/bot_loop.py` is the only application file changed. Details are in `14_source_change_log.md`.

## 15. Test isolation

Socket and DNS barriers refused every constructor. Counts are in `11_test_isolation_preflight.json`. The dotenv stub was called once per process and did not read a file.

## 16. Integration test ledger

`12_test_ledger.json` holds K001–K212. Pytest: 203 passed, 0 failed, 9 skipped. Ledger: 203 PASS, 0 PARTIAL, 9 NOT_EVALUATED. K204–K212 are the explicit NOT_EVALUATED rows.

## 17. R.8–R.17 regressions

Every suite exited 0. R.4–R.9: 120 passed, 7 skipped, 1 deselected. R.10: 69/5. R.11: 51/5. R.12: 118/5. R.13: 81/6. R.14: 143/5. R.15: 165/6. R.16: 135/6. R.17: 174/9. Fixtures now carry a quote timestamp, and the missing-timestamp and unapproved-spread assertions require explicit ineligibility. No assertion was weakened.

## 18. Remaining defects

No approved spread number. No margin implementation. No production account, market, or quote provenance. No proven loss-halt durability across restart. No broker-flat release.

## 19. Next three priorities

1. Leave production deployment, practice orders, and live trading unauthorised.
2. Obtain an approved spread policy before any numeric spread can pass.
3. Identify a real margin source and production provenance before production eligibility can become true.

## 20. Recommended next stage

Do not start R.19 from this result. A later offline stage can bind an approved spread threshold and a real margin source after a separate authorisation.

## 21. Final integrity

HEAD and branch are unchanged. No commit was created. Protected hashes match. Production adapter invocations: 0. Broker requests: 0. Network successes: 0. PostgreSQL connections: 0.

## 22. Final classification

**R18_OFFLINE_ENTRY_ELIGIBILITY_INTEGRATED**

## 23. Hard stop

STOP. R.19 has not been started.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.

END OF STAGE R.18
