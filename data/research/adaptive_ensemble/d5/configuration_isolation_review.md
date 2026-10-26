# Stage D.5 configuration isolation

## How configuration loads

`forex_bot/config.py` calls `load_dotenv()` at import, then `Config` copies environment variables into class attributes. Later reads of `Config.OANDA_ACCESS_TOKEN` do not call `os.getenv` again. Patching `os.getenv` after `config` has been imported does not change those attributes.

`live_safety.state_path()` does call `os.getenv("LIVE_SAFETY_STATE_PATH")` at call time. The default when the variable is empty is `data/ops/live_safety_state.json`.

`get_execution_mode()` also reads `EXECUTION_MODE` at call time.

## Synthetic configuration before import

The runner is a new process. Its environment is built from a short allow-list of Windows process variables plus explicit synthetic values. The parent environment is not copied, so a real token in the parent is not inherited.

Before `import forex_bot.app`:

- `sys.modules["dotenv"]` provides `load_dotenv` that increments a counter and returns `False`. It does not open a file.
- `OANDA_ACCESS_TOKEN`, `OANDA_API_KEY`, and `OANDA_ACCOUNT_ID` are empty.
- Telegram and Discord variables are empty. `TELEGRAM_COMMANDS=0` and `TELEGRAM_INBOUND=0`.
- `EXECUTION_MODE=paper`, `PAPER_TRADING=true`, `TRADING_MODE=practice`.
- `POSTGRES_HOST=d5-invalid-host` and the password variables are empty.
- `LIVE_SAFETY_STATE_PATH` is an absolute file under a dedicated temporary directory.
- The process working directory is that temporary directory, not the repository.

The passing run recorded `dotenv_calls_at_import >= 1` and zero filesystem denials. The open guard would have raised if a real `.env` basename had been opened. No `.env` file was read by this stage.

## Path and credential isolation

Operational and shadow paths are not selected. The safety file used by the run is the temporary path. `builtins.open` denies a basename of `.env`, a name ending in `.env`, any path containing `data/ops` or `v2_shadow`, and any basename containing `credential`.

Empty token strings are not credentials and were not copied from a broker account.

## Remaining configuration blockers

The production process environment was not read and was not verified. This review shows that a synthetic environment can be installed before import. It does not show what the running container has loaded.
