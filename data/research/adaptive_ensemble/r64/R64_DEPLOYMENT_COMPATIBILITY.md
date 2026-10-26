# R.64 deployment compatibility

Documentation is not a test result. `VERIFIED_ON_HOST` is used only for behaviour exercised on this Windows 11 machine or this WSL2 Ubuntu machine.

## Matrix

| Environment | Mechanisms | Permissions | Observed | Classification |
| --- | --- | --- | --- | --- |
| Windows 11 build 26300 | Creation-time job list, kill-on-close, process handle | The tested interpreter was already in a job. Nested assignment worked in R.63 | R.63 suite re-run: 14 passed, 6 skipped, 9.05s, CPython 3.13.5 | `VERIFIED_ON_HOST` for that job path. Not a cgroup result |
| Windows Server | Same job attribute, documented from Windows Server 2012 | Parent job must allow nesting | No Server host | `SUPPORTED_BY_DESIGN_NOT_TESTED` |
| Ubuntu with delegated cgroup v2 | Private child, `cgroup.procs`, `cgroup.kill`, pidfd | Write access to create the child and to write those two files | Not this machine | `REQUIRES_CONFIGURATION` and `NOT_VERIFIED` |
| Ubuntu without delegation | Strict policy returns before `fork` | None beyond the probe | This WSL image is Ubuntu 24.04.3. mkdir errno 13 | `CONTAINMENT_UNAVAILABLE` and `VERIFIED_ON_HOST` for the refusal |
| Debian | Same cgroup v2 contract as Ubuntu | Same delegation requirement | No Debian host | `NOT_VERIFIED` |
| WSL2 | cgroup2 mounted with `nsdelegate`. This user is in `/init.scope` | `CapEff` is zero. `user-1000.slice` is absent | Probe, refusal, and repeated cleanup tests passed. Kernel containment did not run | `VERIFIED_ON_HOST` for non-delegation. `NOT_VERIFIED` for descendant kill |
| Linux VPS | Depends on whether the guest is a full virtual machine or a container | Do not assume root | No VPS was accessed | `NOT_VERIFIED` |
| Docker | Cgroup namespace and runtime policy | A default container often cannot create a delegated child | No container was started | `NOT_VERIFIED` and `REQUIRES_CONFIGURATION` |
| Other OCI runtimes | Same family of cgroup namespace limits | Runtime-specific | None examined | `NOT_VERIFIED` |

## Windows detail

R.63, re-run in this stage and not modified, assigns the job at `CreateProcess` time on this Windows 11 host, confirms membership, and kills the tested worker and grandchild when the last job handle closes. A duplicated job handle still delays death. A blocked `CreateProcess` is still not cancellable. Those statements are about this host's R.63 suite. They are not a Windows Server result.

Blocker for a strict descendant deployment on Windows: the process must be created with the job attribute, the job handle must be the last one at shutdown, and the host must accept nested jobs when the parent is already in a job. That last condition was true here and is not a general Server claim.

## Linux detail

Blocker on this WSL2 user: no private child cgroup. The strict contract therefore does not start a worker. Installing delegation would be a system change and was not done.

A future delegated host still needs a living owner to write `cgroup.kill`. Process exit does not empty the cgroup by itself.

## VPS

A full virtual machine can expose cgroup v2 to an administrator account. An unprivileged application account may still fail the mkdir, as this WSL user did. A container-based VPS can hide controllers, omit `cgroup.kill`, or mount the hierarchy read-only. This stage does not claim that any provider allows or denies those operations.

Read-only check, to be run as the account that would own the worker:

```text
uname -r
cat /proc/self/cgroup
cat /sys/fs/cgroup/cgroup.controllers
cat /sys/fs/cgroup/cgroup.subtree_control
findmnt -t cgroup2
```

Then one uniquely named `mkdir` under the current cgroup. If it fails, stop and record the errno. If it succeeds, `rmdir` that empty directory. Do not write `cgroup.kill` of an existing system cgroup. Do not use `sudo` to turn the check into a pass.

## Containers

Expect a separate cgroup namespace and no permission to enable controllers in a new child unless the runtime was configured to delegate. That configuration was not inspected. Compatibility with Docker or any other OCI runtime is `NOT_VERIFIED`.

## Capability check the application can keep

`probe_host()` reports `delegated`, the errno, whether `cgroup.procs` and `cgroup.kill` exist, and `kernel_containment: false` until a real placement test has passed. Creation of a directory is not that test.

`R64_DEPLOYMENT_MATRIX_COMPLETE`
