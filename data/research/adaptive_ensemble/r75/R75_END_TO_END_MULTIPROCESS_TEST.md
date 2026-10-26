# R.75 End-to-End Multiprocess Test

Worker: `data/research/adaptive_ensemble/r75/poc/close_worker.py`.

The worker inserts the R.69 isolation module on `sys.path` and imports it before `forex_bot`. Isolation scrubs secret-like environment variables, stubs `dotenv`, blocks non-loopback sockets, blocks `urlopen`, and blocks `psycopg2.connect`. The synthetic account on the stub config is `001-002-0000001-003`. The access token stays empty.

Both processes call `run_guarded_live_close` on a live `Position` with the same instance id, trade id `T1`, instrument `EUR_USD`, and 1000 units. They share `CLOSE_JOURNAL_PATH` and `R75_RECORDER`. The recorder is a separate SQLite file. `PositionClose` inserts one row under `BEGIN IMMEDIATE`. `TransactionDetails` returns one synthetic `ORDER_FILL` and does not insert.

## Results on Windows

| Test | Result |
| --- | --- |
| Two processes started together | Recorder count 1. Both processes exit 0. At least one state is `CLOSE_FULLY_CONFIRMED`. |
| Third process after reopen | Recorder count remains 1. |
| Process A paused after claim, inside `PositionClose`, before the recorder insert | Process B exits 0 with a state other than `CLOSE_FULLY_CONFIRMED`. Recorder count 0. After release, count 1. |
| Forged permit, missing permit, and live `execute_trade` | No recorder insert. |

The in-process R.74 two-thread test also records one `PositionClose` after the shared-operation fix.

## Not covered on Linux

WSL CPython 3.12.3 ran the journal suite (20 passed). Importing the operational worker fails at `oanda_client.py` line 13 because `oandapyV20` is absent. No package was installed. The two-process operational test is `LINUX_INTEGRATION_NOT_VERIFIED`.

No real socket to OANDA was opened. The fake client raises `IsolationBreach` for any endpoint other than `PositionClose` and `TransactionDetails`.
