# R.81 entry authority loss

Evidence class: executed `test_02`, `test_04`, `test_10`, and `test_13`.

- Before the permit claim, a process with no current epoch cannot pass the first `live_management_permitted()` check. The stale-entry child in `test_10` is fenced by a successor startup before it reserves, prints `refused=`, and records no OrderCreate.
- After the permit claim and during the rate-limit wait, `test_02` is the executed case. The post-fix recheck refuses the request. The permit stays consumed. The client id cannot be reserved again.
- A fresh process after an entry timeout (`test_13`) calls `execute_startup_sequence` with an empty snapshot and with an incomplete trade identity. Both attempts to reuse `client-amb` are refused. The recorder stays 0. Memory does not gain EUR_USD from that ambiguous entry.
- A journal fault armed on the counted OrderCreate (`test_15`) leaves `ENTRY_OUTCOME_AMBIGUOUS`. The fresh process cannot reuse the client id.

`R81_STALE_OWNER_ENTRY_REFUSED`: PASS.
`R81_CLIENT_ID_UNIQUENESS_PRESERVED`: PASS.
`R81_AMBIGUOUS_ENTRY_RESTART_VERIFIED`: PASS.
`R81_ATOMIC_ENTRY_FINALISATION_PRESERVED`: PASS for the successful fill in `test_04`, which reaches `ENTRY_FINALISED` through `commit_verified_entry`. The ambiguous paths do not publish a managed position.
