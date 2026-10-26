# Stage D.6 independent D.5 harness review

The D.5 files were read and not modified. Their hashes match the D.5 record.

## What the D.5 runner does

- Builds a child environment from a Windows allow-list plus synthetic values. The parent environment is not copied.
- Uses a temporary working directory and a temporary `LIVE_SAFETY_STATE_PATH`.
- Removes the `concensus-forecast` path entry before import.
- Installs a fake `dotenv` module before import.
- Replaces `requests` and `psycopg2.connect` before import. The D.5 database fake raises on every connect.
- Replaces lifespan service names after import and before the context manager.
- Denies `socket.connect`, `connect_ex`, `create_connection`, `urlopen`, and `asyncio.open_connection`.
- Allows one loopback connect inside the replacement `socket.socketpair`, only to the port that call just bound.
- Denies `builtins.open` for `.env`, `data/ops`, `v2_shadow`, and credential basenames.
- The parent test uses `subprocess.run(..., timeout=180)`, which kills the child on timeout.
- Guards die with the child. The parent process does not install them.

## Suitability for D.6 fault injection

The D.5 runner is sufficient for its own pass/fail lifespan cases. It is not sufficient, unchanged, for D.6 database fault injection, because `psycopg2.connect` always raises and `app.get_connection` is replaced, so the real `get_connection` failure path never runs.

The D.5 filesystem guard does not wrap `os.open`, `os.replace`, `os.rename`, `os.remove`, `os.unlink`, or `shutil`. `live_safety` writes through `os.replace`. The D.5 path is still confined for the tested safety file because `LIVE_SAFETY_STATE_PATH` is temporary, but a stray `os.replace` into `data/ops` would not be denied.

D.6 therefore uses a separate runner. The D.5 runner was not edited. The D.6 runner keeps the same socketpair rule and adds path denial on those additional filesystem operations, DNS denial, and a fake connection object so the real `get_connection` can run.
