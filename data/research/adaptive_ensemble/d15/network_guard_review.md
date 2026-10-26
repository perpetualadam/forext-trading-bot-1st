# Network guard review

The installed denials cover `socket.socket.connect`, `connect_ex`, `socket.create_connection`, `socket.getaddrinfo`, `socket.gethostbyname`, `asyncio.open_connection`, `asyncio.start_server`, `urllib.request.urlopen`, asyncio subprocess creation, `os.system`, and `subprocess.Popen`. The fake `requests` session and fake `psycopg2.connect` replace those external boundaries before production import.

Arbitrary localhost connections are denied. The existing Windows asyncio self-pipe exception remains limited to an `AF_INET` or `AF_INET6` stream socket bound to `127.0.0.1` or `::1` on port 0, with the original connect used only for that address. It was not widened.

Observed `network_after` was empty for the lifespan, Telegram, database, shutdown, and safety children. No OANDA request, Telegram HTTP request, DNS lookup, or PostgreSQL connection was attempted.
