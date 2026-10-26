# R.62 Process Ownership Model

This model is the contract for the isolated proof of concept. It is not wired into the R.61 supervisor.

## Ownership objects

A pid is a name. It is not ownership.

| Object | Platform | What it owns | What it does not own |
| --- | --- | --- | --- |
| Process handle from `CreateProcess` | Windows | That process, including while it is suspended. `TerminateProcess` and `WaitForSingleObject` use the handle, so pid reuse does not redirect them. | Other processes, unless they are in a job this handle's job also contains. |
| Job handle with `KILL_ON_JOB_CLOSE` | Windows | Processes assigned to the job, and children they create while they remain in the job without breakaway. Closing the last handle asks the kernel to terminate those processes. | Processes created before assignment. Processes that break away. Anything created by a `CreateProcess` that has not returned. |
| pidfd | Linux | One process. `pidfd_send_signal` still targets that process after the numeric pid would have been reused. | Grandchildren. A new process that happens to reuse the numeric pid. |
| Park pipe | Linux | The decision to exec. The child runs the worker only after it reads the byte `R`. EOF or any other byte makes it exit without exec. | A child that has already exec'd. |
| cgroup directory | Linux, when writable | Members written to `cgroup.procs`, and children they create while membership is inherited. `cgroup.kill` terminates the members. | This WSL2 user. Creating a child of `/init.scope` was denied. |
| Side-effect file | Both | Evidence that worker code ran. Absence is evidence only if the worker's first action would have been to create it. | Proof that no process object exists. A suspended or parked process has not written it yet. |

The supervisor, or the short-lived owner process in a crash test, holds the job handle or the pidfd. The worker never receives the job handle. The park pipe's write end stays in the parent.

## States

`NOT_STARTED`
No process object. Deadline expired before create, or create has not been called.

`WORKER_CREATED`
The kernel has returned a process. Windows: it is suspended. Linux: it is blocked on the park pipe and has not exec'd. Worker code has not run.

`WORKER_CONTAINED`
Windows: `AssignProcessToJobObject` succeeded and the job limit is kill-on-close. Linux: this state is not claimed on this host. A failed cgroup attempt stays out of this state and records `CONTAINMENT_UNAVAILABLE`.

`WORKER_READY`
The process was resumed or released, and the ready file appeared before the deadline.

`SHUTDOWN_REQUESTED`
The owner has decided to stop. No stdin flush is part of this transition.

`TERMINATION_ATTEMPTED`
Windows: the job handle was closed, or `TerminateProcess` was called on a process that never resumed. Linux: `SIGKILL` was sent through the pidfd when one exists.

`EXIT_VERIFIED`
A bounded wait completed and the process is not still active. This is the only state that means the direct child is dead. It does not by itself mean a grandchild is dead.

`OWNERSHIP_UNCERTAIN`
The create call has not returned, or the process exists and is not in the kill domain. The proof of concept does not return success from a timeout thread in this state. A crash between `CreateProcess` and assignment is this state and is not covered by an automated crash injection.

`CLEANUP_INCOMPLETE`
Termination was attempted and the bounded wait still sees the direct child as active. Callers must not report success. The test harness may then kill the process, and the record says the harness intervened.

`LAUNCHER_CREATED` is defined for the rejected launcher design and is not a runtime state of this experiment. The supervisor is the owner. Adding a launcher would insert another `WORKER_CREATED`-equivalent process that itself has to be inside the kill domain before it is allowed to spawn.

## Transitions

