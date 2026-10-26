# R.74 Cross-process Coordination

The single-flight constraint is the partial unique index `one_unresolved_close` plus `BEGIN IMMEDIATE`. It is not a `threading.Lock`, a PID file, or a lease.

`test_two_processes_one_reservation` started two `journal_worker.py` processes against one temporary database. One JSON result was `ok`. The other was `unresolved_operation_exists`. The worker imports `close_journal` only. It does not construct a broker request.

`test_two_threads_one_reservation` produced the same one-success result on one connection. `test_two_threads_submit_once` on the synthetic broker recorded one `PositionClose`.

The worker does not call the broker, so the two-process test does not count HTTP calls. `run_guarded_live_close` cannot reach `_submit_position_close_body` without a committed intent token. Only one unresolved row can hold that intent for one account binding, instrument, and trade id.

## Fencing

`owner_token` is written in the intent transaction. `submission_authorized` requires that exact token (`close_journal.py` lines 270–287). `test_stale_token_is_not_authorised` updated the stored token and the previous token returned false. There is no function that replaces a live owner in order to take over a submission.

An expired lease is not implemented. A dead process leaves the intent row in place. The next process recovers it as ambiguous and does not submit.

This was tested on a local temp filesystem from Windows and, for the journal suite, from WSL against the same source. That does not establish locking across two machines or across a sync folder.
