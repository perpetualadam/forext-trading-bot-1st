# R.81 remaining risks

R.66 remains open: `broker_sl_tp_hit` is still false, sizing currency is unresolved, and duplicate-close suppression is journal-side rather than broker-enforced. R66-16 is outside this stage.

R.81 leaves these gaps:

- After the final `live_management_permitted()` call, `api.request` is still a separate statement. A crash or an epoch change inside that call can leave one request in flight. The permit stays consumed. That does not prove the broker rejected a duplicate.
- A journal disconnect after the rate-limit slot, distinct from an epoch change, was not injected.
- Journal faults during close confirmation and protection persistence were not each injected.
- Repair does not apply to a completed recovery session. A dead submission owner is fenced by the next startup, not by repair, unless the crash left `RECOVERY_IN_PROGRESS`.
- The in-progress repair fixture writes the durable claim a crash between `_claim_run` and `_finish_run` leaves, then runs the real repair function. It is not a kill inside `execute_startup_sequence`.
- `CloseGuardRefusal` after a consumed permit is recorded as reconciliation and `NOT_SENT`. The permit remains consumed, so a second submit is blocked. The `NOT_SENT` label means the request was refused, including when the claim had already happened.
- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
- `CLEAN_REINSTALL_VERIFIED = NOT_VERIFIED`.

Production trading remains NO-GO.
