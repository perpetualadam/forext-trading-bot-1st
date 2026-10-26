# Independent isolation review

The D.12 child calls the D.11 guard installer before importing `forex_bot`. The self-check passed in every D.12 mode. `network_after` was empty.

Denied calls raise immediately for socket connect, connect_ex, create_connection, getaddrinfo, gethostbyname, urlopen, asyncio open_connection and start_server, asyncio subprocess, os.system, and subprocess Popen and run. Localhost is denied.

The only socket exception is the Windows asyncio self-pipe: `socketpair` for IPv4 127.0.0.1 or IPv6 ::1, stream sockets, protocol 0, bound to port 0, and the original connect is used only for that pair.

Filesystem guards deny `.env`, credential names, `data/ops`, `v2_shadow`, and `pgdata` through open, Path.open, os.open, replace, rename, remove, unlink, and shutil copy, move, and rmtree.

The child environment is synthetic. Dotenv is replaced. psycopg2 and requests are replaced. Broker, reconciliation, and trading-loop entry points used by the lifespan are replaced. Blocked workers run only in the child. The parent timeout is 120 seconds.
