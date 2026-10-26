# Exposure and order safety

PENDING, PARTIAL, UNRESOLVED, and an unknown status still block a new entry. A historical FILLED hold remains. FILLED does not mean flat. A missing in-memory position does not clear the hold.

`confirm_exposure_flat` still returns false for `CONFIRMED_FLAT`, `verified=True`, and a reconciliation dictionary. Partial, timeout, ambiguous, and position-recording failure keep the hold. Uncertainty does not send a second adapter call.

There is still one `execute_oanda_market_open` reference, inside `production_execution_adapter`. It was not called. No position was fabricated from a rejection. No migration ran. Authoritative broker-flat release remains NOT_EVALUATED.
