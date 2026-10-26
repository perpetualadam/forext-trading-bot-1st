# R.63 proof-of-concept test report

## Baseline

Checked before any R.63 code was added:

| Item | Result |
| --- | --- |
| `R62_POC_SOURCE_REVIEW.zip` | 10692 bytes, SHA-256 `6cde480eacf8fc4812e11041ae23860366743d38b5f2cdc8333128509a80ce49` |
| Five R.62 members | Hashes matched the R.62 security review |
| R.62 tests, Windows | 13 passed, 4 skipped, 7.33s |
| R.62 tests, WSL2 | 5 passed, 12 skipped, 4.97s |
| `R61_SOURCE_REVIEW.zip` | 27255 bytes, SHA-256 `43b0acc351fb6292535ef4f86063fe4e95b6a66c9c5a8baf715f2ba93f62ab86` |
| R.56, R.59, R.60, R.61 gates | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `one_session.consumed` | 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| `one_session.permit` | Absent |

The same R.61 and R.62 archive hashes were checked again after the R.63 suite. `git diff` for the R.56, R.59, R.60, R.61, and R.62 trees was empty.

## Commands and hosts

Windows 11 10.0.26300, CPython 3.13.5, pytest 8.4.1. 14 passed, 6 skipped, 8.69s.

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r63\poc -q --tb=line
```

WSL2 Ubuntu 24.04.3 LTS, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3, pytest 9.1.1 from `$HOME/r60pytest`. 8 passed, 12 skipped, 3.44s.

```text
"$HOME/r60pytest/bin/python" -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r63/poc -q --tb=line
```

Skips are the other platform's tests. No `time.sleep(60)` or `synthetic_worker.py` process remained after either suite.

`REAL_NETWORK_EXECUTION_NOT_TESTED`.

## Windows experiments

| Experiment | Observed result | Classification |
| --- | --- | --- |
| Parent already in a job | `IsProcessInJob` on the interpreter is true. Creation-time assignment still confirmed membership | `VERIFIED_WINDOWS` on this host |
| Worker created inside the job, code not run | Suspended process, job active count at least 1, `side.txt` absent, then job close and a process-handle wait | `VERIFIED_WINDOWS` |
| Deadline before release | Hook slept past the deadline on the owner thread. No resume. Exit verified. Side-effect absent. Harness did not intervene | `VERIFIED_WINDOWS` |
| Unsupported attribute | `CREATE_ATTRIBUTE_REJECTED`, pid 0, no side-effect file | `VERIFIED_WINDOWS` |
| Grandchild | Job active count at least 2. Last handle close left worker and grandchild not `STILL_ACTIVE` | `VERIFIED_WINDOWS` |
| Owner exit after creation, before resume | Return code 9. Suspended worker became inactive. Side-effect absent | `VERIFIED_WINDOWS` |
| Owner exit while worker and grandchild run | Both inactive. No harness kill | `VERIFIED_WINDOWS` |
| Duplicate job handle | First close: `CLEANUP_INCOMPLETE`, worker still active. Last close: process-handle wait verifies exit | `VERIFIED_WINDOWS` |
| `terminate` before `verify_exit` | `exit_verified` stays false after the close request | `VERIFIED_WINDOWS` |
| SIGTERM-ignoring worker | Job close still ended it | `VERIFIED_WINDOWS` |
| Worker exits before ready | `EXIT_BEFORE_READY`, exit verified | `VERIFIED_WINDOWS` |
| Three repeated sessions | Each exit verified. Harness did not intervene | `VERIFIED_WINDOWS` |
| 256 KiB blocked stdin | Writer finished after job close in under 4s. Owner thread did not close the write end while the child was alive | `VERIFIED_WINDOWS` |
| Pre-create hook stall | Caller still alive 0.5s after the deadline. Status stayed `entered`. No side-effect file. Outer kill | `KNOWN_LIMITATION` for the kernel call |
| Legacy create-then-assign gap | Owner exited before assignment. Suspended process was still active and had not written `side.txt`. Harness then terminated it | `VERIFIED_WINDOWS` that this gap still leaks. The public API does not use it |
| Crash inside `CreateProcess` before the job is assigned | Not injected | `SOURCE_REVIEW_ONLY` |
| Windows Server | No host | `NOT_VERIFIED` |

## Linux experiments

| Experiment | Observed result | Classification |
| --- | --- | --- |
| cgroup v2 delegation | `CONTAINMENT_UNAVAILABLE:13` | `VERIFIED_LINUX_WSL2` |
| Default policy | No fork, pid 0, `worker_executed` false, no side-effect file | `VERIFIED_LINUX_WSL2` |
| Explicit direct-child ready | Status `DIRECT_CHILD_ONLY`, ownership `pidfd`. `exit_verified` was false after `terminate` and true after `verify_exit` | `VERIFIED_LINUX_WSL2` |
| Deadline before `exec` | Park dropped. Side-effect absent. Exit verified. Harness did not intervene | `VERIFIED_LINUX_WSL2` |
| Owner exit before release | Parked child became inactive. No side-effect file | `VERIFIED_LINUX_WSL2` |
| Owner exit after a grandchild exists | Direct child died (`PR_SET_PDEATHSIG`). Grandchild pid 390 in the observation run was still alive. Harness then killed it | `VERIFIED_LINUX_WSL2` for the direct child. Descendant containment failed and stays visible |
| `cgroup.procs` / `cgroup.kill` placement | Not reached | `SOURCE_REVIEW_ONLY` |
| Delegated cgroup host, VPS, container, bare metal | Not present | `NOT_VERIFIED` |
| Blocked `fork` | Not cancellable. The same pre-call limitation as Windows | `KNOWN_LIMITATION` |

Process groups were not called. The surviving grandchild is the evidence that direct-child mechanisms are not a job object.

## Unsupported guarantees

- Kernel `CreateProcess` and `fork` are not bounded by a user-mode timeout.
- The legacy Windows assignment gap still leaves a suspended process if owner death happens before assignment.
- The in-kernel creation-time window was not crash-injected.
- One extra job handle delays kill-on-close until the last close.
- Linux descendant containment is refused by default on this host and is not silently replaced.
- The explicit Linux policy kills the observed direct child on owner death and does not kill the grandchild.
- `PR_SET_PDEATHSIG` still has a short race if the parent dies before `prctl`. The park pipe covers the pre-exec case. The post-exec case was observed once, not proved for every interleaving.
- Windows Server, delegated-cgroup Linux, VPS, and containers were not tested.

The stage label is `R63_POC_INCOMPLETE`. Windows creation-time containment and the Linux refusal path are each `R63_POC_VERIFIED` only for the properties in the tables above.
