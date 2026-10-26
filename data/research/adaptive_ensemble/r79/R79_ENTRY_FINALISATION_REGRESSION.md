# R.79 Entry Finalisation Regression

Evidence class: executed R.79 tests and the R.77 suite. `commit_verified_entry` was not edited. `entry_journal.py` hash remains `aea5b74e0f431a90b1bd410d650295a5b79d4d901f77391234cd9ddaa5653a07`.

The durable managed-position insert and `ENTRY_FINALISED` remain one transaction. Memory publication now happens only when `recovery_fence_allows_publication()` is true after that commit.

| Case | Result |
| --- | --- |
| Successful finalisation without a recovery session | Journal `ENTRY_FINALISED`. Memory not published. `test_08`. |
| Successful finalisation after recovery | Memory published. `test_17`. |
| Failure during commit after a synthetic OrderCreate | One OrderCreate, `JournalUnavailable`, outcome `ENTRY_OUTCOME_AMBIGUOUS`, memory empty. `test_16`. No second order. |
| Repeat finalisation | Stored `profit_protection_exit_pips` stayed `3.5`. `test_17`. |
| Duplicate client id, duplicate trade, conflicting instance | R.77 tests for those journal refusals remained in the passing set. The suite ended 82 passed, 2 failed, 3 errors of 87. |
| Missing stop or take-profit, partial fill, mixed response, ambiguous body | Covered by the passing remainder of R.77. The new failures are the memory-publication assertion, the ratchet test that indexed memory before the journal assertion, and the OrderCreate test that expected a submit without recovery. |
| Stale authority during publication | `test_05` refuses `publish_recovered` with `recovery_fence_lost`. |

R.77 `test_01` now fails on `published is True` before it reads the journal. `test_08` in R.79 reads the journal and confirms `ENTRY_FINALISED`. The classification reason on the evidence object is not overwritten.

No retry was added after an ambiguous broker response. Strategy, size, and stop-loss or take-profit policy were not changed.
