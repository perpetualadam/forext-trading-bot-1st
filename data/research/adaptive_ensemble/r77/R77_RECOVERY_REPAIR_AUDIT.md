# R.77 recovery-repair audit

Each repair that successfully opens the configured journal inserts one `recovery_repairs` row in the same transaction as any claim update. The columns are:

- `repair_id`
- `journal_identity` (SHA-256 of the resolved journal path, not an account id)
- `account_binding`
- `target_run_id`
- `previous_state` and `new_state`
- `operator_acknowledgement`
- `liveness_method` and `liveness_status`
- `integrity_result`
- `unresolved_entry_count` and `unresolved_close_count`
- `result` (`REPAIR_COMMITTED` or `REPAIR_REFUSED`)
- `reason`
- `created_at`

No credential column exists. The acknowledgement is the operator sentence supplied to the function.

A `before_commit` fault rolls back the audit insert and the claim update together (test 61). The run stays `RECOVERY_IN_PROGRESS` and the audit count stays 0. A committed release remains after `reset_journal_process_state` (test 64).

Two overlapping repair processes produced one `REPAIR_COMMITTED` and one refusal (test 62). The run ended as `RECOVERY_REPAIR_RELEASED`.

A wrong-path request can write a refusal audit on the configured journal. It does not write the other file and does not change the claim (test 52). A journal that fails `open_journal` returns before an audit insert, because there is no accepted connection to append to. Corrupt and unsupported files therefore refuse with no claim change (tests 53 and 54).
