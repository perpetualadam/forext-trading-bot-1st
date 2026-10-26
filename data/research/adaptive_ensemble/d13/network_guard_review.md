# Network guard review

Installed before forex import, from `tests/d11_telegram_shutdown_runner.py` `_install_guards`:

- `socket.socket.connect`
- `socket.socket.connect_ex`
- `socket.create_connection`
- `socket.getaddrinfo`
- `socket.gethostbyname`
- `urllib.request.urlopen`
- `asyncio.open_connection`
- `asyncio.start_server`
- `asyncio.create_subprocess_exec`
- `asyncio.create_subprocess_shell`
- `os.system`
- `subprocess.Popen`
- `subprocess.run`

Each denial raises `RuntimeError` and appends to `NETWORK`. The self-check calls the guarded functions, including localhost port 5432.

The one allowed socket path is `socket.socketpair` for `AF_INET` to `127.0.0.1` or `AF_INET6` to `::1`, `SOCK_STREAM`, protocol 0, bound to port 0. The original connect is used only for that just-bound address. Other families and socket types are denied.

Telegram and OANDA HTTP clients are replaced in-process. `psycopg2.connect` returns a fake connection. D.13 runs recorded an empty `network_after` list.
