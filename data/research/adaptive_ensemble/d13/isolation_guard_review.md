# Isolation guard review

The D.13 runner loads `tests/d12_shutdown_contract_runner.py`, which loads the D.11 installer. Guards are installed, then a self-check must pass, and only then does the child import `forex_bot`.

The child environment keeps Windows process essentials and replaces broker, database, and Telegram settings with synthetic values. `LIVE_SAFETY_STATE_PATH` points at a temporary file. `dotenv.load_dotenv` is replaced with a function that returns false and increments a counter.

`sys.path` entries containing `concensus-forecast` are removed before import. The child working directory is a temporary pytest directory. The parent timeout is 120 seconds.

Blocked-worker scenarios run in that child. The application snapshot is stored before harness join and connection close. The parent process does not import `app.py`.
