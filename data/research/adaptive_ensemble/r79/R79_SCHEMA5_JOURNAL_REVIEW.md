# R.79 Schema-5 Journal Review

Evidence class: source inspection of the unchanged `close_journal.py` and executed tests.

`SCHEMA_VERSION` remains 5. Hash `4593b42c27b099bc87a225bc7de50b6a9908d41dca5464889f9f26e5d500ef9b`.

| Check | Result |
| --- | --- |
| Version 4 fails closed | `open_journal` refuses it. `test_09` built a version-4 file and observed `JournalUnavailable`. R.78 `test_02` passed. |
| Explicit migration | `migrate_journal_4_to_5` remains the migration. Startup does not call it. |
| Transaction and rollback | Unchanged from R.78. R.78 migration and fault tests passed. |
| Recovery authority row | Inserted at bootstrap with epoch 0. Claim increments it. |
| Epoch monotonicity | Claim and repair increment. They do not decrease it. |
| Repair audit | Same transaction as the epoch increment. R.78 tests passed. |
| Entry investigation | Append-only module unchanged. R.78 `test_16` passed. |
| Client-id registry | Permanent uniqueness unchanged. R.78 `test_18` passed. |
| Managed-trade uniqueness | Unchanged. Conflicting R.77 identity tests stayed in the passing set. |
| WAL and `synchronous=FULL` | Unchanged configuration. Not re-measured with a power cut. |
| Production paths | Tests set `CLOSE_JOURNAL_PATH` to a temporary file. |

No production journal was opened and no production migration was run.

`SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` remains. Process kill and a simulated boot-id mismatch are not power-loss proof.
