# R.84 safety gates

`test_01_baseline_gates_and_unchanged_modules` reads the four gate files. Each still contains `REAL_SESSION_SOURCE_ENABLEMENT = False`.

`one_session.permit` was absent at baseline and `tearDown` asserts it stays absent. The consumed-marker hash was checked at baseline and its body was not printed. The suite uses disposable journals and the isolation harness. It does not start `main.py`, `run_bot`, a broker host, PostgreSQL, or a production journal.
