# R.80 security review

Evidence class: static inspection plus the executed suites.

- `main.py`, `forex_bot.app`, and `run_bot` were not started.
- No OANDA practice or live URL was requested. `R80_NO_REAL_BROKER_REQUEST`: PASS.
- No PostgreSQL connection. `R80_NO_POSTGRESQL_CONNECTION`: PASS. The isolation harness still raises on `psycopg2.connect`.
- `.env`, credentials, and tokens were not read. `R80_NO_CREDENTIAL_ACCESS`: PASS.
- Production SQLite journals were not opened. `R80_NO_PRODUCTION_JOURNAL_ACCESS`: PASS.
- `one_session.permit` is absent. The consumed-marker hash is unchanged. Its contents were not printed.
- The four live-session gates still set `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- Worker environment names do not carry account ids, tokens, or database DSNs. Isolation is imported before `forex_bot`.
- The second authority check cannot authorise a write. It can only refuse one.
- No automatic retry, lease expiry, or recovery takeover was added.
- Client-id uniqueness, atomic `commit_verified_entry`, and one-shot close permits were not weakened.
- An order id is still refused as a trade id in `test_06`.
- Broker-only and manual rows stay out of `positions` in `test_14`.
- The ratchet does not move backwards in `test_16`.
- No dependency was installed.

`R80_NO_LIVE_PERMIT`: PASS.
