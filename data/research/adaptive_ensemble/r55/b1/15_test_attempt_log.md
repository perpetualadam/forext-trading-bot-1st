# Test attempt log

Attempt 1: `python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r55/b1/test_session.py`

Result: collection failed. The test looked for `fixtures.py` one directory above `adaptive_ensemble`. No assertion ran. The session and transport files were not changed.

Correction: the test now resolves `fixtures.py` and the project root from the B1 directory. No expected security result was relaxed.

Attempt 2: the same command.

Result: 8 passed, 0 failed, 3.01 seconds.

The tests call `run_session` with synthetic readers and a fake client. `--offline` uses that same function with `SyntheticTransport`. `run_live` was replaced with a sentinel during the default-launch test and was not entered. The application suite and the R.28 database scripts were not run.

Attempt 3, after the targeted safety correction: the same command.

Result: 6 passed, 2 failed, then 8 passed, 0 failed, 2.98 seconds. The first of those runs failed because a live-label check happened after the key allowlist. The check was moved ahead of that allowlist. The expected code was not relaxed.

Attempt 4, offline hardening: the same command.

Result: 8 passed, 2 failed, 2.32 seconds. The new socket-denial test looked for `classification` on an endpoint result. The connector field is `error_classification`. The assertion was corrected to that existing field. No earlier assertion was relaxed.

Attempt 5, offline hardening: the same command.

Result: 10 passed, 0 failed, 2.97 seconds. The application suite, database scripts, Docker, and WSL were not run. No OANDA connection was opened.
