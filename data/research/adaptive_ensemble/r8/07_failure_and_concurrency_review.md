# Failure and concurrency

| Case | Evidence | Result |
| --- | --- | --- |
| F01 Two sequential reservations, same symbol | SYNTHETICALLY TESTED | First accepted, second refused. |
| F02 Two concurrent reservations, same symbol | SYNTHETICALLY TESTED in-process lock | One true and one false. |
| F03 Different client ids | SYNTHETICALLY TESTED | The second id does not bypass. |
| F04 Duplicate client id | SYNTHETICALLY TESTED | Second call returns false and leaves one order. |
| F05 Rollback | SOURCE-REVIEWED | The exception path calls rollback and then fail-closes. |
| F06 Commit failure | SOURCE-REVIEWED and synthetic flag | Returns false and blocks later ids. |
| F07 Ambiguous commit | SOURCE-REVIEWED and synthetic flag | Returns false, records the hold, sets fail-closed. No retry. |
| F08 Connection loss | SOURCE-REVIEWED | A missing connection refuses and fail-closes when persistence is requested. |
| F09 Lock acquisition failure | Synthetic flag only | The except path fail-closes. Engine lock failure was not run. |
| F10 Lock timeout | NOT_EVALUATED on the engine | Same fail-closed source path. |
| F11 Deadlock | NOT_EVALUATED on the engine | Same fail-closed source path. |
| F12 Status update beside a reservation | SOURCE-REVIEWED | Terminal cancel releases only that symbol. UNRESOLVED is left in place. |
| F13 Recovery overlapping a reservation | SYNTHETICALLY TESTED | Loaded active rows block a new id. |
| F14 Reconciliation overlapping a reservation | SOURCE-REVIEWED | Unavailable reconciliation stays blocked. No broker call. |
| F15 Different symbols | SYNTHETICALLY TESTED | Distinct lock keys and both reservations accepted. |
| F16 Duplicate broker events | Existing book helper | The first unresolved id is kept. |
| F17 Missing broker response | Existing ambiguous path | Becomes UNRESOLVED and stays blocking. |
| F18 Malformed broker response | Existing classifier tests in the rerun | Not a successful reservation. |
| F19 Pending then unresolved | SYNTHETICALLY TESTED | The block remains. |
| F20 Partial then connection loss | SYNTHETICALLY TESTED | The block remains. |

PostgreSQL engine concurrency: NOT_EVALUATED. No atomicity claim is made from the synthetic thread test or from reading the SQL text.
