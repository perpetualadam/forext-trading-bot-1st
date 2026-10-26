# R.85 Coverage Equivalence Matrix

Windows CPython 3.13.5 and Linux CPython 3.12.3 ran the same modules. R.85 was 48 passed on both. Historical pass/fail/error/skip counts matched across the two platforms.

| Area | Windows | Linux | Class |
| --- | --- | --- | --- |
| Partial snapshot matrix | Executed | Executed | EQUIVALENT_COVERAGE |
| BUY, SELL, USD_JPY | Executed | Executed | EQUIVALENT_COVERAGE |
| Entry fence race | Executed | Executed | EQUIVALENT_COVERAGE |
| Close finalise race | Executed | Executed | EQUIVALENT_COVERAGE |
| Process kill then successor | Executed | Executed | EQUIVALENT_COVERAGE |
| Genuine successor startup | Executed | Executed | EQUIVALENT_COVERAGE |
| Operational cycle | Executed | Executed | EQUIVALENT_COVERAGE |
| Snapshot freshness timestamp | Not in the view | Not in the view | MISSING_COVERAGE |
| Pagination cursor | Not in the view | Not in the view | MISSING_COVERAGE |
| Live OANDA close | Not run | Not run | MISSING_COVERAGE |
| R.84 behavioural cases | 11 passed | 11 passed | EQUIVALENT_COVERAGE |
| R.84 hash pin | 1 failed | 1 failed | EQUIVALENT_COVERAGE |
| R.81 hash pin | 1 failed | 1 failed | EQUIVALENT_COVERAGE |
| R.83 and R.82 obsolete assertion | 1 failed each | 1 failed each | EQUIVALENT_COVERAGE |
| R.80 through R.78 and R.74 journal and R.71 | Green | Green | EQUIVALENT_COVERAGE |
| Older failing suites | Same counts | Same counts | EQUIVALENT_COVERAGE |

The OS lock uses `msvcrt` on Windows and `fcntl` on Linux. Both allowed the successor to acquire the lock after the parent had released it, and both refused the stale finalisation. That is equivalent coverage of the handoff, not a claim that the two lock implementations are the same code.

Power-loss durability and broker idempotency remain `MISSING_COVERAGE` on both platforms.
