# R.64 Linux cgroup audit

Real cgroup containment was not established. The host classification is `CGROUP_DELEGATION_UNAVAILABLE`.

## Host

| Item | Observation |
| --- | --- |
| Machine | WSL2, not a separate bare-metal or VPS host |
| Distribution | Ubuntu 24.04.3 LTS |
| Kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Python | 3.12.3 |
| Mount | `/sys/fs/cgroup`, cgroup2, options include `nsdelegate` |
| Current cgroup | `0::/init.scope` |
| Controllers on the root | `cpuset cpu io memory hugetlb pids rdma` |
| `cgroup.subtree_control` | `memory pids` |
| `cgroup.procs` on `init.scope` | Present |
| `cgroup.kill` on `init.scope` | Present |
| `cgroup.kill` on the cgroup root | Absent |
| Directory writable by this user | No |
| `mkdir /sys/fs/cgroup/init.scope/r64-probe-<pid>` | `PermissionError`, errno 13 |
| `user.slice/user-1000.slice` | Absent |
| `CapEff` | `0000000000000000` |
| Namespaces | cgroup, pid, and user namespaces exist. This user cannot create a private delegated child |

A visible `cgroup.kill` file is not delegation. The private child directory could not be created, so nothing was moved into a cgroup and `cgroup.kill` was not written. The refusal guard rejects a kill aimed at the caller's own cgroup, including `init.scope`.

No `sudo`, systemd edit, controller change, or container setting was used.

## Experiments that ran

| Experiment | Kind | Result |
| --- | --- | --- |
| Probe and private mkdir | Real kernel | `CGROUP_DELEGATION_UNAVAILABLE`, errno 13. `kernel_containment` false |
| Strict open | Real | No fork, pid 0, no side-effect file |
| Three repeated probes | Real | No `r64-*` directory left under `init.scope` |
| Kill request for the current cgroup | Real guard | `CGROUP_KILL_REFUSED`. The existing kill file was not a write target |
| Creation, placement, membership, deadline, exit-before-placement, owner crash, grandchild survival, kill failure, populated cgroup, cleanup failure, missing path | Simulated state machine | `evidence` is `SIMULATED`. `kernel_containment` is false |

The function that would fork, write `cgroup.procs`, check membership, release the worker, and write a child `cgroup.kill` was not entered. It is `SOURCE_REVIEW_ONLY`.

## What cgroup v2 would have to provide

A real proof needs a directory this process can create under its current cgroup, a writable `cgroup.procs`, and a `cgroup.kill` in that child. The parked worker is moved before `exec`. Membership has to be read back before the release byte. Descendants stay in that cgroup only while they do not migrate themselves out. Termination is a write of `1` to that child `cgroup.kill`, followed by an empty `cgroup.procs` and `populated 0` before `rmdir`. pidfd identifies the direct child. The numeric pid is not the ownership proof.

## Owner crash

Cgroup membership does not install kill-on-close. If the process that holds the lifecycle exits after release, the cgroup stays populated until some still-living owner writes `cgroup.kill`. The simulated result is `CLEANUP_INCOMPLETE`, `crash_safe` false, and `requires_live_owner_for_cgroup_kill` true. No privileged daemon was added. This crash case was not executed on a real cgroup.

`PR_SET_PDEATHSIG` is not part of this package and would not kill grandchildren. `cgroup.kill` does not make `fork` cancellable.

## Cleanup

`rmdir` of a cgroup can fail while it is populated or while the kernel still reports it busy. The untested path reads `cgroup.events` and does not delete a populated directory. That behaviour was not observed on a cgroup this process created.

## Untested

- Placement of a parked pid.
- Inherited membership of a grandchild.
- Descendant death after `cgroup.kill`.
- An empty-cgroup `rmdir` race.
- A delegated systemd user slice.
- A container cgroup namespace with write permission.
- Bare metal, Debian, and every VPS.

`R64_LINUX_CGROUP_NOT_VERIFIED`
