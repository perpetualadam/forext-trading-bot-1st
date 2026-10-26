# Order and position recovery

The offline path calls the real `ingest_recovery_snapshot` and the real `exposure_entry_block_reason`. Rows are synthetic. PostgreSQL was not queried.

| Scenario | Result |
| --- | --- |
| E01 empty readable book | No exposure block. Offline ready. Trading ready stays false. |
| E02 PENDING | `active_reservation` |
| E03 PARTIAL | `active_reservation` |
| E04 UNRESOLVED | `unresolved_intent` |
| E05 FILLED with UNCONFIRMED | `exposure_unconfirmed`. Empty position slot is not flat proof. |
| E06 FILLED without marker, when the row is supplied | `exposure_unconfirmed` |
| E07 corrupt status | `OrderRecoveryUnreadable`, not ready |
| E08 missing symbol | `OrderRecoveryUnreadable`, not ready |
| E09 provider raises | `RuntimeError`, not ready |
| E10 provider returns a non-list | `OrderRecoveryUnreadable`, not ready |
| E11 duplicate client id | One in-memory order |
| E12 two active rows for one symbol | Both retained. Entry stays blocked. |
| E13 missing position | Hold remains |
| E14 conflicting synthetic position | `record_synthetic_fill_position` returns `conflict` and does not replace the position |
| E15 reconciliation unavailable | Startup can still finish offline initialization. The reservation hold stays. |
| E16 historical FILLED without the R.9 marker | NOT RESOLVED. `fetch_exec_orders_open_for_recovery` still does not select an unmarked FILLED row. A supplied snapshot blocks through ingest. |
| E17 unknown exposure token | `confirm_exposure_flat` returns false |
| E18 CONFIRMED_FLAT while UNRESOLVED remains | Flat token refused |
| E19 repeated initialization with the same row | Order count stays 1 |
| E20 recovery failure | `offline_ready` and `trading_ready` stay false |

`order_status_proves_exposure_closed` remains false for FILLED. A synthetic flat token is not broker evidence.
