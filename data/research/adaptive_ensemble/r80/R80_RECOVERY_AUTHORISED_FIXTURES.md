# R.80 recovery-authorised fixtures

Evidence class: executed tests. The fixture is `AuthorisedBase._authorise` in `data/research/adaptive_ensemble/r80/poc/test_r80_authorised_concurrency.py`. The multiprocess worker is `data/research/adaptive_ensemble/r80/poc/race_worker.py`.

The fixture does all of the following with operational functions:

1. Creates a disposable schema-5 journal with `bootstrap_journal`.
2. Uses the synthetic account inside the test and worker. The account is not read from the environment.
3. Supplies a complete broker snapshot built from durable rows, or an empty complete snapshot when there are none.
4. Calls `execute_startup_sequence`.
5. Lets `_claim_run` increment the fencing epoch.
6. Asserts the state is `RECOVERY_COMPLETED` or `RECOVERY_COMPLETED_WITH_QUARANTINE`.
7. Asserts the process-local epoch equals the durable `recovery_authority` epoch.
8. Asserts `RecoveryOwnerLock.try_acquire()` succeeds after startup, which shows the lock was released, then releases it.
9. Asserts `live_management_permitted()` is true.
10. Asserts the synthetic broker recorded no write during startup.
11. Returns that broker.
12. Leaves `claim_entry_permit` and `claim_network_permit` unchanged.

`reset_close_evidence_state()` runs in `setUp` because close evidence is process-global. Without that reset, a later test observed the previous confirmed close and never reached the broker.

The worker imports the isolation harness before `forex_bot`. Modes are `reserve`, `startup-only`, `entry-cold`, `startup-entry`, `close-cold`, and `startup-close`. OrderCreate and PositionClose wait on `R80_ENTERED` / `R80_RELEASE` and then insert one recorder row. TransactionDetails is returned without the barrier. No mode copies an in-memory epoch into the child. Each child that needs authority calls `execute_startup_sequence`.

Two processes are not both valid owners. The tested interleavings are one authorised owner, a cold competitor refused, an owner killed during the entry request, and a later startup that becomes the new owner and does not submit the same durable operation again.

`R80_RECOVERY_AUTHORISED_FIXTURES_VALID`: PASS.
