# Recovery ingestion results

SYNTHETICALLY TESTED through `select_rows_for_recovery` and `ingest_recovery_snapshot`.

| Case | Result |
| --- | --- |
| Missing metadata | Selected and held as `exposure_unconfirmed` |
| NULL metadata | Selected. Not treated as flat |
| Empty metadata | Selected. Not treated as flat |
| Malformed metadata | Selected, then ingest fail-closes |
| UNCONFIRMED | Selected and held |
| CONFIRMED_FLAT alone | Not selected. Token is not broker evidence |
| Unknown marker | Selected, then ingest fail-closes |
| PENDING, PARTIAL, UNRESOLVED | Selected and held |
| Unknown status | Fail closed |
| Identical duplicate client id | One order |
| Same client id with a different identity | Fail closed, neither row overwrites the other |
| Missing symbol or client id | Fail closed |
| Two FILLED rows for one symbol | Both retained. The symbol stays blocked |
| FILLED plus UNRESOLVED | Flat token refused |
| Empty cursor result | Success, fail-closed flag stays false |
| Query exception | `OrderRecoveryUnreadable`, then the loader fail-closes |

No broker position was fabricated.
