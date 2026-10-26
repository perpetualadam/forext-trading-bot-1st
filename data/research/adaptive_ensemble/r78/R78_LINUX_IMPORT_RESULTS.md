# R.78 Linux import results

Command: `python3 data/research/adaptive_ensemble/r78/poc/linux_import_audit.py` under WSL.

The script inserts the R.69 isolation harness on `sys.path` and imports `isolation` before any `forex_bot` module. `ISOLATION_READY` was true. Network and PostgreSQL attempts recorded by the harness: 0.

| Module | Result | Evidence |
| --- | --- | --- |
| `forex_bot.oanda_client` | `IMPORT_BLOCKED_DEPENDENCY` | `No module named 'oandapyV20'` |
| `forex_bot.oanda_exec` | `IMPORT_BLOCKED_DEPENDENCY` | `No module named 'oandapyV20'` |
| `forex_bot.bot_loop` | `IMPORT_BLOCKED_DEPENDENCY` | `No module named 'numpy'` |
| `forex_bot.startup_recovery` | `IMPORT_PASSED` | import completed |
| `forex_bot.entry_journal` | `IMPORT_PASSED` | import completed |
| `forex_bot.entry_capture` | `IMPORT_PASSED` | import completed |
| `forex_bot.position_recovery` | `IMPORT_PASSED` | import completed |
| `forex_bot.recovery_repair` | `IMPORT_PASSED` | import completed |
| `forex_bot.recovery_owner_lock` | `IMPORT_PASSED` | import completed |
| `forex_bot.broker_entry_evidence` | `IMPORT_PASSED` | import completed |
| `forex_bot.broker_close_evidence` | `IMPORT_PASSED` | import completed |
| `forex_bot.reconciliation` | `IMPORT_BLOCKED_DEPENDENCY` | `No module named 'oandapyV20'` |
| `forex_bot.live_manage` | `IMPORT_PASSED` | import completed |
| `forex_bot.profit_protection` | `IMPORT_PASSED` | import completed |
| `forex_bot.entry_investigation` | `IMPORT_PASSED` | import completed |

`IMPORT_PASSED` means the module body executed under the isolation harness. It does not mean the OANDA client was constructed or that a broker call ran. `oanda_client.py` imports `oandapyV20` before `forex_bot.config`, so the failed import does not reach `load_dotenv`.

`startup_recovery` imports cleanly because `load_startup_broker_view` imports the OANDA client only when called. That function was not called on Linux. The passed import is not an operational cycle.

No module was classified `IMPORT_BLOCKED_SIDE_EFFECT` or `IMPORT_FAILED_PLATFORM`.
