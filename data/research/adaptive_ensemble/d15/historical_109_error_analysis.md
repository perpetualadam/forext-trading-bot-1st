# Historical 109 setup-error analysis

D.14 reported 109 historical setup errors. This stage ran the same historical modules again. Pytest reported `109 errors in 1.13s` and exit code 1. The error lines were counted independently: 109. Every error is an `AssertionError` from a source-hash comparison during setup. No historical test body ran. A hash conflict is not a production defect and it is not evidence that the current source is safe.

| Group | Collected | Setup errors | Stopping assertion | Expected SHA | Current SHA | Explained by | Body ran | Obsolete assertion in source | Invariant still relevant | Current-source coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D.5 | 15 | 15 | app.py equality | `f38c304c…` | `3ff01244…` | D.7, D.13, D.14 | no | no | yes | D.4 and D.15 safety / corrupt lifespan |
| D.6 | 12 | 12 | app.py equality | `f38c304c…` | `3ff01244…` | D.7 | no | yes, pre-fix cleanup gaps | yes, as the repaired behaviour | D.7 and D.15 exception schedules |
| D.8 | 7 | 7 | app.py and old database equality | app `08766300…`, database `74bb9f5d…` | app `3ff01244…`, database `cf978bfa…` | D.9, D.13, D.14 | no | yes, unlocked overlap was expected to abandon a connection | yes | D.7 and D.15 B01–B06 |
| D.9 | 6 | 6 | app.py equality | `08766300…` | `3ff01244…` | D.13, D.14 | no | no | yes | D.7 and D.15 B04–B06 |
| D.10 | 14 | 8 + 6 | app.py and pre-D.11 telegram equality | app `08766300…`, telegram `270f2b48…` | app `3ff01244…`, telegram `d32b5603…` | D.11, D.13, D.14 | no | yes, one test expects the stop event cleared and two workers | yes | D.15 T05–T08 and R08–R12 |
| D.11 | 31 | 14 + 17 | app.py equality | `08766300…` | `3ff01244…` | D.13, D.14 | no | no | yes | D.15 Telegram and database schedules |
| D.12 | 16 | 7 + 3 + 6 | app.py and pre-D.14 telegram equality | app `08766300…`, telegram `193a5964…` | app `3ff01244…`, telegram `d32b5603…` | D.13, D.14 | no | yes, incomplete stop was expected to be unreported | yes | D.15 L14–L17 |
| D.13 | 8 | 5 + 3 | telegram equality | `193a5964…` | `d32b5603…` | D.14 | no | yes, startup refusal was expected to be invisible | yes | D.15 L06–L07 and R08–R10 |

File counts from the error list: D.5 15, D.6 12, D.8 7, D.9 6, D.10 telegram 8, D.10 borrower 6, D.11 telegram 14, D.11 borrower 17, D.12 shutdown 7, D.12 repeated 3, D.12 ownership 6, D.13 lifecycle 5, D.13 application 3. The sum is 109.

The obsolete assertions were classified from the test source. They did not execute, so they did not fail at runtime. If the hash pins were removed, those assertions would conflict with the repaired contracts. Both categories are recorded for those groups.

D.2 (30), D.3 (35), D.4 (50), D.7 (18), and D.14 (10) ran against the current source: 143 passed in 34.62s. Safety-repair ran alone: 23 passed in 4.95s. Those passes are separate from the 109 setup errors.

The 109 blocked tests are mapped in `historical_invariant_coverage_map.json`. Each row points at the current function and the D.15 or D.7/D.4 test that checks the same safety property. No row is marked `COVERAGE_GAP`. The exact D.9 commit, rollback, and close-failure schedule names were not rebuilt inside the D.15 child. Their safety property was executed by the current-source D.7 cleanup tests in the 143-pass run.
