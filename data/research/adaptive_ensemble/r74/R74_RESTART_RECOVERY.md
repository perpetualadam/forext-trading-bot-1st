# R.74 Restart Recovery

`active_journal` (`close_journal.py` lines 620–635) opens `CLOSE_JOURNAL_PATH`, checks integrity and schema version, then calls `recover` before returning. `run_guarded_live_close` calls `active_journal` before `reserve` and before the broker helper (`broker_close_evidence.py` lines 641–675).

`recover` (`_recover_locked`, starting at line 445):

- Intent 0 and `CLOSE_PREPARED` becomes `CLOSE_RECONCILIATION_REQUIRED` / `reserved_without_submission_intent`.
- Intent 1 and a non-terminal submitting or response state becomes `CLOSE_OUTCOME_AMBIGUOUS` / `crash_after_submission_intent`.
- A partial row stays partial, with its confirmed and remaining units.
- A full confirmation stays full and is marked `recovered_confirmed_delete_not_assumed`.
- Nothing in `recover` calls the broker.

Fail closed, with submission left disabled:

- missing file: `missing_journal`
- empty or unreadable file: `corrupt_journal`
- schema version other than 1: `unsupported_schema`
- `BEGIN IMMEDIATE` timeout: `journal_lock_or_disk`
- incomplete identity on insert: `incomplete_identity`
- bootstrap flag not set: `bootstrap_does_not_authorise_closes`

These outcomes were exercised in `test_missing_corrupt_and_schema_fail_closed`, `test_lock_and_disk_failure`, `test_bootstrap_without_acknowledgement_refuses_reserves`, and `test_missing_and_unauthorised_journal_do_not_submit`. The last of those recorded no `PositionClose`.

`declare_process_restart` still only moves the in-memory map. It is not the durable recovery path. The journal survives that function because it lives in the SQLite file.
