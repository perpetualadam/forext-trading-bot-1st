# Test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest -q data/research/adaptive_ensemble/r51/test_adapter.py`

Attempt 1: 11 passed, 0 failed. No assertion was weakened and no correction was required.

The same run includes a wrapper that repeats the flow while DNS lookup, connection open, and HTTPS connection construction raise if called. That wrapper passed.

Unchanged R.50 suite, run separately: 26 passed, 0 failed.

The application suite was not run. Importing it reads `OANDA_ACCESS_TOKEN` through `forex_bot.config`. R.28 PostgreSQL scripts were not run. `live_safety.py` was not edited.

No credential file was read. No authenticated request was sent.
