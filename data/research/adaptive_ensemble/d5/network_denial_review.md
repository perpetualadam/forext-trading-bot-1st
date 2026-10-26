# Stage D.5 network denial

The runner installs these guards before importing `forex_bot.app`:

- `socket.socket.connect` raises `RuntimeError` and records the address.
- `socket.socket.connect_ex` raises the same way.
- `socket.create_connection` raises.
- `urllib.request.urlopen` raises.
- `asyncio.open_connection` raises.
- Fake `requests.get`, `requests.post`, and `requests.request` raise.
- Fake `psycopg2.connect` raises.

The first guarded execution reached `asyncio.run` and then denied `socket.connect(('127.0.0.1', <ephemeral>))`. The traceback was `asyncio.proactor_events.BaseProactorEventLoop._make_self_pipe` calling `socket.socketpair`, which on this Windows Python uses a loopback TCP pair. That is the event-loop wakeup socket. It is not an OANDA, Postgres, or Telegram connection. Import of `app.py` had already finished before that connect.

The guard was not changed to allow `127.0.0.1` in general. A local Postgres on localhost would still be denied. `socket.socketpair` was replaced with a function that binds `127.0.0.1` or `::1` port 0 and connects only to that just-bound port, using the original `connect` for that one socket. Every other `connect` still raises. The passing run recorded `network: []` and a non-zero self-pipe count.

No HTTP client call, broker call, or database TCP call was recorded. No package was downloaded.
