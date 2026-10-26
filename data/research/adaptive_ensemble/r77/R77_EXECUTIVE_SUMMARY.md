# R.77 executive summary

Classification: `R77_IMPLEMENTATION_PARTIALLY_VALIDATED`

Production trading remains **NO-GO**. R.78 was not started.

A verified single-trade entry and its managed-position row are now committed in one SQLite transaction by `commit_verified_entry` (`forex_bot/entry_journal.py` lines 357–447). Memory publication in `record_entry_response` (`forex_bot/entry_capture.py` lines 104–121) happens only after that commit. A client order id is retained for the life of the journal by the unique index `one_client_order_id` and the `client_order_id_registry` tombstone (`forex_bot/close_journal.py` lines 140–148). An abandoned `RECOVERY_IN_PROGRESS` claim can be released only by the offline operator function `repair_abandoned_recovery` (`forex_bot/recovery_repair.py` lines 63–92). That function does not enable trading, submit orders, delete positions, or resolve broker ambiguity. `run_bot` now calls `run_startup_and_one_iteration` (`forex_bot/bot_loop.py` lines 4523–4543) before its loop. The isolated harness executed that function on Windows without a real broker call.

## What was verified

- Windows: `test_r77_atomic_entry.py`, 87 tests, all passed.
- Windows regressions that stayed green: R.75 13, R.74 journal 20, R.74 operational 9, R.71 8.
- WSL Python 3.12.3: `test_r77_linux_journal.py`, 2 tests, both passed. Those tests do not import the OANDA SDK.
- Overlapping Windows processes: one of two reservations accepted; one of two repairs committed.

## What was not verified

- Broker-enforced idempotency.
- SQLite durability across power loss.
- Linux execution of `bot_loop` or `oanda_exec`. WSL raised `ModuleNotFoundError: No module named 'oandapyV20'` before `forex_bot.config` was imported.
- Real or practice network execution.
- PostgreSQL.
- Data-only mode as a safe trading mode.

## Acceptance

| Criterion | Result |
| --- | --- |
| `R77_BASELINE_VERIFIED` | Pass. HEAD and unchanged hashes matched before and after the edit set. |
| `R77_ENTRY_FINALISATION_ATOMIC` | Pass. Tests 01–04. |
| `R77_POSITION_CAPTURE_AND_FINALISATION_SAME_TRANSACTION` | Pass. Test 02 counted one commit. |
| `R77_MEMORY_PUBLICATION_AFTER_COMMIT` | Pass. Tests 07–10. |
| `R77_CRASH_AFTER_COMMIT_RECOVERABLE` | Pass. Test 09 reopened the journal and restored the row. |
| `R77_CRASH_BEFORE_COMMIT_ROLLED_BACK` | Pass. Tests 03, 05, 11. |
| `R77_PARTIAL_R76_STATE_QUARANTINED` | Pass. Test 29 and `test_finalised_without_position_is_not_invented`. |
| `R77_CLIENT_ID_PERMANENT_UNIQUENESS` | Pass. Tests 31–45. |
| `R77_FINALISED_CLIENT_ID_REUSE_REFUSED` | Pass. Test 33. |
| `R77_MULTIPROCESS_CLIENT_ID_COLLISION_REFUSED` | Pass. Test 37, two overlapping processes. |
| `R77_SCHEMA_VERSION_EXPLICIT` | Pass. `SCHEMA_VERSION = 4`. |
| `R77_UNSUPPORTED_SCHEMA_FAILS_CLOSED` | Pass. Tests 28 and 54. |
| `R77_CONTROLLED_RECOVERY_REPAIR_IMPLEMENTED` | Pass. Tests 46–65. |
| `R77_ACTIVE_RECOVERY_OWNER_NOT_OVERRIDDEN` | Pass. Tests 48–50. |
| `R77_REPAIR_AUDIT_DURABLE` | Pass. Tests 60 and 61. |
| `R77_REPAIR_DOES_NOT_ENABLE_TRADING` | Pass. Tests 47, 57, 58. |
| `R77_REPAIR_DOES_NOT_RESOLVE_BROKER_AMBIGUITY` | Pass. Tests 55 and 56. |
| `R77_REPAIR_REQUIRES_FULL_RECONCILIATION` | Pass. Test 65. |
| `R77_OPERATIONAL_STARTUP_HARNESS_EXECUTED` | Pass on Windows. Not executed on Linux. |
| `R77_RECOVERY_BEFORE_MANAGEMENT` | Pass. Tests 66–70. |
| `R77_R76_ENTRY_JOURNAL_PRESERVED` | Pass with three obsolete R.76 expectations. 69 of 72 passed. |
| `R77_R75_CLOSE_GUARD_PRESERVED` | Pass. 13 of 13. |
| `R77_R74_CLOSE_JOURNAL_PRESERVED` | Pass. 20 and 9. |
| `R77_R73_FILL_CONFIRMATION_PRESERVED` | Historical suite not green. Matcher behaviour remains in source. |
| `R77_R72_PROTECTION_EVIDENCE_PRESERVED` | Historical hash pin only. |
| `R77_R70_SNAPSHOT_CLASSIFICATION_PRESERVED` | One obsolete empty-book expectation remains. |
| `R77_R68_OWNERSHIP_PRESERVED` | Historical pins remain. Discovery still returns observation-only. |
| `R77_R71_PROFIT_PROTECTION_UNCHANGED` | Pass. File hash unchanged. 8 of 8. |
| `R77_ENTRY_GATES_UNCHANGED` | Pass. Test 82. |
| `R77_SOURCE_GATES_UNCHANGED` | Pass. Gate hashes unchanged. |
| `R77_NO_REAL_NETWORK_EXECUTION` | Pass for this stage. |
| `R77_NO_POSTGRESQL_CONNECTION` | Pass. No `psycopg2.connect` attempt was recorded. |
| `R77_NO_PERMIT_CREATION` | Pass. No `one_session.permit`. Marker hash unchanged. |

Retained limitations: `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`, `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`, `LINUX_INTEGRATION_NOT_VERIFIED`, `REAL_NETWORK_EXECUTION_NOT_TESTED`, `POSTGRESQL_INTEGRATION_NOT_TESTED`, `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.
