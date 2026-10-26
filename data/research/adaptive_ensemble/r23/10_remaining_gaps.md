# Remaining gaps

This stage does not establish PostgreSQL durability or broker integration. The persistent record is a synthetic JSON file under `r23`.

The production process was not started. Production isolation is the selection function, which ignores `EXEC_ORDER_OFFLINE_STORE`, and the absence of an arm call in `main.py`, `app.py`, and the broker module. A future production change that called `arm_offline_exec_order_store` would be a new defect.

`select_rows_for_recovery` and `ingest_recovery_snapshot` ran inside `initialise_application`. The trace names them because that startup branch completed and the recovered order source is `db_recovery`. They were not wrapped with a separate call counter.

The historical `WinError 5` on `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json` did not recur. The file-lock limitation is not closed. R.23 used its own safety-state path.

R.21 and R.22 still assert their own network-barrier tokens. This stage ran them with their own runners. That is a token match, not a change to the assertions.

Standing eligibility gaps remain: live permission blocked, numeric spread unapproved, margin not implemented, and production provenance missing. Production eligibility stayed false. No strategy activation or risk threshold was changed.
