# STAGE R.17 — OFFLINE HARD RISK-LIMIT ENFORCEMENT AND MARKET-DATA ENTRY SAFETY REPORT

## 1. Executive summary and classification

Classification: **R17_OFFLINE_HARD_RISK_GATES_PARTIAL**.

Gates: A complete, B enabled-offline complete with production defaults disabled, C enabled-offline complete with durability partial, D structural checks complete and numeric spread partial, E partial, F complete for the gates that exist, G complete with spread and margin partial, H complete, I complete, J complete, K complete.

Source modified: `forex_bot/bot_loop.py`. Tests added or updated under `tests/`. No supporting application file was modified.

R.17 tests: collected 183, executed 174, passed 174, failed 0, skipped 9. Ledger: 158 PASS, 16 PARTIAL, 9 NOT_EVALUATED, 0 FAIL.

Production defaults that are active on the shared path once permission allows it: account snapshot, accepted-equity sizing, the 5% portfolio stop-risk cap, exposure holds, structural bid/ask checks, and minimum lookback. Production defaults that stay disabled: gross notional at percentage 0, unit cap at 0, and daily-loss/drawdown behind `DECISION_REPAIR_ACCOUNT_RISK` off. Those three execute only when an isolated test turns the existing control on.

No threshold, percentage, unit default, or sizing formula was changed. Daily-loss state was shown to survive a later read in the same process. Process restart was not executed, so durability across restart is not claimed. No numeric spread threshold is approved. Minimum lookback hard-blocks. Margin sufficiency is not verified. The actual strategy selector, `AIEnsemble.vote`, and `RLAgent.decide` executed. Valid synthetic BUY and SELL each reached the inert adapter once. The production adapter was not invoked. `run_bot` and the launcher did not execute. Real broker requests: 0. Network successes: 0. PostgreSQL connections: 0.

Recommended next action: stop. A later stage would need a separate authorisation to define an approved spread policy and a real margin source.

Labels: SOURCE-REVIEWED. CODE MODIFIED. ENABLED OFFLINE RISK GATE TESTED. PRODUCTION DEFAULT DISABLED for gross notional, unit cap, and account-risk. HARD ENTRY BLOCK VERIFIED OFFLINE for quotes, lookback, enabled caps, and enabled loss checks. ACTUAL STRATEGY SELECTOR EXECUTED. ACTUAL AI VOTE EXECUTED. ACTUAL RL VETO EXECUTED. INERT ADAPTER DISPATCH. PRODUCTION ADAPTER SOURCE-VERIFIED. PRODUCTION ACCOUNT PROVENANCE NOT_EVALUATED. PRODUCTION MARKET-DATA PROVENANCE NOT_EVALUATED. POSTGRESQL NOT_EVALUATED. BROKER NOT_EVALUATED.

## 2. Safety and scope

Offline source and tests only. `main.py` was not run. The production lifespan was not entered. `run_bot` was not executed. No OANDA client was constructed. `execute_oanda_market_open` was not called. PostgreSQL was not started. `.env` was not read. No package was installed. No Docker, WSL, or VM was used. No git commit, reset, or rollback was made.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The r17 directory was absent at the start. Pre-stage hashes matched. Protected hashes still match.

## 4. Actual risk-control inventory

See `02_risk_control_inventory.md`. A zero gross or unit limit is disabled. The account-risk flag is disabled. Structural quotes and lookback are hard blocks on the shared path.

## 5. Gross-notional and unit-limit implementation

Enabled gross caps include open positions, the candidate, and readable pending exposure, and they fail closed when pending exposure cannot be read. Enabled unit caps block a candidate above `MAX_POSITION_UNITS` before reservation. Defaults remain 0 and are reported disabled.

## 6. Daily-loss and drawdown implementation

When the existing flag is on, `block_reason` uses the accepted equity and the supplied unrealised value. The existing 2%, 3%, and 5% boundaries block. A halt survives a later read and is not cleared by `verified=True` or a fabricated payload. Restart durability and production coverage are not claimed.

## 7. Spread and lookback implementation

Missing or invalid quotes, crossed markets, malformed candles, and short history block. Spread is ask minus bid in price units. `spread_limit` stays `not_approved`. The existing 90-second manage window applies only when a quote timestamp is supplied.

## 8. Margin evidence and limitations

Margin evidence is `not_implemented`. Sufficiency is `NOT_EVALUATED`. Equity is not treated as margin proof. No broker margin rule was invented.

## 9. Integrated safety ordering

Market data, the account snapshot, optional loss checks, sizing, optional unit and gross caps, and margin evidence all sit before reservation and the inert adapter. Existing exposure holds remain earlier.

## 10. Offline end-to-end results

Valid BUY and SELL reached the recording adapter once. Cap, loss, quote, lookback, account, and exposure failures did not. Wide numeric spread and missing margin are PARTIAL. See `08_offline_end_to_end_results.md`.

## 11. Exposure and account safety

FILLED, PENDING, PARTIAL, and UNRESOLVED holds still block. Invalid and unverified accounts still block. Accepted equity stays the sizing and portfolio-cap equity. `confirm_exposure_flat` still returns false.

## 12. Source modifications

`forex_bot/bot_loop.py` only, among application sources. Post hash `683cb8d172011548820b48fd936e583e0be991e7e79adc6f37e97c309005bf4a`. Details are in `12_source_change_log.md`.

## 13. Test isolation

Socket and DNS barriers refused every constructor. Counts are in `09_test_isolation_preflight.json`. The dotenv stub was called once per process and did not read a file.

## 14. Integration test ledger

`10_test_ledger.json` holds I001–I183. Pytest 174 passed, 0 failed, 9 skipped. Ledger 158 PASS, 16 PARTIAL, 9 NOT_EVALUATED. I175–I183 are the explicit NOT_EVALUATED rows.

## 15. R.8–R.16 regressions

Every suite exited 0. R.4–R.9: 120 passed, 7 skipped, 1 deselected. R.10: 69/5. R.11: 51/5. R.12: 118/5. R.13: 81/6. R.14: 143/5. R.15: 165/6. R.16: 135/6. Five R.12 assertions were strengthened to the new fail-closed results. None were weakened.

## 16. Remaining defects

No approved spread number. No quote-timestamp requirement. No production loss ledger or proven restart durability. No margin policy. No broker-flat release. Production account and market provenance remain unverified.

## 17. Next three priorities

1. Keep production deployment, practice orders, and live trading unauthorised.
2. Obtain an approved spread policy before treating any numeric spread as a block.
3. Identify a real margin and daily-loss source before describing those controls as production protection.

## 18. Recommended next stage

Do not start R.18 from this result. A later offline stage can bind an approved spread threshold and a real margin source after separate authorisation.

## 19. Final integrity

HEAD and branch unchanged. No commit. Protected hashes unchanged. Production adapter invocations 0. Broker requests 0. Network successes 0. PostgreSQL connections 0.

## 20. Final classification

**R17_OFFLINE_HARD_RISK_GATES_PARTIAL**

## 21. Hard stop

STOP. R.18 has not been started.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.

END OF STAGE R.17
