# R.81 ambiguous entry restart

Evidence class: executed `test_13` and `test_15`. Fresh OS processes call `execute_startup_sequence`.

Timeout path:

1. The parent completes recovery and reserves `client-amb`.
2. One OrderCreate is counted, then `TimeoutError` is raised.
3. The row is `ENTRY_OUTCOME_AMBIGUOUS`. EUR_USD is not in memory.
4. A new process starts on `COMPLETE_EMPTY` and tries the same client id. It prints `refused=` and inserts nothing.
5. Another new process starts with a trade that has an empty trade id. It also refuses the same client id and inserts nothing.

Journal-fault path in `test_15`: the OrderCreate is counted, `before_commit` fires, the outcome is `ENTRY_OUTCOME_AMBIGUOUS`, and a fresh process cannot reuse `client-fault`.

The successor epoch does not mint a new permit or release the client id. No broker confirmation was invented.

`R81_AMBIGUOUS_ENTRY_RESTART_VERIFIED`: PASS.
