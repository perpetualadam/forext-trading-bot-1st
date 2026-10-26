# R.78 remaining risks

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`. Documentation does not provide the guarantee, and no broker request was made.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`. Process exit was tested. Power loss was not.
- `LINUX_INTEGRATION_NOT_VERIFIED` for `run_startup_and_one_iteration` and `_execute_bot_cycle`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
- Windows reboot detection is not implemented. The boot id is a constant.
- An actual Linux reboot was not performed. Only a stored boot-id mismatch was tested.
- A repair that races a process restart in the middle of the repair transaction was not simulated. The lock makes the old and new owner unable to hold the claim lock together, but that interleaving was not executed.
- Recovery locks on 9p, SMB, or another shared filesystem were not tested.
- `tradesOpened` is not in the official OrderFill schema. The defensive list branch remains and is not broker-verified.
- Official `OrderFillTransaction` uses optional `clientOrderID`. The create example puts the client id in `clientExtensions`. Both are accepted by the classifier. A broker that returns neither now fails closed. That failure mode was not seen on a live response.
- R.66-03 remains: `broker_sl_tp_hit` is still not a true broker stop or take-profit fill signal in `live_manage.py`.
- R.66-07 remains: sizing currency was not revisited.
- R.66-10 and R.66-11 remain: duplicate close suppression is journal-side, not a broker idempotency guarantee.
- R.66-16 remains outside this stage.
- Historical R.68 through R.73 suites are not green. Their failures are classified as old pins or obsolete expectations. They are still failures.
