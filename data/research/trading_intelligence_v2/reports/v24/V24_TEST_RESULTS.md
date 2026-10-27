# V2.4 Test Results

Executable commands use python -I -S -B and the audit-isolated v24_run.py with
--v24-tests, --tests, --mtf-tests and --v23-tests. Coordinator uses its separate
offline_exposure/run_checks.py. Structured current results: test_results.json.

First V24 test run: 65 tests, four failures, zero errors/skips. Four arithmetic
fixtures unintentionally hit a four-pip stop; corrected the synthetic fixtures
to use a 20-pip stop while preserving the same expected arithmetic. No engine
behavior or safety assertion changed to satisfy them. Subsequent V24 run: 73
passed, zero failures/errors/skips. Added explicit stop, target, gap, pip-value,
margin and software-protection oracles. Double-counting negative controls reject.
One replay attempt rejected reconstructed factor-1 quotes due to float rounding; factor-1 now uses source candles unchanged. A V2.3 regression error rejected edits to its hash-pinned source; original engine.py and run.py were restored, and V24 uses separate observed copies. An AST-equivalence test strips only trace additions and requires the remaining engine to equal the frozen source. Full rerun results and hosted outcomes must be reported separately; a failing
historical full suite is never described as green.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
