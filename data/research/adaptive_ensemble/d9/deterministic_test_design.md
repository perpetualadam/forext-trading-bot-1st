# D.9 deterministic test design

The fake driver gives each connection and cursor its own integer identity. It records connect, execute, commit, rollback, and close. Failure injection is one-shot or continuous by phase. Observation lists are updated by the creating thread. The post-fix success case does not put a barrier inside `connect`, because the lock allows only one caller to enter it. A barrier there would deadlock the harness.

Pre-fix reproduction, run before the source edit, did use a two-party barrier inside fake connect. That schedule is not part of the post-fix pytest module.

Post-fix overlap: the first caller sets an event inside fake connect and waits. The main thread then starts the second caller and waits up to 0.3 seconds for it to finish. It must still be blocked, and `connect` must have been called once. The main thread then releases the first caller. Both must return the same published identity, with one connection and one cursor.

Failure schedules are sequential: cursor creation, SQL, commit, rollback, cursor close, and connection close. The notes from the failed attempt are recorded before the retry, because a later initialization clears the note list. Both-fail leaves the phase raising for both calls.

Release and replacement use the real release helper. Nested checks call the real `fetch_all_trades_ordered`, which takes the lock and calls `get_connection`.

Every wait is bounded: 3 seconds for events, 5 seconds for thread join, 0.3 seconds for the negative "still blocked" check. Harness close runs after the snapshot and is counted separately.
