# R.81 security review

- No `main.py`, `forex_bot.app`, or `run_bot`.
- No OANDA practice or live request. `R81_NO_REAL_BROKER_REQUEST`: PASS. Unexpected synthetic request types raise `IsolationBreach`.
- No PostgreSQL connection. `R81_NO_POSTGRESQL_CONNECTION`: PASS.
- No `.env`, token, or credential read. `R81_NO_CREDENTIAL_ACCESS`: PASS.
- No production journal. `R81_NO_PRODUCTION_JOURNAL_ACCESS`: PASS.
- Permit absent. Consumed-marker hash unchanged. Contents not printed.
- Gates remain disabled.
- The new check only refuses. It does not add a write path, a retry, a lease, or a takeover.
- Client-id reuse, permit reuse, and false close confirmation were tested and refused on the executed paths.
- A synthetic recorder row was not treated as an OANDA fill.
- No dependency was installed.

`R81_NO_LIVE_PERMIT`: PASS.
