# R.79 Linux Import Results

Evidence class: executed Linux operational import. Isolation was imported before any `forex_bot` module. This is not a mocked-dependency import.

Command:

```text
export TMPDIR=/tmp
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/linux_import_audit.py
```

`ISOLATION_READY True`.

| Module | Result |
| --- | --- |
| forex_bot.oanda_client | IMPORT_PASSED |
| forex_bot.oanda_exec | IMPORT_PASSED |
| forex_bot.bot_loop | IMPORT_PASSED |
| forex_bot.startup_recovery | IMPORT_PASSED |
| forex_bot.entry_journal | IMPORT_PASSED |
| forex_bot.entry_capture | IMPORT_PASSED |
| forex_bot.position_recovery | IMPORT_PASSED |
| forex_bot.recovery_repair | IMPORT_PASSED |
| forex_bot.recovery_owner_lock | IMPORT_PASSED |
| forex_bot.broker_entry_evidence | IMPORT_PASSED |
| forex_bot.broker_close_evidence | IMPORT_PASSED |
| forex_bot.entry_investigation | IMPORT_PASSED |
| forex_bot.reconciliation | IMPORT_PASSED |
| forex_bot.live_manage | IMPORT_PASSED |
| forex_bot.profit_protection | IMPORT_PASSED |
| forex_bot.execution | IMPORT_PASSED |
| forex_bot.trading | IMPORT_PASSED |
| forex_bot.positions | IMPORT_PASSED |

R.78 had blocked `oanda_client`, `oanda_exec`, `reconciliation`, and `bot_loop` because `oandapyV20` and `numpy` were absent. Those modules imported here from the disposable environment.

Import review before the run: `oanda_client` imports `oandapyV20` and pandas at module import. `build_api` returns None when the access token is empty. The isolation stub sets an empty token and a synthetic account id, and replaces `load_dotenv`. Import did not start `run_bot`, `main.py`, or `forex_bot.app`.
