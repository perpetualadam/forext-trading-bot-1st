# R.73 Test Results

Windows CPython 3.13.5.

`data/research/adaptive_ensemble/r73/poc/test_r73_close_evidence.py`: 31 passed, 0 failed, 0.263s.

The operational function executed was `run_guarded_live_close`. The synthetic client recorded `PositionClose` and `TransactionDetails`. No `OrderCreate` was recorded.

WSL CPython 3.12.3 failed before any test:

`ModuleNotFoundError: No module named 'oandapyV20'`

from `forex_bot/oanda_client.py` line 13. Nothing was installed.

`LINUX_INTEGRATION_NOT_VERIFIED`
