# STAGE R.7 — OFFLINE POSTGRESQL ORDER-SAFETY AND PERSISTENT RECOVERY VERIFICATION REPORT

## 1. Executive summary

Overall classification: `R7_OFFLINE_SAFETY_PARTIAL`.

PostgreSQL 18 is installed. It was not used. No disposable cluster was created. Actual PostgreSQL used: NO.

Application files modified: none. Test file added: `tests/test_r7_order_safety.py`.

Tests executed: 13 collected. Passed: 12. Failed: 0. Not evaluated: 1 skipped engine test, covering the concurrency and storage cases.

PostgreSQL tests executed: 0. Synthetic tests executed: 12.

Network connections: 0. Broker requests: 0.

Recommended next action: stop. Do not start the bot. Do not treat the synthetic results as engine proof.

Gates: A blocked for the engine, B source pass, C synthetic pass, D not engine-verified, E partial, F source and synthetic, G pass, H synthetic pass with engine cases skipped, I no repair, J pass.

## 2. Safety and scope

No application source was changed. The real application was not started. No existing database was opened.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`. The three R.5 hashes and the protected hashes matched before the stage. They were not edited.

## 4. PostgreSQL availability

Binaries exist at `C:\Program Files\PostgreSQL\18\bin`. `postgres.exe` is 18.1. `initdb.exe` is 18.0. Starting a server on Windows needs a localhost TCP socket, or an unproven substitute. This stage forbids that socket. The server was not started. `POSTGRESQL_ENGINE_NOT_EVALUATED`.

## 5. Database schema

SOURCE-REVIEWED. `status` is unconstrained text. `UNRESOLVED` fits that column. The only uniqueness rule is the client order id. There is no one-open-row-per-symbol rule. No migration was run.

## 6. Unresolved order persistence

SYNTHETICALLY TESTED. A fake unresolved row keeps its id and symbol, reloads as unresolved, and blocks a new client id in memory. A timeout does not become a cancel. A generic cancel does not clear that in-memory status. This was not a database round trip.

## 7. Concurrent reservations

NOT_EVALUATED on the engine.

SOURCE-REVIEWED: the advisory lock ends when the pending insert commits. The check only looks for `UNRESOLVED`. A second client id can be reserved while the first row is still `PENDING`. That hole was not patched, because the patch could not be executed on PostgreSQL in this stage.

## 8. Database failure modes

Missing, unknown, and corrupt recovery snapshots fail closed in the synthetic tests. Real connection loss, commit failure, and ambiguous commit were not produced.

## 9. Database and memory consistency

The startup loader and the in-memory gate agree on the synthetic cases. `app.py` was not imported. A failed recovery is not treated as an empty book in the current source. That raise was not sent to a server.

## 10. Source repairs

None. The pending-window hole is recorded in `14_remaining_blockers.md`.

## 11. Test isolation

Plugin autoload was off. The project conftest was not loaded. Dotenv was stubbed once. One socket constructor was blocked during import. No connection completed.

## 12. Regression test results

12 passed, 0 failed, 1 skipped. The skip is the PostgreSQL concurrency and storage test. It was not given a pass.

## 13. PostgreSQL engine results

Statements executed: 0. Connections: 0. Cluster created: no.

## 14. Unresolved defects

The lock does not cover the pending window. There is no unique open-row constraint. Ambiguous commit behaviour is untested. The initdb and postgres version strings differ by a patch level. None of this authorises a source change until an isolated engine can run.

## 15. Next three priorities

1. Leave the application off.
2. Do not describe these synthetic tests as PostgreSQL verification.
3. A later stage may start a disposable cluster only if a connection method with no forbidden socket is proven first, or the socket rule is explicitly changed.

## 16. Recommended next stage

None is started. R.8 from the earlier roadmap was a fake startup harness. It is not started either. The database hole is still open.

## 17. Final integrity

No production database, broker, Telegram, package install, Docker, or Git commit. Writes are the new test and the R.7 folder.

## 18. Final classification

`R7_OFFLINE_SAFETY_PARTIAL`

## 19. Hard stop

R.7 is finished. R.8 is not started. The application stays off. Strategies stay inactive. Live orders stay blocked. No order was sent. No database was migrated.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
