# R.83 test matrix

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1 | R.82 baseline integrity | PASS | Hashes and archive matched before the two R.83 edits. R.82 suite 19/0/0/0 on Windows and Linux |
| 2 | Entry durable commit before publication | PASS | `test_02` leaves `ENTRY_FINALISED` while the book assignment raises |
| 3 | Entry publication exception after commit | PASS | `test_02`. OrderCreate count 1. Client retained |
| 4 | Entry process kill after commit | PASS | `test_03`. `process.kill()` during the book assignment |
| 5 | Entry stale-owner publication refusal | PASS | `test_04`. Child `published=0` after a real successor startup |
| 6 | Entry fresh-process reconstruction | PASS | `test_03` successor `manageable=1`, trade `T-R83`, units 1000 |
| 7 | Entry client-ID reuse refusal | PASS | `test_02` and `test_03` raise `JournalUnavailable` on a second begin |
| 8 | Entry duplicate publication refusal | PASS | `test_04` publishes once in the successor. Recorder stays 1 |
| 9 | Close durable full confirmation before removal | PASS | `test_05`. Confirmed 1000, remaining 0, before the caller raises |
| 10 | Close removal exception after commit | PASS | `test_05`. The exception is between the close return and `close_confirmed_live_position` |
| 11 | Close process kill before removal | PASS | `test_06` |
| 12 | Close stale-owner removal | PASS | `test_07` returns `None` and does not write `CLOSE_FINALISED` |
| 13 | Close fresh-process reconciliation | PASS | `test_06` successor. `manageable=0`. Confirmation retained |
| 14 | Close conflicting broker snapshot | PASS | `test_07` successor `manageable=0` with the original units still in the snapshot |
| 15 | No second PositionClose | PASS | Recorder or call list stays at one in `test_05`, `test_06`, `test_07`, and `test_08` |
| 16 | Partial-close commit before process kill | PASS | `test_08` |
| 17 | Partial-close restart quarantine | PASS | `test_08` `manageable=0` |
| 18 | Partial 400/1000 retained | PASS | Confirmed 400, remaining 600, durable units 1000 |
| 19 | Partial ratchet preserved | PASS | `ratchet=40` |
| 20 | Genuine `SQLITE_BUSY` on the production WAL authority SELECT | NOT_VERIFIED | `SQLITE_BUSY_AUTHORITY_READ_NOT_REPRODUCED`. A DELETE-mode disposable SELECT did raise `SQLITE_BUSY` code 5 in `test_09` |
| 21 | Genuine `SQLITE_LOCKED` on the authority SELECT | NOT_VERIFIED | `test_10` raises `SQLITE_LOCKED_SHAREDCACHE` code 262 on shared-cache `BEGIN IMMEDIATE`. The SELECT succeeded. Shared cache is not the production configuration |
| 22 | Injected busy on entry authority read | PASS | `test_11`, labelled `INJECTED_SQLITE_BUSY`. OrderCreate 0 |
| 23 | Injected busy on close authority read | PASS | `test_11` GBP_USD trade `T2`, labelled `INJECTED_SQLITE_BUSY`. PositionClose 0 |
| 24 | Injected locked on entry authority read | PASS | `test_11` client `client-locked`, labelled `INJECTED_SQLITE_LOCKED`. OrderCreate 0 |
| 25 | Injected locked on close authority read | PASS | `test_11` EUR_USD, labelled `INJECTED_SQLITE_LOCKED`. PositionClose 0 |
| 26 | Closed journal on entry authority read | PASS | `test_12`. OrderCreate 0 |
| 27 | Closed journal on close authority read | PASS | `test_14`. PositionClose 0 |
| 28 | Missing authority row | PASS | `test_12` raises `EntryGuardRefusal`. OrderCreate 0 |
| 29 | Stale recovery epoch | PASS | `test_14` epoch update sends no close. `test_04` and `test_07` use a real successor startup |
| 30 | Negative `tradesClosed` units | PASS | `test_13` raises `CloseReadError`. Source lines 526-528 unchanged |
| 31 | Positive partial closed units | PASS | 400 remaining 600, and 999 remaining 1 |
| 32 | Full closed units | PASS | 1000 remaining 0 |
| 33 | Overfill and zero units | PASS | Both `CLOSE_RECONCILIATION_REQUIRED`. Zero is not full |
| 34 | Wrong identity and duplicate transaction | PASS | Wrong account, instrument, trade, empty id, and duplicate trade id raise `CloseReadError` |
| 35 | R.82–R.78 regression | PASS | 19, 16, 17, 17, and 21 passed on Windows and Linux |

Rows 20 and 21 are not marked PASS. The DELETE-mode busy result and the shared-cache locked result are executed evidence of different configurations.
