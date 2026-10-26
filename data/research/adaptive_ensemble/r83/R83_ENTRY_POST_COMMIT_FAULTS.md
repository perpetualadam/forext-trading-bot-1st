# R.83 entry post-commit faults

## Exception — `test_02_publication_exception_keeps_finalised_entry`

Executed in-process. Real startup, one synthetic OrderCreate, then `entry_capture.positions.__setitem__` raises `RuntimeError` after `commit_verified_entry` returns.

| Record | Result |
| --- | --- |
| OrderCreate | 1 |
| Outcome | `ENTRY_FINALISED` |
| `network_permit` | 1 |
| Broker trade | `T-R83` |
| In-memory book | Empty |
| Managed rows | 1 |
| Second `begin_entry_submission` for `client-r83` | `JournalUnavailable` |

The same client is not reserved again and a second OrderCreate is not sent. This is an exception test, not a process kill.

## Authority change — `test_04_stale_owner_publication_is_refused`

A child pauses inside `recovery_fence_allows_publication` after the durable commit and before that check reads the epoch. A successor process runs real startup. The child is then released.

| Record | Result |
| --- | --- |
| OrderCreate in the recorder | 1 |
| Child `published` | 0 |
| Successor `manageable` | 1 |
| Successor state | Printed by `race_worker.py` mode `successor` |

The stale process does not publish. The successor reconstructs the one durable position. This uses a real `execute_startup_sequence`, not a direct epoch write.

## Memory publication then continued life

`test_03` kills during the assignment, so publication does not complete. A separate case where publication succeeds and the process is killed before a later observation is the normal finalised row with the position already in the dead process's memory. The successor test in `test_04` is the reconstruction after commit. A kill after a completed assignment was not given its own barrier. The durable row and the client registry are already committed at that point, so a later observation cannot create a second entry. That last sub-case is covered by the committed state in `test_02` and `test_03`, not by a fourth kill.
