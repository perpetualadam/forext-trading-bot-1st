# R.64 policy decision

The R.63 contract stands. R.64 does not edit it and does not connect it to the diagnostic supervisor.

## Default

`REQUIRE_DESCENDANT_CONTAINMENT`

On a host that cannot arm the platform kill domain, the open call returns `CONTAINMENT_UNAVAILABLE` and does not execute the worker. That refusal was executed here for Linux cgroups. It is the same rule R.63 uses.

## Reduced policy

`DIRECT_CHILD_ONLY_EXPLICIT` is available only as an explicit caller choice. The status must keep the requested policy, the actual mechanism, and `equivalent_to_descendant_containment: false`.

For the current R.61 diagnostic worker, the source audit supports that reduced level: the worker does not create descendants. The record names `r61-diagnostic-worker-current-source`. It does not cover the trading bot, a future worker, or a host whose cgroup behaviour has not been measured.

Selecting the reduced policy is not a report of full containment.

## Platform rules

| Situation | Result |
| --- | --- |
| Windows, creation-time job confirmed | `DESCENDANT_CONTAINMENT_ACTIVE` after `IsProcessInJob`, as R.63 tested on this Windows 11 host |
| Windows, assignment not confirmed, or the legacy gap before assignment | `OWNERSHIP_UNCERTAIN`. Do not resume |
| Linux, private cgroup created, membership read back, child `cgroup.kill` usable | Not observed. Would be required before `DESCENDANT_CONTAINMENT_ACTIVE` |
| Linux, mkdir or placement denied | `CGROUP_DELEGATION_UNAVAILABLE` or the matching denial. Do not release |
| Explicit direct-child selection for this diagnostic worker | `DIRECT_CHILD_ONLY`. pidfd plus a bounded wait for that one process |
| Kill call returned, wait has not finished | Not terminated |
| Wait expired, or a cgroup stays populated | `CLEANUP_INCOMPLETE` |
| Owner exits after Linux release without a live writer of `cgroup.kill` | Not crash-safe. Incomplete |
| Duplicate Windows job handle | `CLEANUP_INCOMPLETE` until the last handle closes and the process handle is not `STILL_ACTIVE` |
| Unsupported operating system | Fail closed. No worker |

## Failure model

- A blocked `CreateProcess` or `fork` stays inside the kernel call. No timeout thread is added. `cgroup.kill` does not cancel creation.
- Windows creation-time job assignment removes the user-mode gap after `CreateProcess` returns. The in-kernel gap was not crash-injected in R.63 and is still `SOURCE_REVIEW_ONLY`.
- A Windows job handle that has been duplicated does not kill on the first close.
- Linux cgroup membership does not kill on owner exit. A living owner, not a new privileged daemon, has to write the child `cgroup.kill`.
- Parent-death signal and pidfd name one process. A grandchild can survive both.
- A pid in a file can be reused. pidfd or a Windows process handle is the direct-child identity.
- The cgroup path has to be a child this call created. The current cgroup, and any ancestor, is not a kill target.
- `rmdir` can fail while the kernel still considers the cgroup busy. Check `populated` and `cgroup.procs` first. Failure stays `CLEANUP_INCOMPLETE`.
- An untracked descendant is outside the guarantee of a direct-child policy. The current diagnostic worker does not create one. That is a source finding, not a permanent property of the program.

## Integration

`ADDITIONAL_PLATFORM_VALIDATION_REQUIRED`

A future design review is not justified yet. Windows job behaviour is known on this Windows 11 host, and the current diagnostic worker does not need descendants, but Linux descendant containment has no kernel test, Windows Server is untested, and no VPS or container was examined. This recommendation does not authorise integration.

`R64_POLICY_VERIFIED` applies to the default refusal and to the rule that an explicit reduced record is not full containment. It does not apply to a successful cgroup kill.
