# R.80 remaining risks

R.66 findings still open:

- R66-03: `broker_sl_tp_hit` remains false in `live_manage.py`. A local ratchet is not a broker stop fill.
- R66-07: sizing currency is unresolved.
- R66-10 and R66-11: duplicate close suppression is journal-side. It is not broker-enforced.
- R66-16: outside this stage.

R.80 gaps:

- Close-owner crash before the request, and close-owner crash after the request begins, were not executed.
- Explicit repair during an in-flight submit was not executed. R.78 repair tests still pass on their own.
- `test_rejection_can_reserve_a_new_operation` has no R.80 replacement.
- Ambiguous-entry restart through a fresh startup was not asserted.
- Journal faults were not injected at every listed point between snapshot reading and protection persistence.
- The check-to-request race remains after `api.request` has been entered. See the design note. No new protocol was implemented.
- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`. A killed process is not a power loss. Windows boot id remains the constant `windows:boot-id-unavailable`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
- `CLEAN_REINSTALL_VERIFIED` is NOT_VERIFIED.
- `CloseGuardRefusal` after a consumed close permit is recorded as reconciliation with `NOT_SENT`. The permit stays consumed, so a second submit is still blocked. The label is easy to misread.

Production trading remains NO-GO.
