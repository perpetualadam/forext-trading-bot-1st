# Exposure safety invariants

FILLED means the order executed. `order_status_proves_exposure_closed` remains false.

A missing position object is not proof that the broker is flat. A timeout, a lost connection, a malformed close, a rejected close, a partial close, and an unavailable reconciliation keep the hold. A failed or incomplete recovery is not zero exposure. A stale snapshot and an unknown marker fail closed.

A FILLED or PARTIAL order without an explicit flat marker blocks another entry. An open position also blocks, including a direct reservation. A confirmed flat token releases only that symbol's exposure hold, and only when recovery is not fail-closed, no unresolved order remains, and the reservation id matches. The token is the internal word `CONFIRMED_FLAT`. It is not broker reconciliation.

No timer releases a hold. No retry creates another client id. Cancelling one order does not clear an exposure hold. The R.8 reservation block for PENDING, PARTIAL, UNRESOLVED, and unknown status remains. Live authorisation stays blocked.
