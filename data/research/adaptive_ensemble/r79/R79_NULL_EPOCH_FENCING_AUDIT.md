# R.79 Null-Epoch Fencing Audit

Evidence class: source inspection and executed tests.

R.78 `recovery_fence_allows_publication()` returned true when `_fencing_epoch` was None. That let an operational caller publish with no recovery session.

The function now returns false when the epoch is None or the state is outside `{RECOVERY_IN_PROGRESS, RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE}` (`startup_recovery.py` 123–130). There is no `allow_unfenced` parameter and no environment-variable capability.

| Question | Finding |
| --- | --- |
| Can startup publish before assigning an epoch? | No. `_claim_run` commits the epoch before `publish_recovered`. A failed claim returns blocked and does not enter the publish loop. |
| Can an entry callback publish without an epoch? | The durable row can commit. The memory write is skipped. `test_08` observed `ENTRY_FINALISED`, `published` false, and no `EUR_USD` in memory. |
| Can a legacy recovery API publish without an epoch? | `recover_managed_book` can place a row. It does not call the fence and does not make `live_management_permitted()` true. `test_04`. |
| Can a failed startup leave the epoch unset and still publish? | A blocked startup can leave the epoch unset. Later `publish_recovered` returns `recovery_authority_absent`. Management stays false. |
| Can operator repair clear the epoch? | Repair increments the epoch in the same transaction as the claim update. It does not set the in-memory epoch of a stale process. R.78 repair tests passed. |
| Can a restart leave memory with no epoch while durable rows exist? | Yes. `reset_startup_recovery_memory` clears the epoch. `test_12` showed management false until a new startup claims a new epoch. |
| Can import or reset clear the epoch? | `reset_startup_recovery_memory` clears it. Import does not grant one. |
| Can a stale owner use a null epoch? | A null epoch fails the operational fence. A stale non-null epoch fails `_authority_matches` and returns `recovery_fence_lost`. `test_03` and `test_05`. |
| Can another path call `publish_recovered` directly? | Yes. The function itself refuses without authority. |
| Can a null epoch bypass provenance or journal identity checks? | The operational function returns before `_place_recovered_position`, so those checks are not reached and nothing is published. The offline function still runs `evaluate_durable_row`. |

Missing operational recovery authority fails closed. Offline reconstruction remains a separate function so R.75 tests can rebuild a book without receiving live-management authority.
