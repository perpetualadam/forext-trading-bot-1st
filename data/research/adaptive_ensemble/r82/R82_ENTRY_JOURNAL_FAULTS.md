# R.82 entry journal faults

Command: `python -B data/research/adaptive_ensemble/r82/poc/test_r82_journal_and_exposure.py`

Synthetic account `001-002-0000001-003`. Disposable journal. Real `execute_startup_sequence` before each authorised case. OrderCreate count is `self._writes()`.

| Test | Fault | OrderCreate | Permit | Outcome |
| --- | --- | --- | --- | --- |
| `test_02_entry_authority_missing_before_claim` | Authority row deleted before submit | 0 | `network_permit=0` | `EntryGuardRefusal` |
| `test_04_entry_authority_missing_after_claim` | Row deleted on the second authority check, after claim and before the slot | 0 | `network_permit=1` | Remains `ENTRY_SUBMITTING` |
| `test_06_entry_journal_unreadable_after_rate_limit` | Connection closed inside the slot, before the post-slot check | 0 | `network_permit=1` | `ProgrammingError` classified as ambiguous transport. No request |
| `test_08_entry_authority_row_removed_during_slot` | Row deleted inside the slot | 0 | `network_permit=1` | `EntryGuardRefusal`. A second client also sends nothing |
| `test_12_entry_commit_failure_after_acceptance` | `before_commit` armed inside the accepted OrderCreate | 1 | `network_permit=1` | Outcome is not `ENTRY_FINALISED`. Reusing the client raises `JournalUnavailable` |
| `test_19_readable_wal_stays_authorised_and_malformed_file_does_not` | Malformed file after close | 0 | Reservation does not start | `JournalUnavailable` |

The permit is not cleared after a consumed claim. When the journal connection is closed, the permit row is read only after `reset_journal_process_state()` and a fresh `active_journal()`.

No second OrderCreate was observed for the same consumed client.
