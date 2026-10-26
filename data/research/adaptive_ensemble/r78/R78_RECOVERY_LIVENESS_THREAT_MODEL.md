# R.78 recovery liveness threat model

The R.77 repair API accepted `ProcessLivenessEvidence` and did not inspect the operating system. A caller could say `inactive` while the recovery owner was still inside `execute_startup_sequence`. That was the trust boundary for this stage.

| Threat | Treatment |
| --- | --- |
| Forged inactive evidence | Repair acquires the OS lock first. If the owner holds it, the result is `recovery_owner_active` and the claim stays `RECOVERY_IN_PROGRESS`. |
| Stale inactive evidence | A timestamp is not an approved method. `timestamp` returns `timestamp_not_sufficient` before the lock is acquired. |
| PID alone | `pid` is a weak method and returns `pid_reuse_ambiguous` before the lock is acquired. |
| PID reuse | If the recorded start token differs from the process now using that PID, the old process is not treated as alive. Release still requires the lock, the owner token, and no boot or path mismatch. |
| Same process, lock dropped | If the PID is alive and the start token matches, repair returns `recovery_owner_active` even though the lock is free. |
| Process restart | A new process has a new start token and must claim a new fencing epoch. The old epoch cannot manage. |
| Parent and child | The lock is per process. A child that inherits no lock cannot release the parent's claim without acquiring it. |
| Recovery crash | Process exit closes the lock. The journal row can remain `RECOVERY_IN_PROGRESS`. Repair can then acquire the lock. |
| Host reboot | On Linux a changed `/proc/sys/kernel/random/boot_id` refuses with `host_boot_identity_changed`. This path was tested by storing a different id. An actual reboot was not performed. |
| Windows reboot | `host_boot_id()` is `windows:boot-id-unavailable`. Reboot detection is `NOT_VERIFIED` on Windows. |
| Journal moved | A stored lock-path hash that differs from the current path refuses with `journal_lock_path_changed`. |
| Different host | A different Linux boot id or a different resolved lock path fails closed. Moving a journal between hosts was not performed physically. |
| Shared filesystem | Tests used local Windows temp and WSL ext4 `/tmp`. 9p locking is not claimed. |
| Clock drift | Release does not read `created_at` or the evidence time. Moving those values still requires the lock and token. |
| Check-then-release race | The repair process holds the OS lock across the SQLite transaction that changes the claim and increments the epoch. The old owner cannot hold the same lock during that commit. After commit, the old epoch no longer matches. |
| Two repair operators | The lock plus the single `RECOVERY_IN_PROGRESS` row produce one `REPAIR_COMMITTED`. |
| Two bot instances | The second `execute_startup_sequence` gets `recovery_already_in_progress` while the first holds the lock. |

A matching owner token does not prove that a process has exited. A stale timestamp does not prove inactivity. The lock is necessary and is not sufficient on its own. The fencing epoch is the authority check after the lock is released.
