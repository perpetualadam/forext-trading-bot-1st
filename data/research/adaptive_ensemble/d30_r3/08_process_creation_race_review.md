# PROCESS CREATION RACE

Windows assigns a new child to the parent's Job Object only after the parent is a member. If the worker runs fixture code before `AssignProcessToJobObject`, it can create a descendant outside the intended job. A short window is not treated as harmless.

The permitted sequence is:

1. `CreateProcessW` with `CREATE_SUSPENDED`.
2. `AssignProcessToJobObject`.
3. `IsProcessInJob` on that same process handle.
4. `ResumeThread` only when membership is true.

While the primary thread stays suspended, the worker interpreter has not started. Fixture code cannot run and cannot call `CreateProcess`.

If assignment or the membership check fails, the supervisor calls `TerminateProcess` on the suspended process handle from `CreateProcess`, waits on that handle, and does not call `ResumeThread`. No descendant is created on that path.

The descendant repeats the rule. It stays suspended until the supervisor has matched its creation `FILETIME` and confirmed the intended Job Object. The resume call stays in the worker, on the thread handle returned with that descendant. An identity mismatch closes the supervisor's newly opened handle and does not terminate an unverified process id.

There is no second path that starts a running worker and assigns the job afterward.
