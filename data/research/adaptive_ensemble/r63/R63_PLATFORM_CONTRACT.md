# R.63 platform contract

Isolated research. The contract is not wired into the R.61 diagnostic supervisor.

R.62 remains `R62_POC_INCOMPLETE`. Its archive was re-checked at `6cde480eacf8fc4812e11041ae23860366743d38b5f2cdc8333128509a80ce49` before this package was written.

## Problem

The application needs one lifecycle API on Windows and Linux. The same call names do not imply the same kernel guarantee. A caller that requires descendant containment must see a refusal when the host cannot provide it. A successful `CreateProcess` or `fork` is not containment. A successful kill call is not exit verification.

## Capability levels

| Level | Meaning |
| --- | --- |
| `DESCENDANT_CONTAINMENT_AVAILABLE` | The probe believes the host can arm a tree kill domain. No process has been placed in it. |
| `DESCENDANT_CONTAINMENT_ACTIVE` | This process was confirmed in the armed domain before worker code ran. |
| `DIRECT_CHILD_ONLY` | The caller explicitly accepted a reduced policy. Descendants are not covered. |
| `CONTAINMENT_UNAVAILABLE` | Descendant containment was required and cannot be armed. The worker is not executed. |
| `OWNERSHIP_UNCERTAIN` | A process exists, or may exist, outside a kill domain the owner controls. |
| `CLEANUP_INCOMPLETE` | Termination was requested and the bounded wait still sees the process as active. |

The default policy is `REQUIRE_DESCENDANT_CONTAINMENT`. It does not downgrade to `DIRECT_CHILD_ONLY`. The reduced policy is selected only by constructing the manager with `require_descendant_containment=False`, and the status record keeps `DIRECT_CHILD_ONLY_EXPLICIT`.

`probe_capabilities()` returns availability. `establish_containment()` is the only step that may set `DESCENDANT_CONTAINMENT_ACTIVE`, and only after a membership check.

## Operations

`ProcessLifecycleManager` exposes `probe_capabilities`, `create_suspended_or_parked`, `establish_containment`, `start_worker`, `wait_ready`, `terminate`, `verify_exit`, `cleanup`, and `get_process_status`.

`terminate` records `TERMINATION_ATTEMPTED` and does not set `exit_verified`. `verify_exit` waits on the process handle or `waitpid`. `CLEANUP_INCOMPLETE` stays in place if that wait expires. `cleanup` may kill a survivor and sets `harness_intervened`. That flag does not rewrite the state to `EXIT_VERIFIED`.

## Windows

The public path uses `PROC_THREAD_ATTRIBUTE_JOB_LIST` (`0x0002000D`) with `STARTUPINFOEX`, `EXTENDED_STARTUPINFO_PRESENT`, and `CREATE_SUSPENDED`. The job limit `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` is set before `CreateProcess`. The job handle is not inheritable. Breakaway is not enabled.

Microsoft documents this attribute from Windows 8 and Windows Server 2012. The process is assigned to the job as part of creation, before it is resumed. This host is Windows 11 build 26300. The interpreter is already inside a job, and a nested creation-time assignment succeeded here. Windows Server was not available.

After `CreateProcess` returns, the next user-mode step queries `IsProcessInJob`. Active containment is set only when that query is true. Resume happens after that confirmation. A deadline that expires in between terminates through the job and does not resume. The side-effect file stays absent.

The old sequence, suspended `CreateProcess` and then a later `AssignProcessToJobObject`, is not the public path. A crash helper still creates that suspended process and exits before assignment. The process remained alive and suspended, with no side-effect file. The harness terminated it. That gap is reproduced, not closed, for any caller that still uses the two-step sequence.

The public crash experiment exits immediately after creation-time assignment and before resume. The suspended worker was then dead, and the side-effect file was absent. Closing the last job handle on owner exit is what ended it. A second experiment resumed a worker, let it spawn a grandchild, and exited. Both were dead without a harness kill.

A duplicated job handle keeps the tree alive after the first close. The status stays `CLEANUP_INCOMPLETE` until the last handle closes and the process-handle wait reports an exit code other than `STILL_ACTIVE` (259).

An unsupported attribute id fails inside attribute setup. No process is returned.

What remains untested: a crash inside the kernel during `CreateProcess`, after the process object exists and before the job assignment completes. That interval is not injectable from this program. The claim that the attribute is atomic is `SOURCE_REVIEW_ONLY`, supported by the platform documentation and by the observation that the process is already in the job when `CreateProcess` returns. It is not a crash-injection result.

A blocked `CreateProcess` is still not cancellable. The stall test blocks in a Python hook before the call. The outer driver kills that caller. No worker file appears. The kernel call itself was not interrupted.

## Linux

cgroup v2 is mounted on this WSL2 host. Creating `r63-poc-<pid>` under `/sys/fs/cgroup/init.scope` returns permission denied, errno 13. There is no delegated user cgroup. `cgroup.kill` is not used. No `sudo`, no systemd change, and no container runtime change was made.

With the default policy the manager returns `CONTAINMENT_UNAVAILABLE` and does not fork. The placement function that would write `cgroup.procs` and `cgroup.kill` is present and was not executed on this host. That function is `SOURCE_REVIEW_ONLY`.

The explicit reduced policy forks, parks the child until it reads `R`, redirects its standard streams to `/dev/null`, and records a pidfd. The child calls `prctl(PR_SET_PDEATHSIG, SIGKILL)` before the park read, and exits if the parent has already changed. EOF on the park pipe also exits without `exec`. After `exec`, owner death delivered `SIGKILL` to the direct child in the observed run. The grandchild stayed alive. pidfd does not name that grandchild. `PR_SET_PDEATHSIG` does not name it either.

Process groups, `setsid`, subreapers, and PID namespaces were assessed and not used as a substitute. A process group loses a child that calls `setsid`, and `killpg` can strike a recycled pid. A subreaper reparents orphans. It does not kill them. A PID namespace would contain descendants only when the runtime actually creates one. This user did not create one.

## Environments

| Environment | Evidence |
| --- | --- |
| Windows 11 build 26300, CPython 3.13.5 | Tested |
| Windows Server | Not present. Not claimed |
| Linux with delegated cgroup v2 | Not present. Placement code was not executed |
| Linux without delegation | This WSL2 user. Refusal tested |
| Linux VPS | Not present |
| Linux container | Not present |
| WSL2 Ubuntu 24.04.3, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3 | Tested. Not a bare-metal claim |

## Decision

The contract is specific enough to experiment with, and the unsupported cases stay visible.

`R63_DESIGN_REVIEW_PASS`

This does not approve integration into R.61.
