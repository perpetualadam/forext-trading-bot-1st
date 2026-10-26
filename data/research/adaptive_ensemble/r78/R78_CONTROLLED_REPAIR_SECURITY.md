# R.78 controlled repair security

`repair_abandoned_recovery` still cannot create a permit, enable a source gate, send an order, send a close, delete a position, promote a broker-only position, resolve an ambiguous entry or close, reset profit protection, mark an account flat, or skip startup.

The function's only journal writes are the `recovery_runs` state change, the `recovery_authority` epoch increment, and one `recovery_repairs` row. Those three writes share one `BEGIN IMMEDIATE` transaction. `arm_active_journal_fault("before_commit")` rolls the transaction back. The tested result leaves the claim `RECOVERY_IN_PROGRESS` and leaves an ambiguous entry outcome unchanged.

Unresolved entry and close rows are counted into the audit and are not updated.

The repair module does not import an OANDA client. Its source does not contain `orderCreate` or `one_session.permit`. The phase-6, R.59, R.60, and R.61 gate files were hashed after a committed repair and matched the baseline. The consumed marker hash was unchanged. No permit file existed.

Schema 5 is explicit. `open_journal` refuses every version other than 5, including a version-4 file (`close_journal.py` lines 823–824). `migrate_journal_4_to_5` (lines 1001–1078) refuses anything other than version 4, checks integrity, and can roll back before commit. Startup does not call it.

Operator acknowledgement is still required. An empty acknowledgement returns `operator_acknowledgement_required` without acquiring the lock.
