# R.77 client-id uniqueness

R.76 indexed `(account_binding, client_order_id)` only where `outcome != 'ENTRY_FINALISED'`. A completed id could be reserved again.

R.77 adds two durable facts:

- `CREATE UNIQUE INDEX one_client_order_id ON entry_operations(account_binding, client_order_id)` (`forex_bot/close_journal.py` lines 140–141).
- `client_order_id_registry` (lines 142–148), primary key `(account_binding, client_order_id)`. `begin_entry_submission` inserts the registry row in the same transaction as the entry reservation (`forex_bot/entry_journal.py` lines 142–149).

`canonical_client_order_id` (lines 830–837) strips whitespace. An empty id raises `client_order_id_missing`. An id longer than 128 characters raises `client_order_id_exceeds_broker_limit`. The function does not truncate. `client_order_truncation_key` shows the 128-character broker label so tests can prove two longer ids would collide if they were sliced. Comparison is case-sensitive. A different account binding may use the same client id (test 38).

Reuse rules in `begin_entry_submission` (lines 89–108):

- An existing `ENTRY_RESERVED`, `ENTRY_SUBMITTING`, or `ENTRY_SENT` row raises `unresolved_entry_exists`. This keeps the R.76 unresolved-duplicate result.
- Any other existing row, or a registry tombstone without an in-flight row, raises `client_order_id_retained`.
- A unique-index race raises `client_order_id_retained`.

`archive_finalised_client_id` (lines 450–478) deletes a finalised `entry_operations` row only when the registry row is present. It does not delete the registry row. A later reservation of that id is refused. There is no pruner that deletes registry rows.

Uniqueness is the retained journal file. A missing journal raises `missing_journal` and does not create a reservation (test 45). A deleted or replaced journal file is a new history. These tests do not show that OANDA rejects a repeated client extension. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains. `_submit_order_create` still slices a client extension to 128 characters (`forex_bot/oanda_exec.py` line 516). The journal never stores an id that needs that slice.
