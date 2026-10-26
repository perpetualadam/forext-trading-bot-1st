# R.79 Multiprocess Results

Evidence class: executed subprocess tests.

| Test | Platform | Result |
| --- | --- | --- |
| R.79 `test_13` second process holds `RecoveryOwnerLock` | Windows | Startup reason `recovery_already_in_progress`. Management false. |
| Same test | Linux, `TMPDIR=/tmp` | Passed inside the 17-test run. |
| R.78 crashed owner, PID reuse, two repairs, overlapping repairs, second startup | Windows | 21 passed. |
| Same R.78 suite | Linux disposable interpreter | 21 passed. |

The R.75 two-process close test and the R.76 two-process entry test previously expected one broker write. Those workers do not run startup, so they now have no fencing epoch. The close worker no longer reaches PositionClose, and the entry worker no longer reaches the entered-file point before OrderCreate. Those historical tests fail. They were not rewritten.

An authorised owner can still close once in-process (`test_15`) and can still submit one OrderCreate (`test_16`). A second process cannot acquire the recovery lock while that owner holds it. Two authorised recovery sessions at the same time were not constructed, because the lock is exclusive.

No test claimed reboot safety from a stored boot-id mismatch.
