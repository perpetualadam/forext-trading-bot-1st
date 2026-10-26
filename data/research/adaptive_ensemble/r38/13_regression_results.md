# R.38 regression results

R.38 focused tests: 9 passed.

The first full offline run exited 0 for every suite except R.10. R.10 attempt 1 failed in `test_i25_unresolved_order_prevents_false_flat` because Windows returned `WinError 5` while replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. `live_safety.py` was not changed and the file was not deleted. The separate retry passed: 69 passed, 5 skipped.

R.28 PostgreSQL scripts were not run.
