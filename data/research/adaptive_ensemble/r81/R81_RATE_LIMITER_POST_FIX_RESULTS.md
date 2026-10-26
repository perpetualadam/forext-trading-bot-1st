# R.81 post-fix rate-limit results

Evidence class: the same two tests after the recheck, plus the valid-once test. Windows CPython 3.13.5. The full R.81 file was 16 passed in 24.760s before a later exception-propagation tightening. The final source rerun is in the Windows and Linux result reports.

The change is one `live_management_permitted()` call after `acquire_oanda_rest_slot()` and before `api.request` in both sinks (`oanda_exec.py` 455–457 and 553–555). `CloseGuardRefusal` and `EntryGuardRefusal` from that check are re-raised so the generic handlers do not relabel them as transport outcomes. The consumed permit is not released. There is no retry.

## Entry

`test_02` blocks inside the rate-limit slot, lets a successor startup increment the epoch, then releases the child. Recorder count is 0. The child prints `refused=`. `network_permit` stays 1. A second `begin_entry_submission` for that client raises `JournalUnavailable`. No managed position is published.

`R81_ENTRY_RATE_LIMIT_RACE_BLOCKED`: PASS.
`R81_ENTRY_PERMIT_REMAINS_CONSUMED`: PASS.

## Close

`test_03` uses a durable EUR_USD position, a real close permit, and the real `run_guarded_live_close` path. After the successor startup, the recorder count is 0 and the output does not contain `CLOSE_FULLY_CONFIRMED`. `network_permit` stays 1. A fresh successor process does not add a submission.

`R81_CLOSE_RATE_LIMIT_RACE_BLOCKED`: PASS.
`R81_CLOSE_PERMIT_REMAINS_CONSUMED`: PASS.

## Valid authority

`test_04` does not change the epoch during the slot. One OrderCreate finalises the entry. The same client cannot be reserved again. One PositionClose reaches `CLOSE_FULLY_CONFIRMED`. The repeat close does not add a second PositionClose.

`R81_VALID_ENTRY_SUBMITS_ONCE`: PASS.
`R81_VALID_CLOSE_SUBMITS_ONCE`: PASS.

The rate limiter was not changed. A successor startup is a real recovery handoff, not a direct epoch write.
