# R.68 cross-platform report

Same file, same assertions.

| Host | Python | Command | Result |
| --- | --- | --- | --- |
| Windows 10.0.26300 | CPython 3.13.5 MSC v.1943 64-bit | `python -B data/research/adaptive_ensemble/r68/poc/test_r68_observation_boundary.py` | 31 tests, 0 failures, 1 skipped, 0.190s |
| WSL2 `Linux NucBoxM5PLUS 6.6.87.2-microsoft-standard-WSL2` | CPython 3.12.3 GCC 13.3.0 | `python3 -B data/research/adaptive_ensemble/r68/poc/test_r68_observation_boundary.py` | 31 tests, 0 failures, 1 skipped, 0.254s |

The skip on both hosts is `test_23_concurrent_interleaving_not_verified` (`NOT_VERIFIED`).

No assertion differed between the two runs. Log lines matched.

WSL2 is not a Linux VPS. This report does not claim VPS or cgroup compatibility.

Changed-file hashes were computed on Windows after the patch and are recorded in `R68_DIFF_REVIEW.md`. The WSL run executed the same bytes on the shared filesystem.
