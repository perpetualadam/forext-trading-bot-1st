# D.11 isolation guard review

The D.11 runner installs guards before importing `forex_bot`. Denied operations raise on the call. They are not detected only from a log.

Network denials cover `socket.connect`, `connect_ex`, `create_connection`, `getaddrinfo`, `gethostbyname`, `urllib.request.urlopen`, `asyncio.open_connection`, `asyncio.start_server`, asyncio subprocess creation, `os.system`, `subprocess.Popen`, and `subprocess.run`. Localhost and loopback ports are denied, including a later connect to a port that the self-pipe just used.

The only socket exception is `socket.socketpair` for `AF_INET` `127.0.0.1` or `AF_INET6` `::1`, `SOCK_STREAM`, protocol 0, bound to port 0. The original connect is used only for that just-bound pair. This is the Windows asyncio self-pipe.

Filesystem denials cover `open`, `Path.open`, `os.open`, `replace`, `rename`, `remove`, `unlink`, and shutil copy, move, and rmtree when the path is `.env`, a credential name, `data/ops`, `v2_shadow`, or `pgdata`.

The child environment keeps only the Windows and Python location variables required to import installed packages. Tokens, broker keys, and database settings are synthetic. `dotenv.load_dotenv` is replaced before import. `psycopg2` and `requests` are replaced before import. The child working directory is temporary. `concensus-forecast` is removed from `sys.path` if present. The parent waits at most 120 seconds.

Lifecycle scenarios run in that child. A worker that cannot be joined is recorded and the child stops that scenario through the runner error path rather than continuing with an escaped thread. Daemon status is not used as containment. The final D.11 runs had no escaped threads and an empty network list.
