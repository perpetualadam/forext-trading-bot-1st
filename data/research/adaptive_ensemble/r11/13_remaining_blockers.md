# Remaining blockers

1. PostgreSQL has not executed the repaired SQL. I51 and I52 are NOT_EVALUATED.
2. Broker reconciliation has not run. I53 is NOT_EVALUATED.
3. Production lifespan and `run_bot` have not run. I54 is NOT_EVALUATED.
4. There is still no durable position table. I55 is NOT_EVALUATED. Historical FILLED rows stay blocking until a later authorised reconciliation or migration.
5. `CONFIRMED_FLAT` remains an internal token. A row carrying it is not reselected, and the token is not broker proof.
6. A recovery page above 2000 rows fail-closes in source. That limit was not measured against a database.
7. `confirm_exposure_flat` still does not clear a durable marker.
