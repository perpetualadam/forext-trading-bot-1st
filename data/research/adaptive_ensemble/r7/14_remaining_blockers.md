# Remaining blockers

1. PostgreSQL was not started. Persistent recovery and the advisory lock are not engine-verified.

2. The lock does not cover the time after a `PENDING` insert commits and before the row becomes `UNRESOLVED`. A second client id can pass the current check in that window. There is no unique constraint on one open row per symbol.

3. An ambiguous commit can leave a `PENDING` row while the caller is told the reservation failed. That row does not block a different client id.

4. `initdb` reports 18.0 and `postgres` reports 18.1. That was not investigated further because the server was not started.

5. No broker, startup, or production database check was done.
