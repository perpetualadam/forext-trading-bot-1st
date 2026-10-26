# Filesystem guard review

Child environment:

- Inherited only `PATH`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `PATHEXT`, `TEMP`, `TMP`, `SYSTEMDRIVE`, `APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, `HOMEDRIVE`, and `HOMEPATH`.
- `PYTHONPATH` is the project root.
- `PYTHONDONTWRITEBYTECODE=1`.
- `LIVE_SAFETY_STATE_PATH` points at a temporary file.
- `PAPER_TRADING=true`, `EXECUTION_MODE=paper`, `TRADING_MODE=practice`, `USE_OANDA_LIVE=false`.
- Telegram token is the synthetic value `d10-synthetic-token`. Chat id is `1001`.
- OANDA token, API key, and account id are empty.
- Postgres host is `d10-invalid-host`, port `1`, user `d10`, password empty, database `d10`.
- `dotenv.load_dotenv` is a fake that returns false. It was called once at import and did not read a file.

The guarded open path denied temporary probes containing `.env`, `credential`, `data/ops`, `v2_shadow`, and `pgdata`. `Path.open` was denied for the ops probe. Those probes were created as path strings under the temp work directory. The real production files were not opened.

The child working directory was the temp directory. The concensus-forecast entry, when present on `sys.path`, is removed before import.

No production safety-state, operational-state, or shadow-state file was read or written.
