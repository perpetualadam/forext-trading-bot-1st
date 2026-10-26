# Network guard review

The D.11 installer denies `socket.connect`, `connect_ex`, `create_connection`, `getaddrinfo`, `gethostbyname`, `urllib.request.urlopen`, `asyncio.open_connection`, `asyncio.start_server`, asyncio subprocess creation, `os.system`, `subprocess.Popen`, and `subprocess.run`.

The allowed socket path is `socketpair` for `AF_INET` `127.0.0.1` or `AF_INET6` `::1`, stream sockets, protocol 0, bound to port 0. The original connect is used only for that bound address.

Telegram and PostgreSQL clients are in-process fakes. D.14 runs recorded an empty network-denial list.
