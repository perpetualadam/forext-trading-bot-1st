# D.9 isolation review

The D.9 runner installs denials before importing `forex_bot.database` or `forex_bot.app`. The parent does not copy its environment. The child receives a synthetic database password, empty broker and Telegram tokens, paper execution, and a temporary safety-state path.

Network denials, confirmed by the self-check before the schedules:

- `socket.connect`, including `127.0.0.1:5432`
- `socket.connect_ex`
- `socket.create_connection`
- `socket.getaddrinfo`
- `socket.gethostbyname`
- `urllib.request.urlopen`
- `asyncio.open_connection`
- `asyncio.start_server`
- `asyncio.create_subprocess_exec`
- `asyncio.create_subprocess_shell`
- `os.system`
- `subprocess.Popen` and `subprocess.run`
- `requests` methods, which increment a counter and raise

`socket.socketpair` still binds only `127.0.0.1` or `::1` on port 0 and uses the original connect for that just-bound address. A later connect to that port is denied. The self-check recorded `self_pipe_not_reusable`.

Filesystem denials cover `builtins.open`, `pathlib.Path.open`, `os.open`, replace, rename, remove, unlink, and shutil copy, copy2, move, and rmtree. The self-check denied paths containing `data/ops`, `v2_shadow`, `pgdata`, a `.env` basename, and a credential basename. Those probes were under the temporary work directory, not the production mounts.

`psycopg2` is a fake module installed before import. `connect` cannot fall through. `dotenv.load_dotenv` is replaced and was called once at import.

The D.7 and D.8 runners were not modified. D.8's missing `connect_ex`, `create_connection`, and `asyncio.open_connection` wrappers are covered here. Schedule network lists stayed empty.
