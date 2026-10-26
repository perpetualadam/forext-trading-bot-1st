# R.80 multiprocess entry results

Evidence class: executed OS processes. Windows and Linux both passed these tests. Temporary journals. No OANDA request.

`test_10_two_processes_cannot_reserve_one_client`

- Two `reserve` children, same client id, same disposable journal.
- One stdout contains `reserved`. The other contains `unresolved_entry_exists`.
- Recorder count is 0. Neither process submitted.
- This is the SQLite reservation race. It does not grant both processes recovery authority.

`test_11_authorised_entry_pauses_and_competitor_cannot_submit`

- Owner mode `startup-entry` calls `execute_startup_sequence`, reserves, then pauses inside OrderCreate after both authority checks and after the permit claim.
- Competitor mode `entry-cold` has no recovery session. It prints `refused` and inserts no recorder row.
- After `R80_RELEASE`, the recorder has one OrderCreate.
- A later `startup-entry` for the same client increments the epoch and does not insert a second row.

`test_13_kill_during_entry_request_does_not_authorise_a_second`

- The owner is killed while blocked on the barrier, which is inside the synthetic `request` and after the permit claim.
- Recorder count stays 0, because the insert is after the barrier.
- The successor startup does not print `submitted` and does not insert a row.
- The killed process leaves the durable reservation consumed. The successor does not receive a second permit.
- A process kill is not power-loss durability. `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` stays.

`R80_TWO_PROCESS_ENTRY_RACE_VERIFIED`: PASS.
`R80_NO_DUPLICATE_SYNTHETIC_SUBMISSION`: PASS for these interleavings.
