# Reservation and dispatch

J53–J72 passed.

- A clean simulation reserves with `try_begin_order_submission` and then calls the fake broker once.
- The same client id, a pending reservation, a partial reservation, an unresolved reservation, and a historical FILLED hold all refuse a second dispatch.
- Persistence fail, uncertain commit, timeout, and a malformed reservation response call `refuse_reservation_after_database_fault` and do not dispatch.
- An open position blocks before reservation. Exposure without a position object still blocks.
- A fake refusal is classified as a rejection and releases the in-memory reservation.
- A timeout does not create a replacement client id.
- A second client id does not bypass an active reservation.
- `simulation=False` never reaches `submit`.
- `oanda_client._api` stayed `None`. The socket barrier rejected the probe.
