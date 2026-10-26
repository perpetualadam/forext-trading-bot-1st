# R.24 startup recovery failures

Failures were confined to the R.24 database. The Windows service and port 5432 were not used.

| Case | What was done | Application result | Evaluate | Dispatch |
| --- | --- | --- | --- | --- |
| Connection unavailable | `CONNECT` revoked from `r24_tester` on `r24_synthetic_orders`, then restored | `read_durable_recovery` returned unreadable and set the failure latch | `recovery_unreadable` | 0 |
| Query failure | `client_order_id` removed from `exec_orders`, then restored | `OrderRecoveryUnreadable: order recovery query failed` | `recovery_unreadable` | 0 |
| Explicit unsuccessful snapshot | `ingest_recovery_snapshot([], False)` | `OrderRecoveryUnreadable` | `recovery_unreadable` before and after `confirm_exposure_flat` | 0 |
| Empty success | Recovery before any orders | 0 rows, readable, failure latch clear | `ai_vote_rejected`, not `recovery_unreadable` | 0 |
| Existing exposure | FILLED, UNRESOLVED, and PARTIAL rows recovered | Failure latch clear, exposure hold kept | `exposure_unconfirmed` on a repeated evaluate | 0 |
| Failed insert | Before-insert trigger raised `r24_insert_rejected`, then the trigger was removed | Insert returned false, no row, failure latch set | `recovery_unreadable` | 0 |

`confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")` returned false. It did not clear an unreadable recovery or an exposure hold.

A later process inserted `cid-r24-after` on `EUR_GBP` after the failed transaction had ended. That insert succeeded, so the failed transaction had released its lock.
