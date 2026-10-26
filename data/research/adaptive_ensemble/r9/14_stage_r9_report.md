# STAGE R.9 — OFFLINE POSITION-STATE INTEGRITY AND RECOVERY REPAIR REPORT

## 1. Executive summary

Classification: `R9_OFFLINE_POSITION_SAFETY_PARTIAL`.

A filled order no longer releases entry eligibility. The loop checks that hold before strategy selection and sizing. The position object itself is still not durable, and no schema was added. PostgreSQL, broker reconciliation, and application startup were not run.

Gates A–K: A traced; B policy set; C marker added on existing metadata, position table stopped; D synthetic fill repair; E close does not release by itself; F synthetic recovery; G R.8 gates rerun; H isolation held; I 120 passed, 0 failed, 7 skipped; J no migration; K no prohibited operation.

Application files modified: `forex_bot/bot_loop.py`, `forex_bot/database.py`, `forex_bot/orders.py`. `oanda_exec.py` was not modified. Tests added: `tests/test_r9_position_safety.py`. Existing test updated: `tests/test_r8_reservation_safety.py`.

Tests collected 128. Executed 120. Passed 120. Failed 0. Skipped 7. Deselected 1. Not evaluated 7.

Fill-to-position defect: blocked in source and synthetic tests. Restart of the uncertainty marker: source-reviewed and snapshot-tested, engine NOT_EVALUATED. PostgreSQL: NOT_EVALUATED. Broker reconciliation: NOT_EVALUATED. Application startup: NOT_EVALUATED. Network successes: 0. Broker requests: 0.

Next action: stop. Do not start R.10.

## 2. Safety and scope

No application start, no trading loop, no OANDA, no Telegram or Discord, no `.env` read, no database server, no Docker, WSL, or VM, no package install, no git commit or reset. Persistence was forced off. The socket barrier raises before a real constructor.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. Pre-stage hashes matched. Protected files still match. `oanda_exec.py` remains `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8`.

Post-stage: bot_loop.py `9fbb8c326c35d312b86b88a3d49f395993c2e1fee303afb15a56d7c14c4b2941`. database.py `4c289dfaa2ca70077fc314a9bb3f92609ab0a9dbda9db26ff912d80b8d03a4a8`. orders.py `78c34c86bcc5f1d90d3979b18052a4fc9496a2b3cc2f37589f17ef2b6f7f0dd9`.

The diff against HEAD is the whole dirty tree: 972 insertions and 125 deletions across the three files. It includes earlier stages.

## 4. Fill-to-position lifecycle

SOURCE-REVIEWED. An open position returns at line 755. The new exposure check is at line 1087, before strategy, direction, and sizing. Reservation and the broker call site come later. `finalize_order_fill` marks exposure unconfirmed. `open_position` then stores one in-memory slot. There is no open-position table. Startup would load orders through `load_open_orders_from_db_into_memory`, then call broker reconciliation. Those calls were not made.

## 5. Exposure safety policy

FILLED is not proof the exposure is closed. A missing position is not proof the broker is flat. Timeouts, lost connections, malformed results, and unavailable reconciliation keep the hold. A flat token releases one symbol only when no unresolved order remains. The token is not broker evidence. Live trading stays blocked.

## 6. Position-state model

CODE MODIFIED. The existing order statuses remain. The new internal marker is `metadata.exposure_safety` with `UNCONFIRMED` or `CONFIRMED_FLAT`. No new table or column. The position object is still memory only. Historical FILLED rows without the marker are not selected and are not declared flat.

## 7. Fill-to-position repairs

A complete synthetic fill creates one position and still blocks another entry. Incomplete evidence does not create a position. A conflicting quantity does not replace the position. Duplicate evidence is idempotent. A persistence fault refuses another reservation. The engine write was not run.

## 8. Position close and release

Popping the position object does not release the hold. Close requested, timeout, connection loss, partial close, rejection, and a malformed result do not release it. The flat token releases only the matching symbol and refuses when an unresolved order remains. It does not erase a durable unconfirmed marker.

## 9. Restart and recovery

SYNTHETICALLY TESTED with snapshots. FILLED, PARTIAL, UNRESOLVED, and PENDING block. Corrupt, stale, and unreadable snapshots fail closed. Repeated loading does not duplicate the order. Application startup and the recovery SQL were NOT_EVALUATED.

## 10. R.8 reservation integration

The prior reservation blocks still pass. An exposure hold cannot be bypassed by a new client id. An open position cannot be bypassed by `try_begin_order_submission`. A database fault still fail-closes. Direction, strategy, and live-auth gates still stop before an order.

## 11. Source modifications

`database.py` holds the marker, the recovery select, and the flat-token rule. `orders.py` stops a fill from releasing the reservation and refuses a reservation while a position exists. `bot_loop.py` checks the hold before sizing and does not continue when position recording fails. `oanda_exec.py` was not edited.

## 12. Test isolation

Runner: `data/research/adaptive_ensemble/r9/20_run_offline_tests.py`. Five socket or DNS attempts were blocked. The dotenv stub ran once. `forex_bot.app` was not imported. The PostgreSQL connection object stayed None.

## 13. Regression test results

120 passed, 0 failed, 7 skipped, 1 deselected. The skips are the earlier engine cases plus I55–I58. Those four are NOT_EVALUATED, not passes. Details are in `10_regression_test_results.json`.

## 14. Remaining defects

The entry path no longer treats FILLED as a free instrument. The position object is still not recovered from a database. The recovery query and the marker update were not engine-tested. Broker reconciliation was not run. Historical FILLED rows without the marker are outside the new select.

## 15. Next three priorities

1. Leave the application, broker, and PostgreSQL stopped.
2. Do not add a position table unless a later approval allows that schema.
3. Do not treat the internal flat token as broker proof.

## 16. Recommended next stage

No automatic next stage. A later approval would be required before any engine test, broker reconciliation, or position-schema design. R.10 is not authorised.

## 17. Final integrity

No production database, no PostgreSQL start, no broker, no network success, no DNS success, no application or trading-loop start, no practice or real order, no strategy activation, no live-permission change, no package install, no Docker, WSL, or VM, no git commit or reset. Writes stayed in the approved source, tests, and `data/research/adaptive_ensemble/r9/`.

## 18. Final classification

`R9_OFFLINE_POSITION_SAFETY_PARTIAL`

SOURCE-REVIEWED: lifecycle and recovery SQL. CODE MODIFIED: bot_loop.py, database.py, orders.py. SYNTHETICALLY TESTED: fills, holds, closes, and snapshots. POSTGRESQL-ENGINE TESTED: no. BROKER-VERIFIED: no. NOT_EVALUATED: I55, I56, I57, I58, startup, and engine recovery.

## 19. Hard stop

R.9 is finished. Production deployment is NO-GO. Practice orders are not authorised. Live trading is not authorised. Rollback is NO-GO. The application was not started and will not be started from this stage.
