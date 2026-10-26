# R.76 durable entry-intent design

Module: `forex_bot/entry_journal.py`

The entry rows live in the same SQLite file as the close journal. `SCHEMA_VERSION` is 3 (`forex_bot/close_journal.py` line 31). A version other than 3 raises `unsupported_schema` from `open_journal` (line 778). Version 2 is not migrated.

`begin_entry_submission` (line 58):

1. Requires `closes_authorised = 1`. An unacknowledged bootstrap raises `bootstrap_does_not_authorise_closes`. That check does not authorise an entry.
2. Inserts `ENTRY_RESERVED` with `submission_intent = 0` and `network_permit = 0`, then commits.
3. Updates the same row to `submission_intent = 1`, `submission_state = SENDING`, and `outcome = ENTRY_SUBMITTING`, then commits.
4. Returns an `EntrySubmissionPermit`. Constructing a permit elsewhere does not grant a claim.

`claim_entry_permit` (line 168) sets `network_permit = 1` and `submission_state = SENT` only when the owner token, account binding, instrument, direction, units, instance, generation, client id, intent, and outcome still match. A stale token rolls back and raises `entry_authority_refused`. The claim is not reset after a crash.

Uniqueness is the partial index `one_unresolved_entry` on `(account_binding, client_order_id)` where `outcome != 'ENTRY_FINALISED'`. A second reservation of an unresolved client id raises `unresolved_entry_exists` before HTTP. `ENTRY_FINALISED` is the only outcome that releases the index. Rejected, partial, conflicting, and ambiguous rows stay unresolved, so they cannot be reused as a retry.

`recover_entry_operations` (line 279) does not call the broker.

- Intent 0 and `ENTRY_RESERVED` becomes `ENTRY_RECONCILIATION_REQUIRED` / `reserved_without_submission_intent`.
- Intent 1 and an outcome in `{ENTRY_RESERVED, ENTRY_SUBMITTING, ENTRY_SENT}` becomes `ENTRY_OUTCOME_AMBIGUOUS` / `crash_after_entry_submission_intent`.
- A recorded reject, conflict, or partial outcome is left as recorded.

The journal stores no credentials. It stores the account binding, which is a SHA-256 of the account id (`account_binding` in `close_journal.py` line 192).

Client extensions on the market order are a label. They are not broker-enforced idempotency. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains.
