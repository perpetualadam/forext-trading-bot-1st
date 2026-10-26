# STAGE R.6 — FULL BOT INTEGRATION AUDIT AND OFFLINE STARTUP READINESS REPORT

## 1. Executive summary

Overall classification: `R6_FULL_AUDIT_PARTIAL`.

The bot has a real startup path and a real order path. They were read, not run. Six strategy names are labels on one shared decision. Shadow rules for those names exist and are not connected to orders. PostgreSQL recovery is written but not engine-tested. Historical session evidence is still 27 complete common sessions against a requirement of 40.

Gates A–K are covered as a source audit. Startup execution and the database engine are NOT_EVALUATED.

Inventory rows: 25. Connected to the live or startup path: 16. Disconnected, shadow, research, or test-only: 6. Partial: 1 (`backtest.py`). Configuration only: 2.

Critical gaps: 0 treated as a proven live bypass. High gaps: G01, G02, G03, G04, G05, G09.

Tests executed this stage: 0. Passed: 0. Failed: 0. Not evaluated: the suite, by design.

Source files modified: none. Production changes: none. Network requests: 0. Broker requests: 0.

Recommended next action: stop. The next useful build, after approval, is an offline PostgreSQL proof and then a fake startup harness. Do not start the bot.

## 2. Safety and scope

Read-only. No application file, test, config, or older research file was edited. `.env` was not read. The off-limits project was not touched.

## 3. Baseline and file integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. The R.5 hashes and the protected hashes matched before the audit and were checked again after the R.6 files were written.

## 4. Full project inventory

See `02_full_project_inventory.csv`. A file existing in the tree is not a working feature. The rows say whether startup or the live loop actually reaches it.

## 5. Historical implementation findings

Safety blocks, the direction gate, and unresolved orders are in the current live source. Six-strategy performance claims are not. Session counts were not improved. Docker work did not become a deployment. Details are in `03_historical_implementation_audit.md`.

## 6. Application startup call graph

`main.py` serves `forex_bot.app:app`. Lifespan loads fail-closed safety state, connects to PostgreSQL, reloads orders, builds the broker client, and then starts reconciliation, health, Telegram, and `run_bot`. That graph is source-only. Startup did not succeed because it did not run.

## 7. Strategy and AI integration

All six names are inactive by default. `select_strategy` picks a name and a lookback. The trade side comes from `ai.vote`, then the direction gate, then an RL veto. `shadow/signals.py` has separate entry rules and is not called by `bot_loop.py`. There is no performance evidence.

A vote with no models returns `allow` false and the text BUY. The loop returns on `allow` false before sizing. That string does not trade today.

## 8. Risk and trade management

Connected: shared sizing, shared stop and target, session window, weekend flatten, notional cap, halt and kill switch, live-order block, unresolved-order hold.

Present but off unless an environment flag is set: daily loss, drawdown, and exposure limits in `decision_repair`.

Missing on the live path: margin, leverage, correlation, financing, and news blocks.

None of these were broker-validated.

## 9. Order and database integration

The R.4 and R.5 repairs are still in `bot_loop.py`, `database.py`, and `orders.py`. Recovery is called before the trading loop in `app.py`. The database engine was not run, so persistent recovery is not proven. The in-process lock is not a substitute for the untested PostgreSQL lock.

## 10. Data and backtest readiness

Existing research still records 27 complete common sessions and a minimum of 40. R.6 did not recount raw files and did not download data. `backtest.py` lines 352–354 still force BUY. No profitability claim is made.

## 11. Offline startup readiness

The bot cannot be called ready to switch on. A later harness must fake the broker, account, candles, database, and Telegram, keep live orders blocked, keep strategies inactive, and stop before the real loop. That harness was not built. `app.py` has no seam yet, so the harness likely needs a later approved edit.

## 12. Test coverage

Helper tests exist for the new gates. Application-start tests exist and import `app`, so they were not run. Async broker tests previously died on a Windows socket barrier. That barrier must stay. R.6 executed no tests.

## 13. Master integration gap register

Twelve gaps are in `11_integration_gap_register.csv`. The highest are the untested database, the unrun startup, the backtest BUY fallback, the strategy-name mismatch, the 13-session shortfall, and the untested two-session lock.

## 14. Practical implementation roadmap

R.7 disposable PostgreSQL proof. R.8 fake startup harness. R.9 backtest direction repair. R.10 strategy decision without connecting shadow rules to orders. Practice and production remain later and unauthorised.

## 15. Next three priorities

1. Do not start the bot.
2. After approval, prove the unresolved-order SQL on a disposable database.
3. After that, add a fake startup that cannot reach OANDA or Telegram.

## 16. Recommended next stage

None is started. R.7 is the first build that would reduce a real safety unknown. It needs a separate approval and must not use production or Docker.

## 17. Final integrity

No source, test, or older research file was modified. No network, broker, Docker, or Git write occurred. New files are only under `data/research/adaptive_ensemble/r6/`.

## 18. Final classification

`R6_FULL_AUDIT_PARTIAL`

The map is complete enough to plan work. It is partial because startup and PostgreSQL were not executed, raw session files were not re-read, and `.env` was not inspected.

## 19. Hard stop

R.6 is finished. R.7 is not started. The application stays off. Strategies stay inactive. Live orders stay blocked. No practice or real order was sent. Production was not accessed.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE-ACCOUNT ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
