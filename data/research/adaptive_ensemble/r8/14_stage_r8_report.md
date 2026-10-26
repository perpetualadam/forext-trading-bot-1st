# STAGE R.8 — OFFLINE ORDER-RESERVATION SAFETY REPAIR AND REGRESSION TEST REPORT

## 1. Executive summary

Classification: `R8_OFFLINE_RESERVATION_REPAIR_PARTIAL`.

The pending-window defect is repaired in source and covered by synthetic tests. PostgreSQL was not started, so the lock and the committed row were not engine-tested. A filled order is still not proof that exposure is closed. That position question was recorded and not patched with a migration or a permanent block.

Gates A–K: A source-reviewed; B policy defined; C source repair done, engine not run; D position gap left open; E synthetic recovery passed; F synthetic failures reviewed, engine concurrency not evaluated; G existing safety rerun; H isolation held; I 102 passed, 3 skipped, 0 failed; J scope held; K no prohibited operation.

Files modified: `forex_bot/database.py`, `forex_bot/orders.py`, `tests/test_r5_integration.py`. New test file: `tests/test_r8_reservation_safety.py`. `bot_loop.py` was not modified.

Tests collected 106. Executed 102. Passed 102. Failed 0. Skipped 3. Deselected 1. Not evaluated 3.

Pending-window defect: repaired in source, synthetically tested, not engine-proven.

PostgreSQL engine: NOT_EVALUATED. Application startup: not run. Network requests succeeded: 0. Broker requests: 0.

Next action: stop. Do not start R.9.

## 2. Safety and scope

No application start, no `run_bot`, no OANDA, no Telegram or Discord, no `.env` read, no production or existing database, no PostgreSQL server, no Docker, WSL, or VM, no package install, no git commit or reset. The socket barrier rejects constructors before they open. DNS lookup raises. Persistence was forced off.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. Pre-stage hashes matched. Protected hashes still match. `bot_loop.py` is unchanged.

Post-stage: database.py `6cafdc5aba020b774f6f235b427d34950d373e5427da9c97fcbe1cfcbfc0c7d9`. orders.py `ed05062d895574fc1ea21d1486f316271165466bf01330cf38e8a42c4c4450b1`.

The git diff against HEAD is the whole dirty tree, 736 insertions and 100 deletions across the three application files. That count includes earlier stages. R.8 did not edit `bot_loop.py`.

## 4. Order lifecycle map

SOURCE-REVIEWED in `02_order_lifecycle_map.md`. Signal, live auth, strategy, and direction all return before sizing when they fail. Reservation is `try_begin_order_submission` after `broker_entry_block_reason`, and broker dispatch is later in the same function. The loop was not executed.

## 5. Reservation policy

PENDING, PARTIAL, UNRESOLVED, and unknown statuses block another client id for the same symbol. CANCELLED and REJECTED release that symbol's reservation hold only. FILLED releases the in-flight reservation and does not prove the position is flat. The policy lives in `reservation_status_block_reason` and is used by the insert, the memory book, recovery, and the preflight.

## 6. Pending-window repair

CODE MODIFIED. The old check selected only UNRESOLVED. The new check, still inside the advisory-lock transaction, selects any status other than FILLED, CANCELLED, or REJECTED before insert. The in-process map blocks a second id after the first call returns, including when persistence is off. A fault fail-closes and does not retry. SYNTHETICALLY TESTED. POSTGRESQL-ENGINE TESTED: no.

## 7. Order status and position safety

Order status and the position object are different records. `order_status_proves_exposure_closed` is false for FILLED. The loop returns at `POSITION_ALREADY_OPEN` before reservation while a position object exists. A fill that never records a position is an open design question. No migration and no permanent symbol block were added.

## 8. Recovery and restart

SYNTHETICALLY TESTED. PENDING, PARTIAL, and UNRESOLVED snapshots still block. Unknown, malformed, and unreadable snapshots fail closed. A failed read is not treated as an empty safe book. Engine recovery was not run.

## 9. Failure and concurrency

Sequential and in-process concurrent reservations cannot both succeed. Different symbols can. Duplicate ids do not create a second order. Lock timeout, deadlock, and ambiguous commit are fail-closed in source and by the synthetic fault flag. Their PostgreSQL behaviour is NOT_EVALUATED. The thread test is not PostgreSQL proof.

## 10. Integration with existing safety

Invalid direction and inactive strategy still stop before sizing. Live authorisation stays blocked. UNRESOLVED cannot be erased by generic cancel. No replacement order is created. The loop source still checks the block and the reservation before `execute_oanda_market_open`. A false reservation does not register an order.

## 11. Source modifications

`database.py` holds the policy, the transaction check, and the fail-closed fault path. `orders.py` checks memory, restores active recovery rows, and releases a hold on authoritative cancel or full fill. One R.5 assertion changed from true to false because that true result was the defect. No strategy, sizing, risk, or startup edit.

## 12. Test isolation

Runner: `data/research/adaptive_ensemble/r8/20_run_offline_tests.py`. Plugins disabled. Three socket or DNS attempts were blocked. The dotenv stub was called once. No family was allowed through. `forex_bot.app` was not imported. The PostgreSQL connection object stayed None.

## 13. Regression test results

102 passed, 0 failed, 3 skipped, 1 deselected. The skips are the R.7 engine case and R.8 I39 and I40. They are NOT_EVALUATED, not passes. I27 is a source assertion, not an executed transaction. I26 is an in-process lock. Details are in `10_regression_test_results.json`.

## 14. Remaining defects

The pending-window hole in the reservation function is closed in source and in the synthetic book. It is not closed by an engine test. FILLED versus an open broker position remains unresolved by design stop. There is still no database constraint limiting one active row per symbol.

## 15. Next three priorities

1. Keep the application, broker, and PostgreSQL stopped until a later approval names an engine test that does not use a forbidden socket.
2. Decide position-state handling for a fill that has no position record, in its own approved stage, without a hidden permanent block.
3. Leave the live-order gate blocked and the strategies inactive.

## 16. Recommended next stage

No automatic next stage. A later approval can review position state, or can design an engine test that stays inside the network rules. R.9 is not authorised by this result.

## 17. Final integrity

No production database, no existing database, no PostgreSQL start, no broker, no Telegram or Discord, no external network success, no DNS success, no application or trading-loop start, no practice or real order, no strategy activation, no live-permission change, no package install, no Docker, WSL, or VM, no git commit or reset. Writes stayed in the approved source, tests, and r8 artifacts.

## 18. Final classification

`R8_OFFLINE_RESERVATION_REPAIR_PARTIAL`

SOURCE-REVIEWED: lifecycle, SQL text, and loop call order. CODE MODIFIED: database.py and orders.py. SYNTHETICALLY TESTED: reservation, recovery, and concurrency in memory. POSTGRESQL-ENGINE TESTED: no. NOT_EVALUATED: I39, I40, and engine lock behaviour.

## 19. Hard stop

R.8 is finished. Production deployment is NO-GO. Practice orders are not authorised. Live trading is not authorised. Rollback is NO-GO. The application was not started and will not be started from this stage.
