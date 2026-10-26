# Test attempt log

Attempt 1: `python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r54/test_session.py`

Result: 7 passed, 0 failed, 1.54 seconds.

No assertion was changed after the run. No security check was weakened. The application suite and the R.28 database scripts were not run.

The tests call `run_session`. That is the same function that builds the preview and then calls the pinned R.53 connector. The fake client class and the synthetic readers are the only substituted boundaries.
