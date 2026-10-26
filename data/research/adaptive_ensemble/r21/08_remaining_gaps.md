# Remaining gaps

- Default `select_strategy` still returns null while every production strategy is inactive. R.21 does not activate any strategy. A valid offline name comes only from `select_deterministic` when an eligibility map marks one of the six names.
- Unknown and malformed selector outputs are not produced by the real selector. Those two cases use a test double.
- The `UNRESOLVED` status is in-memory. `PERSIST_EXEC_ORDERS=0`, and no PostgreSQL connection was opened. Restart durability remains not evaluated.
- Production eligibility remains false. Numeric spread stays unapproved, margin evidence is not implemented, and production strategy activation stays blocked.
- The historical Windows `WinError 5` on the R.10 synthetic safety-state replace did not occur in this run. The limitation is not closed.
- This stage does not authorise practice orders, live trading, deployment, or rollback.
