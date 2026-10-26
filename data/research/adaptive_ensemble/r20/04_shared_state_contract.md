# Shared state contract

Both cycles use the existing process-local order book, position book, and exposure maps. Nothing is reset between cycle 1 and cycle 2. No second position policy was added.

- A FILLED synthetic order calls `finalize_order_fill` and `record_synthetic_fill_position`. That writes `exposure_safety=UNCONFIRMED`, notes the exposure hold, and opens a local position.
- Cycle 2 reads that hold (`exposure_read=exposure_unconfirmed`) and then the existing position gate returns `position_already_open` before reservation.
- An ambiguous adapter result does not open a position. It keeps the reservation, calls `restore_unresolved_intent`, and notes unconfirmed exposure. The local order status stays `PENDING`. That is the existing safe equivalent of an unresolved attempt. Cycle 2 returns `exposure_unconfirmed` and does not dispatch.
- PARTIAL uses the same unconfirmed exposure mark.
- A reservation persistence failure returns before dispatch.
- `confirm_exposure_flat` still returns false for a caller token.
- No PostgreSQL connection was opened.
- These maps do not survive a process restart. Restart durability remains NOT_EVALUATED.
