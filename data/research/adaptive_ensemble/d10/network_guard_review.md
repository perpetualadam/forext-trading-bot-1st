# Network guard review

The D.10 runner installs denials before any production import.

Denied, and confirmed by the self-check:

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

Telegram and OANDA HTTP entry points are replaced by the fake `requests` module. `requests.Session.get` and `requests.get` record only the method name after the last slash. They do not open a socket. The real `psycopg2.connect` is not reachable because `sys.modules["psycopg2"]` is the fake before `database.py` imports it.

Allowed socketpair:

- Family `AF_INET` to `127.0.0.1`, or `AF_INET6` to `::1`.
- Type `SOCK_STREAM`, protocol 0.
- The listener binds port 0.
- Only the original `connect` is used, and only to the address just returned by `getsockname`.
- A later `connect` to `127.0.0.1` on that same port is denied. The self-check recorded `self_pipe_not_reusable: true`.
- Connect to `127.0.0.1:5432` is denied.

After the self-check cleared its denial log, both the thread run and the lifespan run recorded `network_after: []`. The fake HTTP methods actually used were `getWebhookInfo`, `setMyCommands`, `getUpdates`, and `sendMessage`. Those stayed inside the fake.

No DNS lookup, Telegram request, OANDA request, or PostgreSQL connection left the process.
