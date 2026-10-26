# Test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest -q data/research/adaptive_ensemble/r50/test_connector.py tests/test_r48_readonly_transport.py data/research/adaptive_ensemble/r49/test_handoff.py`

Attempt 1, R.50 only: 25 passed, 1 failed. The failure is recorded in `04_security_tests.md`. The security assertion was not relaxed.

Attempt 2, R.50 plus the two earlier offline gates: 38 passed.

No credential file was read. No environment variable was read by the connector. No DNS lookup or HTTP request was made. The fake transport answered both allowlisted calls in memory.

Skipped:

- The R.8 through R.42 application suite. It imports modules that read `OANDA_ACCESS_TOKEN` through `forex_bot.config`.
- R.28 PostgreSQL scripts.
- Any Docker, WSL, scheduler, or `main.py` run.

`live_safety.py` was not edited.
