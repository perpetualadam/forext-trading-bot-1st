# R.62 Architecture Decision

Isolated research into process creation, ownership, and descendant containment. This document does not authorise a change to the R.61 diagnostic supervisor, a broker connection, or production trading.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

Production trading remains NO-GO.

## Problem statement

R.61 can refuse to call `Popen` after the session deadline, and it can retain a `Popen` object if registration raises. It cannot:

- Interrupt a `Popen` or `CreateProcess` call that has entered the kernel and has not returned a handle.
- Stop a worker that appears after the supervisor has given up, if creation was moved to another thread.
- Kill a grandchild by killing the tracked parent. That escape was observed on Windows and on WSL2.

A bounded supervisor return is not sufficient. The design has to say who owns the worker, how that ownership is verified, and what happens to descendants when the owner stops or crashes.

## Existing R.61 guarantees

These are properties of the unchanged R.61 tree. Baseline for this stage: archive `R61_SOURCE_REVIEW.zip`, 27255 bytes, SHA-256 `43b0acc351fb6292535ef4f86063fe4e95b6a66c9c5a8baf715f2ba93f62ab86`. The R.61 suite passed 14 tests in 3.88 seconds on Windows 11 before this research. Gates in R.56, R.59, R.60, and R.61 remain false. The R.56 consumed marker is unchanged and the permit is absent.

| Property | R.61 status |
| --- | --- |
| Deadline check immediately before `Popen` | Guaranteed for in-process work. |
| `Popen` call itself | Not cancellable. Observed: a 30 second stall was still inside the call 0.5 seconds after a 0.25 second deadline. |
| Direct child after a successful `kill()` | Exit is taken from `poll()`, not from the `kill()` return. |
| Direct child when `kill()` fails | `child_alive` stays true. Stdin is not closed. |
| Full stdin pipe | Not closed on the supervisor thread while the child is alive. |
| Descendants | Not owned. Grandchild survived parent termination on both tested hosts. |
| Daemon thread around `Popen` | Rejected. A late create would be untracked. |

## Host observations used for the decision

These probes are not the proof-of-concept suite. They were run to decide whether a design is credible on this machine.

Windows 11 10.0.26300, Python 3.13.5:

- `IsProcessInJob` on the current process is true. This interpreter is already inside a job.
- `CreateJobObject`, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and `AssignProcessToJobObject` on a `CREATE_SUSPENDED` child succeeded. Nested assignment worked on this host.
- The suspended child did not create its marker file. `TerminateProcess` before `ResumeThread` left the marker absent.
- After resume, the job accounting reported 2 active processes: the worker and the grandchild it had spawned.
- The worker was still active. Closing the last job handle made the wait on the worker return. The worker and the grandchild were both not `STILL_ACTIVE`. The probe then had nothing left to kill.

WSL2 Ubuntu 24.04.3 LTS, kernel `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3:

- cgroup v2 is mounted at `/sys/fs/cgroup` with `nsdelegate`.
- This process is in `/init.scope`, owned by root.
- `cgroup.subtree_control` on the root exposes `memory` and `pids`.
- There is no delegated `user@1000.service` cgroup for this user.
- `mkdir /sys/fs/cgroup/init.scope/r62probe…` returned `Permission denied`.
- `cgroup.kill` is therefore not available to this user. It is not used as a silent fallback.

## Candidate architectures

### A. Existing synchronous `Popen`

The supervisor thread calls `Popen`. When the call returns, the object can be tracked. When the call is inside the kernel, the supervisor is blocked and there is still no handle.

Limits:

- Startup timeout is not enforceable around the kernel call.
- Ownership begins only after return. A crash between return and `tracker.add` can drop the object. R.61 narrows that window; it does not close a crash inside the C call.
- `Popen.kill()` does not kill grandchildren. Observed in R.61.
- Cleanup of the direct child is bounded only when `wait(timeout=5)` is used. A full stdin `close()` is not bounded on Windows.
- Failure mode: antivirus or a stuck image load stalls the session past the deadline, and the supervisor has no process handle to cancel.

### B. Supervised launcher subprocess

A small launcher would create the worker and report an identity to the supervisor.

What it does not do:

- Creating the launcher is another `CreateProcess` or `fork`. That call can block. Moving the block one process away does not make it cancellable.
- If the supervisor stops waiting while the launcher is still running, the launcher can create the worker afterwards. That worker is untracked unless the launcher was already inside a containment domain that the supervisor can still close.
- If the launcher crashes after creating the worker and before reporting the identity, the supervisor has a pid that may already be wrong, and no handle.
- A pid in a message is not durable ownership. The pid can be reused after exit.

The launcher is useful only as a process that is itself created suspended, assigned to a job or cgroup, and then resumed. At that point the extra process is optional. The containment handle is the ownership object, not the launcher.

### C. Windows Job Object with suspended create

Sequence:

1. Create a job and set `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
2. `CreateProcess` with `CREATE_SUSPENDED`.
3. Assign the process to the job before `ResumeThread`.
4. Resume only if assignment succeeded and the deadline has not passed.
5. On deadline or owner exit, close the last job handle. Do not infer death from the close call. Wait on the process handle and read the exit code.
6. Do not set `JOB_OBJECT_LIMIT_BREAKAWAY_OK`. Do not pass the job handle as inheritable.

