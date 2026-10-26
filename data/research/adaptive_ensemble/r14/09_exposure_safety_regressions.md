# Exposure safety

The R.13 fail-closed release remains. `confirm_exposure_flat` returns false for a CONFIRMED_FLAT string, `verified=True`, a fabricated dictionary, a missing in-memory position, and a synthetic close. Partial, timeout, and ambiguous outcomes hold. Historical FILLED, PENDING, PARTIAL, and UNRESOLVED block a new entry. There is no retry and no migration.

Authoritative broker-flat release: NOT_EVALUATED. No new release authority was added.
