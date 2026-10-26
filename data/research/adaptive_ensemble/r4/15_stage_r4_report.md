# STAGE R.4 — OFFLINE TRADING-SAFETY REPAIRS AND REGRESSION TEST REPORT

## 1. Executive summary

Overall classification: `R4_OFFLINE_SAFETY_REPAIRS_PARTIAL`.

Gates: A PASS, B PASS, C PASS, D PASS, E PASS, F PASS for the executed cases, G BLOCKED, H PASS, I PASS.

Files modified: `forex_bot/bot_loop.py`, `forex_bot/database.py`.

Files added: `tests/test_r4_trading_safety.py` and the R.4 research files under `data/research/adaptive_ensemble/r4/`.

Tests executed: 33. Tests passed: 33. Tests failed: 0. Tests not evaluated: the inactive-strategy return inside the trading loop (F30).

Confirmed repairs: an unresolved broker outcome now keeps the original intent and refuses a replacement client order id; a missing or invalid direction no longer becomes BUY.

Incomplete: the inactive-strategy return was not run, and the PostgreSQL statements were not executed.

Production modifications: none. Network requests: none completed. Broker requests: none.

Recommended next action: stop. Do not start another stage until it is separately approved.

## 2. Safety and scope

This stage repaired two offline safety defects. It did not enable a strategy, grant live-order permission, contact OANDA, send an order, open the application, or migrate a database.

## 3. Baseline and pre-existing changes

Git HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. The tree was already dirty. Nothing was committed, reset, or cleaned.

All protected hashes matched before editing. `database.py` was already dirty, and its bytes matched `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`. `bot_loop.py` and `oanda_exec.py` had no pre-existing difference. The earlier database cleanup code was kept.

## 4. Order-uncertainty repair design

CODE DESIGNED, then CODE MODIFIED.

The defect was not the timeout label. The timeout was already ambiguous. The loop then stored that attempt as cancelled, so a new client order id could pass.

The repair identity is the symbol plus the first unresolved client order id. A later id for that symbol is refused until the outcome is explicit.

## 5. Order-state transition table

See `04_order_state_transition_table.json`.

Timeout, reset, and malformed stay unresolved. Confirmed fill, rejection, and cancellation close the intent and do not create a replacement by themselves. Missing or corrupt recovery fails closed. A simulated confirmed absence can release the intent without creating an id. A simulated confirmed fill does not create a replacement. An unavailable reconciliation stays blocked.

## 6. Order-repair implementation

CODE MODIFIED in `forex_bot/database.py` and `forex_bot/bot_loop.py`. `oanda_exec.py` was not changed.

`broker_entry_block_reason` runs at `bot_loop.py` line 1469, before `generate_client_order_id`. Unknown outcomes call `remember_ambiguous_outcome` at lines 1588 and 1597. Confirmed rejection is handled separately at line 1574 and does not use the unresolved path.

SYNTHETICALLY TESTED: F01–F16. The trading-loop exception body itself was not entered. SOURCE-REVIEWED: those handlers call the functions the tests executed.

## 7. Direction-repair implementation

CODE MODIFIED. `canonical_entry_direction` is at `bot_loop.py` line 155. The loop uses it at line 1199 and returns at line 1207 when the value is not buy or sell.

SYNTHETICALLY TESTED: BUY, SELL, lowercase, spaces, None, empty, whitespace, UNKNOWN, NO_TRADE, and numbers. Invalid values made zero sizing, construction, and dispatch calls in `direction_action_gate`. The trading loop was not started.

## 8. Test isolation preflight

Gate E PASS. Plugin autoload was off. The project conftest was not loaded. A socket and name-lookup barrier was installed. Dotenv was stubbed once. One IPv6 constructor was blocked during import. No connection completed.

## 9. Order-recovery test results

F01–F16 PASS. Fixtures were synthetic classifications, in-memory books, and one synthetic recovery row. No PostgreSQL connection was opened. No broker reconciliation was requested.

## 10. Direction test results

F17–F28 and F33 PASS. Function under test: `canonical_entry_direction` and `direction_action_gate` in `tests/test_r4_trading_safety.py`.

## 11. Inactive-strategy test results

F29 PASS: all six strategies were inactive and not authorised for live.

F30 NOT_EVALUATED: `INACTIVE_ENTRY_NOT_EVALUATED`. The return is at `bot_loop.py` lines 1108–1116. It is after the live-authorisation gate, so it was not executed. Sizing, construction, and dispatch counts are not reported as zero.

## 12. Regression summary

33 pytest cases passed and 0 failed. F30 was not given a pass. F31 and F32 passed on a synthetic safety file under the R.4 directory: a saved ALLOWED value still left the effective permission BLOCKED, and strategies stayed inactive. F34 PASS: the fixture run completed no external connection.

## 13. Remaining risks

The inactive loop branch is still unproven. The SQL text was not run. `orders.py` can still label an unknown status as PENDING in memory; the new database gate is what blocks the replacement id. No broker behaviour was validated.

## 14. Final file integrity

Protected files other than `database.py` still match their expected hashes. `database.py` changed on purpose from `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e` to `e3e4be7c70e55757d8692b36044a9f7ed1bfc00884236a892b926f76c715a683`. That new hash is not a later-stage baseline.

`bot_loop.py` is now `c16c289a61f03a98260aa4f6e4c4c616c07e7aaded73a69bf126dd6d41a98744`. `oanda_exec.py` is unchanged.

No Git commit. No writes outside the two source files, the new test, and `data/research/adaptive_ensemble/r4/`.

## 15. Next three priorities

1. Leave strategies inactive and live orders blocked.
2. If the unresolved SQL needs proof, use a future approved offline test database only. Do not migrate production.
3. Do not grant live permission merely to reach the inactive-strategy return.

## 16. Recommended next stage

No next stage is started. A later offline stage would be required before the unrun loop branch or the unrun SQL could be called proven. That stage is not authorised by this report.

## 17. Final classification

`R4_OFFLINE_SAFETY_REPAIRS_PARTIAL`

Both repairs are implemented and the focused offline tests passed. The stage is partial because the inactive-entry branch was not evaluated and the durable SQL was not executed. No safety result was marked pass without a run.

## 18. Hard stop

R.4 is finished. R.5 is not started. Strategies stay inactive. Live-order permission stays blocked. OANDA was not contacted. No practice order and no real order was sent. Production was not accessed or migrated. No market data was downloaded. No profitability backtest was run. Docker research was not continued.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE-ACCOUNT ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