Observed on this host: steps 1–3 succeed while the parent is already in a job, a grandchild is counted in the job, and closing the job ends both the worker and the grandchild.

Failure modes that remain:

- `CreateProcess` can block before it returns a handle. A timeout thread around that call can return while the kernel still creates an untracked process. That wrapper is rejected.
- A crash in the few instructions between a successful `CreateProcess` and `AssignProcessToJobObject` leaves a suspended process outside the job. The window is real and small. It is not tested by injecting a crash into that gap.
- Nested jobs are an observed property of this Windows 11 process, not a proof about every Windows host. A host whose existing job forbids nesting can fail assignment. The suspended process must then be terminated and must not be resumed.
- `KILL_ON_JOB_CLOSE` fires when the last handle closes. A duplicated job handle keeps the tree alive. That is an ownership bug if the duplicate is leaked.
- A process started with breakaway rights could leave the job. This design does not grant those rights. It does not prove that no future worker can obtain them by some other mechanism.
- Handle inheritance: `bInheritHandles=TRUE` can duplicate unrelated inheritable handles. The containment path does not need inherited stdio.

### D. Linux process containment

Process groups are not a Job Object.

- `start_new_session` makes the child a session leader. `killpg` signals that process group.
- A descendant that calls `setsid` or `setpgid` leaves the group. `SIGKILL` of the parent does not follow it.
- The pid passed to `killpg` can be reused by an unrelated process after the child exits. A pid is not a capability.
- Subreapers adopt orphans. They do not kill those orphans when the subreaper exits.
- `pidfd_open` is a capability for one pid. It does not become invalid and then point at a new process. It does not include grandchildren.
- cgroup v2 `cgroup.kill` (Linux 5.14+) can kill every member of a cgroup, which is the closest equivalent to a job. It requires a writable cgroup. This user, in WSL2 `/init.scope`, received `Permission denied`. The design does not replace that with `killpg` and call it containment.

The Linux shape that matches the Windows sequence, as far as this host allows:

1. `fork`.
2. The child blocks reading a one-byte park pipe and execs the worker only if the byte is `R`. Any other result, including EOF from a dead parent, exits without exec.
3. The parent records a pidfd when `os.pidfd_open` is available.
4. The parent tries to place the pid in a private cgroup. On this host that fails and is recorded as containment unavailable.
5. The parent releases the child only if the deadline remains and containment policy for that platform is satisfied. On Linux, release is allowed for direct-child experiments, and the result says descendants are not contained.
6. Shutdown is `pidfd_send_signal(SIGKILL)` or `SIGKILL` plus a bounded `waitpid`. Death of the direct child is not reported as death of a grandchild.

## Comparison matrix

| Criterion | A. Synchronous `Popen` | B. Launcher process alone | C. Job + suspended create | D. Linux group / pidfd / cgroup |
| --- | --- | --- | --- | --- |
| Startup latency | One process create. | Two creates. | One create, plus assign and resume. | One fork, plus park and exec. |
| Startup timeout | Not enforceable inside the kernel call. | Not enforceable for the launcher create. | Same kernel limit. Enforceable after the handle exists, before resume. | Same kernel limit. Enforceable while the child is parked, before exec. |
| Ownership | `Popen` object after return. | Pid message is not ownership. | Job handle plus process handle. | pidfd for one process. No tree handle on this host. |
| Descendants | Not contained. Observed escape. | Not contained unless the launcher is inside a job or cgroup. | Contained on this Windows host when assignment happens before resume and breakaway is off. | Process group: escape and pid reuse. pidfd: direct child only. cgroup: unavailable here. |
| Failure recovery | `poll` after `kill`. | Lost acknowledgement drops the identity. | Terminate the suspended process if assign or deadline fails. Verify with the process handle. | Kill the parked child if the deadline passes. Verify with `waitpid`. Grandchild may remain. |
| Cleanup bound | `wait(timeout=5)` if the handle exists. | Unbounded if the worker is untracked. | Job close, then a bounded wait. No stdin flush. | Bounded `waitpid`. No stdin flush. |
| Portability | High. | High, and the guarantee does not travel with it. | Windows only. Nested jobs need Windows 8 or later and a parent job that allows nesting. | cgroup v2 needs delegation. This WSL2 user does not have it. |
| Security | Stdin close can block and can retain a frame. | A late worker can outlive the session. | Job handle must not be inherited or duplicated by accident. | pidfd is a capability. `killpg` is not. |
| Complexity | Already shipped in R.61. | Extra protocol and an extra crash window. | Private `CreateProcess` path. | Fork/exec park protocol, plus an explicit non-containment result. |
| Testability | R.61 suite. | Easy to show a late spawn. | Probe already showed job membership of a grandchild and death on close. | cgroup denial is already observed. Escape remains testable. |

