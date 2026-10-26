# R.80 executive summary

Classification: `R80_CONCURRENCY_AND_REGRESSION_PARTIALLY_VERIFIED`

Production trading remains NO-GO. R.81 was not started.

The R.79 baseline matched before any edit. Historical R.68–R.79 test files were not edited. The only operational edit is a second `live_management_permitted()` check immediately before `api.request` in the OrderCreate and PositionClose sinks (`forex_bot/oanda_exec.py` lines 449–450 and 544–545). Recovery fencing, schema 5, permits, and profit-protection parameters were not changed.

New tests call the real `execute_startup_sequence` on disposable schema-5 journals and a synthetic broker. On Windows CPython 3.13.5 and the existing Linux CPython 3.12.3 disposable environment, the R.80 suite was 17 passed. R.79 remained 17 passed and R.78 remained 21 passed on both platforms. Historical R.68–R.77 totals match the R.79 rerun. No new genuine behavioural regression was observed.

Executed safety results:

- One authorised close, and one authorised entry, each produce one synthetic write.
- A repeat or stale close permit does not add a second PositionClose.
- An ambiguous close stays `CLOSE_OUTCOME_AMBIGUOUS` and is not retried.
- Two OS processes cannot reserve one client id.
- An authorised owner paused inside the synthetic request blocks a cold competitor. A later startup does not receive a second submission permit.
- Killing the entry owner during the request leaves the recorder at zero and the successor does not submit.
- Three durable managed trades recover through `run_startup_and_one_iteration`. Broker-only and manual rows stay out of `positions`.
- Profit protection on those recovered rows keeps the 0.67 trigger, 4-pip fallback, and monotonic ratchet. No broker stop was modified.
- A journal fault after recovery, and a corrupt journal after the connection is dropped, fail closed.
- Authority lost after the permit claim and before `api.request` sends nothing. Authority lost inside the request does not create a second request.

Not executed, and the reason for the partial classification:

- A close-owner crash before the request, and a close-owner crash after the request has begun, were not separate process kills.
- An explicit `repair_abandoned_recovery` interleaving was not added. The still-passing R.78 suite covers repair by itself.
- A rejected close that is allowed to reserve a later operation was not rebuilt (`MISSING_COVERAGE`).
- The dependency lock records the R.79 pip report. A clean reinstall was not performed.

Retained: `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`, `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`, `REAL_NETWORK_EXECUTION_NOT_TESTED`, `POSTGRESQL_INTEGRATION_NOT_TESTED`, `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
