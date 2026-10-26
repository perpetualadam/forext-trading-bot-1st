# R.74 Security Review

- The journal stores `account_binding`, a SHA-256 of the account id. Inserts and logs in the new path do not write the raw account id.
- No credential, token, `.env`, or permit is read by the journal.
- Operational tests import the R.69 isolation harness before `forex_bot`. The synthetic account is the established test account. `FakeAPI` raises `IsolationBreach` for an unexpected endpoint.
- `psycopg2` was not used. No migration ran.
- `CLOSE_JOURNAL_PATH` is an explicit path. The close path does not create a default database in the repository.
- A missing, corrupt, wrong-schema, locked, or unacknowledged journal does not fall through to `_submit_position_close_body`.
- Symbol-only live deletion was removed. Observation rows remain non-deletable.
- The owner token comparison refuses a stale process. There is no takeover helper.
- Source gates remain `REAL_SESSION_SOURCE_ENABLEMENT = False`. The consumed marker was not modified. No `one_session.permit` was created.
- Tests used a temporary directory, not an operational journal left in the tree.

Residual: a process that calls `_submit_position_close_body` while bypassing `run_guarded_live_close` is not fenced by the journal. The manage path does not do that. `execute_trade` can still reach the older live helper for a non-manage caller. No new caller was added.
