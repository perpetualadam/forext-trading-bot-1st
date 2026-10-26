# Startup integration results

OFFLINE INITIALIZATION EXECUTED WITH FAKE DEPENDENCIES. `initialise_application` calls `select_rows_for_recovery` before `ingest_recovery_snapshot` on the injected path.

A startup book containing a legacy FILLED row and a CANCELLED row keeps only the FILLED row and records `exposure_unconfirmed`. `trading_ready` stays false. `offline_ready` means offline initialization only.

Corrupt recovery, a failing provider, and a conflicting client id do not reach ready. Reconciliation unavailable leaves the hold in place. Two FILLED rows both survive startup. A `CONFIRMED_FLAT` row does not remove an UNRESOLVED row. Repeated ingest of the same client id does not duplicate it.

Shutdown closes the fake resources and does not clear the exposure hold. Live-order auth stays BLOCKED. Strategies stay inactive. `run_bot` is not imported. The fake broker records no startup submission. `database._pg_conn` stays None.

The production lifespan was not entered.
