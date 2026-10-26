# Fake broker outcomes

J73–J92 passed. These are simulated responses, not OANDA results.

- Accepted leaves the reservation in place.
- FILLED calls `finalize_order_fill` and leaves `exposure_unconfirmed`. `confirm_exposure_flat` with evidence `FILLED` returns false.
- A partial fill stays unconfirmed.
- A rejection cancels the reservation.
- Timeout, connection failure, an ambiguous body, and a body without `kind` keep an unresolved exposure hold. The next iteration does not dispatch.
- A duplicate fill script is submitted once.
- Conflicting quantities do not open a position and keep the hold.
- A failed position record and a failed reservation update each block the next entry.
- A fake `CONFIRMED_FLAT` reconciliation token is ignored by the seam. The hold remains.
- `interpret_close_evidence` keeps the hold for timeout, rejection, and partial close evidence. No close request was sent.
- After the process memory is cleared, `select_rows_for_recovery` plus `ingest_recovery_snapshot` still blocks the historical FILLED row.
