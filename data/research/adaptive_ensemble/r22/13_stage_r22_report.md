# STAGE R.22 — OFFLINE RESTART RECOVERY AND PERSISTENT ORDER-STATE INTEGRATION REPORT

## 1. Executive summary and classification

**Classification: `R22_OFFLINE_RESTART_RECOVERY_INTEGRATED`**

A FILLED order and an UNRESOLVED order were written by the real offline `evaluate` path into an isolated JSON store. The in-memory maps were cleared. `initialise_application` rebuilt them through `select_rows_for_recovery` and `ingest_recovery_snapshot`. The second `evaluate` blocked before reservation and dispatch. PostgreSQL was not used.

| Scenario | Instance A | Restart | Instance B | Inert dispatches | Result |
|---|---|---|---|---|---|
| FILLED | Synthetic FILLED recorded | Fresh startup and recovery | Exposure blocks | 1 total | PASS |
| UNRESOLVED | Ambiguous attempt recorded | Fresh startup and recovery | Exposure blocks | 1 total | PASS |

## 2. Safety and scope

Production deployment is NO-GO. Practice orders are not authorised. Live trading is not authorised. Rollback is NO-GO. No launcher, broker client, PostgreSQL server, network, or operational state was used.

## 3. Baseline integrity

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The measured R.21 `bot_loop.py` hash was `081314246ce22fa092d6f7de9ef8f84760bf87e086f5838e763fb08d7f34f55f`. Supporting hashes for `app.py`, `orders.py`, and the pre-change `database.py` matched the known values. `r22` was empty before this stage.

## 4. Actual recovery contract

`initialise_application` calls `select_rows_for_recovery` and `ingest_recovery_snapshot`. Those two functions reconstructed the exposure. The file reader only supplied rows. It did not set the hold maps itself.

The recovery logic is the offline branch of the production startup function. The production lifespan, which opens PostgreSQL and calls `run_bot`, was not executed. A test-only parser did not replace `ingest_recovery_snapshot`.

## 5. Isolated persistent test store

JSON files under `r22/stores`, schema `exec_orders_offline_v1`. The variable `EXEC_ORDER_OFFLINE_STORE` enables them. Unset, the old persistence behaviour remains. This is not a PostgreSQL certification.

## 6. FILLED restart trace

Instance A: one inert dispatch, status `FILLED`, strategy `scalp`, production eligibility false. File SHA-256 `e6594e518dc92ca2d4953a1f33e39ec1669276e68e64f2e7b6789872b55cc987`. Maps were then all zero and the hash was unchanged. Instance B read `exposure_unconfirmed`, did not reserve, and did not dispatch.

## 7. UNRESOLVED restart trace

Instance A: one inert dispatch, status `UNRESOLVED`. File SHA-256 `f2e1924aef6fb54160cb738ba2d1bd8ff420180783d632ea42b48afb0f2e79a2`. Recovery rebuilt a new order with that status. Instance B stopped with `exposure_unconfirmed` and did not retry.

## 8. Legacy and failure cases

PENDING, PARTIAL, FILLED, UNRESOLVED, and legacy FILLED rows block. Missing, corrupt, truncated, duplicate, and inconsistent files fail closed. A failed store write refuses the reservation before dispatch. A caller flat marker does not release exposure. The scenarios did not write `CONFIRMED_FLAT`.

## 9. Source modifications

`forex_bot/database.py` and `forex_bot/bot_loop.py`. No protected file changed. `orders.py` and `app.py` are unchanged.

## 10. Test isolation

Sockets and DNS were blocked. Dotenv was stubbed. `PERSIST_EXEC_ORDERS=0`. The safety-state path and the order files are under `r22`, not under the R.10 safety-state file. Blocked attempts were recorded. Successes were zero.

## 11. R.22 test results

20 passed, 0 failed, exit 0.

## 12. R.8–R.21 regressions

All exited 0. R.21 passed 24 under its own runner. In the combined R.22 process that one network assertion saw the R.22 barrier token; that is a token mismatch, and the dedicated rerun passed. R.10 did not hit `WinError 5`. Hash pins were updated to the new source hashes.

## 13. Remaining integration gaps

No PostgreSQL durability. No second operating-system process. The position book is not restored from the file. Production eligibility stays false.

## 14. Next three priorities

1. Keep the JSON store disabled unless an offline test sets its path.
2. When a database is authorised, run the same FILLED and UNRESOLVED records through the existing PostgreSQL recovery reader.
3. Decide whether a recovered fill should also rebuild the local position book.

## 15. Recommended next milestone

A separately approved check of this same recovery contract against PostgreSQL, or a second-process restart. Neither is authorised by this stage.

## 16. Final integrity

`bot_loop.py` `a8b455dad91c464df8ba030b7f119f3c1795ce289e21b83de0af771309823ac2`. `database.py` `c6f761104a3ff3fb36a23aa0e90a9f6516c4c802ed233319151c2b27875ff563`. Broker calls, PostgreSQL connections, and network successes were zero.

## 17. Final classification

`R22_OFFLINE_RESTART_RECOVERY_INTEGRATED`

The original maps were destroyed. The file survived. Instance B was a new startup plus a new `evaluate` after those maps were empty, in the same interpreter. It called `evaluate`, attempted no reservation, called no inert adapter, and created no duplicate order. PostgreSQL and OANDA were not contacted. Production eligibility remained false. No protected file changed.

## 18. Hard stop

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

End of stage R.22. No further stage was started.
