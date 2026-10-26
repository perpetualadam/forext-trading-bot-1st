# Recovery and restart

Evidence: SYNTHETICALLY TESTED with snapshot rows. The application was not started. PostgreSQL was not queried.

| Case | Result |
| --- | --- |
| E01 Existing PENDING | Ingest keeps PENDING and a new client id is refused. |
| E02 Existing PARTIAL | Ingest keeps PARTIAL and a new client id is refused. |
| E03 Existing UNRESOLVED | Ingest keeps UNRESOLVED and a new client id is refused. |
| E04 Unknown status | Ingest raises `OrderRecoveryUnreadable` and fail-closes. |
| E05 Malformed row | A row missing its client id raises and fail-closes. |
| E06 Duplicate client id | The second ingest of the same id does not create another local order. |
| E07 Multiple active rows | Two active rows for one symbol block a new id. |
| E08 Recovery query failure | An unreadable snapshot fail-closes. The real query was not run. |
| E09 Empty confirmed read | A readable empty list does not invent orders. A failed read is not turned into that empty list. |
| E10 Missing required state | Missing fields fail closed. |
| E11 Corrupt snapshot | Unknown status and non-list input fail closed. |
| E12 Database unavailable | Persistence off is treated as unreadable by `read_durable_recovery`. A reservation fault sets the fail-closed flag. No server was contacted. |
| E13 Restart during broker timeout | Synthetic UNRESOLVED survives ingest and still blocks. |
| E14 Restart during a reservation | Synthetic PENDING survives ingest and still blocks. |
| E15 Restart after an ambiguous commit | The process flag blocks until restart. After restart, a surviving PENDING or UNRESOLVED row blocks. An engine commit that the client did not see was not created. |

Failed recovery is not treated as an empty safe book. `broker_entry_block_reason` returns `recovery_unreadable` when the snapshot cannot be read.
