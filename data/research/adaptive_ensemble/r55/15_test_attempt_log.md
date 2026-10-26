# Test attempt log

Attempt 1: `python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r55/test_session.py`

Result: 8 passed, 0 failed, 1.88 seconds.

No assertion was changed after the run. No security check was weakened. The application suite and the R.28 database scripts were not run.

The tests call `run_session`. That function shows the preview, requires confirmation, then reads the injected credentials, then calls the pinned R.53 connector. The fake client class and the synthetic readers are the only substituted boundaries. A refused confirmation does not call the credential readers.