## Threat and failure model

| Event | Required outcome |
| --- | --- |
| Deadline expires before create | No process. |
| Kernel create blocks | Caller remains inside the call. No second thread creates a process after a timeout return. |
| Handle exists, deadline expires before resume or exec | Process is killed without running worker code. A side-effect file must be absent. |
| Assignment to the job fails | Suspended process is terminated and not resumed. |
| Ready line is never read | Owner still closes the kill domain or signals the pidfd. Exit is verified by a wait, not assumed. |
| Owner crashes after the worker is contained | Windows: last job handle closes and the tree should die. Linux: descendants are not in a cgroup and may survive. |
| `kill()` or job close is reported successful by the API | Death is still checked with the process handle or `waitpid`. |
| Stdin buffer is full and the child is alive | The supervisor thread does not `close()` that pipe. The kill domain is used instead. |
| Grandchild calls `setsid` or is simply orphaned | A process group is not treated as success. |
| Credential or trading payload | Not part of this protocol. |

## Recommended design

Supervisor-owned kill domain, established before the worker runs user code.

- Windows proof of concept: job object, `CREATE_SUSPENDED`, assign, then resume. `KILL_ON_JOB_CLOSE`. Verify exit with the process handle. No breakaway permission. No inheritable job handle.
- Linux proof of concept: fork, park before exec, pidfd for the direct child, cgroup attempt recorded and expected to fail on this host. Do not call `killpg` containment. A grandchild that survives is a failed containment result and stays in the report.
- No middle launcher in the experiment. It does not remove the kernel stall, and without a pre-existing kill domain it can create an untracked worker after the supervisor returns.
- No daemon thread around `CreateProcess` or `fork`.
- IPC for the experiment is a side-effect file and a single ready line in a file, plus one pipe test that must not `close()` a live stdin. Payload is `R62.1` and a mode name. No credentials.
- R.61 is not modified. The package lives under `r62/poc/` and imports none of the trading or diagnostic supervisors.

## Rejected alternatives

- A timeout thread around `Popen` or `CreateProcess`. The thread can return while the kernel still creates a process that nobody owns.
- A launcher that is not placed in a kill domain before it is allowed to create children. The acknowledgement race and the launcher's own `CreateProcess` stall remain.
- Assigning a job after the child has been resumed. The child can spawn a grandchild before assignment. R.61 named that race. The probe avoided it by assigning while suspended.
- `start_new_session` plus `killpg` as a Linux substitute for a job. Escape and pid reuse are structural.
- Using cgroup v2 on this WSL2 user anyway. The directory create was denied. Pretending otherwise would be a false guarantee.
- Integrating any of this into `r61/diagnostic_supervisor.py` in this stage.

## Unresolved questions

- Whether every Windows host that already has the interpreter in a job will allow the nested assign that succeeded here.
- The exit code observed after job-close termination on this host was 0. Liveness is decided by `STILL_ACTIVE` and the wait, not by assuming a particular code.
- The instruction window between `CreateProcess` returning and `AssignProcessToJobObject` is not crash-tested.
- Linux descendant containment requires a delegated cgroup or another kernel mechanism this user does not have. No substitute was accepted.
- Bare-metal Linux was not available. WSL2 evidence is not a bare-metal claim.
- A production integration would need a reviewed launcher in the diagnostic supervisor. This decision does not approve that integration.

## Stage A decision

`R62_DESIGN_APPROVED_FOR_ISOLATED_POC`

The ownership model is coherent enough to experiment with: a handle or pidfd owned by the supervisor, worker code released only after containment is attempted, death verified by a wait, and descendant containment claimed only where the kernel object includes the tree. The Windows job path is that object on this host. The Linux path must report that it does not have one.

Approval is permission to write `data\research\adaptive_ensemble\r62\poc\`. It is not permission to edit R.61.
