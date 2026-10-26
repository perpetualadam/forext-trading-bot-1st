# STAGE D.12 — APPLICATION SHUTDOWN CONTRACT AND LIFECYCLE OBSERVABILITY AUDIT REPORT

## 1. Executive summary

- Overall result: `D12_AUDIT_COMPLETE_APPLICATION_CONTRACT_GAPS_FOUND`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Actual lifespan executed: yes
- Actual Telegram functions executed: yes
- Actual database functions executed: yes
- Tests passed: D.12 16; D.2/D.3/D.4/D.7/D.9/D.11 170; safety-repair 23
- Tests failed: none in the D.12 acceptance set. Historical hash pins stopped D.5, D.6, D.8, and D.10.
- Confirmed findings: D12-STOP-01 and D12-START-01
- Application observability: incomplete stop and refused start are not reported
- Database ownership: intentional process-global retention. No ownership defect confirmed.
- Recommended next stage: a separately approved `app.py` reporting change. Do not start it from this audit.

## 2. Live safety

No production container change, broker request, broker mutation, production database access, Telegram network request, operational-state access, shadow-mount access, Docker, WSL, VM, network, download, or package installation. Live-order authorisation and strategy activation were not changed.

## 3. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: main
- Working tree: dirty from earlier stages and preserved
- app.py: `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`
- database.py: `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`
- telegram_control.py: `193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780`
- live_safety.py: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Unexpected changes: none. D.12 did not modify production source.

## 4. Application shutdown contract

Stop is called at app.py lines 383-384. The return is not captured, logged, or stored as a cleanup error. A live worker is not reported. Task cleanup still runs. Successful shutdown retains the database. Stop exceptions are recorded separately and do not skip task cleanup.

## 5. Telegram startup contract

Start is called at app.py line 370 and returns None. A refused start returns without a log. The application does not detect it. A second lifespan in the same process still yields. The old worker remains the only worker.

## 6. Database ownership

One connection is published under `_pg_lock`. Normal shutdown retains it. Failed startup before Telegram releases it. Repeated lifespans reused the same connection id. Release waits for an in-flight query. A stopped worker did not reconnect. Classification: `INTENTIONAL_PROCESS_GLOBAL_RETENTION` plus `FAILED_STARTUP_CLEANUP`.

## 7. Deterministic lifespan results

Normal shutdown leaves no worker and an empty cleanup list. Incomplete shutdown leaves the worker alive, the reference stored, the database published, tasks drained, and cleanup errors empty. After the harness releases the fake poll, the worker exits. A second lifespan does not create a worker and still reports startup success. A third lifespan can start a new worker after the old one exits.

## 8. Error precedence

The primary startup exception survives. A stop exception, task-await exception, release note, and alert exception are recorded without skipping the remaining cleanup. An incomplete stop is absent from that list. Cancellation does not re-raise secondary cleanup errors. Exception order is intact.

## 9. Safety invariants

Isolated authorisation stayed BLOCKED. The six strategies stayed inactive: scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, swing_breakout. No order routing, broker, PostgreSQL, Telegram network, operational state, shadow state, or other network access occurred. Current production state was not reverified.

## 10. Regression compatibility

D.2, D.3, D.4, D.7, D.9, and D.11 passed together, 170 tests. Safety-repair passed, 23 tests. D.5 had 15 hash-pin errors, D.6 had 12, D.8 had 7, and D.10 had 14. Those conflicts are not passes.

## 11. Confirmed findings

D12-STOP-01, reporting, `lifespan` in app.py lines 383-387. A blocked actual lifespan returned with a live stored worker and an empty cleanup-error list. Tasks were drained and the database stayed published. No post-stop query occurred. Remediation belongs in app.py: record and log the status, do not raise, and do not release the database. Evidence: `ACTUAL_LIFESPAN_ISOLATED`.

D12-START-01, reporting, `lifespan` in app.py lines 367-370 and the silent return in telegram_control.py lines 1183-1184. A second lifespan yielded while the original worker remained the only worker. Startup success does not prove a new worker started. Do not fail trading startup. Log the refusal from app.py. Evidence: `ACTUAL_COMBINED_LIFECYCLE_ISOLATED`.

## 12. Application contract decision

Classification: application contract gaps found, without a separate ownership defect. Shutdown observability and startup observability are both gaps. Database retention is intentional. Repeated lifespan is safe at the resource level and silent at the reporting level. A later app.py change is required for the reporting gaps. It was not made here.

## 13. Remaining deployment blockers

Production startup, the live database, dependencies, packaging, rollback, and production state remain unverified. The running image does not contain the working tree. D12-STOP-01 and D12-START-01 are confirmed and not remediated. Research backtests may still assume strategies start active.

## 14. Validation

Commands were the baseline hash, the D.12 pytest, the combined regression pytest, the safety-repair pytest, the historical hash-pin pytest, and ruff. Production files were read and not modified. New files are the D.12 tests and this research directory. Prohibited operations: none. Production process state was not observed.

## 15. Final classification

`D12_AUDIT_COMPLETE_APPLICATION_CONTRACT_GAPS_FOUND`

## 16. Next action

D.12 is complete. Application contract gaps were found. Database ownership defects were not found. Actual lifespan, Telegram status handling, and repeated lifespans were tested. Production startup was not verified. The bot may not be restarted. An image may not be built. Deployment is not authorised. Live trading is not authorised. A separately approved remediation stage is required before any app.py change.

PRODUCTION DEPLOYMENT: NO-GO. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
