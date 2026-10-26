# R.78 multiprocess tests

Harness: `data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py` and `liveness_worker.py`. The worker imports the R.69 isolation harness before `forex_bot`. Journals are temporary. The worker environment names do not contain `TOKEN`, so isolation does not scrub them. The crashed-owner token is a SQL literal, not an environment variable.

| Test | Processes | Windows | WSL |
| --- | --- | --- | --- |
| Forged inactive evidence while another process holds the lock | 2 | passed | passed |
| Owner `os._exit` while holding the lock, then repair | 2 | passed | passed |
| Two overlapping `repair_worker.py` repairs | 2 | passed, one `REPAIR_COMMITTED` | passed, one `REPAIR_COMMITTED` |
| Startup while another process holds the lock | 2 | `recovery_already_in_progress` | same |

Same-process tests covered PID reuse against the current PID with a foreign start token, and the current PID with its real start token. Those are not two OS processes. They are recorded separately from the multiprocess rows.

The R.77 overlapping repair worker still passes as part of the R.77 suite except for the schema-version cases classified in the regression report.
