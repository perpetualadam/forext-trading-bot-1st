# R.75 Security Review

## Test isolation

`test_r75_guard_and_recovery.py` and `close_worker.py` import `data/research/adaptive_ensemble/r69/poc/isolation.py` before any `forex_bot` import. The child process does this itself, so it does not inherit a bypass from the parent.

Isolation, unchanged this stage:

- scrubs environment names containing token, secret, password, account, postgres, database, oanda, and the other markers in that file
- replaces `dotenv.load_dotenv`
- installs a synthetic config with an empty access token and account `001-002-0000001-003`
- refuses non-loopback sockets and `urlopen`
- refuses `psycopg2.connect`
- refuses to open a path ending in `.env` or `one_session.permit`

The worker's fake client raises `IsolationBreach` for every endpoint name other than `PositionClose` and `TransactionDetails`.

## What was not loaded

`.env` was not read. Credentials were not printed. The consumed-marker body was not printed. No operational journal was copied into the tests. Journals and the recorder were temporary files. PostgreSQL was not contacted. `main.py`, `forex_bot.app`, and `run_bot` were not started. No permit file was created.

## Account binding

`account_binding` stores SHA-256 of the account id. Raw account ids are not written into `close_operations` or `managed_positions`. Tests use the synthetic id already fixed in the R.69 harness.

## Remaining exposure

The production process is still capable of constructing `OrderCreate` if a future caller passes the existing entry gates. Those gates were not opened. The close boundary cannot be skipped by a boolean. A forged permit does not match a journal row.

`tests/conftest.py` can still load live configuration if someone runs pytest. This stage did not run pytest.
