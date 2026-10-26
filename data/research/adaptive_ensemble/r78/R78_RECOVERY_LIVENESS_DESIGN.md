# R.78 recovery liveness design

Module: `forex_bot/recovery_owner_lock.py`.

`RecoveryOwnerLock` opens `journal path + ".recovery.lock"` and takes a non-blocking exclusive lock. The file contains one byte so the Windows byte-range lock has a region. `try_acquire` returns false on `OSError` and does not keep the handle. `release` unlocks and closes the handle.

The lock is acquired in `_claim_run` (`startup_recovery.py` lines 152–207) before the recovery row is inserted. If the lock is busy, `_claim_run` returns `None` and startup reports `recovery_already_in_progress`. If the insert hits `IntegrityError`, the lock is released and the function returns `None`, so an existing in-progress row is not taken over. The lock is held until `_finish_run` (lines 217–225). The fencing epoch stays in process memory after the lock is released.

Repair acquires the same lock only after the existing R.77 refusals for acknowledgement, weak method, active status, unknown status, and caller-supplied `pid_reused` (`recovery_repair.py` lines 69–122). A refusal on those paths does not take the owner's lock. On the approved path the lock is held across `_record` and released in `finally`.

Process identity is defense in depth, not the sole proof:

- `owner_process_status` returns `unrecorded`, `dead`, `unknown`, `alive`, or `pid_reused`.
- `alive` refuses release.
- `unknown` refuses with `process_status_unknown`.
- `dead` or `unrecorded` may release when the lock is held and the token matches.
- `pid_reused` may release on that same path. The audit result remains `abandoned_claim_released`. The return value includes `process_observation=pid_reused`.

`host_boot_id` and `lock_identity` are stored on the run. A non-null mismatch fails closed. Null values, which are what an R.77-style SQL insert leaves behind, do not by themselves refuse.

No broker write is involved. The lock does not grant trading authority. There is no lease expiry and no automatic takeover.
