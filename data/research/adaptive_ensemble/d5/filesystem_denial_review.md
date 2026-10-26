# Stage D.5 filesystem denial

`builtins.open` is wrapped before import. The wrapper denies:

- basename `.env` or a name ending in `.env`
- a path containing `data/ops`
- a path containing `v2_shadow`
- a basename containing `credential`

Denied opens raise `PermissionError` and are recorded. The passing run recorded `fs_denials: []`.

Safety reads and writes use `LIVE_SAFETY_STATE_PATH`, set to a file in the process temporary directory. The process working directory is that temporary directory. `state_path()` therefore does not fall through to `data/ops/live_safety_state.json`.

The real `.env` was not opened. Production operational-state, shadow-state, and database volume paths were not opened. Production safety-state bytes were not read or copied.

`load_dotenv` is a fake that does not open a file. The open guard is the backstop if a real loader runs.
