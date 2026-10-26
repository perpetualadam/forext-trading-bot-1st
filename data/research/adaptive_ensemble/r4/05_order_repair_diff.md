# Order-repair diff

`forex_bot/oanda_exec.py` was not edited. Its timeout and connection classification was already `AMBIGUOUS_TRANSPORT_OUTCOME`.

`forex_bot/database.py` was already dirty versus Git HEAD. Its pre-edit SHA-256 matched the protected baseline `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`. The earlier connection-cleanup code was left in place.

R.4 added:

- Status `UNRESOLVED`.
- `book_on_ambiguous`, `book_on_terminal`, `book_on_reconciliation`, and `new_intent_block_reason`.
- `remember_ambiguous_outcome`, `read_durable_recovery`, and `persist_unresolved_order`.
- A reservation refusal when that symbol already has an unresolved intent.
- Recovery reload now includes status `UNRESOLVED`.

`forex_bot/bot_loop.py` was clean before this stage. The broker path now calls `broker_entry_block_reason` before `generate_client_order_id`. Confirmed cancellation and confirmed rejection still close the reservation. Ambiguous, malformed, and unknown exceptions call `remember_ambiguous_outcome` and do not mark the order cancelled.

No production database was opened. The new status does not add a table or column. The new `database.py` hash is not a permanent baseline for a later stage.
