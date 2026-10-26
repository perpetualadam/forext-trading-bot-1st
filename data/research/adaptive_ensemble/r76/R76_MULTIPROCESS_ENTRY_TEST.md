# R.76 multiprocess entry test

Worker: `data/research/adaptive_ensemble/r76/poc/entry_worker.py`

The worker imports `data/research/adaptive_ensemble/r69/poc/isolation.py` before `forex_bot`. Its recorder accepts only an object named `OrderCreate`. Any other endpoint name raises `IsolationBreach`.

Test 20:

1. Creates a temporary SQLite recorder.
2. Starts one worker with a shared client id and a release barrier inside `api.request`, after the journal claim and before the response returns.
3. Waits until that worker writes the entered file, which happens only after `OrderCreate` begins.
4. Starts a second worker with the same client id.
5. The second worker prints `unresolved_entry_exists`.
6. Releases the first worker.
7. The recorder count is 1.

The unique index, not a process-local lock, stops the second reservation. The test does not prove that OANDA would reject a duplicate client extension. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains.

Test 48 is the recovery counterpart. A row already in `RECOVERY_IN_PROGRESS` makes the worker's `execute_startup_sequence` return `RECOVERY_BLOCKED` / `recovery_already_in_progress`. The second process does not restore a book and does not submit an entry.
