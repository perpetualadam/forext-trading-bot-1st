# Historical FILLED policy

FILLED is not proof that broker exposure is closed. Missing `exposure_safety`, NULL metadata, an empty object, and a missing in-memory position are not proof of flat exposure.

The selection rule keeps:

- PENDING, PARTIAL, and UNRESOLVED rows.
- FILLED rows whose marker is missing, empty, NULL, UNCONFIRMED, unknown, or malformed.

It does not keep CANCELLED or REJECTED rows. It does not keep a FILLED row whose marker is exactly `CONFIRMED_FLAT`. That token is internal. It is not broker evidence, and it does not hide an unresolved or active order on the same symbol.

Unknown statuses and conflicting identities for one client id fail closed. A failed or truncated recovery result fails closed. An empty successful result does not. Unavailable reconciliation does not clear a hold. There is no time-based release, no automatic replacement order, no strategy activation, and no migration.

A historical FILLED row without an authoritative flat marker therefore stays in recovery and blocks a new entry. Releasing that hold later requires a separately authorised broker reconciliation or a durable position record. This stage does not invent that closure.
