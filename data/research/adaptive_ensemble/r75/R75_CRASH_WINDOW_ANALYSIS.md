# R.75 Crash Window Analysis

These windows are different. Only the first two were exercised.

| Window | Observed or designed result | Test |
| --- | --- | --- |
| Python exception before `COMMIT` | Rollback. `before_reserve_commit` returns `injected_before_reserve_commit`. No `PositionClose`. | `test_journal_update_fault_does_not_submit` |
| Process exit after `COMMIT` returns | The row is visible to a new process. A second close is refused. | Two-process test, then a third process |
| Process exit after claim and before the HTTP response is marked | `network_permit` stays 1. `recover` does not submit and does not clear the permit. | Designed from `claim_network_permit` and `_recover_locked`. Not a kill-during-fsync test. |
| Process termination while SQLite is inside the commit fsync | Not injected. | Not tested |
| Operating-system crash or power loss | Not tested. | `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` |

## Position row versus memory

| Order | Next `recover_managed_book` |
| --- | --- |
| Crash before `persist_bot_position` commits | No row. Nothing is restored. Entry currently ends in this state because it does not persist a trade id. |
| Crash after the durable commit and before `publish_recovered` | The row can be published if the broker view matches and protection fields are present. `test_persist_then_restart_restores_the_same_identity` clears memory and recovers. |
| Crash after publish | Memory is gone. The durable row remains and can be published again. A second recovery of the same instance and generation is `unchanged`. |

A confirmed close that has not been finalised stays `awaiting_finalisation`. Recovery does not `pop` the book. `close_confirmed_live_position` remains the only live delete, and it still checks identity after the journal row is loaded.

No claim is made that the SQLite commit and the dictionary mutation are atomic.
