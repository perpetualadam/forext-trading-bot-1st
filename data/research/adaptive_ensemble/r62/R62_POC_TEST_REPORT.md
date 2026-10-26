# R.62 proof-of-concept test report

Stage A selected `R62_DESIGN_APPROVED_FOR_ISOLATED_POC`. The experiment lives only under `data\research\adaptive_ensemble\r62\poc\`. R.61 was not edited. The suite does not import the diagnostic supervisor, a broker client, or credential loading.

## Environment

| Host | Result |
| --- | --- |
| Windows 11 10.0.26300, CPython 3.13.5, pytest 8.4.1 | 13 passed, 4 skipped, 7.37s |
| WSL2 Ubuntu 24.04.3 LTS, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3, pytest 9.1.1 from `$HOME/r60pytest` | 5 passed, 12 skipped, 4.91s |

Skipped tests are the other platform's cases. A failed containment result is not hidden behind a skip.

Windows command, from the project root:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r62\poc\test_contained_launch.py -q --tb=line
```

WSL2 command:

```text
"$HOME/r60pytest/bin/python" -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r62/poc/test_contained_launch.py -q --tb=line
```

`REAL_NETWORK_EXECUTION_NOT_TESTED`.

## What the suite actually ran

There is no middle launcher. `LAUNCHER_CREATED` is not a runtime state. The owner process holds the job handle or the pidfd.

| Experiment | Windows | WSL2 |
| --- | --- | --- |
| Deadline already passed before create | No process, no side-effect file | Same path exists in the module and was not the WSL case that ran |
| Process created, deadline expires before resume or exec | Suspended process terminated. `side.txt` absent. Exit verified | Parked child received no `R` byte. `side.txt` absent. Exit verified |
| Containment setup fails | Simulated `OSError` before assign. Process not resumed. Side-effect absent | cgroup mkdir returned errno 13. Reported `CONTAINMENT_UNAVAILABLE:13` |
| Grandchild of a running worker | Died when the last job handle closed. Harness did not have to kill it | Direct child and grandchild were both still alive after the owner called `os._exit`. Harness then killed both. Containment failed |
| Child installs a SIGTERM handler | Job close still ended it | Not separately run |
| Child exits before the ready file | Exit verified, ready false | Not separately run |
| One extra job handle remains | First close left the worker alive (`CLEANUP_INCOMPLETE`). Closing the duplicate then ended it | Not applicable |
| Ready file contents are ignored | Shutdown still verified exit | Not separately run |
| Three launches in sequence | Each shutdown verified. No harness kill | Not separately run |
| 256 KiB write into a non-reading stdin | Writer finished after job close in under 4s. Owner thread did not close the write end while the child was alive | Not run. The file protocol is what the Linux cases use |
| Caller blocked in a pre-create hook | Outer driver still alive 0.5s after the deadline, then killed. Status stayed `entered`. No side-effect file | Not run. This hook is before `CreateProcess` and does not cancel a kernel create |
| Owner exits after the worker is running | Worker and grandchild both dead. No follow-up kill | Worker and grandchild both survived. Follow-up kill was required |

## Startup ownership

`VERIFIED_WINDOWS` for the pre-resume deadline: the side-effect file stayed absent and the process handle was not `STILL_ACTIVE` after termination.

`VERIFIED_LINUX_WSL2` for the pre-exec deadline and for owner death before the `R` byte: the parked child exited and `side.txt` was absent.

`KNOWN_LIMITATION`: a blocked `CreateProcess` or `fork` is not cancelled. The stall test blocks in a Python hook before the kernel call, then an outer process kills that caller. It shows that the caller had not returned and that no worker file appeared. It does not show that the kernel call is cancellable.

`SOURCE_REVIEW_ONLY`: the few instructions between `CreateProcess` returning and `AssignProcessToJobObject` are not crash-injected. A crash in that window can leave a suspended process outside the job.

## Descendant containment

`VERIFIED_WINDOWS` on this host: a grandchild started by the synthetic worker was in the kill domain. Closing the last job handle, including by owner process exit, left both the worker and the grandchild not `STILL_ACTIVE`. The test recorded `harness_intervened` false on the in-process shutdown path.

`KNOWN_LIMITATION` / failed containment on this WSL2 host: cgroup creation under `/sys/fs/cgroup/init.scope` was denied. pidfd identifies the direct child and does not include the grandchild. After owner exit, both the worker (pid recorded by the owner) and the grandchild (pid written by the worker) were still alive. The test fails closed if the grandchild is already dead, because that would hide the gap. The harness killed both afterwards. That cleanup is not counted as containment.

Process groups and `killpg` were not used.

## Resource and IPC observations

The duplicate job handle is the observed cleanup gap: `KILL_ON_JOB_CLOSE` runs when the last handle closes. One close left the worker alive. The report state stayed `CLEANUP_INCOMPLETE` until the duplicate was closed.

The stdin test did not call `close()` on the write end from the owner thread. Job close unblocked the 256 KiB `os.write`. Elapsed time was under 4 seconds. `stdin_closed_while_alive` stayed false.

`fail_job=True` is a simulated assignment failure, not a real handle-table exhaustion. Real exhaustion was not induced.

No synthetic sleeper was left after the Windows suite or the WSL2 suite. An earlier debug grandchild was killed before the final WSL2 run.

## Unsupported guarantees

- Kernel process creation is not bounded by a user-mode timeout.
- A PID is not durable ownership. Windows ownership is the job handle plus the process handle. Linux ownership of the direct child is the pidfd plus `waitpid`. Linux has no tree handle here.
- Linux descendant containment is not claimed.
- Bare-metal Linux was not tested. WSL2 is not that claim.
- Nested job assignment was shown on this Windows 11 host, where the interpreter is already in a job. It is not a claim about every Windows configuration.
- An explicit `CREATE_BREAKAWAY_FROM_JOB` attempt was not run. Breakaway was not enabled on the job. The tested grandchild used ordinary `Popen` and died with the job.
- This package is not integrated into R.61.

## Classifications for individual properties

| Property | Classification |
| --- | --- |
| Windows assign-before-resume, job close kills the tested worker and grandchild | `VERIFIED_WINDOWS` |
| Windows deadline before create and before resume | `VERIFIED_WINDOWS` |
| Windows full-pipe write released by job close without owner-thread `close()` | `VERIFIED_WINDOWS` |
| Windows duplicate handle keeps the tree until the last close | `VERIFIED_WINDOWS` |
| Linux park-before-exec and direct-child exit verification | `VERIFIED_LINUX_WSL2` |
| Linux cgroup unavailable to this user | `VERIFIED_LINUX_WSL2` |
| Linux descendant containment | `KNOWN_LIMITATION` (experiment showed survival) |
| Cancelling a blocked `CreateProcess` or `fork` | `KNOWN_LIMITATION` |
| Crash between create return and job assign | `SOURCE_REVIEW_ONLY` |
| Bare-metal Linux | `NOT_VERIFIED` |

The stage label is `R62_POC_INCOMPLETE`. Passing Windows tests do not close the Linux descendant gap or the kernel-create gap.
