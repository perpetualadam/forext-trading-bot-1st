# R.81 close-owner crash before the request

Evidence class: executed process kill in `test_05`.

The child completes `execute_startup_sequence`, reserves the close, claims the permit, and blocks inside the rate-limit instrumentation. That barrier is before `api.request`. The parent reads `network_permit=1` and a confirmation state other than `CLOSE_FULLY_CONFIRMED`, then calls `process.kill()` and `communicate()`.

The synthetic recorder stays 0. No PositionClose was entered.

The successor is a new process. It calls `execute_startup_sequence` and then `run_guarded_live_close`. Startup recovery reclassifies the consumed `CLOSE_SUBMITTING` row as `CLOSE_OUTCOME_AMBIGUOUS` with `crash_after_submission_intent`. That label is the existing conservative journal rule for a consumed intent. It is not a broker timeout. The successor prints that ambiguous state, does not print `CLOSE_FULLY_CONFIRMED`, and does not insert a recorder row.

`R81_CLOSE_PRE_REQUEST_CRASH_VERIFIED`: PASS.
`R81_NO_SECOND_CLOSE_AFTER_CRASH`: PASS for this window.

A process kill is not power-loss durability. `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` stays.
