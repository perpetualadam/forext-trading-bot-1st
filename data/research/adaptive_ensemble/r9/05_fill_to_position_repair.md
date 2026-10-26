# Fill-to-position repair

Defect: `finalize_order_fill` marked FILLED and released the reservation. The position lived only in memory. After a missing or lost position, a new client id could be reserved.

Repair:

- A FILLED or PARTIAL update carries `exposure_safety=UNCONFIRMED` in the same metadata payload as the status change.
- The process hold is set and the reservation hold is not released by the fill.
- `try_begin_order_submission` returns false while a position object exists or an exposure hold exists.
- The next loop pass calls `exposure_entry_block_reason` before strategy selection and sizing.
- If broker filled units are not positive, or `open_position` raises, the function returns and the hold stays.
- `record_synthetic_fill_position` creates a position only from complete synthetic evidence. It does not replace a conflicting position and it does not call a broker.
- Duplicate same-size evidence is idempotent.

A durable write failure while persistence is enabled fail-closes. Persistence off keeps the process hold and does not pretend the marker was stored. Restart safety for that mode remains the existing unreadable-recovery block, not a restored position.

PostgreSQL did not execute the update or the recovery query. Broker fills were synthetic.
