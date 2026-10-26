# R.82 Windows test results

Interpreter: CPython 3.13.5. OS: Windows. Command:

`python -B data/research/adaptive_ensemble/r82/poc/test_r82_journal_and_exposure.py`

| Suite | Exit | Tests | Passed | Failed | Errors | Skipped | Runtime |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R.82 final | 0 | 19 | 19 | 0 | 0 | 0 | 12.987s |
| R.81 | 0 | 16 | 16 | 0 | 0 | 0 | 28.179s |
| R.80 | 0 | 17 | 17 | 0 | 0 | 0 | 15.618s |
| R.79 | 0 | 17 | 17 | 0 | 0 | 0 | 4.957s |
| R.78 | 0 | 21 | 21 | 0 | 0 | 0 | 2.252s |
| R.77 atomic | 1 | 87 | 82 | 2 | 3 | 0 | 6.545s |
| R.77 journal file | 1 | 2 | 0 | 1 | 1 | 0 | 0.351s |
| R.76 | 1 | 72 | 64 | 6 | 2 | 0 | 12.973s |
| R.75 | 1 | 13 | 10 | 3 | 0 | 0 | 7.966s |
| R.74 operational | 1 | 9 | 3 | 6 | 0 | 0 | 0.623s |
| R.74 journal | 0 | 20 | 20 | 0 | 0 | 0 | 1.840s |
| R.73 | 1 | 31 | 8 | 21 | 2 | 0 | 5.159s |
| R.72 | 1 | 37 | 36 | 1 | 0 | 0 | 0.068s |
| R.71 | 0 | 8 | 8 | 0 | 0 | 0 | 0.004s |
| R.70 | 1 | 26 | 25 | 1 | 0 | 0 | 7.674s |
| R.69 | 1 | 48 | 44 | 3 | 0 | 1 | 4.562s |
| R.68 | 1 | 31 | 27 | 2 | 1 | 1 | 0.223s |

R.82 journal state in the passing tests: permits that were claimed stay `network_permit=1`; unclaimed entry and close permits stay 0. Synthetic OrderCreate and PositionClose counts are 0 when the final journal check cannot verify authority, and 1 when the request was entered before a later persistence fault. The 400-unit close stores confirmed 400 and remaining 600. Position memory stays 1000. `restart-cycle` prints `cycle=1` and `manageable=0`.

The R.77 two-test file is outside the R.81 historical row. Its error is `unsupported_schema` on a schema-3 open. Its failure is `evidence["published"]` false because `record_entry_response` now requires recovery fencing. Neither assertion depends on the negative-unit change. The 87-test R.77 module matches the R.81 count of 2 failures and 3 errors.
