# STAGE R.5 — OFFLINE APPLICATION INTEGRATION AND STARTUP READINESS REPORT

## 1. Executive summary

Overall classification: `R5_OFFLINE_INTEGRATION_PARTIAL`.

Gates: A PASS, B BLOCKED as an engine proof, C PASS for the in-process wiring, D PASS, E PASS, F PASS as a source-verified path, G PASS, H PASS for executed cases, I PASS.

Application files modified: `forex_bot/bot_loop.py`, `forex_bot/database.py`, `forex_bot/orders.py`.

Test file added: `tests/test_r5_integration.py`.

Pytest executed: 65. Passed: 65. Failed: 0. Not evaluated: the PostgreSQL engine (H32 and H33).

Database integration: source-reviewed and wired into recovery. Not executed on PostgreSQL.

Startup wiring: source-reviewed. The application was not started.

Inactive strategy: the gate the loop calls was tested with spies. `evaluate` was not run.

Production changes: none. Network requests completed: 0. Broker requests: 0.

Recommended next action: stop. Do not start the bot.

## 2. Safety and scope

The repairs are in the modules the running bot already calls. This stage did not start that bot, enable a strategy, grant live permission, or contact OANDA.

## 3. Baseline and pre-existing changes

HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. The R.4 hashes of `bot_loop.py` and `database.py` matched before this edit. Protected files matched. Earlier dirty tree content was kept. Nothing was committed.

## 4. Application call graph

SOURCE-REVIEWED. Startup in `app.py` loads safety state, then reloads orders, then later schedules `run_bot`. The loop checks live permission, then the strategy gate, then direction, then sizing, then the unresolved-order gate, then a client id and reservation, and only then the broker call. Details are in `02_application_call_graph.md`.

## 5. Order-state integration

CODE MODIFIED. `orders.py` now has status `UNRESOLVED`. A cancel cannot silently clear it. A synthetic restart snapshot reloads it and blocks a new client id. SYNTHETICALLY TESTED.

## 6. Database persistence

SOURCE-REVIEWED. The status column is text and has no check constraint, so `UNRESOLVED` fits without a new column. Recovery failure now raises instead of looking like an empty book. The loader turns that into a fail-closed block.

DATABASE-ENGINE TESTED: no. `POSTGRESQL_EXECUTION_NOT_EVALUATED`.

## 7. Direction safety

SYNTHETICALLY TESTED. Invalid direction does not size, reserve, or dispatch inside the gate. The live evaluation source no longer contains the old BUY fallback. `backtest.py` still does, and it was not edited.

## 8. Inactive strategy safety

SYNTHETICALLY TESTED. An inactive strategy and an unknown strategy name produce zero sizing, construction, client-id, and dispatch calls. All six strategies remain inactive by default. The trading loop was not started.

## 9. Startup wiring

SOURCE-REVIEWED, not executed. `load_open_orders_from_db_into_memory` is the startup call, and it now uses the new snapshot loader. `app.py` was not modified. Actual startup was not tested.

## 10. Source changes

`bot_loop.py`, `database.py`, and `orders.py` only, plus the new test and the R.5 research files. `oanda_exec.py` was not changed.

## 11. Test isolation

Plugin autoload off. Conftest not loaded. Dotenv stubbed once. One socket constructor blocked. No completed connection. `forex_bot.app` was not imported.

## 12. Integration test results

65 pytest cases passed, including the earlier R.4 file. H32 and H33 were not given a pass. The application was not started, so those source-wiring checks are not a startup test.

## 13. Unresolved defects

PostgreSQL execution is unproven. `backtest.py` still has the old direction fallback and is outside this stage. A database outage blocks new broker orders and does not, by itself, stop `app.py` from continuing, because that file was not edited.

## 14. Readiness assessment

The safety pieces are connected in the code the bot will call when it is switched on. The bot was not switched on. It is not ready for practice orders, live orders, or deployment.

## 15. Next three priorities

1. Leave the application off, strategies inactive, and live orders blocked.
2. Prove the unresolved SQL on an offline PostgreSQL engine only under a separate approval.
3. Decide separately whether the backtest direction fallback should be removed.

## 16. Recommended next stage

No next stage is started.

## 17. Final integrity

Protected hashes still match. New hashes are in `12_modified_file_hashes.json`. No production access, broker request, package install, Docker, or Git commit.

## 18. Final classification

`R5_OFFLINE_INTEGRATION_PARTIAL`

## 19. Hard stop

R.5 is finished. R.6 is not started. The application was not started. The trading loop was not started. Strategies stay inactive. Live-order permission stays blocked. OANDA was not contacted. No practice or real order was sent. Production was not accessed or migrated.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE-ACCOUNT ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
