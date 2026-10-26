# R.81 repair and liveness

Evidence class: executed `test_08` and `test_09`. `repair_abandoned_recovery` is the operational function. Its liveness checks were not bypassed.

## Completed owner paused inside the request

The close owner has finished startup, so its run is not `RECOVERY_IN_PROGRESS`. Repair of that run returns `REPAIR_REFUSED` while the child is inside PositionClose and the recorder is still 0. The protocol does not repair a completed session. No second close is created. The child is then released so it is not left running.

## In-progress owner still alive

`abandoned-hold` takes the real OS recovery lock and inserts one `RECOVERY_IN_PROGRESS` row with its own pid, process start, boot id, and lock identity. This is the durable shape `_claim_run` commits before `_finish_run`. Startup has no pause hook, so the test builds that row and holds the lock instead of racing a kill into the middle of startup.

Repair with approved inactive evidence is refused: `REPAIR_REFUSED` / `recovery_owner_active`. The lock check beats a claim that the owner is inactive. The holder is then released.

## Owner confirmed dead

`abandoned-die` writes the same in-progress row, signals, and exits while holding the lock. The parent waits for process exit. Repair then returns `REPAIR_COMMITTED`. The fencing epoch increases. `order_submission_count` and `close_submission_count` are 0. The repair does not resolve the earlier ambiguous close.

The parent's `live_management_permitted()` becomes false. A fresh successor startup does not add a PositionClose and does not mark the old close fully confirmed. `network_permit` stays 1.

`R81_REPAIR_LIVENESS_VERIFIED`: PASS.
`R81_REPAIR_FENCING_VERIFIED`: PASS for the dead in-progress claim. Repair does not apply to a completed submission session, and that refusal was executed.
