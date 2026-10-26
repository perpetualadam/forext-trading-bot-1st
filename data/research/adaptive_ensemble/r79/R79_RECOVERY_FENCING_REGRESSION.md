# R.79 Recovery Fencing Regression

Evidence class: R.78 suite executed after the fence change, plus R.79 tests.

Windows command:

```text
python -B data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py
```

Linux used the disposable interpreter and `TMPDIR=/tmp`. Both runs: 21 passed.

Preserved behaviour:

- Exclusive non-blocking OS lock before the recovery insert.
- Process-start identity and boot identity recorded on the claim.
- Fencing epoch incremented in the claim transaction.
- Stale owner publication returns `recovery_fence_lost` (`R.78 test_11` and R.79 `test_05`).
- Missing epoch returns `recovery_authority_absent` (`test_03`).
- Crashed owner, PID reuse, same-process start, boot mismatch, and lock-path mismatch remain covered by R.78.
- Two repairs and overlapping repairs still commit once.
- Repair does not enable trading.
- Fresh startup after repair reconciles again.

`test_13` held the lock in another process. `execute_startup_sequence` returned `recovery_already_in_progress`, the cycle counter stayed 0 because startup was called directly, and management stayed false.

`test_12` reset process memory after a committed recovery. Management was false until a new startup assigned a new epoch.

No automatic lease expiry and no automatic recovery takeover were added. A simulated boot-id mismatch is not a reboot test. Windows boot id remains the constant `windows:boot-id-unavailable`. A crash injected inside the repair transaction was not added; R.78 already rolls back a failed repair transaction. `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` remains.
