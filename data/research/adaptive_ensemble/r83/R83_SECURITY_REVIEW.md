# R.83 security review

Static inspection and the executed suite.

- Isolation is imported before any `forex_bot` import in the R.83 test and worker.
- Unexpected request types raise `IsolationBreach`. The worker recorder counts OrderCreate and PositionClose. Restart workers refuse further writes.
- Non-loopback network use and `psycopg2.connect` are refused by the existing harness. No PostgreSQL connection was opened.
- `.env`, tokens, and the consumed-marker body were not read. The marker was checked by hash only.
- `one_session.permit` stayed absent. `tearDown` asserts that.
- The four `REAL_SESSION_SOURCE_ENABLEMENT` assignments stayed `False`.
- Production journals were not opened. Journals were temporary schema-5 files.
- `main.py`, `run_bot`, and live or practice OANDA hosts were not used.
- The two operational edits do not add a submission path, a retry, a permit release, or a broker stop change.
- `oanda_exec.py` still reads token environment names. The tests do not set those names, and the archived source contains the names only.
- No secret value was found in the files packaged for review.

`R83_NO_REAL_BROKER_REQUEST`, `R83_NO_POSTGRESQL_CONNECTION`, `R83_NO_CREDENTIAL_ACCESS`, and `R83_NO_PRODUCTION_JOURNAL_ACCESS` are PASS for this stage.
