# R.86 Recovery Authority Boundary

Evidence: source of `exposure_report.py` and `test_56`, plus the cycle tests. The OS lock was not redesigned.

The report receives copies of rows and an observation. It returns a dictionary. It does not call `execute_startup_sequence`, `finalise`, `record_entry_response`, or the position book.

Executed checks:

- A caller list is unchanged after the call (`test_44`, `test_46`).
- `journal_mutated` and `position_book_mutated` are false.
- `broker_requests` is 0.
- An observation recorded at epoch 1, reported while the caller says the current epoch is 2, has `authoritative_current` false and stale quality.
- The report does not change `current_epoch`. The epoch is only an argument.

A stale owner can build that historical description. The description is not labelled current. The final check-to-request race is unchanged and remains open. Startup still releases the OS lock when recovery finishes.