| From | To | Who owns the worker | Who can terminate | How death is verified | Failure |
| --- | --- | --- | --- | --- | --- |
| `NOT_STARTED` | `WORKER_CREATED` | Parent, via the new process handle or the fork pid. | Parent. | Not dead yet. | Kernel create blocks: the caller does not return. Create fails: stay `NOT_STARTED`. |
| `WORKER_CREATED` | `WORKER_CONTAINED` | Parent holds the job handle. The process is assigned and still suspended. | Parent, by `TerminateProcess` or by closing the job later. | Still suspended, so the side-effect file must be absent. | Assignment fails: terminate, wait, do not resume. State becomes `EXIT_VERIFIED` or `CLEANUP_INCOMPLETE`. Error `CONTAINMENT_FAILED`. |
| `WORKER_CREATED` | `EXIT_VERIFIED` | Parent still holds the handle. | Parent. | Wait on the handle or `waitpid`. Side-effect file absent. | Deadline passed before resume or before the park byte. Linux EOF on the park pipe must not exec. |
| `WORKER_CONTAINED` | `WORKER_READY` | Parent holds the job. The worker is running and may create children in the job. | Parent, by closing the last job handle. | Ready file appeared. Children are not verified one by one. | Deadline during ready wait: go to shutdown, then verify the direct child. A missing ready line is not success. |
| `WORKER_READY` | `TERMINATION_ATTEMPTED` | Same handle. | Same owner. | Not yet. | Closing a job handle that is not the last handle does not kill. That result is `CLEANUP_INCOMPLETE` if the process is still active after the wait. |
| `TERMINATION_ATTEMPTED` | `EXIT_VERIFIED` | The handle remains until the wait returns, then it is closed. | Already requested. | `WaitForSingleObject` or `waitpid` within 5 seconds, and the exit code is not still-active. | Timeout: `CLEANUP_INCOMPLETE`. The API return is not success. |
| Any owned state | `CLEANUP_INCOMPLETE` | The handle may still be open. | Parent, if it still can. | The bounded wait failed. | Harness intervention is recorded separately and does not rewrite the state to `EXIT_VERIFIED`. |

## Failure handling

Process creation stalls. The call stays on the owner thread. There is no second thread. The proof-of-concept test of a stall uses an outer process that kills the owner. That outer kill is harness intervention. It shows the owner did not return by itself. It does not show that the kernel call is cancellable.

Worker created immediately before the deadline. Resume or park-release is allowed only when time remains. The ready wait uses the remaining time. On expiry the kill domain or pidfd is used, then the wait verifies the direct child.

Worker created immediately after the deadline. The process object may already exist, suspended or parked. It is terminated without resume and without the release byte. The side-effect file must be absent. `EXIT_VERIFIED` here means that suspended process is dead, not that a running worker was reaped after doing work.

Launcher crashes before worker creation. There is no launcher. The corresponding experiment is an owner that exits before `CreateProcess` or `fork`. No side-effect file and no child pid appear.

Launcher or supervisor crashes after the worker is contained. Windows: the owner process is a short-lived process that assigns the job, resumes, records the pids, and calls `os._exit` without an explicit terminate. The job handle closes with the process. The experiment expects the worker and the grandchild to be dead and records harness intervention only if they are not. Linux: the same shape expects the grandchild to remain, because there is no cgroup. The harness then kills it and the result stays "not contained".

Ready acknowledgement lost. The owner does not need the ready file in order to terminate. Shutdown uses the job or the pidfd. A ready line sitting unread in a file or a pipe is not a live process.

Containment setup fails. Windows assignment failure terminates the suspended process. Linux cgroup denial does not pretend to be success. The direct child may still be run for direct-child tests, with `contained` false.

Supervisor stops waiting while the worker runs. Shutdown is requested and the bounded wait runs. If the direct child is still active, the state is `CLEANUP_INCOMPLETE`.

Owner death during the park. The write end closes. The child sees EOF, not `R`, and exits without exec. That is an explicit transition so a crashed parent does not accidentally release the worker.

Stdin. The containment protocol does not create an inherited stdin for the worker. One Windows experiment opens a stdin pipe, blocks a large write, and shuts down by closing the job. The owner thread does not call `close()` on that pipe while the child is alive. The writer thread is allowed to finish after the child dies.

## What is a guarantee in this model

A guarantee requires a kernel object the owner holds, a test that uses it, and a check that does not treat the API's return code as death.

- Windows, this host: the job handle plus assignment before resume is the proposed guarantee under test.
- Linux, this host: the pidfd plus the park byte is a direct-child guarantee under test. Descendant containment is not a guarantee here.
- Both: absence of a side-effect file is the evidence that worker code did not run. It is not evidence about processes that have not been resumed.
