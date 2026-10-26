# Termination and cleanup

J93–J107 passed.

- Each successful simulation submits one request and returns. `scheduled_another` is false.
- `run_bot` is not in the phase list and was not called.
- No sleep phase and no new thread were observed.
- The fake broker is closed after success and after a raised submit error.
- Two reset runs of the same inputs produced the same status and the same unit count.
- `_pg_conn` stayed `None`.
- The production permission file timestamp did not change.
- Saturday is blocked by the session rule and does not schedule another iteration.
