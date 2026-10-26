# R.72 Test Results

## Windows CPython 3.13.5

| Suite | Result |
| --- | --- |
| `r72/poc/test_r72_broker_protection.py` | 37 passed, 0 failed, 0 skipped, 0.069s |
| `r71/poc/test_r71_readonly_calculations.py` | 8 passed, 0 failed, 0.005s |
| `r70/poc/test_r70_snapshot.py` | 26 passed, 0 failed, 7.876s |
| `r68/poc/test_r68_observation_boundary.py` | 29 passed, 1 failed, 1 skipped, 0.251s |
| `r69/poc/test_r69_integration.py` | 46 passed, 1 failed, 1 skipped, 4.861s |

The R.68 failure is `test_17_and_18_stop_quote_and_profit_files_unchanged`. It pins the pre-R.72 prefix of `live_manage.py` (`60d87b86`). The current digest is `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71`. Trading, profit protection, execution, and `oanda_exec` prefixes still matched. The historical test file was not edited.

The R.69 failure is `test_operational_hashes_match_r68` for `bot_loop.py`. It expects `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51`. The current digest is `f4130bc50ae6b9fe1894fbcee835b6f5d9fcd0de5763124bb769fa800f9755aa`. Positions, reconciliation, and broker exit still matched. The other R.69 tests passed, including the manage-path runs. One of those runs logged `broker protection evidence withheld: trade_identity_mismatch` and did not close.

The R.68 skip remains `test_23_concurrent_interleaving_not_verified`. The R.69 skip remains `test_entry_tail_was_not_executed`.

Pytest was not used. `tests/conftest.py` imports the live config.

## WSL CPython 3.12.3

The same R.72 command failed before any test:

`ModuleNotFoundError: No module named 'oandapyV20'`

from `forex_bot/oanda_client.py` line 13. No package was installed. No operational function ran on Linux.

`LINUX_INTEGRATION_NOT_VERIFIED`
