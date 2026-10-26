# R.78 recovery fencing review

The recovery gate is both process-local and journal-backed.

Process memory holds `_state` and `_fencing_epoch` in `startup_recovery.py`. `live_management_permitted` (lines 130–134) is true only when the state is `RECOVERY_COMPLETED` or `RECOVERY_COMPLETED_WITH_QUARANTINE`, the in-memory epoch is set, and it equals `recovery_authority.fencing_epoch`. A journal read failure returns false.

`recovery_fence_allows_publication` (lines 123–127) returns true when no epoch is set. That preserves R.75 `recover_managed_book`, which publishes outside a startup session. When an epoch is set, publication requires the same journal match.

`publish_recovered` (`position_recovery.py` lines 388–394) returns `recovery_fence_lost` and does not write `positions` when the fence fails.

`execute_startup_sequence` checks the fence again before it publishes durable rows (lines 271–281). A lost fence blocks recovery.

Epoch changes:

- Bootstrap inserts `recovery_authority` id 1, epoch 0 (`close_journal.py` lines 772–775).
- `_claim_run` increments the epoch in the same transaction as the run insert.
- Repair increments it again in the same transaction as the claim update and the `recovery_repairs` insert (`recovery_repair.py` lines 196–205). If that update does not change one row, the transaction rolls back and the claim stays in progress.

A repair does not set `_state` to a completed value and does not call startup. After `RECOVERY_REPAIR_RELEASED`, `live_management_permitted()` is false until a later `execute_startup_sequence` claims a new epoch and reconciles the synthetic snapshot.

A process that keeps running after its epoch is superseded fails `live_management_permitted` and `publish_recovered`. The file lock alone is not that fence. The lock decides who may release the claim. The epoch decides who may publish or manage afterwards.

No automatic takeover was added.
