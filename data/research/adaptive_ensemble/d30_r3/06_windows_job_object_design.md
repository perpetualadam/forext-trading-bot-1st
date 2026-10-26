# WINDOWS JOB OBJECT DESIGN

The supervisor and the worker are separate processes. The supervisor owns the stage clock, the operation clock, the Job Object, both verified process handles, the budgets, and the evidence ledger. The worker owns one allowlisted fixture. The descendant owns one allowlisted sleep or exit. Neither fixture opens a network socket.

```
SUPERVISOR
    |
    +-- unnamed Job Object
            |
            +-- synthetic worker
                    |
                    +-- one synthetic descendant
```

## Creation order

The worker is created with `CREATE_SUSPENDED`. `AssignProcessToJobObject` runs next. `IsProcessInJob` must be true for that process handle. `ResumeThread` runs only after that check. The previous suspend count returned by `ResumeThread` is retained so a thread that was already running is visible.

The descendant uses the same order. The worker creates it suspended, publishes its process id and creation `FILETIME`, and waits. The supervisor opens that process, requires the creation time to match, and requires membership in the same Job Object. Only then does the supervisor send `resume`. The worker calls `ResumeThread` on the thread handle from its own `CreateProcess`. The supervisor does not resume a thread id it looked up.

`CREATE_BREAKAWAY_FROM_JOB` is not a creation flag. `JOB_OBJECT_LIMIT_BREAKAWAY_OK` and `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK` are not limit flags.

## Limits

`JOBOBJECT_EXTENDED_LIMIT_INFORMATION` carries:

- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
- `JOB_OBJECT_LIMIT_ACTIVE_PROCESS`

Worker-only fixtures set the active limit to 1. Fixtures that need a descendant set it to 2. The flags are read back with `QueryInformationJobObject` before resume.

## Handles

The worker is started with `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`. The inherited handles are `NUL`, the stdout write end, and the stderr write end. The Job Object handle is not inheritable and is not in that list. The descendant is started with a handle list that contains only `NUL`.

The supervisor keeps the worker process handle from `CreateProcess`. It keeps the descendant process handle from `OpenProcess` only after the creation time matches. Exit waits use those handles with `WaitForSingleObject` and `GetExitCodeProcess`. A process id is not treated as an exit proof.

Termination of a live tree uses `TerminateJobObject` on the supervisor's job handle. `TerminateProcess` is reserved for a process handle this stage created or verified, and only when that process must be stopped without being resumed or when job termination did not reap that same handle. There is no name-based process scan.

## Clocks

The operation deadline, the moment termination is requested, the cleanup duration, and the confirmed exit are separate measurements. Cleanup has its own allowance. A wait that returns at the operation deadline is not recorded as completed cleanup.

## Nested jobs

If this Python process is already in a Job Object, a new job is a nested job on Windows versions that allow it. Assignment failure stops the stage before a descendant exists. The suspended worker is then terminated through the handle `CreateProcess` returned.

## What this design does not claim

A passing Job Object test does not show that real DNS, TLS, or HTTP can be cancelled. It does not measure Python ABI or libc. It does not make the tested Windows version a universal guarantee.
