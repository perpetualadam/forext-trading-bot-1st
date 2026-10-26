# R.67C Test report

## Commands

Windows, from the repository root:

```text
python -B -m unittest discover -s data/research/adaptive_ensemble/r67/c/poc -t data/research/adaptive_ensemble/r67/c/poc -p test_*.py
```

WSL2, same tests:

```text
python3 -B -m unittest discover -s "/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st/data/research/adaptive_ensemble/r67/c/poc" -t "/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st/data/research/adaptive_ensemble/r67/c/poc" -p test_*.py
```

## Results

| Host | Python | Result | Time |
| --- | --- | --- | --- |
| Windows 11 10.0.26300 | CPython 3.13.5 | 70 passed, 0 failed, 0 skipped, 0 errors | 0.076s |
| WSL2 Ubuntu, kernel 6.6.87.2-microsoft-standard-WSL2 | CPython 3.12.3 | 70 passed, 0 failed, 0 skipped, 0 errors | 0.091s |

No failure output. No skipped tests.

## What the 70 tests are

- 60 numbered scenarios in `ScenarioTests`.
- 9 focused partial-fill, duplicate-send, lock, expiry, and import-boundary tests.
- 1 seeded sweep: seed `67`, `200` sequences, `12` steps each, invariants checked after every step. That is 2,400 invariant checks inside one test.

## Invariants checked

| # | Property | Where it was asserted |
| --- | --- | --- |
| 1 | Observation does not grant management | 1, 3, seeded monitor refusals |
| 2 | Management does not grant execution | 5 |
| 3 | Reconciliation does not grant execution | 3, 33 |
| 4 | Import does not grant execution | 6 |
| 5 | Local fallback is not broker protection | 12, 16, seeded sweep |
| 6 | Stale snapshot is not flat | 20, 26 |
| 7 | Failed snapshot is not flat | 18, 19 |
| 8 | Timeout is not a retry | 31, 34 |
| 9 | Send requires pre-send commit | `test_no_send_before_commit_and_no_lock_across_wait`, 28 |
| 10 | A grant is consumed at most once | pre-send commit, seeded sweep |
| 11 | A close is not submitted twice | 36 |
| 12 | Competing closes are not both sendable | 35, 36 |
| 13 | Partial fill does not erase remainder | 29, 5,000-of-10,000 test |
| 14 | Requested-unit completion is not broker flat | 28, 5,000-of-10,000 test |
| 15 | A zero snapshot is not bot attribution | 21, 49 |
| 16 | Conflict does not become a silent full close | 45, 51, 52 |
| 17 | An unknown trade id does not satisfy the grant | 46 |
| 18 | Duplicate fill ids do not add units | 42, 47 |
| 19 | Older snapshots do not overwrite | 27, 43 |
| 20 | Restart does not restore execution | 10, 39, 40 |
| 21 | Failed persistence does not authorise send | 37, 38, 60 |
| 22 | Unresolved close blocks retirement | 50, 56 |
| 23 | Retirement requires broker evidence | 53, 54, 55 |
| 24 | A manual close does not grant the bot authority | 2, 21 |
| 25 | Reconciliation keeps `pending_close_id` | 33, 58 |

## Evidence limits

`MODEL_TRANSACTION_TESTED`. `POSTGRESQL_INTEGRATION_NOT_TESTED`. `REAL_NETWORK_EXECUTION_NOT_TESTED`.

The ledger is an in-memory copy-on-write commit. It does not prove PostgreSQL row locks, isolation, or crash recovery on disk.

The expected dictionaries live in the test module that drives the model. A bug shared by both would not be caught. The refusals for `execution_kind`, send-before-commit, stale compare-and-swap, and the seeded invariant checks are the independent pressure on that risk.

No operational module was imported. `forex_bot` and `oandapyV20` were absent from `sys.modules` during the run.
