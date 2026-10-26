# R.81 recovery fencing review

Evidence class: static comparison plus the executed successor startups.

`startup_recovery.py`, `position_recovery.py`, and `entry_capture.py` were not edited. Their hashes match the R.80 baseline. Schema 5, the OS recovery lock, the fencing epoch, and the rule that startup does not take over a live owner are unchanged.

A second `execute_startup_sequence` increments the epoch and makes the previous process-local epoch fail `live_management_permitted()`. The R.81 tests use that successor startup as the authority change during the rate-limit wait and for stale-owner refusal.

Repair increments the epoch only for an abandoned `RECOVERY_IN_PROGRESS` claim after the lock and liveness checks. It does not publish a position, send an order, or clear a consumed permit.

`R80_R79_INTEGRATION` behaviour relied on by R.81 remains: null or stale epochs do not publish or manage. The new check is an additional refusal. It does not grant authority.
