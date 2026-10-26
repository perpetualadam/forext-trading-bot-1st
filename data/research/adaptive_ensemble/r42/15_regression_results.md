# R.42 focused tests and offline regressions

## Focused lifecycle tests

Attempt 1, before the protocol hash: 2 failed, 3 passed.

- `test_latest_pair_tie_break_and_crossed_levels` expected `levels[0]` to be the first support. Same-timestamp ordering applies `HIGH` before `LOW`, so `levels[0]` was the resistance. The assertion was pointed at the support priced 1.0.
- `test_level_and_line_lifecycle_are_causal` included a second support line whose price was also beyond a later close, so the run recorded two first breaks. The break fixture was limited to the first line. The supersession fixture uses a later line that stays on the supported side.

The lifecycle rules were not changed to obtain the pass. No tolerance was introduced.

Attempt 2: `5 passed` in `tests/test_r42_lifecycle.py`.

The protocol was hashed after attempt 2 and before the descriptive run.

## Offline R.8–R.42 regressions

One run. Every suite exited 0. No retry. No `WinError 5`. R.28 PostgreSQL scripts were not run.

| Suite | Result |
| --- | --- |
| R.42 | 5 passed |
| R.41 | 6 passed |
| R.40 | 6 passed |
| R.39 | 9 passed |
| R.38 | 9 passed |
| R.37 | 7 passed |
| R.36 | 10 passed |
| R.35 | 10 passed |
| Legacy | 55 passed |
| R.34 | 5 passed |
| R.33 | 4 passed |
| R.32 | 10 passed |
| R.31 | 7 passed |
| R.30 | 13 passed |
| R.29 | 8 passed |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 | 69 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

Descriptive lifecycle run: exit 0. Prefix and clock checks passed on all twelve series. The output contained no `BUY` or `SELL` decision.
